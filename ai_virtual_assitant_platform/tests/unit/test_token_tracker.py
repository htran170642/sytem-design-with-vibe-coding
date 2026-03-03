"""
Tests for Token Tracker
"""

import pytest
from datetime import datetime

from app.services.token_tracker import (
    TokenTracker,
    TokenUsage,
    get_token_tracker,
    TOKEN_PRICING,
)


def test_token_tracker_singleton():
    """Test that get_token_tracker returns same instance"""
    
    tracker1 = get_token_tracker()
    tracker2 = get_token_tracker()
    
    assert tracker1 is tracker2
    print("✓ Token tracker is a singleton")


def test_calculate_cost_gpt35():
    """Test cost calculation for GPT-3.5"""
    
    tracker = TokenTracker()
    
    input_cost, output_cost, total_cost = tracker.calculate_cost(
        model="gpt-3.5-turbo",
        prompt_tokens=1000,
        completion_tokens=500
    )
    
    # GPT-3.5: $0.0005 per 1K input, $0.0015 per 1K output
    expected_input = 1000 * 0.0005 / 1000  # $0.0005
    expected_output = 500 * 0.0015 / 1000  # $0.00075
    expected_total = expected_input + expected_output  # $0.00125
    
    assert input_cost == pytest.approx(expected_input)
    assert output_cost == pytest.approx(expected_output)
    assert total_cost == pytest.approx(expected_total)
    
    print(f"✓ GPT-3.5 cost: ${total_cost:.6f} for 1000+500 tokens")


def test_calculate_cost_gpt4():
    """Test cost calculation for GPT-4"""
    
    tracker = TokenTracker()
    
    input_cost, output_cost, total_cost = tracker.calculate_cost(
        model="gpt-4",
        prompt_tokens=1000,
        completion_tokens=500
    )
    
    # GPT-4: $0.03 per 1K input, $0.06 per 1K output
    expected_input = 1000 * 0.03 / 1000  # $0.03
    expected_output = 500 * 0.06 / 1000  # $0.03
    expected_total = expected_input + expected_output  # $0.06
    
    assert total_cost == pytest.approx(expected_total)
    
    print(f"✓ GPT-4 cost: ${total_cost:.6f} for 1000+500 tokens")


def test_calculate_cost_partial_model_name():
    """Test cost calculation with partial model name"""
    
    tracker = TokenTracker()
    
    # Model name includes version/variant
    input_cost, output_cost, total_cost = tracker.calculate_cost(
        model="gpt-3.5-turbo-0125",  # Variant
        prompt_tokens=1000,
        completion_tokens=500
    )
    
    # Should match "gpt-3.5-turbo" pricing
    expected_total = (1000 * 0.0005 / 1000) + (500 * 0.0015 / 1000)
    
    assert total_cost == pytest.approx(expected_total)
    
    print("✓ Partial model name matching works")


def test_track_request():
    """Test tracking a single request"""
    
    tracker = TokenTracker()
    
    usage = tracker.track_request(
        model="gpt-3.5-turbo",
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=1234.5
    )
    
    assert usage.model == "gpt-3.5-turbo"
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 150
    assert usage.latency_ms == 1234.5
    assert isinstance(usage.timestamp, datetime)
    
    # Check costs are calculated
    assert usage.input_cost > 0
    assert usage.output_cost > 0
    assert usage.total_cost > 0
    
    print(f"✓ Request tracked: {usage.total_tokens} tokens, ${usage.total_cost:.6f}")


