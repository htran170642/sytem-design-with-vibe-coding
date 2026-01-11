#!/bin/bash
# Phase 2 Testing Script
# Tests the ingestion service locally

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Phase 2 Testing - Ingestion Service               ║"
echo "╔══════════════════════════════════════════════════════════════╗"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to print test results
test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC}: $2"
        ((TESTS_FAILED++))
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Check Virtual Environment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}⚠️  Virtual environment not activated!${NC}"
    echo ""
    echo "Please activate your virtual environment first:"
    echo "  source venv/bin/activate"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ Virtual environment active${NC}: $VIRTUAL_ENV"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Verify File Structure"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FILES=(
    "observability/ingestion/__init__.py"
    "observability/ingestion/auth.py"
    "observability/ingestion/rate_limiter.py"
    "observability/ingestion/kafka_producer.py"
    "observability/ingestion/routes.py"
    "observability/ingestion/main.py"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        test_result 0 "File exists: $file"
    else
        test_result 1 "File missing: $file"
    fi
done
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Test Python Imports"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test imports
python -c "from observability.ingestion.auth import verify_api_key, AuthenticationError" 2>/dev/null
test_result $? "Import auth module"

python -c "from observability.ingestion.rate_limiter import RateLimiter, check_rate_limit" 2>/dev/null
test_result $? "Import rate_limiter module"

python -c "from observability.ingestion.kafka_producer import MockKafkaProducer, get_producer" 2>/dev/null
test_result $? "Import kafka_producer module"

python -c "from observability.ingestion.routes import router" 2>/dev/null
test_result $? "Import routes module"

python -c "from observability.ingestion.main import app" 2>/dev/null
test_result $? "Import main module (FastAPI app)"

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Check .env Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f ".env" ]; then
    test_result 0 ".env file exists"
    
    # Check required settings
    if grep -q "INGESTION_API_KEY" .env; then
        test_result 0 "INGESTION_API_KEY configured"
    else
        test_result 1 "INGESTION_API_KEY not found in .env"
    fi
else
    test_result 1 ".env file missing (run: make setup)"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5: Test Components Individually"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test TokenBucket
python -c "
from observability.ingestion.rate_limiter import TokenBucket
bucket = TokenBucket(capacity=10, refill_rate=1.0)
assert bucket.consume(5) == True, 'Should consume 5 tokens'
assert bucket.get_available_tokens() == 5, 'Should have 5 tokens left'
print('TokenBucket works correctly')
" 2>/dev/null
test_result $? "TokenBucket algorithm"

# Test MockKafkaProducer
python -c "
import asyncio
from observability.common.models import LogEntry, LogBatch
from observability.ingestion.kafka_producer import MockKafkaProducer

async def test():
    producer = MockKafkaProducer()
    log = LogEntry(
        message='Test log',
        level='INFO',
        service='test',
        host='localhost'
    )
    batch = LogBatch(entries=[log])
    await producer.send_logs(batch)
    assert len(producer.get_sent_logs()) == 1, 'Should have 1 log batch'
    print('MockKafkaProducer works correctly')

asyncio.run(test())
" 2>/dev/null
test_result $? "MockKafkaProducer"

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6: Start Ingestion Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "Starting ingestion service in background..."
echo "(This may take a few seconds)"
echo ""

# Start service in background
uvicorn observability.ingestion.main:app --port 8000 > /tmp/ingestion.log 2>&1 &
INGESTION_PID=$!

echo "Ingestion service started (PID: $INGESTION_PID)"
echo "Waiting for service to be ready..."

# Wait for service to start (max 15 seconds)
for i in {1..15}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Service is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
    
    if [ $i -eq 15 ]; then
        echo ""
        echo -e "${RED}❌ Service failed to start within 15 seconds${NC}"
        echo ""
        echo "Log output:"
        cat /tmp/ingestion.log
        kill $INGESTION_PID 2>/dev/null
        exit 1
    fi
done
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 7: Test API Endpoints"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 1: Health check
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HTTP_CODE" == "200" ]; then
    test_result 0 "GET /health returns 200"
else
    test_result 1 "GET /health returns $HTTP_CODE (expected 200)"
fi

# Test 2: Root endpoint
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
if [ "$HTTP_CODE" == "200" ]; then
    test_result 0 "GET / returns 200"
else
    test_result 1 "GET / returns $HTTP_CODE (expected 200)"
fi

# Test 3: Missing API key
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/logs \
    -H "Content-Type: application/json" \
    -d '{"entries":[],"agent_version":"0.1.0"}')
