from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from ..models import (
    UserCreate, UserInDB, UserUpdate,
    ContentCreate, ContentInDB, ContentUpdate,
    QuestionCreate, QuestionInDB,
    AnalyticsCreate, AnalyticsInDB
)


# =====================
# FILE HASH UTILITIES
# =====================

def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA-256 hash of a file for duplicate detection
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA-256 hash as hex string
    """
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


async def find_duplicate_content(db: AsyncIOMotorDatabase, file_hash: str, user_id: Optional[str] = None) -> Optional[ContentInDB]:
    """
    Find existing content with the same file hash
    
    Args:
        db: Database connection
        file_hash: SHA-256 hash of the file
        user_id: Optional user ID to limit search to user's content
        
    Returns:
        ContentInDB if duplicate found, None otherwise
    """
    query = {
        "file_hash": file_hash,
        "status": "completed",  # Only consider successfully processed content
        "is_duplicate": False  # Get the original, not another duplicate
    }
    
    # Optionally limit to same user (or could search globally)
    if user_id:
        query["user_id"] = user_id
    
    result = await db.content.find_one(query)
    
    if result:
        result['_id'] = str(result['_id'])
        return ContentInDB(**result)
    
    return None


# =====================
# USER OPERATIONS
# =====================

async def create_user(db: AsyncIOMotorDatabase, user_data: UserCreate, hashed_password: str) -> UserInDB:
    """Create a new user in the database"""
    user_dict = user_data.model_dump()
    user_dict['hashed_password'] = hashed_password
    user_dict['created_at'] = datetime.now(timezone.utc)
    user_dict['updated_at'] = datetime.now(timezone.utc)
    user_dict['is_active'] = True
    user_dict['total_contents'] = 0
    user_dict['total_questions'] = 0
    
    result = await db.users.insert_one(user_dict)
    user_dict['_id'] = str(result.inserted_id)
    
    return UserInDB(**user_dict)


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[UserInDB]:
    """Get user by email"""
    user = await db.users.find_one({"email": email})
    if user:
        user['_id'] = str(user['_id'])
        return UserInDB(**user)
    return None


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[UserInDB]:
    """Get user by ID"""
    if not ObjectId.is_valid(user_id):
        return None
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        user['_id'] = str(user['_id'])
        return UserInDB(**user)
    return None


async def update_user(db: AsyncIOMotorDatabase, user_id: str, user_update: UserUpdate) -> Optional[UserInDB]:
    """Update user information"""
    if not ObjectId.is_valid(user_id):
        return None
    
    update_data = {k: v for k, v in user_update.model_dump().items() if v is not None}
    if not update_data:
        return await get_user_by_id(db, user_id)
    
    update_data['updated_at'] = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    return await get_user_by_id(db, user_id)


async def delete_user(db: AsyncIOMotorDatabase, user_id: str) -> bool:
    """Delete user (soft delete by setting is_active to False)"""
    if not ObjectId.is_valid(user_id):
        return False
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return result.modified_count > 0


async def update_user_stats(db: AsyncIOMotorDatabase, user_id: str, 
                           increment_contents: int = 0, increment_questions: int = 0):
    """Update user statistics"""
    if not ObjectId.is_valid(user_id):
        return
    
    update_dict = {}
    if increment_contents != 0:
        update_dict['total_contents'] = increment_contents
    if increment_questions != 0:
        update_dict['total_questions'] = increment_questions
    
    if update_dict:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": update_dict}
        )


# =====================
# CONTENT OPERATIONS
# =====================

async def create_content(db: AsyncIOMotorDatabase, content_data: ContentCreate, 
                        user_id: str, file_info: Dict[str, Any]) -> ContentInDB:
    """Create a new content entry in the database"""
    content_dict = content_data.model_dump()
    content_dict.update({
        'user_id': user_id,
        'file_name': file_info['file_name'],
        'file_path': file_info['file_path'],
        'file_size': file_info['file_size'],
        'file_type': file_info['file_type'],
        'file_hash': file_info.get('file_hash'),
        'is_duplicate': file_info.get('is_duplicate', False),
        'original_content_id': file_info.get('original_content_id'),
        'status': 'processing',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
        'total_questions': 0,
        'total_views': 0,
        'chunks_count': 0,
        'metadata': {}
    })
    
    result = await db.content.insert_one(content_dict)
    content_dict['_id'] = str(result.inserted_id)
    
    # Update user stats
    await update_user_stats(db, user_id, increment_contents=1)
    
    return ContentInDB(**content_dict)


async def get_content_by_id(db: AsyncIOMotorDatabase, content_id: str) -> Optional[ContentInDB]:
    """Get content by ID"""
    if not ObjectId.is_valid(content_id):
        return None
    
    content = await db.content.find_one({"_id": ObjectId(content_id)})
    if content:
        content['_id'] = str(content['_id'])
        return ContentInDB(**content)
    return None


async def get_contents_by_user(db: AsyncIOMotorDatabase, user_id: str, 
                              skip: int = 0, limit: int = 100) -> List[ContentInDB]:
    """Get all contents for a user"""
    if not ObjectId.is_valid(user_id):
        return []
    
    cursor = db.content.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
    contents = []
    
    async for content in cursor:
        content['_id'] = str(content['_id'])
        contents.append(ContentInDB(**content))
    
    return contents


async def update_content(db: AsyncIOMotorDatabase, content_id: str, 
                        content_update: ContentUpdate) -> Optional[ContentInDB]:
    """Update content information"""
    if not ObjectId.is_valid(content_id):
        return None
    
    update_data = {k: v for k, v in content_update.model_dump().items() if v is not None}
    if not update_data:
        return await get_content_by_id(db, content_id)
    
    update_data['updated_at'] = datetime.now(timezone.utc)
    
    await db.content.update_one(
        {"_id": ObjectId(content_id)},
        {"$set": update_data}
    )
    
    return await get_content_by_id(db, content_id)


async def update_content_processing(db: AsyncIOMotorDatabase, content_id: str, 
                                   status: str, text_content: Optional[str] = None,
                                   chunks_count: int = 0, vector_store_id: Optional[str] = None,
                                   error_message: Optional[str] = None):
    """Update content processing status"""
    if not ObjectId.is_valid(content_id):
        return
    
    update_dict = {
        'status': status,
        'updated_at': datetime.now(timezone.utc),
        'processed_at': datetime.now(timezone.utc) if status in ['ready', 'error'] else None
    }
    
    if text_content:
        update_dict['text_content'] = text_content
    if chunks_count > 0:
        update_dict['chunks_count'] = chunks_count
    if vector_store_id:
        update_dict['vector_store_id'] = vector_store_id
    if error_message:
        update_dict['error_message'] = error_message
    
    await db.content.update_one(
        {"_id": ObjectId(content_id)},
        {"$set": update_dict}
    )


async def delete_content(db: AsyncIOMotorDatabase, content_id: str, user_id: str) -> bool:
    """Delete content"""
    if not ObjectId.is_valid(content_id):
        return False
    
    result = await db.content.delete_one({
        "_id": ObjectId(content_id),
        "user_id": user_id
    })
    
    if result.deleted_count > 0:
        # Update user stats
        await update_user_stats(db, user_id, increment_contents=-1)
        return True
    
    return False


async def increment_content_stats(db: AsyncIOMotorDatabase, content_id: str,
                                 increment_questions: int = 0, increment_views: int = 0):
    """Increment content statistics"""
    if not ObjectId.is_valid(content_id):
        return
    
    update_dict = {}
    if increment_questions != 0:
        update_dict['total_questions'] = increment_questions
    if increment_views != 0:
        update_dict['total_views'] = increment_views
    
    if update_dict:
        await db.content.update_one(
            {"_id": ObjectId(content_id)},
            {"$inc": update_dict}
        )


# =====================
# QUESTION OPERATIONS
# =====================

async def create_question(db: AsyncIOMotorDatabase, question_data: QuestionCreate,
                         user_id: str, answer: str, **kwargs) -> QuestionInDB:
    """Create a new question entry in the database"""
    question_dict = question_data.model_dump()
    question_dict.update({
        'user_id': user_id,
        'answer': answer,
        'created_at': datetime.now(timezone.utc),
        **kwargs
    })
    
    result = await db.questions.insert_one(question_dict)
    question_dict['_id'] = str(result.inserted_id)
    
    # Update statistics
    await update_user_stats(db, user_id, increment_questions=1)
    await increment_content_stats(db, question_data.content_id, increment_questions=1)
    
    return QuestionInDB(**question_dict)


async def get_question_by_id(db: AsyncIOMotorDatabase, question_id: str) -> Optional[QuestionInDB]:
    """Get question by ID"""
    if not ObjectId.is_valid(question_id):
        return None
    
    question = await db.questions.find_one({"_id": ObjectId(question_id)})
    if question:
        question['_id'] = str(question['_id'])
        return QuestionInDB(**question)
    return None


async def get_questions_by_content(db: AsyncIOMotorDatabase, content_id: str,
                                  skip: int = 0, limit: int = 100) -> List[QuestionInDB]:
    """Get all questions for a content"""
    if not ObjectId.is_valid(content_id):
        return []
    
    cursor = db.questions.find({"content_id": content_id}).sort("created_at", -1).skip(skip).limit(limit)
    questions = []
    
    async for question in cursor:
        question['_id'] = str(question['_id'])
        questions.append(QuestionInDB(**question))
    
    return questions


async def get_questions_by_user(db: AsyncIOMotorDatabase, user_id: str,
                               skip: int = 0, limit: int = 100) -> List[QuestionInDB]:
    """Get all questions by a user"""
    if not ObjectId.is_valid(user_id):
        return []
    
    cursor = db.questions.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
    questions = []
    
    async for question in cursor:
        question['_id'] = str(question['_id'])
        questions.append(QuestionInDB(**question))
    
    return questions


async def update_question_feedback(db: AsyncIOMotorDatabase, question_id: str,
                                  feedback: Dict[str, Any]) -> Optional[QuestionInDB]:
    """Update question feedback"""
    if not ObjectId.is_valid(question_id):
        return None
    
    update_data = {k: v for k, v in feedback.items() if v is not None}
    if not update_data:
        return await get_question_by_id(db, question_id)
    
    await db.questions.update_one(
        {"_id": ObjectId(question_id)},
        {"$set": update_data}
    )
    
    return await get_question_by_id(db, question_id)


# =====================
# ANALYTICS OPERATIONS
# =====================

async def create_analytics_event(db: AsyncIOMotorDatabase, analytics_data: AnalyticsCreate,
                                **kwargs) -> AnalyticsInDB:
    """Create a new analytics event"""
    analytics_dict = analytics_data.model_dump()
    analytics_dict.update({
        'timestamp': datetime.now(timezone.utc),
        'status': 'success',
        **kwargs
    })
    
    result = await db.analytics.insert_one(analytics_dict)
    analytics_dict['_id'] = str(result.inserted_id)
    
    return AnalyticsInDB(**analytics_dict)


async def get_analytics_by_user(db: AsyncIOMotorDatabase, user_id: str,
                               event_type: Optional[str] = None,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               skip: int = 0, limit: int = 100) -> List[AnalyticsInDB]:
    """Get analytics events for a user"""
    if not ObjectId.is_valid(user_id):
        return []
    
    query = {"user_id": user_id}
    
    if event_type:
        query["event_type"] = event_type
    
    if start_date or end_date:
        query["timestamp"] = {}
        if start_date:
            query["timestamp"]["$gte"] = start_date
        if end_date:
            query["timestamp"]["$lte"] = end_date
    
    cursor = db.analytics.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    analytics = []
    
    async for event in cursor:
        event['_id'] = str(event['_id'])
        analytics.append(AnalyticsInDB(**event))
    
    return analytics


async def get_analytics_summary(db: AsyncIOMotorDatabase, user_id: str) -> Dict[str, Any]:
    """Get analytics summary for a user"""
    if not ObjectId.is_valid(user_id):
        return {"user_id": user_id}
    
    # Get user's contents
    contents = await get_contents_by_user(db, user_id)
    total_contents = len(contents)
    contents_by_status = {}
    for content in contents:
        status = content.status
        contents_by_status[status] = contents_by_status.get(status, 0) + 1
    
    # Get user's questions
    questions = await get_questions_by_user(db, user_id, limit=1000)
    total_questions = len(questions)
    
    # Calculate average questions per content
    avg_questions_per_content = total_questions / total_contents if total_contents > 0 else 0.0
    
    # Questions by rating
    questions_by_rating = {}
    helpful_count = 0
    total_rated = 0
    confidence_scores = []
    
    for q in questions:
        if q.user_rating:
            questions_by_rating[q.user_rating] = questions_by_rating.get(q.user_rating, 0) + 1
            total_rated += 1
        if q.is_helpful is not None:
            if q.is_helpful:
                helpful_count += 1
        if q.confidence_score:
            confidence_scores.append(q.confidence_score)
    
    # Time-based statistics
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    
    questions_last_7_days = sum(1 for q in questions if q.created_at >= seven_days_ago)
    questions_last_30_days = sum(1 for q in questions if q.created_at >= thirty_days_ago)
    
    # Calculate averages
    avg_confidence_score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    helpful_responses_percentage = (helpful_count / total_rated * 100) if total_rated > 0 else 0.0
    
    return {
        "user_id": user_id,
        "total_contents": total_contents,
        "contents_by_status": contents_by_status,
        "total_questions": total_questions,
        "avg_questions_per_content": round(avg_questions_per_content, 2),
        "questions_by_rating": questions_by_rating,
        "questions_last_7_days": questions_last_7_days,
        "questions_last_30_days": questions_last_30_days,
        "avg_confidence_score": round(avg_confidence_score, 2),
        "helpful_responses_percentage": round(helpful_responses_percentage, 2)
    }

