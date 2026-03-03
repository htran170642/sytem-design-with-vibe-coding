#!/usr/bin/env bash
# =============================================================================
# AIVA Demo Script
# Walks through the full RAG pipeline: upload → process → search → query
# Usage: bash scripts/demo.sh [API_BASE] [API_KEY]
# =============================================================================

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
API_KEY="${2:-${API_KEY:-demo-api-key}}"
SAMPLE_FILE="/tmp/aiva_demo_sample.txt"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

header()  { echo -e "\n${CYAN}══════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════${NC}"; }
ok()      { echo -e "${GREEN}[OK]${NC} $1"; }
info()    { echo -e "${YELLOW}[INFO]${NC} $1"; }
fail()    { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

# --------------------------------------------------------------------------- #
# 0. Preflight
# --------------------------------------------------------------------------- #
header "0. Preflight"

command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v jq   >/dev/null 2>&1 || fail "jq is required (brew install jq / apt install jq)"

info "API base : $API_BASE"
info "API key  : ${API_KEY:0:8}..."

# --------------------------------------------------------------------------- #
# 1. Health check
# --------------------------------------------------------------------------- #
header "1. Health Check"

HEALTH=$(curl -sf "$API_BASE/health") || fail "API is not reachable at $API_BASE"
echo "$HEALTH" | jq .
ok "API is healthy"

# --------------------------------------------------------------------------- #
# 2. Create a sample document
# --------------------------------------------------------------------------- #
header "2. Creating sample document"

cat > "$SAMPLE_FILE" <<'EOF'
# AIVA Tech Company — Q3 2025 Business Report

## Executive Summary

AIVA Tech achieved record performance in Q3 2025, with total revenue reaching
$4.2 million — a 12% year-over-year increase. Operating costs were reduced by
8% through infrastructure optimisation, bringing operating margin to 28%.

## Product Updates

The AI Virtual Assistant Platform (AIVA) launched three major features:
- Retrieval-Augmented Generation (RAG) pipeline with Qdrant vector store
- Background document processing via Celery and Redis
- Prometheus metrics and structured JSON logging for observability

## Headcount

The engineering team grew from 12 to 18 engineers in Q3. Two new senior
ML engineers joined to accelerate the embedding pipeline roadmap.

## Outlook

Q4 2025 target: $5.0 million revenue with expansion into the European market.
Key initiatives: multimodal document support and real-time streaming responses.
EOF

ok "Sample document written to $SAMPLE_FILE"

# --------------------------------------------------------------------------- #
# 3. Upload document
# --------------------------------------------------------------------------- #
header "3. Upload Document"

UPLOAD=$(curl -sf -X POST "$API_BASE/documents/upload" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@$SAMPLE_FILE") || fail "Upload failed"

echo "$UPLOAD" | jq .
DOC_ID=$(echo "$UPLOAD" | jq -r '.id')
TASK_ID=$(echo "$UPLOAD" | jq -r '.message' | grep -oP 'task: \K[a-f0-9]+' || true)

ok "Document uploaded (id=$DOC_ID)"

# --------------------------------------------------------------------------- #
# 4. Wait for background processing
# --------------------------------------------------------------------------- #
header "4. Waiting for Background Processing"

if [ -z "$TASK_ID" ]; then
  info "Could not extract task ID; waiting 5 s..."
  sleep 5
else
  info "Task ID: $TASK_ID"
  for i in $(seq 1 12); do
    TASK=$(curl -sf "$API_BASE/documents/tasks/$TASK_ID" \
      -H "X-API-Key: $API_KEY") || break
    STATE=$(echo "$TASK" | jq -r '.state')
    info "  Attempt $i — state: $STATE"
    if [ "$STATE" = "SUCCESS" ] || [ "$STATE" = "FAILURE" ]; then
      echo "$TASK" | jq .
      break
    fi
    sleep 3
  done
fi

ok "Processing complete"

# --------------------------------------------------------------------------- #
# 5. Semantic search
# --------------------------------------------------------------------------- #
header "5. Semantic Search"

SEARCH=$(curl -sf -X POST "$API_BASE/documents/search" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Q3 revenue and financial results", "limit": 3, "min_score": 0.5}') \
  || fail "Search failed"

echo "$SEARCH" | jq .
RESULTS=$(echo "$SEARCH" | jq '.total_results')
ok "Semantic search returned $RESULTS result(s)"

# --------------------------------------------------------------------------- #
# 6. RAG query
# --------------------------------------------------------------------------- #
header "6. RAG Query — Ask a Question"

RAG=$(curl -sf -X POST "$API_BASE/documents/query" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What was the Q3 revenue and how does it compare to last year?",
    "top_k": 5,
    "min_score": 0.5
  }') || fail "RAG query failed"

echo "$RAG" | jq .
ANSWER=$(echo "$RAG" | jq -r '.answer')
CONFIDENCE=$(echo "$RAG" | jq -r '.confidence')

ok "RAG answer received (confidence=$CONFIDENCE)"
echo -e "\n${GREEN}Answer:${NC} $ANSWER\n"

# --------------------------------------------------------------------------- #
# 7. Cache statistics
# --------------------------------------------------------------------------- #
header "7. Cache Stats"

curl -sf "$API_BASE/health/cache-stats" | jq .
ok "Cache stats retrieved"

# --------------------------------------------------------------------------- #
# 8. Prometheus metrics sample
# --------------------------------------------------------------------------- #
header "8. Prometheus Metrics (sample)"

curl -sf "$API_BASE/metrics" | grep "^aiva_" | head -20
ok "Metrics endpoint reachable"

# --------------------------------------------------------------------------- #
# Done
# --------------------------------------------------------------------------- #
header "Demo Complete"
echo -e "${GREEN}All steps passed successfully.${NC}"
echo ""
echo "Next steps:"
echo "  - Open Swagger UI : $API_BASE/docs"
echo "  - Open Flower UI  : http://localhost:5555"
echo "  - Scrape metrics  : $API_BASE/metrics"
