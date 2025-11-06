"""
Unit tests for Rate Limiter
"""

import pytest
import asyncio
from src.backend.utils.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test suite for rate limiter functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Test 1: Rate limiter initializes with correct settings"""
        limiter = RateLimiter(
            max_concurrent=5,
            max_retries=3,
            retry_delay=1.0,
            retry_backoff=2.0
        )
        
        assert limiter.max_concurrent == 5
        assert limiter.max_retries == 3
        assert limiter.retry_delay == 1.0
        assert limiter.retry_backoff == 2.0
        assert limiter.total_requests == 0
        assert limiter.successful_requests == 0
        assert limiter.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test 2: Successful function execution with rate limiter"""
        limiter = RateLimiter(max_concurrent=2, max_retries=1)
        
        async def mock_success_function():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await limiter.execute_with_retry(mock_success_function)
        
        assert result == "success"
        assert limiter.total_requests == 1
        assert limiter.successful_requests == 1
        assert limiter.failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_request_limiting(self):
        """Test 3: Concurrent request limiting works correctly"""
        limiter = RateLimiter(max_concurrent=2, max_retries=1)
        
        execution_times = []
        
        async def mock_slow_function(task_id):
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.2)
            end = asyncio.get_event_loop().time()
            execution_times.append((task_id, start, end))
            return f"task_{task_id}"
        
        # Execute 4 tasks with max_concurrent=2
        tasks = [
            limiter.execute_with_retry(mock_slow_function, i)
            for i in range(4)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all tasks completed
        assert len(results) == 4
        assert limiter.successful_requests == 4
        
        # Verify concurrent execution was limited
        # At most 2 should be running at the same time
        assert limiter.max_concurrent == 2
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test 4: Retry logic on transient failures"""
        limiter = RateLimiter(max_concurrent=1, max_retries=2, retry_delay=0.1)
        
        attempt_count = 0
        
        async def mock_flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise Exception("Transient error")
            return "success_after_retry"
        
        result = await limiter.execute_with_retry(mock_flaky_function)
        
        assert result == "success_after_retry"
        assert attempt_count == 2
        assert limiter.retried_requests == 1
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test 5: Statistics tracking works correctly"""
        limiter = RateLimiter(max_concurrent=2, max_retries=1)
        
        async def mock_function():
            return "done"
        
        # Execute some requests
        await limiter.execute_with_retry(mock_function)
        await limiter.execute_with_retry(mock_function)
        
        stats = limiter.get_stats()
        
        assert stats["total_requests"] == 2
        assert stats["successful_requests"] == 2
        assert stats["success_rate"] == 100.0
        assert stats["max_concurrent"] == 2
    
    @pytest.mark.asyncio
    async def test_reset_stats(self):
        """Test 6: Statistics can be reset"""
        limiter = RateLimiter(max_concurrent=1, max_retries=1)
        
        async def mock_function():
            return "done"
        
        await limiter.execute_with_retry(mock_function)
        
        assert limiter.total_requests == 1
        
        limiter.reset_stats()
        
        assert limiter.total_requests == 0
        assert limiter.successful_requests == 0
        assert limiter.failed_requests == 0

