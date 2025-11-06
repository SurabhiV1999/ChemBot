"""
RAG Pipeline Orchestrator
Coordinates document processing, chunking, and vector storage with progress tracking
"""

import logging
import asyncio
from typing import Dict, Any, Callable, Optional
from enum import Enum
from datetime import datetime, timezone
from .document_processor import DocumentProcessor
from .chunking import get_chunker
from .vector_store import VectorStoreManager
from ..config import settings

logger = logging.getLogger(__name__)


class ProcessingStage(str, Enum):
    """Processing stages for progress tracking"""
    INITIALIZING = "initializing"
    CONVERTING = "converting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETING = "completing"
    ERROR = "error"


class RAGPipeline:
    """
    RAG Pipeline for processing documents
    Handles conversion, chunking, embedding, and storage with progress tracking
    """
    
    def __init__(self):
        self.doc_processor = DocumentProcessor()
        self.vector_manager = VectorStoreManager()
        self.chunking_strategy = settings.CHUNKING_STRATEGY
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP
        
        # Progress tracking
        self.current_stage = ProcessingStage.INITIALIZING
        self.progress_percentage = 0
        self.progress_callbacks = []
        
        logger.info(f"Initialized RAG Pipeline with strategy: {self.chunking_strategy}")
    
    def register_progress_callback(self, callback: Callable):
        """Register a callback for progress updates"""
        self.progress_callbacks.append(callback)
    
    async def _update_progress(self, stage: ProcessingStage, percentage: int, 
                             message: str = "", metadata: Dict = None):
        """Update processing progress"""
        self.current_stage = stage
        self.progress_percentage = percentage
        
        progress_data = {
            "stage": stage.value,
            "percentage": percentage,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Progress: {stage.value} - {percentage}% - {message}")
        
        # Call registered callbacks
        for callback in self.progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress_data)
                else:
                    callback(progress_data)
            except Exception as e:
                logger.error(f"Error in progress callback: {str(e)}")
    
    async def process_document(self, file_path: str, file_type: str, 
                              content_id: str) -> Dict[str, Any]:
        """
        Process a document through the complete RAG pipeline
        
        Args:
            file_path: Path to the document file
            file_type: MIME type of the document
            content_id: Unique identifier for the content
        
        Returns:
            Dict with processing results and statistics
        """
        try:
            start_time = datetime.now(timezone.utc)
            
            # Stage 1: Initialize
            await self._update_progress(
                ProcessingStage.INITIALIZING,
                0,
                "Initializing RAG pipeline..."
            )
            
            # Initialize vector store
            await self.vector_manager.initialize()
            
            # Stage 2: Convert document to markdown
            await self._update_progress(
                ProcessingStage.CONVERTING,
                10,
                f"Converting {file_type} to Markdown..."
            )
            
            conversion_result = await self.doc_processor.process_document(
                file_path, file_type
            )
            
            markdown_text = conversion_result["markdown_text"]
            word_count = conversion_result["word_count"]
            
            await self._update_progress(
                ProcessingStage.CONVERTING,
                25,
                f"Conversion complete. Extracted {word_count} words",
                {"word_count": word_count}
            )
            
            # Stage 3: Chunk the document
            await self._update_progress(
                ProcessingStage.CHUNKING,
                30,
                f"Chunking document using {self.chunking_strategy} strategy..."
            )
            
            chunker = get_chunker(
                strategy=self.chunking_strategy,
                chunk_size=self.chunk_size,
                overlap=self.chunk_overlap
            )
            
            chunks = await chunker.chunk(markdown_text, metadata={
                "content_id": content_id,
                "file_type": file_type,
                "source_file": file_path,
                **conversion_result.get("metadata", {})
            })
            
            chunks_count = len(chunks)
            
            await self._update_progress(
                ProcessingStage.CHUNKING,
                50,
                f"Created {chunks_count} chunks",
                {"chunks_count": chunks_count}
            )
            
            # Stage 4: Generate embeddings and store
            await self._update_progress(
                ProcessingStage.EMBEDDING,
                55,
                f"Generating embeddings for {chunks_count} chunks..."
            )
            
            # Process chunks in batches with progress updates
            batch_size = 10
            stored_count = 0
            
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                
                # Store batch
                await self.vector_manager.store_chunks(batch, content_id)
                stored_count += len(batch)
                
                # Update progress
                embedding_progress = 55 + int((stored_count / chunks_count) * 35)
                await self._update_progress(
                    ProcessingStage.EMBEDDING,
                    embedding_progress,
                    f"Processed {stored_count}/{chunks_count} chunks"
                )
            
            # Stage 5: Completing
            await self._update_progress(
                ProcessingStage.COMPLETING,
                95,
                "Finalizing processing..."
            )
            
            # Calculate statistics
            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()
            
            result = {
                "success": True,
                "content_id": content_id,
                "markdown_text": markdown_text,
                "chunks_count": chunks_count,
                "word_count": word_count,
                "processing_time_seconds": processing_time,
                "chunking_strategy": self.chunking_strategy,
                "conversion_method": conversion_result.get("conversion_method"),
                "metadata": conversion_result.get("metadata", {}),
                "vector_store": self.vector_manager.provider
            }
            
            await self._update_progress(
                ProcessingStage.COMPLETING,
                100,
                "Processing complete!",
                result
            )
            
            logger.info(f"Document processing complete: {content_id} "
                       f"({chunks_count} chunks in {processing_time:.2f}s)")
            
            return result
        
        except Exception as e:
            logger.error(f"Error in RAG pipeline: {str(e)}", exc_info=True)
            
            await self._update_progress(
                ProcessingStage.ERROR,
                0,
                f"Processing failed: {str(e)}",
                {"error": str(e)}
            )
            
            return {
                "success": False,
                "content_id": content_id,
                "error": str(e),
                "stage": self.current_stage.value
            }
    
    async def delete_content(self, content_id: str):
        """Delete content from vector store"""
        try:
            await self.vector_manager.delete_content(content_id)
            logger.info(f"Deleted content from vector store: {content_id}")
        except Exception as e:
            logger.error(f"Error deleting content: {str(e)}")
            raise
    
    def cleanup(self):
        """Cleanup resources"""
        self.doc_processor.cleanup()


class ProgressTracker:
    """
    Standalone progress tracker for monitoring pipeline progress
    Can be used to track progress across different processes
    """
    
    def __init__(self):
        self.progress_data = {}
    
    async def update(self, content_id: str, progress: Dict[str, Any]):
        """Update progress for a content"""
        self.progress_data[content_id] = progress
    
    def get_progress(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Get progress for a content"""
        return self.progress_data.get(content_id)
    
    def clear_progress(self, content_id: str):
        """Clear progress data for a content"""
        if content_id in self.progress_data:
            del self.progress_data[content_id]


# Global progress tracker instance
progress_tracker = ProgressTracker()

