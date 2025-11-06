"""
Content Routes
Handles file upload, processing, and content management
"""

import os
import logging
import aiofiles
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, BackgroundTasks
from typing import List
from pathlib import Path
from bson import ObjectId

from ..database import Database
from ..models import ContentCreate, ContentStatus
from ..utils import db_utils
from ..rag import RAGPipeline
from ..chatbot import ChatbotEngine
from ..routes.auth import get_current_user
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Create uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def copy_content_from_original(content_id: str, original_content_id: str, user_id: str):
    """
    Copy chunks and embeddings from original content instead of reprocessing
    This is MUCH faster and saves on embedding API costs
    """
    db = Database.get_db()
    
    try:
        logger.info(f"♻️ Copying data from original content {original_content_id} to {content_id}")
        
        # Get original content
        original = await db.content.find_one({"_id": ObjectId(original_content_id)})
        
        if not original:
            logger.error(f"Original content {original_content_id} not found!")
            await db.content.update_one(
                {"_id": ObjectId(content_id)},
                {"$set": {
                    "status": "failed",
                    "error_message": "Original content not found",
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            return
        
        # Copy all relevant data
        update_data = {
            "text_content": original.get("text_content"),
            "vector_store_id": original.get("vector_store_id"),
            "chunks_count": original.get("chunks_count", 0),
            "embeddings_count": original.get("embeddings_count", 0),
            "metadata": original.get("metadata", {}),
            "status": "completed",
            "processed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        await db.content.update_one(
            {"_id": ObjectId(content_id)},
            {"$set": update_data}
        )
        
        logger.info(f"✅ Successfully copied data! Chunks: {original.get('chunks_count', 0)}, Status: completed")
        logger.info(f"⚡ INSTANT PROCESSING - No chunking or embeddings needed!")
        
    except Exception as e:
        logger.error(f"Error copying content data: {str(e)}", exc_info=True)
        await db.content.update_one(
            {"_id": ObjectId(content_id)},
            {"$set": {
                "status": "failed",
                "error_message": f"Error copying data: {str(e)}",
                "updated_at": datetime.now(timezone.utc)
            }}
        )


async def process_content_background(content_id: str, file_path: str, user_id: str):
    """Background task to process uploaded content"""
    db = Database.get_db()
    
    try:
        # Convert content_id to ObjectId
        from bson import ObjectId
        content_oid = ObjectId(content_id)
        
        # Update status to processing
        await db.content.update_one(
            {"_id": content_oid},
            {"$set": {"status": "processing"}}
        )
        
        # Initialize RAG pipeline
        pipeline = RAGPipeline()
        
        # Get file type from file path and convert to MIME type
        file_ext = Path(file_path).suffix.lower()
        mime_type_map = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.txt': 'text/plain',
            '.md': 'text/markdown'
        }
        file_type = mime_type_map.get(file_ext, 'application/octet-stream')
        
        # Process content
        result = await pipeline.process_document(
            file_path=file_path,
            file_type=file_type,
            content_id=content_id
        )
        
        # Update status to completed
        await db.content.update_one(
            {"_id": content_oid},
            {
                "$set": {
                    "status": "completed",
                    "chunks_count": result.get("chunks_count", 0),
                    "embeddings_count": result.get("embeddings_count", 0)
                }
            }
        )
    
    except Exception as e:
        # Update status to failed
        logger.error(f"Error processing content {content_id}: {type(e).__name__}: {str(e)}", exc_info=True)
        await db.content.update_one(
            {"_id": content_oid},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e)
                }
            }
        )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_content(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload and process content file"""
    
    # Validate file type
    allowed_extensions = {'.pdf', '.docx', '.txt', '.md'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size (max 50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file_size = 0
    
    try:
        db = Database.get_db()
        user_id = str(current_user["_id"])
        
        # Generate a temporary ObjectId for the file name
        temp_id = ObjectId()
        temp_file_path = UPLOAD_DIR / f"{str(temp_id)}{file_ext}"
        
        # Save file first
        async with aiofiles.open(temp_file_path, 'wb') as f:
            while chunk := await file.read(1024 * 1024):  # Read 1MB at a time
                file_size += len(chunk)
                
                if file_size > MAX_FILE_SIZE:
                    # Clean up
                    await f.close()
                    temp_file_path.unlink()
                    
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File size exceeds 50MB limit"
                    )
                
                await f.write(chunk)
        
        # Calculate file hash for duplicate detection
        logger.info(f"📊 Calculating file hash for duplicate detection...")
        file_hash = db_utils.calculate_file_hash(str(temp_file_path))
        logger.info(f"🔑 File hash: {file_hash[:16]}...")
        
        # Check for duplicate content
        duplicate_content = await db_utils.find_duplicate_content(db, file_hash, user_id)
        
        is_duplicate = duplicate_content is not None
        original_content_id = str(duplicate_content.id) if duplicate_content else None
        
        if is_duplicate:
            logger.info(f"♻️ DUPLICATE DETECTED! Original content: {original_content_id}")
            logger.info(f"⚡ Skipping chunking and embedding generation - reusing existing data")
        
        # Create content record with file info
        content_data = ContentCreate(
            title=file.filename
        )
        
        file_info = {
            'file_name': file.filename,
            'file_path': str(temp_file_path),
            'file_size': file_size,
            'file_type': file_ext[1:],
            'file_hash': file_hash,
            'is_duplicate': is_duplicate,
            'original_content_id': original_content_id
        }
        
        content = await db_utils.create_content(db, content_data, user_id, file_info)
        content_id = str(content.id)
        
        if is_duplicate:
            # Copy data from original content instead of processing
            background_tasks.add_task(
                copy_content_from_original,
                content_id=content_id,
                original_content_id=original_content_id,
                user_id=user_id
            )
            
            message = "File uploaded successfully. Duplicate detected - reusing existing data (instant processing)."
        else:
            # Process in background normally
            background_tasks.add_task(
                process_content_background,
                content_id=content_id,
                file_path=str(temp_file_path),
                user_id=user_id
            )
            
            message = "File uploaded successfully. Processing started."
        
        return {
            "content": {
                "id": content_id,
                "title": file.filename,
                "fileName": file.filename,
                "fileSize": file_size,
                "uploadedAt": datetime.now(timezone.utc).isoformat(),
                "status": "processing",
                "userId": user_id,
                "isDuplicate": is_duplicate,
                "originalContentId": original_content_id
            },
            "message": message
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )


@router.get("/")
async def get_user_content(
    current_user = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50
):
    """Get user's uploaded content"""
    db = Database.get_db()
    
    contents = await db_utils.get_contents_by_user(
        db,
        user_id=str(current_user["_id"]),
        skip=skip,
        limit=limit
    )
    
    # Map backend status to frontend status
    def map_status(backend_status):
        status_map = {
            "processing": "processing",
            "pending": "processing",
            "completed": "ready",
            "failed": "error"
        }
        return status_map.get(backend_status, "processing")
    
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "fileName": c.file_name,
            "fileSize": c.file_size,
            "uploadedAt": c.created_at.isoformat(),
            "status": map_status(c.status),
            "userId": c.user_id
        }
        for c in contents
    ]


