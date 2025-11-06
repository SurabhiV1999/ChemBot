from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId

# Content Status Type
ContentStatus = Literal["pending", "processing", "completed", "failed"]


class Content(BaseModel):
    """Base Content model"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Introduction to Organic Chemistry",
                "description": "Basic concepts of organic chemistry"
            }
        }


class ContentCreate(Content):
    """Content creation model"""
    pass


class ContentUpdate(BaseModel):
    """Content update model"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[ContentStatus] = None


class ContentInDB(Content):
    """Content model as stored in database"""
    id: str = Field(alias="_id")
    user_id: str
    
    # File information
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    file_hash: Optional[str] = None  # SHA-256 hash for duplicate detection
    
    # Duplicate detection
    is_duplicate: bool = False
    original_content_id: Optional[str] = None  # Points to original if duplicate
    
    # Processing status
    status: ContentStatus = "processing"
    error_message: Optional[str] = None
    
    # Extracted content
    text_content: Optional[str] = None
    
    # Vector store information (for RAG)
    vector_store_id: Optional[str] = None
    chunks_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    # Statistics
    total_questions: int = 0
    total_views: int = 0
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ContentResponse(BaseModel):
    """Content response model"""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    file_name: str
    file_size: int
    file_type: str
    status: Literal["processing", "ready", "error"]
    error_message: Optional[str]
    chunks_count: int
    created_at: datetime
    updated_at: datetime
    total_questions: int
    total_views: int
    
    # Renamed for frontend compatibility
    @property
    def fileName(self) -> str:
        return self.file_name
    
    @property
    def uploadedAt(self) -> datetime:
        return self.created_at
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "title": "Introduction to Organic Chemistry",
                "description": "Basic concepts",
                "file_name": "organic_chemistry.pdf",
                "file_size": 2048576,
                "file_type": "application/pdf",
                "status": "ready",
                "error_message": None,
                "chunks_count": 45,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:05:00",
                "total_questions": 10,
                "total_views": 25
            }
        }

