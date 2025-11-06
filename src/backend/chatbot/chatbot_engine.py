"""
Complete Chatbot Engine
Orchestrates all components: RAG, caching, conversation history, query classification
"""

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..rag import QueryEngine
from .query_classifier import QueryClassifier
from .conversation_manager import ConversationManager
from ..cache import get_cache_manager
from ..utils import db_utils
from ..config import settings

logger = logging.getLogger(__name__)


class ChatbotEngine:
    """
    Complete chatbot engine integrating all components
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.query_engine = QueryEngine()
        self.query_classifier = QueryClassifier()
        self.conversation_manager = ConversationManager()
        self.cache_manager = get_cache_manager()

        self.enable_streaming = settings.ENABLE_STREAMING
        self.enable_classification = settings.ENABLE_QUERY_CLASSIFICATION

        logger.info("Initialized ChatbotEngine with caching enabled" if self.cache_manager.enabled else "Initialized ChatbotEngine")
    
    async def initialize(self):
        """Initialize all components"""
        await self.query_engine.initialize()
        logger.info("ChatbotEngine fully initialized")
    
    async def ask_question(
        self,
        question: str,
        content_id: str,
        user_id: str,
        stream: bool = False,
        use_cache: bool = True,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Process a question through the complete pipeline

        Args:
            question: User's question
            content_id: Content ID being queried
            user_id: User asking the question
            stream: Whether to stream the response
            use_cache: Whether to use cached answers
            include_sources: Whether to include source chunks

        Returns:
            Complete response with answer, metadata, and analytics
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"Processing question: '{question[:70]}...' for content {content_id}")

        try:
            # Check cache first
            if use_cache:
                cached_answer = await self.cache_manager.get_cached_answer(
                    question=question,
                    content_id=content_id,
                    top_k=5,
                    model=self.query_engine.llm_model
                )

                if cached_answer:
                    logger.info(f"Cache hit for question: '{question[:70]}...'")
                    end_time = datetime.now(timezone.utc)
                    response_time_ms = int((end_time - start_time).total_seconds() * 1000)

                    cached_answer["cached"] = True
                    cached_answer["total_response_time_ms"] = response_time_ms

                    await self._track_analytics(
                        user_id=user_id,
                        content_id=content_id,
                        question_id=None,
                        response_time_ms=response_time_ms,
                        classification={"question_type": "cached", "confidence": 1.0},
                        cached=True
                    )

                    return cached_answer
            
            # Classify query
            classification = await self._classify_query(question)

            # Check if it's a valid question
            if not classification["is_question"]:
                return {
                    "answer": "I noticed this might not be a question. If you'd like to learn something specific from your material, please ask me a question!",
                    "is_question": False,
                    "classification": classification,
                    "cached": False
                }
            
            if not classification["is_relevant"]:
                return {
                    "answer": "This question seems to be outside the scope of your uploaded learning material. I can only help with questions related to the content you've provided.",
                    "is_question": True,
                    "is_relevant": False,
                    "classification": classification,
                    "cached": False
                }


            # Load conversation history
            conversation_context = self.conversation_manager.get_context_string(
                content_id, user_id, limit=3
            )

            # Get answer from RAG engine
            answer_result = await self.query_engine.answer_question(
                question=question,
                content_id=content_id,
                top_k=5,
                use_cache=use_cache,
                include_sources=include_sources
            )

            # Calculate response time
            end_time = datetime.now(timezone.utc)
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Store question in database
            question_doc = None
            if self.query_classifier.should_store_question(classification):
                question_doc = await self._store_question(
                    question=question,
                    answer=answer_result["answer"],
                    content_id=content_id,
                    user_id=user_id,
                    classification=classification,
                    answer_result=answer_result
                )

            # Update conversation history
            self.conversation_manager.add_turn(
                content_id=content_id,
                user_id=user_id,
                question=question,
                answer=answer_result["answer"]
            )

            # Track analytics
            await self._track_analytics(
                user_id=user_id,
                content_id=content_id,
                question_id=question_doc.id if question_doc else None,
                response_time_ms=response_time_ms,
                classification=classification,
                cached=answer_result.get("cached", False)
            )

            # Prepare final response
            response = {
                **answer_result,
                "question_id": str(question_doc.id) if question_doc else None,
                "is_question": True,
                "is_relevant": True,
                "classification": classification,
                "total_response_time_ms": response_time_ms,
                "has_conversation_context": bool(conversation_context)
            }
            
            return response
        
        except Exception as e:
            logger.error(f"Error in chatbot engine: {str(e)}", exc_info=True)
            return {
                "answer": "I encountered an error processing your question. Please try again.",
                "error": str(e),
                "cached": False
            }
    
    async def ask_question_stream(
        self,
        question: str,
        content_id: str,
        user_id: str,
        use_cache: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Stream answer chunks for real-time response with caching support

        Args:
            question: User's question
            content_id: Content ID
            user_id: User ID
            use_cache: Whether to use cached answers

        Yields:
            Answer chunks as they're generated from LLM
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"Streaming question: '{question[:70]}...' for content {content_id}")

        try:
            # Check cache first
            if use_cache:
                cached_answer = await self.cache_manager.get_cached_answer(
                    question=question,
                    content_id=content_id,
                    top_k=5,
                    model=self.query_engine.llm_model
                )

                if cached_answer:
                    logger.info(f"Cache hit for streaming question: '{question[:70]}...'")

                    # Stream the cached answer in chunks to simulate natural streaming
                    answer = cached_answer.get("answer", "")
                    chunk_size = 10  # Characters per chunk

                    for i in range(0, len(answer), chunk_size):
                        chunk = answer[i:i + chunk_size]
                        yield chunk
                        await asyncio.sleep(0.01)

                    # Track analytics for cached streaming response
                    end_time = datetime.now(timezone.utc)
                    response_time_ms = int((end_time - start_time).total_seconds() * 1000)

                    await self._track_analytics(
                        user_id=user_id,
                        content_id=content_id,
                        question_id=None,
                        response_time_ms=response_time_ms,
                        classification={"question_type": "cached", "confidence": 1.0},
                        cached=True
                    )

                    return

            # Classify query
            classification = await self._classify_query(question)
            
            if not classification["is_question"]:
                yield "I noticed this might not be a question. If you'd like to learn something specific from your material, please ask me a question!"
                return
            
            if not classification["is_relevant"]:
                yield "This question seems to be outside the scope of your uploaded learning material. I can only help with questions related to the content you've provided."
                return
            
            # Load conversation history
            conversation_context = self.conversation_manager.get_context_string(
                content_id, user_id, limit=3
            )

            # Stream answer from RAG engine
            full_answer = ""
            async for chunk in self.query_engine.answer_question_stream(
                question=question,
                content_id=content_id,
                user_id=user_id,
                conversation_context=conversation_context
            ):
                full_answer += chunk
                yield chunk

            # Calculate response time
            end_time = datetime.now(timezone.utc)
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # After streaming is complete, store the question
            question_doc = None
            if self.query_classifier.should_store_question(classification):
                question_doc = await self._store_question(
                    question=question,
                    answer=full_answer,
                    content_id=content_id,
                    user_id=user_id,
                    classification=classification,
                    answer_result={
                        "confidence_score": 0.8,  # Default for streaming
                        "response_time_ms": response_time_ms,
                        "model_used": self.query_engine.llm_model
                    }
                )

            # Cache the answer for future requests
            if use_cache and full_answer:
                cache_data = {
                    "answer": full_answer,
                    "confidence_score": 0.8,
                    "response_time_ms": response_time_ms,
                    "model_used": self.query_engine.llm_model,
                    "tokens_used": 0,
                    "source_chunks": [],
                    "cached": False
                }

                await self.cache_manager.cache_answer(
                    question=question,
                    content_id=content_id,
                    answer_data=cache_data,
                    top_k=5,
                    model=self.query_engine.llm_model
                )

            # Update conversation history
            self.conversation_manager.add_turn(
                content_id=content_id,
                user_id=user_id,
                question=question,
                answer=full_answer
            )

            # Track analytics
            await self._track_analytics(
                user_id=user_id,
                content_id=content_id,
                question_id=str(question_doc.id) if question_doc else None,
                response_time_ms=response_time_ms,
                classification=classification,
                cached=False
            )
            
        except Exception as e:
            logger.error(f"Error in streaming: {str(e)}", exc_info=True)
            yield "I encountered an error processing your question. Please try again."
    
    async def _classify_query(self, question: str) -> Dict[str, Any]:
        """Classify the query"""
        if not self.enable_classification:
            return {
                "is_question": True,
                "is_relevant": True,
                "question_type": "general",
                "confidence": 1.0
            }
        
        return await self.query_classifier.classify_query(question)
    
    async def _store_question(
        self,
        question: str,
        answer: str,
        content_id: str,
        user_id: str,
        classification: Dict[str, Any],
        answer_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store question-answer pair in database"""
        from ..models import QuestionCreate
        
        question_data = QuestionCreate(
            question=question,
            content_id=content_id
        )
        
        question_doc = await db_utils.create_question(
            db=self.db,
            question_data=question_data,
            user_id=user_id,
            answer=answer,
            confidence_score=answer_result.get("confidence_score"),
            response_time_ms=answer_result.get("response_time_ms"),
            model_used=answer_result.get("model_used"),
            tokens_used=answer_result.get("tokens_used"),
            source_chunks=answer_result.get("source_chunks", [])
        )
        
        return question_doc
    
    async def _track_analytics(
        self,
        user_id: str,
        content_id: str,
        question_id: Optional[str],
        response_time_ms: int,
        classification: Dict[str, Any],
        cached: bool
    ):
        """Track analytics event"""
        from ..models import AnalyticsCreate
        
        analytics_data = AnalyticsCreate(
            event_type="question_asked",
            user_id=user_id,
            content_id=content_id,
            question_id=question_id,
            metadata={
                "response_time_ms": response_time_ms,
                "question_type": classification.get("question_type"),
                "cached": cached,
                "confidence": classification.get("confidence")
            }
        )
        
        await db_utils.create_analytics_event(
            db=self.db,
            analytics_data=analytics_data,
            duration_ms=response_time_ms
        )
    
    async def load_conversation_history(
        self,
        content_id: str,
        user_id: str
    ):
        """Load conversation history from database"""
        await self.conversation_manager.load_from_database(
            db=self.db,
            content_id=content_id,
            user_id=user_id
        )
    
    def clear_conversation_history(
        self,
        content_id: str,
        user_id: str
    ):
        """Clear conversation history (start fresh conversation)"""
        self.conversation_manager.clear_history(content_id, user_id)
        logger.info(f"Cleared conversation history for user {user_id}, content {content_id}")

