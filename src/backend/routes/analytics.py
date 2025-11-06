"""
Analytics Routes
Provides engagement metrics and analytics data
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from ..database import Database
from ..services import get_analytics_service
from ..routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/student/{user_id}")
async def get_student_analytics(
    user_id: str,
    days: int = 30,
    current_user = Depends(get_current_user)
):
    """Get student engagement analytics"""
    
    # Only allow users to see their own analytics (or teachers can see all)
    if str(current_user["_id"]) != user_id and current_user.get("role", "student") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this analytics"
        )
    
    db = Database.get_db()
    analytics_service = get_analytics_service(db)
    
    metrics = await analytics_service.get_student_engagement_metrics(
        user_id=user_id,
        days=days
    )
    
    return metrics


@router.get("/content/{content_id}")
async def get_content_analytics(
    content_id: str,
    current_user = Depends(get_current_user)
):
    """Get analytics for specific content"""
    db = Database.get_db()
    analytics_service = get_analytics_service(db)
    
    # Verify user has access to this content
    from ..utils import db_utils
    content = await db_utils.get_content_by_id(db, content_id)
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    if str(content.uploaded_by) != str(current_user["_id"]) and current_user.get("role", "student") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this analytics"
        )
    
    metrics = await analytics_service.get_content_analytics(content_id=content_id)
    
    return metrics


@router.get("/content/{content_id}/popular-questions")
async def get_popular_questions(
    content_id: str,
    limit: int = 10,
    current_user = Depends(get_current_user)
):
    """Get most asked questions for content"""
    db = Database.get_db()
    analytics_service = get_analytics_service(db)
    
    # Verify access
    from ..utils import db_utils
    content = await db_utils.get_content_by_id(db, content_id)
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    questions = await analytics_service.get_most_asked_questions(
        content_id=content_id,
        limit=limit
    )
    
    return {"questions": questions}


@router.get("/response-times")
async def get_response_time_analytics(
    content_id: Optional[str] = None,
    days: int = 30,
    current_user = Depends(get_current_user)
):
    """Get response time analytics"""
    
    # Only teachers can see global analytics
    if content_id is None and current_user.get("role", "student") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view global analytics"
        )
    
    db = Database.get_db()
    analytics_service = get_analytics_service(db)
    
    metrics = await analytics_service.get_response_time_analytics(
        content_id=content_id,
        days=days
    )
    
    return metrics


@router.get("/dashboard")
async def get_dashboard_stats(
    current_user = Depends(get_current_user)
):
    """Get dashboard statistics for current user"""
    db = Database.get_db()
    
    if current_user.get("role", "student") == "student":
        # Student dashboard
        from ..utils import db_utils
        
        # Get student's content count
        contents = await db_utils.get_contents_by_user(
            db,
            user_id=str(current_user["_id"]),
            limit=1000
        )
        
        # Get total questions asked
        questions_cursor = db.questions.find({"user_id": str(current_user["_id"])})
        questions = await questions_cursor.to_list(length=None)
        
        # Get analytics
        analytics_service = get_analytics_service(db)
        engagement = await analytics_service.get_student_engagement_metrics(
            user_id=str(current_user["_id"]),
            days=30
        )
        
        return {
            "total_content": len(contents),
            "total_questions": len(questions),
            "engagement_score": engagement.get("engagement_score", 0),
            "active_days": engagement.get("active_days", 0),
            "avg_confidence": engagement.get("avg_confidence_score", 0)
        }
    
    elif current_user.get("role", "student") == "teacher":
        # Teacher dashboard - global stats
        total_users = await db.users.count_documents({"role": "student"})
        total_contents = await db.contents.count_documents({})
        total_questions = await db.questions.count_documents({})
        total_interactions = await db.analytics.count_documents({})
        
        return {
            "total_students": total_users,
            "total_content": total_contents,
            "total_questions": total_questions,
            "total_interactions": total_interactions
        }
    
    return {}


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 10,
    current_user = Depends(get_current_user)
):
    """Get student engagement leaderboard (teacher only)"""
    
    if current_user.get("role", "student") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can view leaderboard"
        )
    
    db = Database.get_db()
    analytics_service = get_analytics_service(db)
    
    # Get all students
    students_cursor = db.users.find({"role": "student"})
    students = await students_cursor.to_list(length=None)
    
    # Calculate engagement for each
    leaderboard = []
    for student in students[:limit]:
        metrics = await analytics_service.get_student_engagement_metrics(
            user_id=str(student["_id"]),
            days=30
        )
        
        leaderboard.append({
            "user_id": str(student["_id"]),
            "name": student.get("name", "Unknown"),
            "email": student.get("email", ""),
            "engagement_score": metrics.get("engagement_score", 0),
            "total_questions": metrics.get("total_questions", 0),
            "active_days": metrics.get("active_days", 0)
        })
    
    # Sort by engagement score
    leaderboard.sort(key=lambda x: x["engagement_score"], reverse=True)
    
    return {"leaderboard": leaderboard}

