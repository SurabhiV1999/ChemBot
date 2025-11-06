"""
Conversation Manager Module
Manages conversation history for contextual chat interactions
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..config import settings

logger = logging.getLogger(__name__)


class ConversationTurn:
    """Represents a single conversation turn (question + answer)"""
    
    def __init__(self, question: str, answer: str, timestamp: datetime = None):
        self.question = question
        self.answer = answer
        self.timestamp = timestamp or datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_context_string(self) -> str:
        """Format for use in LLM context"""
        return f"Student: {self.question}\nChemBot: {self.answer}"


class ConversationManager:
    """
    Manages conversation history for contextual interactions
    Stores recent exchanges in memory for quick access
    """
    
    def __init__(self, max_history: int = None):
        self.max_history = max_history or settings.CONVERSATION_HISTORY_LENGTH
        # In-memory storage: {content_id_user_id: [ConversationTurn]}
        self.conversations: Dict[str, List[ConversationTurn]] = {}
        
        logger.info(f"Initialized ConversationManager (max_history={self.max_history})")
    
    def _get_conversation_key(self, content_id: str, user_id: str) -> str:
        """Generate unique key for user-content conversation"""
        return f"{content_id}_{user_id}"
    
    def add_turn(self, content_id: str, user_id: str, question: str, answer: str):
        """
        Add a conversation turn to history
        
        Args:
            content_id: Content being discussed
            user_id: User asking the question
            question: User's question
            answer: Bot's answer
        """
        key = self._get_conversation_key(content_id, user_id)
        
        if key not in self.conversations:
            self.conversations[key] = []
        
        turn = ConversationTurn(question, answer)
        self.conversations[key].append(turn)
        
        # Keep only recent history
        if len(self.conversations[key]) > self.max_history:
            self.conversations[key] = self.conversations[key][-self.max_history:]
        
        logger.debug(f"Added conversation turn for {key}. Total turns: {len(self.conversations[key])}")
    
    def get_history(self, content_id: str, user_id: str, limit: Optional[int] = None) -> List[ConversationTurn]:
        """
        Get conversation history for a user and content
        
        Args:
            content_id: Content being discussed
            user_id: User ID
            limit: Maximum number of turns to return (default: all)
        
        Returns:
            List of ConversationTurn objects (oldest first)
        """
        key = self._get_conversation_key(content_id, user_id)
        history = self.conversations.get(key, [])
        
        if limit:
            history = history[-limit:]
        
        return history
    
    def get_context_string(self, content_id: str, user_id: str, limit: Optional[int] = None) -> str:
        """
        Get conversation history formatted as context string for LLM
        
        Args:
            content_id: Content being discussed
            user_id: User ID
            limit: Maximum number of turns to include
        
        Returns:
            Formatted string of conversation history
        """
        history = self.get_history(content_id, user_id, limit)
        
        if not history:
            return ""
        
        context_lines = [turn.to_context_string() for turn in history]
        return "\n\n".join(context_lines)
    
    def clear_history(self, content_id: str, user_id: str):
        """Clear conversation history for a user and content"""
        key = self._get_conversation_key(content_id, user_id)
        if key in self.conversations:
            del self.conversations[key]
            logger.info(f"Cleared conversation history for {key}")
    
    def clear_all(self):
        """Clear all conversation histories"""
        self.conversations.clear()
        logger.info("Cleared all conversation histories")
    
    async def load_from_database(self, db: AsyncIOMotorDatabase, content_id: str, user_id: str, limit: int = None):
        """
        Load conversation history from database
        
        Args:
            db: Database instance
            content_id: Content ID
            user_id: User ID
            limit: Number of recent questions to load
        """
        try:
            from bson import ObjectId
            
            # Query recent questions for this content and user
            query = {
                "content_id": content_id,
                "user_id": user_id
            }
            
            limit = limit or self.max_history
            cursor = db.questions.find(query).sort("created_at", -1).limit(limit)
            
            questions = []
            async for q in cursor:
                questions.append(q)
            
            # Reverse to get chronological order
            questions.reverse()
            
            # Add to conversation history
            key = self._get_conversation_key(content_id, user_id)
            self.conversations[key] = []
            
            for q in questions:
                turn = ConversationTurn(
                    question=q.get("question", ""),
                    answer=q.get("answer", ""),
                    timestamp=q.get("created_at", datetime.now(timezone.utc))
                )
                self.conversations[key].append(turn)
            
            logger.info(f"Loaded {len(questions)} turns from database for {key}")
        
        except Exception as e:
            logger.error(f"Error loading conversation history from database: {str(e)}")

