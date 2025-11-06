"""
Analytics Service
Calculates engagement metrics and provides analytics insights
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from collections import Counter
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for calculating analytics and engagement metrics
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        logger.info("Initialized AnalyticsService")
    
    async def get_student_engagement_metrics(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate student engagement metrics
        
        Args:
            user_id: Student user ID
            days: Number of days to analyze
        
        Returns:
            Dict with engagement metrics matching frontend AnalyticsData interface
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff_7_days = datetime.now(timezone.utc) - timedelta(days=7)
            cutoff_30_days = datetime.now(timezone.utc) - timedelta(days=30)
            
            # Get ALL user's questions (not filtered by date)
            all_questions_cursor = self.db.questions.find({"user_id": user_id})
            all_questions = await all_questions_cursor.to_list(length=None)
            
            # Get questions for specific time periods
            questions_7days_cursor = self.db.questions.find({
                "user_id": user_id,
                "created_at": {"$gte": cutoff_7_days}
            })
            questions_7days = await questions_7days_cursor.to_list(length=None)
            
            questions_30days_cursor = self.db.questions.find({
                "user_id": user_id,
                "created_at": {"$gte": cutoff_30_days}
            })
            questions_30days = await questions_30days_cursor.to_list(length=None)
            
            # Get user's contents
            contents_cursor = self.db.content.find({"user_id": user_id})
            contents = await contents_cursor.to_list(length=None)
            
            # Group contents by status
            contents_by_status = {}
            for content in contents:
                status = content.get("status", "pending")
                contents_by_status[status] = contents_by_status.get(status, 0) + 1
            
            # Group questions by rating
            questions_by_rating = {}
            for question in all_questions:
                rating = question.get("rating")
                if rating is not None:
                    rating_str = f"{rating}"
                    questions_by_rating[rating_str] = questions_by_rating.get(rating_str, 0) + 1
            
            # Calculate helpful responses
            helpful_data = self._count_helpful_responses(all_questions)
            
            # Calculate average confidence score (0-100 scale)
            avg_confidence = self._calculate_avg_confidence(all_questions)
            
            # Calculate average questions per content
            avg_questions_per_content = len(all_questions) / len(contents) if contents else 0.0
            
            # Return metrics matching frontend AnalyticsData interface
            return {
                "total_contents": len(contents),
                "contents_by_status": contents_by_status,
                "total_questions": len(all_questions),
                "avg_questions_per_content": round(avg_questions_per_content, 2),
                "questions_by_rating": questions_by_rating,
                "questions_last_7_days": len(questions_7days),
                "questions_last_30_days": len(questions_30days),
                "avg_confidence_score": round(avg_confidence, 4) if avg_confidence else 0.0,  # 0-1 scale
                "helpful_responses_percentage": helpful_data.get("helpful_percentage", 0.0),
            }
        
        except Exception as e:
            logger.error(f"Error calculating engagement metrics: {e}", exc_info=True)
            # Return default structure on error
            return {
                "total_contents": 0,
                "contents_by_status": {},
                "total_questions": 0,
                "avg_questions_per_content": 0.0,
                "questions_by_rating": {},
                "questions_last_7_days": 0,
                "questions_last_30_days": 0,
                "avg_confidence_score": 0.0,
                "helpful_responses_percentage": 0.0,
            }
    
    async def get_content_analytics(
        self,
        content_id: str
    ) -> Dict[str, Any]:
        """
        Get analytics for specific content
        
        Args:
            content_id: Content ID
        
        Returns:
            Dict with content analytics
        """
        try:
            # Get all questions for this content
            questions_cursor = self.db.questions.find({"content_id": content_id})
            questions = await questions_cursor.to_list(length=None)
            
            # Get analytics events
            analytics_cursor = self.db.analytics.find({
                "content_id": content_id,
                "event_type": "question_asked"
            })
            analytics = await analytics_cursor.to_list(length=None)
            
            # Calculate metrics
            return {
                "total_questions": len(questions),
                "unique_users": len(set(q.get("user_id") for q in questions)),
                "most_asked_question_types": self._get_most_asked_types(analytics),
                "avg_response_time_ms": self._calculate_avg_response_time(analytics),
                "avg_confidence_score": self._calculate_avg_confidence(questions),
                "question_frequency": self._analyze_question_frequency(questions),
                "peak_usage_times": self._find_peak_usage(questions)
            }
        
        except Exception as e:
            logger.error(f"Error getting content analytics: {e}")
            return {}
    
    async def get_most_asked_questions(
        self,
        content_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most frequently asked question types for content
        
        Args:
            content_id: Content ID
            limit: Number of questions to return
        
        Returns:
            List of most asked questions with frequency
        """
        try:
            # Aggregate similar questions
            pipeline = [
                {"$match": {"content_id": content_id}},
                {"$group": {
                    "_id": {"$toLower": "$question"},
                    "count": {"$sum": 1},
                    "avg_confidence": {"$avg": "$confidence_score"},
                    "sample_answer": {"$first": "$answer"}
                }},
                {"$sort": {"count": -1}},
                {"$limit": limit}
            ]
            
            cursor = self.db.questions.aggregate(pipeline)
            results = await cursor.to_list(length=limit)
            
            return [
                {
                    "question": r["_id"],
                    "frequency": r["count"],
                    "avg_confidence": round(r.get("avg_confidence", 0), 2),
                    "sample_answer": r["sample_answer"][:200] + "..."
                }
                for r in results
            ]
        
        except Exception as e:
            logger.error(f"Error getting most asked questions: {e}")
            return []
    
    async def get_response_time_analytics(
        self,
        content_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze response times
        
        Args:
            content_id: Optional content ID filter
            days: Number of days to analyze
        
        Returns:
            Response time statistics
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            match_filter = {
                "event_type": "question_asked",
                "timestamp": {"$gte": cutoff_date}
            }
            
            if content_id:
                match_filter["content_id"] = content_id
            
            # Aggregate response times
            pipeline = [
                {"$match": match_filter},
                {"$group": {
                    "_id": None,
                    "avg_response_time": {"$avg": "$metadata.response_time_ms"},
                    "min_response_time": {"$min": "$metadata.response_time_ms"},
                    "max_response_time": {"$max": "$metadata.response_time_ms"},
                    "total_questions": {"$sum": 1},
                    "cached_questions": {
                        "$sum": {"$cond": [{"$eq": ["$metadata.cached", True]}, 1, 0]}
                    }
                }}
            ]
            
            cursor = self.db.analytics.aggregate(pipeline)
            results = await cursor.to_list(length=1)
            
            if results:
                result = results[0]
                return {
                    "avg_response_time_ms": round(result.get("avg_response_time", 0), 2),
                    "min_response_time_ms": result.get("min_response_time", 0),
                    "max_response_time_ms": result.get("max_response_time", 0),
                    "total_questions": result.get("total_questions", 0),
                    "cache_hit_rate": round(
                        (result.get("cached_questions", 0) / result.get("total_questions", 1)) * 100, 2
                    )
                }
            
            return {}
        
        except Exception as e:
            logger.error(f"Error analyzing response times: {e}")
            return {}
    
    # Helper methods
    
    async def _count_active_days(self, user_id: str, cutoff_date: datetime) -> int:
        """Count number of days user was active"""
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "created_at": {"$gte": cutoff_date}
            }},
            {"$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$created_at"
                    }
                }
            }},
            {"$count": "active_days"}
        ]
        
        cursor = self.db.questions.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        
        return results[0]["active_days"] if results else 0
    
    def _calculate_avg_per_day(self, questions: List[Dict], days: int) -> float:
        """Calculate average questions per day"""
        if days == 0:
            return 0.0
        return round(len(questions) / days, 2)
    
    def _find_most_active_time(self, questions: List[Dict]) -> str:
        """Find most active time of day"""
        if not questions:
            return "N/A"
        
        hours = [q.get("created_at").hour for q in questions if q.get("created_at")]
        
        if not hours:
            return "N/A"
        
        most_common_hour = Counter(hours).most_common(1)[0][0]
        return f"{most_common_hour:02d}:00-{most_common_hour+1:02d}:00"
    
    def _analyze_question_types(self, analytics: List[Dict]) -> Dict[str, int]:
        """Analyze question type distribution"""
        types = [
            a.get("metadata", {}).get("question_type", "general")
            for a in analytics
            if a.get("event_type") == "question_asked"
        ]
        
        return dict(Counter(types))
    
    def _calculate_avg_confidence(self, questions: List[Dict]) -> float:
        """Calculate average confidence score"""
        scores = [q.get("confidence_score", 0) for q in questions if q.get("confidence_score")]
        
        if not scores:
            return 0.0
        
        return round(sum(scores) / len(scores), 2)
    
    def _count_helpful_responses(self, questions: List[Dict]) -> Dict[str, int]:
        """Count helpful vs not helpful responses"""
        helpful = sum(1 for q in questions if q.get("is_helpful") is True)
        not_helpful = sum(1 for q in questions if q.get("is_helpful") is False)
        unrated = len(questions) - helpful - not_helpful
        
        return {
            "helpful": helpful,
            "not_helpful": not_helpful,
            "unrated": unrated,
            "helpful_percentage": round((helpful / len(questions) * 100), 2) if questions else 0
        }
    
    def _calculate_engagement_score(self, metrics: Dict[str, Any], days: int) -> float:
        """Calculate engagement score (0-100)"""
        score = 0.0
        
        # Questions per day (max 30 points)
        avg_questions = metrics.get("avg_questions_per_day", 0)
        score += min(avg_questions * 3, 30)
        
        # Active days (max 30 points)
        active_days = metrics.get("active_days", 0)
        score += min((active_days / days) * 30, 30)
        
        # Confidence score (max 20 points)
        avg_confidence = metrics.get("avg_confidence_score", 0)
        score += avg_confidence * 20
        
        # Helpful responses (max 20 points)
        helpful_data = metrics.get("helpful_responses", {})
        helpful_pct = helpful_data.get("helpful_percentage", 0)
        score += (helpful_pct / 100) * 20
        
        return round(min(score, 100), 2)
    
    def _get_most_asked_types(self, analytics: List[Dict]) -> List[Dict[str, Any]]:
        """Get most asked question types"""
        types = [
            a.get("metadata", {}).get("question_type", "general")
            for a in analytics
        ]
        
        type_counts = Counter(types)
        return [
            {"type": t, "count": c}
            for t, c in type_counts.most_common(5)
        ]
    
    def _calculate_avg_response_time(self, analytics: List[Dict]) -> float:
        """Calculate average response time"""
        times = [
            a.get("metadata", {}).get("response_time_ms", 0)
            for a in analytics
        ]
        
        if not times:
            return 0.0
        
        return round(sum(times) / len(times), 2)
    
    def _analyze_question_frequency(self, questions: List[Dict]) -> Dict[str, int]:
        """Analyze when questions are asked"""
        if not questions:
            return {}
        
        dates = [q.get("created_at") for q in questions if q.get("created_at")]
        
        if not dates:
            return {}
        
        # Group by date
        date_counts = Counter([d.date().isoformat() for d in dates])
        
        return {
            "daily_average": round(sum(date_counts.values()) / len(date_counts), 2),
            "peak_day": max(date_counts.items(), key=lambda x: x[1])[0] if date_counts else "N/A",
            "total_days": len(date_counts)
        }
    
    def _find_peak_usage(self, questions: List[Dict]) -> List[Dict[str, Any]]:
        """Find peak usage times"""
        if not questions:
            return []
        
        hours = [q.get("created_at").hour for q in questions if q.get("created_at")]
        
        if not hours:
            return []
        
        hour_counts = Counter(hours)
        
        return [
            {
                "hour": f"{h:02d}:00",
                "count": c
            }
            for h, c in hour_counts.most_common(3)
        ]


# Global instance getter
_analytics_service: Optional['AnalyticsService'] = None

def get_analytics_service(db: AsyncIOMotorDatabase) -> AnalyticsService:
    """Get or create analytics service instance"""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService(db)
    return _analytics_service