@router.get("/{content_id}")
async def get_content_details(
    content_id: str,
    current_user = Depends(get_current_user)
):
    """Get content details"""
    db = Database.get_db()
    
    content = await db_utils.get_content_by_id(db, content_id)
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # Check ownership
    if str(content.user_id) != str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this content"
        )
    
    return {
        "id": str(content.id),
        "title": content.title,
        "file_type": content.file_type,
        "file_size": content.file_size,
        "status": content.status,
        "chunks_count": content.chunks_count,
        "embeddings_count": content.embeddings_count,
        "created_at": content.created_at.isoformat(),
        "updated_at": content.updated_at.isoformat()
    }


@router.delete("/{content_id}")
async def delete_content(
    content_id: str,
    current_user = Depends(get_current_user)
):
    """Delete content"""
    db = Database.get_db()
    
    content = await db_utils.get_content_by_id(db, content_id)
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # Check ownership
    if str(content.user_id) != str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this content"
        )
    
    # Delete file
    if content.file_path:
        file_path = Path(content.file_path)
        if file_path.exists():
            file_path.unlink()
    
    # Delete from database
    user_id = str(current_user["_id"])
    await db_utils.delete_content(db, content_id, user_id)
    
    # TODO: Delete from vector database
    
    return {"message": "Content deleted successfully"}


