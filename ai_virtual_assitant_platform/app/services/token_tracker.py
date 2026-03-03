"""
Token Tracking Service
Tracks token usage, costs, and latency metrics
Phase 3, Step 7: Track token usage and latency
"""

import time
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from app.core.logging_config import get_logger

logger = get_logger(__name__)


# Token pricing (as of Jan 2025)
# https://openai.com/pricing
TOKEN_PRICING = {
    "gpt-3.5-turbo": {
        "input": 0.0005 / 1000,   # $0.50 per 1M input tokens
        "output": 0.0015 / 1000,  # $1.50 per 1M output tokens
    },
    "gpt-4": {
        "input": 0.03 / 1000,     # $30 per 1M input tokens
        "output": 0.06 / 1000,    # $60 per 1M output tokens
    },
    "gpt-4-turbo": {
        "input": 0.01 / 1000,     # $10 per 1M input tokens
        "output": 0.03 / 1000,    # $30 per 1M output tokens
    },
}


@dataclass
class TokenUsage:
    """
    Token usage and cost tracking
    
    Attributes:
        model: Model name
        prompt_tokens: Tokens in prompt
        completion_tokens: Tokens in completion
        total_tokens: Total tokens used
        input_cost: Cost of input tokens
        output_cost: Cost of output tokens
        total_cost: Total cost
        latency_ms: Response time in milliseconds
        timestamp: When the request was made
    """
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    latency_ms: float
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class TokenTracker:
    """
    Tracks token usage and costs across requests
    
    Features:
    - Per-request tracking
    - Cumulative statistics
    - Cost calculation
    - Latency monitoring
    """
    
    def __init__(self):
        """Initialize tracker with empty stats"""
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency_ms = 0.0
        
        # Per-model stats
        self.model_stats: Dict[str, Dict] = {}
        
        logger.info("Token tracker initialized")
    
    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> tuple[float, float, float]:
        """
        Calculate cost for token usage
        
        Args:
            model: Model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Tuple of (input_cost, output_cost, total_cost)
        """
        # Get pricing for model
        pricing = TOKEN_PRICING.get(model)
        
        if not pricing:
            # Try to match partial model name (e.g., "gpt-3.5-turbo-0125")
            for key in TOKEN_PRICING:
                if model.startswith(key):
                    pricing = TOKEN_PRICING[key]
                    break
        
        if not pricing:
            logger.warning(
                f"Unknown model pricing: {model}, using gpt-3.5-turbo as fallback",
                extra={"model": model},
            )
            pricing = TOKEN_PRICING["gpt-3.5-turbo"]
        
        # Calculate costs
        input_cost = prompt_tokens * pricing["input"]
        output_cost = completion_tokens * pricing["output"]
        total_cost = input_cost + output_cost
        
        return input_cost, output_cost, total_cost
    
    def track_request(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> TokenUsage:
        """
        Track a single request
        
        Args:
            model: Model name
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            latency_ms: Response time in milliseconds
            
        Returns:
            TokenUsage object with all metrics
        """
        # Calculate costs
        input_cost, output_cost, total_cost = self.calculate_cost(
            model, prompt_tokens, completion_tokens
        )
        
        # Create usage record
        usage = TokenUsage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            latency_ms=latency_ms,
            timestamp=datetime.utcnow(),
        )
        
        # Update global stats
        self.total_requests += 1
        self.total_tokens += usage.total_tokens
        self.total_cost += usage.total_cost
        self.total_latency_ms += usage.latency_ms
        
        # Update per-model stats
        if model not in self.model_stats:
            self.model_stats[model] = {
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
                "latency_ms": 0.0,
            }
        
        self.model_stats[model]["requests"] += 1
        self.model_stats[model]["tokens"] += usage.total_tokens
        self.model_stats[model]["cost"] += usage.total_cost
        self.model_stats[model]["latency_ms"] += usage.latency_ms
        
        # Log usage
        logger.info(
            "Request tracked",
            extra={
                "model": model,
                "tokens": usage.total_tokens,
                "cost_usd": round(usage.total_cost, 6),
                "latency_ms": round(latency_ms, 2),
            },
        )
        
        return usage
    
    def get_stats(self) -> Dict:
        """
        Get cumulative statistics
        
        Returns:
            Dict with overall and per-model stats
        """
        avg_latency = (
            self.total_latency_ms / self.total_requests
            if self.total_requests > 0
            else 0
        )
        
        # Per-model averages
        model_stats = {}
        for model, stats in self.model_stats.items():
            model_stats[model] = {
                "requests": stats["requests"],
                "total_tokens": stats["tokens"],
                "total_cost_usd": round(stats["cost"], 6),
                "avg_tokens_per_request": (
                    stats["tokens"] / stats["requests"]
                    if stats["requests"] > 0
                    else 0
                ),
                "avg_cost_per_request": (
                    stats["cost"] / stats["requests"]
                    if stats["requests"] > 0
                    else 0
                ),
                "avg_latency_ms": (
                    stats["latency_ms"] / stats["requests"]
                    if stats["requests"] > 0
                    else 0
                ),
            }
        
        return {
            "overall": {
                "total_requests": self.total_requests,
                "total_tokens": self.total_tokens,
                "total_cost_usd": round(self.total_cost, 6),
                "avg_latency_ms": round(avg_latency, 2),
            },
            "by_model": model_stats,
        }
    
    def reset_stats(self):
        """Reset all statistics"""
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency_ms = 0.0
        self.model_stats = {}
        
        logger.info("Token tracker stats reset")


# Global tracker instance
_token_tracker: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    """
    Get or create token tracker instance (singleton)
    
    Returns:
        TokenTracker instance
    """
    global _token_tracker
    
    if _token_tracker is None:
        _token_tracker = TokenTracker()
    
    return _token_tracker