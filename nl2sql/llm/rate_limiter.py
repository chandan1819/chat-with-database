"""Rate limiting functionality for API calls."""

import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_requests: int = 60  # Maximum requests per window
    window_seconds: int = 60  # Time window in seconds
    burst_limit: int = 10  # Maximum burst requests


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter."""
    
    def __init__(self, config: RateLimitConfig):
        """Initialize the rate limiter.
        
        Args:
            config: Rate limiting configuration
        """
        self.config = config
        self._requests: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
    
    def _cleanup_old_requests(self, client_id: str, current_time: float) -> None:
        """Remove requests outside the current window.
        
        Args:
            client_id: Identifier for the client
            current_time: Current timestamp
        """
        if client_id not in self._requests:
            return
        
        cutoff_time = current_time - self.config.window_seconds
        self._requests[client_id] = [
            req_time for req_time in self._requests[client_id]
            if req_time > cutoff_time
        ]
    
    def _get_retry_after(self, client_id: str, current_time: float) -> float:
        """Calculate how long to wait before next request is allowed.
        
        Args:
            client_id: Identifier for the client
            current_time: Current timestamp
            
        Returns:
            float: Seconds to wait before retry
        """
        if client_id not in self._requests or not self._requests[client_id]:
            return 0.0
        
        # Find the oldest request that would still be in the window
        # after we remove one request
        requests = sorted(self._requests[client_id])
        if len(requests) < self.config.max_requests:
            return 0.0
        
        # The oldest request that needs to expire for us to make a new request
        oldest_blocking_request = requests[-(self.config.max_requests - 1)]
        retry_after = oldest_blocking_request + self.config.window_seconds - current_time
        
        return max(0.0, retry_after)
    
    def check_rate_limit(self, client_id: str = "default") -> None:
        """Check if request is allowed under rate limit.
        
        Args:
            client_id: Identifier for the client (default: "default")
            
        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        current_time = time.time()
        
        with self._lock:
            # Clean up old requests
            self._cleanup_old_requests(client_id, current_time)
            
            # Initialize client if not exists
            if client_id not in self._requests:
                self._requests[client_id] = []
            
            client_requests = self._requests[client_id]
            
            # Check burst limit (requests in last few seconds)
            recent_cutoff = current_time - 5  # Last 5 seconds
            recent_requests = [req for req in client_requests if req > recent_cutoff]
            
            if len(recent_requests) >= self.config.burst_limit:
                retry_after = self._get_retry_after(client_id, current_time)
                logger.warning(
                    "Burst rate limit exceeded for client %s: %d requests in last 5 seconds",
                    client_id, len(recent_requests)
                )
                raise RateLimitExceededError(
                    f"Burst rate limit exceeded. Too many requests in a short time. "
                    f"Please wait {retry_after:.1f} seconds before trying again.",
                    retry_after=retry_after
                )
            
            # Check window limit
            if len(client_requests) >= self.config.max_requests:
                retry_after = self._get_retry_after(client_id, current_time)
                logger.warning(
                    "Rate limit exceeded for client %s: %d requests in %d second window",
                    client_id, len(client_requests), self.config.window_seconds
                )
                raise RateLimitExceededError(
                    f"Rate limit exceeded. Maximum {self.config.max_requests} requests "
                    f"per {self.config.window_seconds} seconds allowed. "
                    f"Please wait {retry_after:.1f} seconds before trying again.",
                    retry_after=retry_after
                )
            
            # Record this request
            client_requests.append(current_time)
            logger.debug(
                "Rate limit check passed for client %s: %d/%d requests in window",
                client_id, len(client_requests), self.config.max_requests
            )
    
    def get_rate_limit_status(self, client_id: str = "default") -> Dict[str, any]:
        """Get current rate limit status for a client.
        
        Args:
            client_id: Identifier for the client
            
        Returns:
            Dict containing rate limit status information
        """
        current_time = time.time()
        
        with self._lock:
            self._cleanup_old_requests(client_id, current_time)
            
            if client_id not in self._requests:
                self._requests[client_id] = []
            
            client_requests = self._requests[client_id]
            remaining = max(0, self.config.max_requests - len(client_requests))
            
            # Calculate reset time (when oldest request expires)
            reset_time = None
            if client_requests:
                oldest_request = min(client_requests)
                reset_time = oldest_request + self.config.window_seconds
            
            return {
                'limit': self.config.max_requests,
                'remaining': remaining,
                'used': len(client_requests),
                'window_seconds': self.config.window_seconds,
                'reset_time': reset_time,
                'current_time': current_time
            }
    
    def reset_client(self, client_id: str = "default") -> None:
        """Reset rate limit for a specific client.
        
        Args:
            client_id: Identifier for the client
        """
        with self._lock:
            if client_id in self._requests:
                del self._requests[client_id]
                logger.info("Rate limit reset for client %s", client_id)


# Global rate limiter instance
_default_rate_limiter: Optional[SlidingWindowRateLimiter] = None


def get_default_rate_limiter() -> SlidingWindowRateLimiter:
    """Get the default global rate limiter instance.
    
    Returns:
        SlidingWindowRateLimiter: The default rate limiter
    """
    global _default_rate_limiter
    if _default_rate_limiter is None:
        # Default configuration: 60 requests per minute, 10 burst
        config = RateLimitConfig(max_requests=60, window_seconds=60, burst_limit=10)
        _default_rate_limiter = SlidingWindowRateLimiter(config)
    return _default_rate_limiter


def configure_default_rate_limiter(config: RateLimitConfig) -> None:
    """Configure the default global rate limiter.
    
    Args:
        config: Rate limiting configuration
    """
    global _default_rate_limiter
    _default_rate_limiter = SlidingWindowRateLimiter(config)
    logger.info(
        "Configured default rate limiter: %d requests per %d seconds, burst limit %d",
        config.max_requests, config.window_seconds, config.burst_limit
    )