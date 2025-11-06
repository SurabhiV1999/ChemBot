"""
Query Engine Module
Handles question answering using RAG (Retrieval Augmented Generation)
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import litellm
from .vector_store import VectorStoreManager
from ..config import settings
from ..cache import get_cache_manager
from ..utils.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


def load_prompts(prompts_file: str = None) -> Dict[str, Any]:
    """Load prompts from YAML file"""
    if prompts_file is None:
        prompts_file = settings.PROMPTS_FILE
    
    prompts_path = Path(prompts_file)
    if not prompts_path.exists():
        # Try relative to current file
        prompts_path = Path(__file__).parent.parent / "prompts.yaml"
    
    if not prompts_path.exists():
        logger.error(f"Prompts file not found: {prompts_file}")
        raise FileNotFoundError(f"Prompts file not found: {prompts_file}")
    
    with open(prompts_path, 'r', encoding='utf-8') as f:
        prompts = yaml.safe_load(f)
    
    logger.info(f"Loaded prompts from {prompts_path}")
    return prompts


class QueryEngine:
    """
    Query Engine for RAG-based question answering
    Retrieves relevant context and generates answers using LLM
    """
    
    def __init__(self):
        self.vector_manager = VectorStoreManager()
        self.llm_model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        
        # Load prompts from YAML
        self.prompts = load_prompts()
        
        # Initialize cache and rate limiter
        self.cache_manager = get_cache_manager()
        self.rate_limiter = get_rate_limiter()
        
        logger.info(f"Initialized QueryEngine with model: {self.llm_model} "
                   f"(caching={'enabled' if settings.REDIS_CACHE_ENABLED else 'disabled'}, "
                   f"rate_limit={settings.LLM_MAX_CONCURRENT_REQUESTS})")
    
    async def initialize(self):
        """Initialize vector store"""
        await self.vector_manager.initialize()
    
    async def answer_question(self, question: str, content_id: str, 
                             top_k: int = 5, include_sources: bool = True,
                             use_cache: bool = True) -> Dict[str, Any]:
        """
        Answer a question using RAG with caching and rate limiting
        
        Args:
            question: User's question
            content_id: Content ID to search in
            top_k: Number of relevant chunks to retrieve
            include_sources: Whether to include source chunks in response
            use_cache: Whether to use cached answers (default: True)
        
        Returns:
            Dict with answer, confidence, sources, and metadata
        """
        try:
            start_time = datetime.now(timezone.utc)
            
            # NOTE: Cache is checked at ChatbotEngine level BEFORE this function is called
            # This function is ONLY called when cache miss happens
            # So we skip cache check here and go straight to generation
            
            # Step 1: Retrieve relevant chunks
            logger.info(f"Searching for relevant chunks for question: {question[:100]}...")
            
            relevant_chunks = await self.vector_manager.search_similar(
                query=question,
                content_id=content_id,
                top_k=top_k
            )
            
            if not relevant_chunks:
                return {
                    "answer": self.prompts.get("error_messages", {}).get(
                        "no_context",
                        "I couldn't find relevant information in the content to answer your question."
                    ),
                    "confidence_score": 0.0,
                    "source_chunks": [],
                    "error": "No relevant context found"
                }
            
            # Step 2: Prepare context from retrieved chunks
            context = self._prepare_context(relevant_chunks)
            
            # Step 3: Generate answer using LLM
            logger.info(f"Generating answer using {self.llm_model}...")
            
            answer_data = await self._generate_answer(question, context)
            
            # Step 4: Calculate response time
            end_time = datetime.now(timezone.utc)
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Step 5: Prepare response
            result = {
                "answer": answer_data["answer"],
                "confidence_score": self._calculate_confidence(relevant_chunks),
                "response_time_ms": response_time_ms,
                "model_used": self.llm_model,
                "tokens_used": answer_data.get("tokens_used", 0),
                "source_chunks": self._format_sources(relevant_chunks) if include_sources else [],
                "cached": False
            }
            
            # Step 6: Cache the answer for future use
            if use_cache:
                logger.info(f"📝 Attempting to cache answer for: '{question[:70]}'")
                await self.cache_manager.cache_answer(
                    question=question,
                    content_id=content_id,
                    answer_data=result,
                    top_k=top_k,
                    model=self.llm_model
                )
                logger.info(f"✅ Cache storage completed for: '{question[:70]}'")
            else:
                logger.info(f"⚠️ Not caching answer (use_cache={use_cache})")
            
            logger.info(f"✅ Answer generated in {response_time_ms}ms")
            return result
        
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}", exc_info=True)
            return {
                "answer": self.prompts.get("error_messages", {}).get(
                    "processing_error",
                    "I encountered an error while processing your question. Please try again."
                ),
                "confidence_score": 0.0,
                "source_chunks": [],
                "error": str(e)
            }
    
    def _prepare_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Prepare context from retrieved chunks"""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            text = chunk["metadata"].get("text", "")
            chunk_index = chunk["metadata"].get("chunk_index", "?")
            
            context_parts.append(f"[Context {i} - Chunk {chunk_index}]\n{text}\n")
        
        return "\n".join(context_parts)
    
    async def _generate_answer(self, question: str, context: str) -> Dict[str, Any]:
        """Generate answer using LLM with rate limiting"""
        
        # Load system prompt from YAML
        system_prompt = self.prompts.get("chatbot_system_prompt", "")
        
        # Load and format user prompt from YAML
        user_prompt_template = self.prompts.get("chatbot_user_prompt", "")
        user_prompt = user_prompt_template.format(
            context=context,
            question=question
        )
        
        try:
            # Use rate limiter to execute LLM call with retry logic
            response = await self.rate_limiter.execute_with_retry(
                litellm.acompletion,
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            answer = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            
            return {
                "answer": answer,
                "tokens_used": tokens_used
            }
        
        except Exception as e:
            logger.error(f"Error generating answer with LLM: {str(e)}")
            raise
    
    def _calculate_confidence(self, chunks: List[Dict[str, Any]]) -> float:
        """
        Calculate confidence score based on retrieval scores
        Higher scores mean more confident answer
        """
        if not chunks:
            return 0.0
        
        # Average the top chunk scores
        scores = [chunk.get("score", 0.0) for chunk in chunks[:3]]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Normalize to 0-1 range (assuming cosine similarity scores)
        # Cosine similarity ranges from -1 to 1, but typically 0.5-1.0 for relevant docs
        confidence = min(max(avg_score, 0.0), 1.0)
        
        return round(confidence, 2)
    
    def _format_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format source chunks for response"""
        sources = []
        
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            sources.append({
                "text": metadata.get("text", "")[:500] + "...",  # Truncate for readability
                "chunk_index": metadata.get("chunk_index", 0),
                "relevance_score": round(chunk.get("score", 0.0), 3),
                "section_title": metadata.get("section_title", ""),
                "page": metadata.get("page", None)
            })
        
        return sources
    
    async def answer_question_stream(
        self,
        question: str,
        content_id: str,
        user_id: str,
        conversation_context: str = "",
        top_k: int = 5
    ):
        """
        Stream answer chunks in real-time using LiteLLM streaming
        
        Args:
            question: User's question
            content_id: Content ID
            user_id: User ID
            conversation_context: Previous conversation context
            top_k: Number of chunks to retrieve
        
        Yields:
            Text chunks as they're generated by the LLM
        """
        try:
            # Retrieve relevant context
            relevant_chunks = await self.vector_manager.search_similar(
                query=question,
                content_id=content_id,
                top_k=top_k
            )
            
            if not relevant_chunks:
                yield "I couldn't find relevant information in your uploaded content to answer this question."
                return
            
            # Prepare context
            context = self._prepare_context(relevant_chunks)
            
            # Build prompt with context
            system_prompt = self.prompts.get("chatbot_system_prompt", "")
            
            user_prompt_template = self.prompts.get("chatbot_user_prompt", "")
            user_prompt = user_prompt_template.format(
                context=context,
                question=question
            )
            
            # Stream response from LLM using rate limiter
            response = await self.rate_limiter.execute_with_retry(
                litellm.acompletion,
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True  # Enable streaming
            )
            
            # Yield chunks as they arrive
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        except Exception as e:
            logger.error(f"Error in streaming answer: {str(e)}", exc_info=True)
            yield "An error occurred while generating the answer. Please try again."