@router.get("/{content_id}/status")
async def get_content_status(
    content_id: str,
    current_user = Depends(get_current_user)
):
    """Get content processing status"""
    db = Database.get_db()
    
    content = await db_utils.get_content_by_id(db, content_id)
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    return {
        "id": str(content.id),
        "status": content.status,
        "chunks_count": content.chunks_count,
        "embeddings_count": content.embeddings_count,
        "error_message": content.error_message,
        "updated_at": content.updated_at.isoformat()
    }


@router.post("/{content_id}/question")
async def ask_question(
    content_id: str,
    request: dict,
    current_user = Depends(get_current_user)
):
    """Ask a question about specific content (supports streaming)"""
    from fastapi.responses import StreamingResponse
    import json
    
    db = Database.get_db()
    
    # Get the question and streaming preference from request
    question = request.get("question")
    stream = request.get("stream", False)
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is required"
        )
    
    # Verify content exists and user has access
    content = await db_utils.get_content_by_id(db, content_id)
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # Check if content is processed
    status_map = {
        "processing": "processing",
        "pending": "processing",
        "completed": "ready",
        "failed": "error"
    }
    mapped_status = status_map.get(content.status, "processing")
    
    if mapped_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content is not ready yet. Status: {mapped_status}"
        )
    
    # Initialize chatbot engine
    chatbot = ChatbotEngine(db)
    await chatbot.initialize()
    
    # Check if we should load history or start fresh
    # If request has "clear_history": true, don't load history
    clear_history = request.get("clear_history", False)
    
    if not clear_history:
        # Load conversation history for context
        await chatbot.load_conversation_history(
            user_id=str(current_user["_id"]),
            content_id=content_id
        )
    else:
        # Clear any existing conversation history (start fresh)
        chatbot.clear_conversation_history(
            content_id=content_id,
            user_id=str(current_user["_id"])
        )
    
    # Handle streaming response
    if stream:
        async def generate_stream():
            try:
                full_answer = ""
                async for chunk in chatbot.ask_question_stream(
                    question=question,
                    content_id=content_id,
                    user_id=str(current_user["_id"])
                ):
                    full_answer += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"

                # Send completion message
                yield f"data: {json.dumps({'done': True, 'full_answer': full_answer})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Non-streaming response
    result = await chatbot.ask_question(
        question=question,
        content_id=content_id,
        user_id=str(current_user["_id"])
    )
    
    # Build response
    response = {
        "answer": result.get("answer", "I couldn't process your question. Please try again."),
        "message": {
            "id": str(result.get("question_id", "")),
            "contentId": content_id,
            "question": question,
            "answer": result.get("answer", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "userId": str(current_user["_id"])
        }
    }
    
    # Add optional fields if they exist
    if "cached" in result:
        response["cached"] = result["cached"]
    if "sources" in result:
        response["sources"] = result["sources"]
    if "confidence_score" in result:
        response["confidence_score"] = result["confidence_score"]
    
    return response


@router.get("/{content_id}/questions")
async def get_questions(
    content_id: str,
    current_user = Depends(get_current_user),
    limit: int = 50
):
    """Get all questions asked about a content"""
    db = Database.get_db()
    
    # Verify content exists
    content = await db_utils.get_content_by_id(db, content_id)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # Get questions
    questions = await db_utils.get_questions_by_content(
        db, 
        content_id=content_id,
        limit=limit
    )
    
    return [
        {
            "id": str(q.id),
            "contentId": content_id,
            "question": q.question,
            "answer": q.answer,
            "timestamp": q.created_at.isoformat(),
            "userId": q.user_id
        }
        for q in questions
    ]

