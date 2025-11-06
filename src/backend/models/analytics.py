from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timezone
from bson import ObjectId


class Analytics(BaseModel):
    """Base Analytics model"""
    event_type: Literal[
        "content_upload",
        "content_view",
        "content_delete",
        "question_asked",
        "question_rated",
        "login",
        "logout",
        "error"
    ]
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "question_asked"
            }
        }


class AnalyticsCreate(Analytics):
    """Analytics creation model"""
    user_id: str
    content_id: Optional[str] = None
    question_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AnalyticsInDB(Analytics):
    """Analytics model as stored in database"""
    id: str = Field(alias="_id")
    user_id: str
    
    # Related entities
    content_id: Optional[str] = None
    question_id: Optional[str] = None
    
    # Event details
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Session information
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[int] = None
    
    # Status
    status: Literal["success", "error"] = "success"
    error_message: Optional[str] = None
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class AnalyticsResponse(BaseModel):
    """Analytics response model"""
    id: str
    user_id: str
    event_type: str
    content_id: Optional[str]
    question_id: Optional[str]
    metadata: Dict[str, Any]
    timestamp: datetime
    status: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "event_type": "question_asked",
                "content_id": "507f1f77bcf86cd799439013",
                "question_id": "507f1f77bcf86cd799439014",
                "metadata": {"response_time": 1234},
                "timestamp": "2024-01-01T00:00:00",
                "status": "success"
            }
        }


class AnalyticsSummary(BaseModel):
    """Analytics summary model for dashboards"""
    user_id: str
    
    # Content statistics
    total_contents: int = 0
    contents_by_status: Dict[str, int] = Field(default_factory=dict)
    
    # Question statistics
    total_questions: int = 0
    avg_questions_per_content: float = 0.0
    questions_by_rating: Dict[int, int] = Field(default_factory=dict)
    
    # Time-based statistics
    questions_last_7_days: int = 0
    questions_last_30_days: int = 0
    most_active_day: Optional[str] = None
    
    # Engagement metrics
    avg_session_duration_minutes: float = 0.0
    total_study_time_minutes: float = 0.0
    most_asked_content: Optional[Dict[str, Any]] = None
    
    # Performance metrics
    avg_response_time_ms: float = 0.0
    avg_confidence_score: float = 0.0
    helpful_responses_percentage: float = 0.0
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "total_contents": 5,
                "contents_by_status": {"ready": 4, "processing": 1},
                "total_questions": 50,
                "avg_questions_per_content": 10.0,
                "questions_by_rating": {"5": 30, "4": 15, "3": 5},
                "questions_last_7_days": 15,
                "questions_last_30_days": 45,
                "most_active_day": "2024-01-15",
                "avg_session_duration_minutes": 25.5,
                "total_study_time_minutes": 350.0,
                "avg_response_time_ms": 1250.0,
                "avg_confidence_score": 0.92,
                "helpful_responses_percentage": 85.0
            }
        }

