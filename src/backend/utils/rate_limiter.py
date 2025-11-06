"""
Rate Limiter for LiteLLM
Implements semaphore-based rate limiting with retry logic and exponential backoff
"""

import asyncio
import logging
from typing import Any, Callable, TypeVar, Optional
from functools import wraps
import litellm
from ..config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RateLimiter:
    """
    Rate limiter using semaphore for concurrent request control
    with retry logic and exponential backoff
    """
    
    def __init__(
        self,
        max_concurrent: int = None,
        max_retries: int = None,
        retry_delay: float = None,
        retry_backoff: float = None
    ):
        """
        Initialize rate limiter
        
        Args:
            max_concurrent: Maximum concurrent requests
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay in seconds
            retry_backoff: Exponential backoff multiplier
        """
        self.max_concurrent = max_concurrent or settings.LLM_MAX_CONCURRENT_REQUESTS
        self.max_retries = max_retries or settings.LLM_MAX_RETRIES
        self.retry_delay = retry_delay or settings.LLM_RETRY_DELAY
        self.retry_backoff = retry_backoff or settings.LLM_RETRY_BACKOFF
        
        # Semaphore for concurrent request limiting
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.retried_requests = 0
        
        logger.info(
            f"Initialized rate limiter: max_concurrent={self.max_concurrent}, "
            f"max_retries={self.max_retries}"
        )
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with rate limiting and retry logic
        
        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            Result from the function
        
        Raises:
            Exception: If all retries are exhausted
        """
        self.total_requests += 1
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Acquire semaphore (wait if at max concurrent)
                async with self.semaphore:
                    logger.debug(f"Executing request (attempt {attempt + 1}/{self.max_retries + 1})")
                    
                    # Execute the function
                    result = await func(*args, **kwargs)
                    
                    # Success!
                    self.successful_requests += 1
                    if attempt > 0:
                        self.retried_requests += 1
                        logger.info(f"Request succeeded after {attempt} retries")
                    
                    return result
            
            except litellm.RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit hit (attempt {attempt + 1}): {e}")
                
                # Don't retry if this was the last attempt
                if attempt < self.max_retries:
                    # Calculate backoff delay
                    delay = self.retry_delay * (self.retry_backoff ** attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    self.failed_requests += 1
                    logger.error("Max retries exhausted for rate limit error")
                    raise
            
            except litellm.APIError as e:
                last_exception = e
                logger.error(f"API error (attempt {attempt + 1}): {e}")
                
                # Retry on specific API errors (timeout, connection error, etc.)
                if attempt < self.max_retries and self._is_retryable_error(e):
                    delay = self.retry_delay * (self.retry_backoff ** attempt)
                    logger.info(f"Retrying API error in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    self.failed_requests += 1
                    raise
            
            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error: {e}")
                self.failed_requests += 1
                raise
        
        # Should not reach here, but just in case
        self.failed_requests += 1
        if last_exception:
            raise last_exception
        else:
            raise Exception("Request failed after all retries")
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable
        
        Args:
            error: The exception that occurred
        
        Returns:
            True if the error should be retried
        """
        # Retry on timeout, connection errors, and server errors (5xx)
        error_str = str(error).lower()
        retryable_patterns = [
            "timeout",
            "connection",
            "503",
            "502",
            "500",
            "429",  # Rate limit
            "server error"
        ]
        
        return any(pattern in error_str for pattern in retryable_patterns)
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        total = self.total_requests
        success_rate = (self.successful_requests / total * 100) if total > 0 else 0
        retry_rate = (self.retried_requests / total * 100) if total > 0 else 0
        
        return {
            "total_requests": total,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "retried_requests": self.retried_requests,
            "success_rate": round(success_rate, 2),
            "retry_rate": round(retry_rate, 2),
            "max_concurrent": self.max_concurrent,
            "max_retries": self.max_retries
        }
    
    def reset_stats(self):
        """Reset statistics"""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.retried_requests = 0
        logger.info("Rate limiter statistics reset")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def with_rate_limit(func: Callable) -> Callable:
    """
    Decorator to add rate limiting to an async function
    
    Usage:
        @with_rate_limit
        async def my_llm_call():
            return await litellm.acompletion(...)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        limiter = get_rate_limiter()
        return await limiter.execute_with_retry(func, *args, **kwargs)
    
    return wrapper

