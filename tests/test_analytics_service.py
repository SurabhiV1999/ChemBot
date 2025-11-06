"""
Unit tests for Analytics Service
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from src.backend.services.analytics_service import AnalyticsService


class TestAnalyticsService:
    """Test suite for analytics service functionality"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = MagicMock()
        db.questions = MagicMock()
        db.content = MagicMock()
        db.analytics = MagicMock()
        return db
    
    @pytest.fixture
    def analytics_service(self, mock_db):
        """Create analytics service with mock database"""
        return AnalyticsService(mock_db)
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, analytics_service, mock_db):
        """Test 7: Analytics service initializes correctly"""
        assert analytics_service.db == mock_db
    
    @pytest.mark.asyncio
    async def test_get_student_engagement_metrics_empty(self, analytics_service, mock_db):
        """Test 8: Student engagement metrics handles empty data"""
        # Mock empty responses
        mock_db.questions.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.content.find.return_value.to_list = AsyncMock(return_value=[])
        
        result = await analytics_service.get_student_engagement_metrics("user123")
        
        assert result["total_contents"] == 0
        assert result["total_questions"] == 0
        assert result["avg_questions_per_content"] == 0.0
    
    @pytest.mark.asyncio
    async def test_get_student_engagement_metrics_with_data(self, analytics_service, mock_db):
        """Test 9: Student engagement metrics calculates correctly"""
        now = datetime.now(timezone.utc)
        
        # Mock questions
        mock_questions = [
            {
                "question": "What is X?",
                "answer": "X is...",
                "confidence_score": 0.9,
                "created_at": now,
                "rating": 5,
                "is_helpful": True
            },
            {
                "question": "What is Y?",
                "answer": "Y is...",
                "confidence_score": 0.8,
                "created_at": now - timedelta(days=5),
                "rating": 4,
                "is_helpful": True
            }
        ]
        
        # Mock contents
        mock_contents = [
            {"status": "completed"},
            {"status": "completed"}
        ]
        
        mock_db.questions.find.return_value.to_list = AsyncMock(return_value=mock_questions)
        mock_db.content.find.return_value.to_list = AsyncMock(return_value=mock_contents)
        
        result = await analytics_service.get_student_engagement_metrics("user123")
        
        assert result["total_contents"] == 2
        assert result["total_questions"] == 2
        assert result["avg_questions_per_content"] == 1.0
        assert result["contents_by_status"]["completed"] == 2
    
    @pytest.mark.asyncio
    async def test_most_asked_questions(self, analytics_service, mock_db):
        """Test 10: Most asked questions aggregation works"""
        mock_results = [
            {
                "_id": "what is chemistry?",
                "count": 5,
                "avg_confidence": 0.85,
                "sample_answer": "Chemistry is the study of matter..."
            },
            {
                "_id": "what is physics?",
                "count": 3,
                "avg_confidence": 0.90,
                "sample_answer": "Physics is the study of energy..."
            }
        ]
        
        mock_db.questions.aggregate.return_value.to_list = AsyncMock(return_value=mock_results)
        
        result = await analytics_service.get_most_asked_questions("content123", limit=10)
        
        assert len(result) == 2
        assert result[0]["question"] == "what is chemistry?"
        assert result[0]["frequency"] == 5
        assert result[1]["question"] == "what is physics?"
        assert result[1]["frequency"] == 3
    
    @pytest.mark.asyncio
    async def test_response_time_analytics(self, analytics_service, mock_db):
        """Test 11: Response time analytics calculates correctly"""
        mock_results = [
            {
                "avg_response_time": 1500.5,
                "min_response_time": 800,
                "max_response_time": 3000,
                "total_questions": 50,
                "cached_questions": 10
            }
        ]
        
        mock_db.analytics.aggregate.return_value.to_list = AsyncMock(return_value=mock_results)
        
        result = await analytics_service.get_response_time_analytics(content_id="content123")
        
        assert result["avg_response_time_ms"] == 1500.5
        assert result["min_response_time_ms"] == 800
        assert result["max_response_time_ms"] == 3000
        assert result["total_questions"] == 50
        assert result["cache_hit_rate"] == 20.0  # 10/50 * 100
    
    @pytest.mark.asyncio
    async def test_content_analytics(self, analytics_service, mock_db):
        """Test 12: Content analytics retrieves correct metrics"""
        # Mock questions for content
        mock_questions = [
            {"question": "Q1", "confidence_score": 0.9, "rating": 5},
            {"question": "Q2", "confidence_score": 0.8, "rating": 4},
            {"question": "Q3", "confidence_score": 0.7, "rating": 5}
        ]
        
        mock_db.questions.find.return_value.to_list = AsyncMock(return_value=mock_questions)
        
        result = await analytics_service.get_content_analytics("content123")
        
        assert "total_questions" in result
        assert "avg_confidence_score" in result
        assert "question_distribution" in result

