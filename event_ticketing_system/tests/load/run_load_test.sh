#!/bin/bash

echo "=========================================="
echo "Event Ticketing System - Load Test"
echo "=========================================="
echo ""

# Configuration
HOST="http://localhost:8000"
USERS=100
SPAWN_RATE=10
DURATION=300  # 5 minutes

# Check if server is running
echo "🔍 Checking server status..."
if ! curl -s "$HOST/health" > /dev/null; then
    echo "❌ Server not running at $HOST"
    echo "Start server with: python -m app.main"
    exit 1
fi

echo "✅ Server is running"
echo ""

# Clear Redis (optional)
read -p "Clear Redis data before test? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 Clearing Redis..."
    redis-cli FLUSHDB
    echo "✅ Redis cleared"
fi

echo ""
echo "📊 Test Configuration:"
echo "  Host: $HOST"
echo "  Users: $USERS"
echo "  Spawn Rate: $SPAWN_RATE users/sec"
echo "  Duration: $DURATION seconds"
echo ""

read -p "Start load test? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Test cancelled"
    exit 0
fi

echo ""
echo "🚀 Starting load test..."
echo ""

# Run locust
locust -f locustfile.py \
    --host="$HOST" \
    --users=$USERS \
    --spawn-rate=$SPAWN_RATE \
    --run-time="${DURATION}s" \
    --headless \
    --csv=results/load_test \
    --html=results/load_test.html

echo ""
echo "✅ Load test completed!"
echo ""
echo "📈 Results saved to:"
echo "  - results/load_test_stats.csv"
echo "  - results/load_test_stats_history.csv"
echo "  - results/load_test.html"
echo ""