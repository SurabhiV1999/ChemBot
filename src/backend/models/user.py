from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime, timezone
from bson import ObjectId

# User Role Type
UserRole = Literal["student", "teacher"]


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class User(BaseModel):
    """Base User model"""
    email: EmailStr
    name: str
    role: UserRole = "student"
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "student@example.com",
                "name": "John Doe",
                "role": "student"
            }
        }


class UserCreate(User):
    """User creation model"""
    password: str = Field(..., min_length=6)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "student@example.com",
                "name": "John Doe",
                "role": "student",
                "password": "securepassword123"
            }
        }


class UserUpdate(BaseModel):
    """User update model"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
    role: Optional[Literal["student", "teacher"]] = None


class UserInDB(User):
    """User model as stored in database"""
    id: str = Field(alias="_id")
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    # Statistics
    total_contents: int = 0
    total_questions: int = 0
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class UserResponse(BaseModel):
    """User response model (without sensitive data)"""
    id: str
    email: EmailStr
    name: str
    role: Literal["student", "teacher"]
    is_active: bool
    created_at: datetime
    total_contents: int = 0
    total_questions: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "email": "student@example.com",
                "name": "John Doe",
                "role": "student",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "total_contents": 5,
                "total_questions": 20
            }
        }