def test_cumulative_stats():
    """Test cumulative statistics"""
    
    tracker = TokenTracker()
    
    # Track multiple requests
    tracker.track_request("gpt-3.5-turbo", 100, 50, 1000)
    tracker.track_request("gpt-3.5-turbo", 200, 100, 1500)
    tracker.track_request("gpt-4", 100, 50, 2000)
    
    stats = tracker.get_stats()
    
    # Check overall stats
    assert stats["overall"]["total_requests"] == 3
    assert stats["overall"]["total_tokens"] == 600  # 150 + 300 + 150
    assert stats["overall"]["total_cost_usd"] > 0
    
    # Check per-model stats
    assert "gpt-3.5-turbo" in stats["by_model"]
    assert "gpt-4" in stats["by_model"]
    
    gpt35_stats = stats["by_model"]["gpt-3.5-turbo"]
    assert gpt35_stats["requests"] == 2
    assert gpt35_stats["total_tokens"] == 450  # 150 + 300
    
    gpt4_stats = stats["by_model"]["gpt-4"]
    assert gpt4_stats["requests"] == 1
    assert gpt4_stats["total_tokens"] == 150
    
    print("✓ Cumulative stats calculated correctly")


def test_average_calculations():
    """Test average calculations in stats"""
    
    tracker = TokenTracker()
    
    # Track requests with known values
    tracker.track_request("gpt-3.5-turbo", 100, 100, 1000)  # 200 tokens
    tracker.track_request("gpt-3.5-turbo", 200, 200, 2000)  # 400 tokens
    
    stats = tracker.get_stats()
    
    gpt35_stats = stats["by_model"]["gpt-3.5-turbo"]
    
    # Average tokens: (200 + 400) / 2 = 300
    assert gpt35_stats["avg_tokens_per_request"] == 300
    
    # Average latency: (1000 + 2000) / 2 = 1500
    assert gpt35_stats["avg_latency_ms"] == 1500
    
    print("✓ Average calculations correct")


def test_reset_stats():
    """Test resetting statistics"""
    
    tracker = TokenTracker()
    
    # Track some requests
    tracker.track_request("gpt-3.5-turbo", 100, 50, 1000)
    tracker.track_request("gpt-4", 100, 50, 1000)
    
    # Verify stats exist
    stats = tracker.get_stats()
    assert stats["overall"]["total_requests"] == 2
    
    # Reset
    tracker.reset_stats()
    
    # Verify stats are cleared
    stats = tracker.get_stats()
    assert stats["overall"]["total_requests"] == 0
    assert stats["overall"]["total_tokens"] == 0
    assert stats["overall"]["total_cost_usd"] == 0
    assert len(stats["by_model"]) == 0
    
    print("✓ Stats reset successfully")


def test_token_usage_to_dict():
    """Test converting TokenUsage to dict"""
    
    usage = TokenUsage(
        model="gpt-3.5-turbo",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        input_cost=0.0001,
        output_cost=0.00015,
        total_cost=0.00025,
        latency_ms=1234.5,
        timestamp=datetime(2024, 1, 1, 12, 0, 0)
    )
    
    data = usage.to_dict()
    
    assert data["model"] == "gpt-3.5-turbo"
    assert data["total_tokens"] == 150
    assert data["total_cost"] == 0.00025
    assert data["timestamp"] == "2024-01-01T12:00:00"
    
    print("✓ TokenUsage converts to dict correctly")


def test_unknown_model_fallback():
    """Test fallback for unknown model"""
    
    tracker = TokenTracker()
    
    # Unknown model should use gpt-3.5-turbo pricing
    input_cost, output_cost, total_cost = tracker.calculate_cost(
        model="unknown-model-xyz",
        prompt_tokens=1000,
        completion_tokens=500
    )
    
    # Should match gpt-3.5-turbo pricing
    expected_total = (1000 * 0.0005 / 1000) + (500 * 0.0015 / 1000)
    
    assert total_cost == pytest.approx(expected_total)
    
    print("✓ Unknown model uses fallback pricing")


def test_zero_tokens():
    """Test handling zero tokens"""
    
    tracker = TokenTracker()
    
    usage = tracker.track_request(
        model="gpt-3.5-turbo",
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=100
    )
    
    assert usage.total_tokens == 0
    assert usage.total_cost == 0.0
    
    print("✓ Zero tokens handled correctly")