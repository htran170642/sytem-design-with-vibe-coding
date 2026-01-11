#!/bin/bash
# Quick Phase 2 Test - Tests ingestion service (assumes it's already running)

echo "Quick Phase 2 Test"
echo "=================="
echo ""
echo "Prerequisites: Ingestion service should be running on port 8000"
echo "If not running, start it with: make run-ingestion"
echo ""

# Check if service is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ ERROR: Ingestion service is not running on port 8000"
    echo ""
    echo "Start it with:"
    echo "  make run-ingestion"
    echo "Or:"
    echo "  uvicorn observability.ingestion.main:app --reload --port 8000"
    echo ""
    exit 1
fi

echo "✅ Service is running"
echo ""

# Test 1: Health check
echo "Test 1: Health Check"
RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$RESPONSE" | grep -q "healthy"; then
    echo "✅ PASS: Health check OK"
else
    echo "❌ FAIL: Health check failed"
fi
echo ""

# Test 2: Send a log
echo "Test 2: Send Log Batch"
RESPONSE=$(curl -s -X POST http://localhost:8000/logs \
  -H "X-API-Key: development-key" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [{
      "timestamp": "2024-01-11T10:00:00Z",
      "level": "INFO",
      "message": "Quick test log",
      "service": "quick-test",
      "host": "localhost"
    }],
    "agent_version": "0.1.0"
  }')

if echo "$RESPONSE" | grep -q "accepted"; then
    echo "✅ PASS: Log ingestion OK"
    echo "Response: $RESPONSE"
else
    echo "❌ FAIL: Log ingestion failed"
    echo "Response: $RESPONSE"
fi
echo ""

# Test 3: Send a metric
echo "Test 3: Send Metric Batch"
RESPONSE=$(curl -s -X POST http://localhost:8000/metrics \
  -H "X-API-Key: development-key" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [{
      "timestamp": "2024-01-11T10:00:00Z",
      "name": "test.metric",
      "value": 42.0,
      "metric_type": "gauge",
      "service": "quick-test",
      "host": "localhost"
    }],
    "agent_version": "0.1.0"
  }')

if echo "$RESPONSE" | grep -q "accepted"; then
    echo "✅ PASS: Metric ingestion OK"
    echo "Response: $RESPONSE"
else
    echo "❌ FAIL: Metric ingestion failed"
    echo "Response: $RESPONSE"
fi
echo ""

# Test 4: Check stats
echo "Test 4: Check Statistics"
RESPONSE=$(curl -s -H "X-API-Key: development-key" http://localhost:8000/stats)
echo "Stats: $RESPONSE"
echo ""

echo "=================="
echo "Quick test complete!"
echo ""
echo "Check the ingestion service terminal to see the logged messages."
echo ""
echo "To view interactive docs: http://localhost:8000/docs"
echo ""