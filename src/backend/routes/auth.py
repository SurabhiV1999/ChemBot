"""
Authentication Routes
Handles user registration, login, and token management
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional

from ..database import Database
from ..models import UserCreate, UserRole
from ..utils import db_utils
from ..auth import create_access_token, decode_access_token
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole = "student"


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user"""
    try:
        token = credentials.credentials
        logger.info(f"Received token (first 20 chars): {token[:20]}...")
        
        payload = decode_access_token(token)
        logger.info(f"Decoded payload: {payload}")
        
        if not payload:
            logger.warning("Token payload is None or empty")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        db = Database.get_db()
        
        # Get user from database (convert string ID back to ObjectId)
        from bson import ObjectId
        user_id = payload["sub"]
        logger.info(f"Looking up user_id: {user_id} (type: {type(user_id)})")
        
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
                logger.info(f"Converted to ObjectId: {user_id}")
            except Exception as conv_err:
                logger.error(f"Failed to convert user_id to ObjectId: {conv_err}")
                pass
        
        user_doc = await db.users.find_one({"_id": user_id})
        
        if not user_doc:
            logger.warning(f"User not found in database for _id: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        logger.info(f"Successfully authenticated user: {user_doc.get('email')}")
        return user_doc
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """Register a new user"""
    db = Database.get_db()
    
    # Check if user exists
    existing_user = await db_utils.get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password
    hashed_password = pwd_context.hash(request.password)
    
    # Create user document directly
    from datetime import datetime, timezone
    from bson import ObjectId
    
    user_id = ObjectId()
    user_doc = {
        "_id": user_id,
        "email": request.email,
        "name": request.name,
        "role": request.role,
        "hashed_password": hashed_password,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "total_contents": 0,
        "total_questions": 0
    }
    
    # Insert into database
    await db.users.insert_one(user_doc)
    
    # Generate token
    access_token = create_access_token({
        "sub": str(user_id),
        "email": request.email,
        "role": request.role
    })
    
    return LoginResponse(
        access_token=access_token,
        user={
            "id": str(user_id),
            "email": request.email,
            "name": request.name,
            "role": request.role
        }
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login user"""
    db = Database.get_db()
    
    # Get user
    user_doc = await db.users.find_one({"email": request.email})
    
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not pwd_context.verify(request.password, user_doc.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate token
    access_token = create_access_token({
        "sub": str(user_doc["_id"]),
        "email": user_doc["email"],
        "role": user_doc.get("role", "student")
    })
    
    return LoginResponse(
        access_token=access_token,
        user={
            "id": str(user_doc["_id"]),
            "email": user_doc["email"],
            "name": user_doc["name"],
            "role": user_doc.get("role", "student")
        }
    )


@router.get("/me")
async def get_current_user_info(current_user = Depends(get_current_user)):
    """Get current user information"""
    return {
        "id": str(current_user["_id"]),
        "email": current_user["email"],
        "name": current_user["name"],
        "role": current_user.get("role", "student"),
        "created_at": current_user["created_at"].isoformat() if current_user.get("created_at") else None
    }


@router.post("/logout")
async def logout(current_user = Depends(get_current_user)):
    """Logout user (client should delete token)"""
    return {"message": "Logged out successfully"}

