"""
Anti-bot protection middleware
Prevents automated seat probing and scraping
"""
from fastapi import Request, HTTPException
from typing import Optional
import time
import logging

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


class AntiBotProtection:
    """
    Protects against:
    - Rapid seat checking (probing)
    - Automated booking bots
    - Seat hoarding
    """
    
    def __init__(self):
        self.redis = redis_client
    
    async def check_seat_probing(self, ip: str, user_id: Optional[int] = None) -> bool:
        """
        Detect rapid seat map requests (seat probing)
        
        Rules:
        - Max 10 seat map requests per minute
        - Max 60 seat map requests per hour
        
        Returns:
            True if allowed, raises HTTPException if blocked
        """
        identifier = f"user:{user_id}" if user_id else f"ip:{ip}"
        
        # Check minute rate
        minute_key = f"antibot:seat_check:minute:{identifier}"
        minute_count = await self.redis.redis.incr(minute_key)
        
        if minute_count == 1:
            await self.redis.redis.expire(minute_key, 60)
        
        if minute_count > 10:
            logger.warning(f"🤖 Seat probing detected: {identifier} ({minute_count} requests/minute)")
            raise HTTPException(
                status_code=429,
                detail="Too many seat checks. Please slow down."
            )
        
        # Check hour rate
        hour_key = f"antibot:seat_check:hour:{identifier}"
        hour_count = await self.redis.redis.incr(hour_key)
        
        if hour_count == 1:
            await self.redis.redis.expire(hour_key, 3600)
        
        if hour_count > 60:
            logger.warning(f"🤖 Excessive seat probing: {identifier} ({hour_count} requests/hour)")
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )
        
        return True
    
    async def check_booking_pattern(self, user_id: int) -> bool:
        """
        Detect suspicious booking patterns
        
        Rules:
        - Max 3 active holds at once
        - Max 10 booking attempts per hour
        
        Returns:
            True if allowed, raises HTTPException if blocked
        """
        # Check booking attempts
        attempts_key = f"antibot:booking_attempts:hour:{user_id}"
        attempts = await self.redis.redis.incr(attempts_key)
        
        if attempts == 1:
            await self.redis.redis.expire(attempts_key, 3600)
        
        if attempts > 10:
            logger.warning(f"🤖 Excessive booking attempts: user {user_id} ({attempts}/hour)")
            raise HTTPException(
                status_code=429,
                detail="Too many booking attempts. Please try again later."
            )
        
        return True
    
    async def verify_user_agent(self, request: Request) -> bool:
        """
        Check for suspicious user agents
        Blocks known bot signatures
        """
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Block common bot patterns
        bot_patterns = [
            "bot", "crawler", "spider", "scraper",
            "curl", "wget", "python-requests",
            "axios", "fetch"
        ]
        
        for pattern in bot_patterns:
            if pattern in user_agent and "headless" not in user_agent:
                # Allow headless browsers (for testing)
                if not any(x in user_agent for x in ["chrome", "firefox", "safari"]):
                    logger.warning(f"🤖 Suspicious user agent blocked: {user_agent}")
                    raise HTTPException(
                        status_code=403,
                        detail="Automated access not allowed"
                    )
        
        return True


# Global instance
anti_bot = AntiBotProtection()
