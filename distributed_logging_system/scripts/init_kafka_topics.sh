#!/bin/bash
# Initialize Kafka topics for observability platform

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Kafka Topic Initialization                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
KAFKA_BROKER="localhost:19092"
PARTITIONS=3
REPLICATION_FACTOR=1
RETENTION_MS=$((7 * 24 * 60 * 60 * 1000))  # 7 days in milliseconds

# Topics to create
TOPICS=(
    "logs.raw"
    "metrics.raw"
    "events.raw"
    "logs.processed"
    "metrics.processed"
)

echo "Configuration:"
echo "  Kafka Broker: $KAFKA_BROKER"
echo "  Partitions: $PARTITIONS"
echo "  Replication Factor: $REPLICATION_FACTOR"
echo "  Retention: 7 days"
echo ""

# Wait for Kafka to be ready
echo -e "${YELLOW}Waiting for Kafka to be ready...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec observability-redpanda rpk cluster info > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Kafka is ready!${NC}"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
    
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo ""
        echo -e "${RED}❌ Kafka failed to start after ${MAX_RETRIES} retries${NC}"
        echo ""
        echo "Troubleshooting:"
        echo "  1. Check if Redpanda is running: docker ps | grep redpanda"
        echo "  2. Check logs: docker logs observability-redpanda"
        echo "  3. Restart: docker compose restart redpanda"
        exit 1
    fi
done
echo ""

# Create topics
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Creating Topics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for topic in "${TOPICS[@]}"; do
    echo -n "Creating topic: $topic ... "
    
    # Check if topic already exists
    if docker exec observability-redpanda rpk topic list | grep -q "^$topic "; then
        echo -e "${YELLOW}Already exists${NC}"
        continue
    fi
    
    # Create topic
    if docker exec observability-redpanda rpk topic create "$topic" \
        --partitions "$PARTITIONS" \
        --replicas "$REPLICATION_FACTOR" \
        --config retention.ms="$RETENTION_MS" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Created${NC}"
    else
        echo -e "${RED}❌ Failed${NC}"
    fi
done

echo ""

# List all topics
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Current Topics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker exec observability-redpanda rpk topic list
echo ""

# Show topic details
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Topic Details"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for topic in "${TOPICS[@]}"; do
    echo ""
    echo "Topic: $topic"
    docker exec observability-redpanda rpk topic describe "$topic" 2>/dev/null || echo "  Not found"
done
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Topic Initialization Complete!                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. View topics in console: http://localhost:8080"
echo "  2. Start ingestion service: make run-ingestion"
echo "  3. Send test data: ./scripts/quick_test.sh"
echo ""