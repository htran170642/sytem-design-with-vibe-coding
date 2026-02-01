.PHONY: help

help:
	@echo "Observability Platform - Phase 5"
	@echo ""
	@echo "Infrastructure Commands:"
	@echo "  make infra-up          - Start all infrastructure (Kafka + OpenSearch)"
	@echo "  make infra-down        - Stop all infrastructure"
	@echo "  make infra-logs        - View infrastructure logs"
	@echo ""
	@echo "Kafka Commands:"
	@echo "  make kafka-up          - Start Kafka only"
	@echo "  make kafka-down        - Stop Kafka"
	@echo "  make kafka-init        - Initialize Kafka topics"
	@echo "  make kafka-topics      - List all topics"
	@echo "  make kafka-consume-logs    - Consume logs from Kafka"
	@echo "  make kafka-consume-metrics - Consume metrics from Kafka"
	@echo ""
	@echo "OpenSearch Commands:"
	@echo "  make opensearch-up     - Start OpenSearch only"
	@echo "  make opensearch-down   - Stop OpenSearch"
	@echo "  make opensearch-health - Check OpenSearch health"
	@echo "  make opensearch-indices - List all indices"
	@echo "  make opensearch-create-template - Create log index template"
	@echo "  make opensearch-logs   - View OpenSearch logs"
	@echo ""
	@echo "Application Commands:"
	@echo "  make run-ingestion     - Run ingestion service"
	@echo "  make run-processor-logs    - Run log processor"
	@echo "  make run-processor-metrics - Run metrics processor"
	@echo ""
	@echo "Test Commands:"
	@echo "  make test-phase5       - Test Phase 5 (log storage)"
	@echo "  make send-test-logs    - Send test logs"
	@echo ""

#############################################################################
# Infrastructure
#############################################################################

infra-up:
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@make kafka-init
	@make opensearch-create-template
	@echo ""
	@echo "✅ Infrastructure ready!"
	@echo "   - Kafka: http://localhost:19092"
	@echo "   - OpenSearch: http://localhost:9200"
	@echo "   - OpenSearch Dashboards: http://localhost:5601"

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f

#############################################################################
# Kafka
#############################################################################

kafka-up:
	docker compose up -d redpanda
	@echo "Waiting for Kafka to be ready..."
	@sleep 5

kafka-down:
	docker compose stop redpanda

kafka-init:
	@echo "Creating Kafka topics..."
	docker exec observability-redpanda \
		rpk topic create logs.raw \
			--partitions 3 \
			--replicas 1 \
			--topic-config retention.ms=604800000 \
			--topic-config compression.type=gzip \
			2>/dev/null || echo "Topic logs.raw already exists"
	docker exec observability-redpanda \
		rpk topic create metrics.raw \
			--partitions 3 \
			--replicas 1 \
			--topic-config retention.ms=604800000 \
			--topic-config compression.type=gzip \
			2>/dev/null || echo "Topic metrics.raw already exists"
	@echo "✅ Kafka topics created"

kafka-topics:
	docker exec observability-redpanda \
		rpk topic list

kafka-consume-logs:
	docker exec observability-redpanda \
		rpk topic consume logs.raw \
			--format '%p %k: %v\n'

kafka-consume-metrics:
	docker exec observability-redpanda \
		rpk topic consume metrics.raw \
			--format '%p %k: %v\n'

#############################################################################
# OpenSearch
#############################################################################

opensearch-up:
	docker compose up -d opensearch opensearch-dashboards
	@echo "Waiting for OpenSearch to be ready..."
	@sleep 15

opensearch-down:
	docker compose stop opensearch opensearch-dashboards

opensearch-health:
	@curl -s http://localhost:9200/_cluster/health?pretty

opensearch-indices:
	@curl -s http://localhost:9200/_cat/indices?v

opensearch-create-template:
	@echo "Creating log index template..."
	@curl -X PUT "http://localhost:9200/_index_template/logs-template" \
		-H 'Content-Type: application/json' \
		-d @scripts/opensearch/log_index_template.json \
		2>/dev/null || echo "Template creation pending..."
	@echo ""
	@echo "✅ Index template created"

opensearch-logs:
	docker compose logs -f opensearch

opensearch-search-all:
	@curl -s "http://localhost:9200/logs-*/_search?pretty&size=10"

opensearch-count:
	@curl -s "http://localhost:9200/logs-*/_count?pretty"

#############################################################################
# Application
#############################################################################

run-ingestion:
	@echo "Starting ingestion service..."
	python -m observability.ingestion.main

run-processor-logs:
	@echo "Starting log processor..."
	python -m observability.processing.log_processor

run-processor-metrics:
	@echo "Starting metrics processor..."
	python -m observability.processing.metrics_processor

#############################################################################
# Testing
#############################################################################

test-phase5:
	@echo "Running Phase 5 tests..."
	@./scripts/test_phase5.sh

send-test-logs:
	@echo "Sending test logs..."
	@for i in 1 2 3 4 5; do \
		echo "INFO: Test log $$i" | python -m observability.agents.log_agent --service test-app --batch-size 1; \
		sleep 1; \
	done
	@echo "✅ Sent 5 test logs"

#############################################################################
# Cleanup
#############################################################################

clean:
	docker compose down -v
	@echo "✅ All data cleared"