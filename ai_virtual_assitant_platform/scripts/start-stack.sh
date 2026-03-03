#!/bin/bash
# Quick Start Script for AIVA Full Stack
# Starts all Docker services and verifies they're running

set -e

echo "🚀 Starting AIVA Full Stack..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Start all services
echo "📦 Starting Docker services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check each service
echo ""
echo "🔍 Checking service health..."

# Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis: Running${NC}"
else
    echo -e "${YELLOW}⚠️  Redis: Not ready${NC}"
fi

# Flower
if curl -s http://localhost:5555 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Flower: Running on http://localhost:5555${NC}"
else
    echo -e "${YELLOW}⚠️  Flower: Not ready (starting...)${NC}"
fi

# PostgreSQL
if docker-compose exec -T postgres pg_isready -U aiva > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL: Running${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL: Not ready${NC}"
fi

# Qdrant
if curl -s http://localhost:6333/collections > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Qdrant: Running on http://localhost:6333${NC}"
else
    echo -e "${YELLOW}⚠️  Qdrant: Not ready (starting...)${NC}"
fi

echo ""
echo "📊 Service URLs:"
echo "   - Flower (Task Monitor): http://localhost:5555"
echo "   - Qdrant Dashboard:      http://localhost:6333/dashboard"
echo "   - PostgreSQL:            localhost:5432"
echo "   - Redis:                 localhost:6379"
echo ""
echo "💡 Next steps:"
echo "   1. Update your .env file (see DOCKER_COMPOSE_GUIDE.md)"
echo "   2. Start FastAPI:  make run"
echo "   3. Start Celery:   celery -A app.core.celery_app worker --loglevel=info"
echo ""
echo "🎉 Full stack is ready!"