from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId


class Question(BaseModel):
    """Base Question model"""
    question: str = Field(..., min_length=1, max_length=2000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the difference between ionic and covalent bonds?"
            }
        }


class QuestionCreate(Question):
    """Question creation model"""
    content_id: str


class QuestionInDB(Question):
    """Question model as stored in database"""
    id: str = Field(alias="_id")
    content_id: str
    user_id: str
    
    # AI Response
    answer: str
    
    # Confidence and metadata
    confidence_score: Optional[float] = None
    response_time_ms: Optional[int] = None
    
    # Source information (for RAG)
    source_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    
    # AI Model information
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    
    # Feedback
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    user_feedback: Optional[str] = None
    is_helpful: Optional[bool] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        "protected_namespaces": ()  # Allow fields starting with "model_"
    }


class QuestionResponse(BaseModel):
    """Question response model"""
    id: str
    content_id: str
    user_id: str
    question: str
    answer: str
    confidence_score: Optional[float]
    created_at: datetime
    user_rating: Optional[int]
    is_helpful: Optional[bool]
    
    # Renamed for frontend compatibility
    @property
    def timestamp(self) -> datetime:
        return self.created_at
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "content_id": "507f1f77bcf86cd799439012",
                "user_id": "507f1f77bcf86cd799439013",
                "question": "What is the difference between ionic and covalent bonds?",
                "answer": "Ionic bonds form when electrons are transferred between atoms, while covalent bonds form when electrons are shared between atoms...",
                "confidence_score": 0.95,
                "created_at": "2024-01-01T00:00:00",
                "user_rating": 5,
                "is_helpful": True
            }
        }


class QuestionFeedback(BaseModel):
    """Question feedback model"""
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    user_feedback: Optional[str] = Field(None, max_length=1000)
    is_helpful: Optional[bool] = None