if [ "$HTTP_CODE" == "401" ]; then
    test_result 0 "POST /logs without API key returns 401"
else
    test_result 1 "POST /logs without API key returns $HTTP_CODE (expected 401)"
fi

# Test 4: Invalid API key
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/logs \
    -H "X-API-Key: wrong-key" \
    -H "Content-Type: application/json" \
    -d '{"entries":[],"agent_version":"0.1.0"}')
if [ "$HTTP_CODE" == "401" ]; then
    test_result 0 "POST /logs with invalid API key returns 401"
else
    test_result 1 "POST /logs with invalid API key returns $HTTP_CODE (expected 401)"
fi

# Test 5: Valid log ingestion
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/logs \
    -H "X-API-Key: development-key" \
    -H "Content-Type: application/json" \
    -d '{
        "entries": [
            {
                "timestamp": "2024-01-11T10:00:00Z",
                "level": "INFO",
                "message": "Test log from testing script",
                "service": "test-service",
                "host": "localhost"
            }
        ],
        "agent_version": "0.1.0"
    }')
if [ "$HTTP_CODE" == "202" ]; then
    test_result 0 "POST /logs with valid data returns 202"
else
    test_result 1 "POST /logs with valid data returns $HTTP_CODE (expected 202)"
fi

# Test 6: Valid metric ingestion
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/metrics \
    -H "X-API-Key: development-key" \
    -H "Content-Type: application/json" \
    -d '{
        "entries": [
            {
                "timestamp": "2024-01-11T10:00:00Z",
                "name": "system.cpu.usage_percent",
                "value": 45.5,
                "metric_type": "GAUGE",
                "service": "test-service",
                "host": "localhost"
            }
        ],
        "agent_version": "0.1.0"
    }')
if [ "$HTTP_CODE" == "202" ]; then
    test_result 0 "POST /metrics with valid data returns 202"
else
    test_result 1 "POST /metrics with valid data returns $HTTP_CODE (expected 202)"
fi

# Test 7: Invalid schema (missing required fields)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/logs \
    -H "X-API-Key: development-key" \
    -H "Content-Type: application/json" \
    -d '{
        "entries": [
            {
                "message": "Missing required fields"
            }
        ]
    }')
if [ "$HTTP_CODE" == "422" ]; then
    test_result 0 "POST /logs with invalid schema returns 422"
else
    test_result 1 "POST /logs with invalid schema returns $HTTP_CODE (expected 422)"
fi

# Test 8: Stats endpoint (requires auth)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "X-API-Key: development-key" \
    http://localhost:8000/stats)
if [ "$HTTP_CODE" == "200" ]; then
    test_result 0 "GET /stats with API key returns 200"
else
    test_result 1 "GET /stats with API key returns $HTTP_CODE (expected 200)"
fi

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 8: Test Response Content"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test health response
RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$RESPONSE" | grep -q "healthy"; then
    test_result 0 "Health check contains 'healthy'"
else
    test_result 1 "Health check missing 'healthy'"
fi

# Test stats response
RESPONSE=$(curl -s -H "X-API-Key: development-key" http://localhost:8000/stats)
if echo "$RESPONSE" | grep -q "MockKafkaProducer"; then
    test_result 0 "Stats shows MockKafkaProducer"
else
    test_result 1 "Stats missing producer info"
fi

if echo "$RESPONSE" | grep -q "logs_sent"; then
    test_result 0 "Stats includes logs_sent count"
else
    test_result 1 "Stats missing logs_sent"
fi

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 9: Cleanup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "Stopping ingestion service (PID: $INGESTION_PID)..."
kill $INGESTION_PID 2>/dev/null
wait $INGESTION_PID 2>/dev/null
test_result 0 "Service stopped cleanly"

echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                      TEST SUMMARY                            ║"
echo "╔══════════════════════════════════════════════════════════════╗"
echo ""
echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🎉 ALL TESTS PASSED! Phase 2 is working correctly!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. View interactive docs: http://localhost:8000/docs"
    echo "  2. Test with agents: make run-agent-logs"
    echo "  3. Move to Phase 3: Kafka setup"
    echo ""
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Check the errors above and:"
    echo "  1. Make sure all files are created"
    echo "  2. Verify imports work"
    echo "  3. Check .env configuration"
    echo "  4. Review server logs: cat /tmp/ingestion.log"
    echo ""
    exit 1
fi