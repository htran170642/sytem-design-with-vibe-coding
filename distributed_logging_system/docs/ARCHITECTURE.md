# Distributed Observability Platform - Architecture

## Table of Contents
1. [High-Level Architecture](#high-level-architecture)
2. [Data Flow](#data-flow)
3. [Component Details](#component-details)
4. [Deployment Architecture](#deployment-architecture)
5. [Scalability Considerations](#scalability-considerations)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Service A  │  │   Service B  │  │   Service C  │                  │
│  │  (API Server)│  │   (Worker)   │  │  (Database)  │                  │
│  │              │  │              │  │              │                  │
│  │ writes logs  │  │ writes logs  │  │ writes logs  │                  │
│  │ uses CPU/mem │  │ uses CPU/mem │  │ uses CPU/mem │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
└─────────┼──────────────────┼──────────────────┼──────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        COLLECTION LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  Log Agent   │  │  Log Agent   │  │  Log Agent   │                  │
│  │  - Tail logs │  │  - Tail logs │  │  - Tail logs │                  │
│  │  - Batch     │  │  - Batch     │  │  - Batch     │                  │
│  │  - Buffer    │  │  - Buffer    │  │  - Buffer    │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                  │                          │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐                  │
│  │Metrics Agent │  │Metrics Agent │  │Metrics Agent │                  │
│  │  - CPU/Mem   │  │  - CPU/Mem   │  │  - CPU/Mem   │                  │
│  │  - Disk/Net  │  │  - Disk/Net  │  │  - Disk/Net  │                  │
│  │  - Batch     │  │  - Batch     │  │  - Batch     │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
└─────────┼──────────────────┼──────────────────┼──────────────────────────┘
          │ HTTP POST        │ HTTP POST        │ HTTP POST
          │ /logs            │ /logs            │ /logs
          │ /metrics         │ /metrics         │ /metrics
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                                   │
│                                                                           │
│              ┌─────────────────────────────────────┐                     │
│              │   Load Balancer (nginx/HAProxy)    │                     │
│              └──────────────┬──────────────────────┘                     │
│                             │                                            │
│         ┌───────────────────┼───────────────────┐                       │
│         ▼                   ▼                   ▼                       │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │ Ingestion   │     │ Ingestion   │     │ Ingestion   │               │
│  │ Service 1   │     │ Service 2   │     │ Service 3   │               │
│  │ (FastAPI)   │     │ (FastAPI)   │     │ (FastAPI)   │               │
│  │             │     │             │     │             │               │
│  │ - Validate  │     │ - Validate  │     │ - Validate  │               │
│  │ - Auth      │     │ - Auth      │     │ - Auth      │               │
│  │ - Rate Limit│     │ - Rate Limit│     │ - Rate Limit│               │
│  └─────┬───────┘     └─────┬───────┘     └─────┬───────┘               │
│        │                   │                   │                        │
│        └───────────────────┼───────────────────┘                        │
│                            │                                            │
└────────────────────────────┼────────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         MESSAGE BUS LAYER                                │
│                                                                           │
│                    ┌─────────────────────────┐                           │
│                    │    Kafka / Redpanda     │                           │
│                    │                         │                           │
│   ┌────────────────┼─────────────────────────┼────────────────┐         │
│   │                │                         │                │         │
│   ▼                ▼                         ▼                ▼         │
│ Topic:         Topic:                    Topic:          Topic:         │
│ logs.raw       metrics.raw               events.raw      (others)       │
│ ────────       ────────────              ──────────      ────────       │
│ 3 partitions   3 partitions              3 partitions    ...            │
│ Retention: 7d  Retention: 7d             Retention: 7d                  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
          │                  │                     │
          ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      STREAM PROCESSING LAYER                             │
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │     Log      │  │   Metrics    │  │   Events     │                  │
│  │  Processor   │  │  Processor   │  │  Processor   │                  │
│  │              │  │              │  │              │                  │
│  │ - Parse      │  │ - Aggregate  │  │ - Correlate  │                  │
│  │ - Enrich     │  │ - Compute    │  │ - Detect     │                  │
│  │ - Filter     │  │   p50/p95    │  │   Anomalies  │                  │
│  │ - Transform  │  │ - Downsample │  │ - Alert      │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                  │                          │
└─────────┼──────────────────┼──────────────────┼──────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                                    │
│                                                                           │
│  ┌────────────────────────────────────────────────────────┐             │
│  │                    HOT STORAGE                          │             │
│  │             OpenSearch / Elasticsearch                  │             │
│  │                                                          │             │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │             │
│  │  │ logs-2024-01 │  │metrics-2024  │  │ events-2024  │ │             │
│  │  │  (7 days)    │  │  (7 days)    │  │  (7 days)    │ │             │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │             │
│  └────────────────────────────────────────────────────────┘             │
│                                                                           │
│  ┌────────────────────────────────────────────────────────┐             │
│  │                   WARM STORAGE                          │             │
│  │                  S3 / MinIO                             │             │
│  │                                                          │             │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │             │
│  │  │ logs-parquet │  │metrics-parquet│ │ events-json  │ │             │
│  │  │  (30 days)   │  │  (30 days)    │  │  (30 days)   │ │             │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │             │
│  └────────────────────────────────────────────────────────┘             │
│                                                                           │
│  ┌────────────────────────────────────────────────────────┐             │
│  │                   COLD STORAGE                          │             │
│  │              S3 Glacier / Archive                       │             │
│  │              (Long-term retention)                      │             │
│  └────────────────────────────────────────────────────────┘             │
│                                                                           │
│  ┌────────────────────────────────────────────────────────┐             │
│  │                    CACHE LAYER                          │             │
│  │                      Redis                              │             │
│  │  - Recent queries                                       │             │
│  │  - Aggregations                                         │             │
│  │  - Rate limiting                                        │             │
│  └────────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         QUERY LAYER                                      │
│                                                                           │
│              ┌─────────────────────────────────────┐                     │
│              │   Load Balancer (nginx/HAProxy)    │                     │
│              └──────────────┬──────────────────────┘                     │
│                             │                                            │
│         ┌───────────────────┼───────────────────┐                       │
│         ▼                   ▼                   ▼                       │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │   Query     │     │   Query     │     │   Query     │               │
│  │  Service 1  │     │  Service 2  │     │  Service 3  │               │
│  │ (FastAPI)   │     │ (FastAPI)   │     │ (FastAPI)   │               │
│  │             │     │             │     │             │               │
│  │ - Search    │     │ - Search    │     │ - Search    │               │
│  │ - Filter    │     │ - Filter    │     │ - Filter    │               │
│  │ - Aggregate │     │ - Aggregate │     │ - Aggregate │               │
│  │ - Paginate  │     │ - Paginate  │     │ - Paginate  │               │
│  └─────┬───────┘     └─────┬───────┘     └─────┬───────┘               │
│        │                   │                   │                        │
│        └───────────────────┴───────────────────┘                        │
│                            │                                            │
└────────────────────────────┼────────────────────────────────────────────┘
                             │ REST API
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      VISUALIZATION LAYER                                 │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │                        Grafana                            │           │
│  │                                                            │           │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │           │
│  │  │  Dashboard:  │  │  Dashboard:  │  │  Dashboard:  │   │           │
│  │  │  Error Rate  │  │  CPU/Memory  │  │ Log Search   │   │           │
│  │  │              │  │              │  │              │   │           │
│  │  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │   │           │
│  │  │  │ Graph  │  │  │  │ Graph  │  │  │  │ Table  │  │   │           │
│  │  │  └────────┘  │  │  └────────┘  │  │  └────────┘  │   │           │
│  │  │  ┌────────┐  │  │  ┌────────┐  │  │              │   │           │
│  │  │  │ Alert  │  │  │  │ Heatmap│  │  │              │   │           │
│  │  │  └────────┘  │  │  └────────┘  │  │              │   │           │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │           │
│  │                                                            │           │
│  │  Alert Rules:                                             │           │
│  │  - Error rate > 5%                                        │           │
│  │  - CPU usage > 80%                                        │           │
│  │  - Disk usage > 90%                                       │           │
│  └──────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Log Data Flow

```
Application writes log
        │
        ▼
   Log file (append)
        │
        ▼
  Log Agent (tail -f)
        │
        ├─ Parse line
        ├─ Detect log level
        ├─ Add metadata (timestamp, host, service)
        ├─ Buffer in memory
        │
        ▼
  Batch when: size=100 OR time=5s
        │
        ▼
  HTTP POST to Ingestion API
        │
        ├─ Retry 1 → wait 1s
        ├─ Retry 2 → wait 2s
        ├─ Retry 3 → success ✓
        │
        ▼
  Ingestion Service (FastAPI)
        │
        ├─ Validate API key
        ├─ Rate limit check
        ├─ Validate schema (Pydantic)
        │
        ▼
  Write to Kafka topic: logs.raw
        │
        ▼
  Log Processor (consumer)
        │
        ├─ Parse structured fields
        ├─ Extract labels
        ├─ Enrich with metadata
        ├─ Filter spam/debug logs
        │
        ▼
  Write to OpenSearch
        │
        ├─ Index: logs-2024-01-10
        ├─ TTL: 7 days
        │
        ▼
  [After 7 days] Archive to S3
        │
        ├─ Format: Parquet (compressed)
        ├─ Location: s3://bucket/logs/2024/01/
        ├─ TTL: 30 days
        │
        ▼
  [After 30 days] Delete or move to Glacier
```

### 2. Metrics Data Flow

```
Metrics Agent (every 10s)
        │
        ├─ Collect CPU: psutil.cpu_percent()
        ├─ Collect Memory: psutil.virtual_memory()
        ├─ Collect Disk: psutil.disk_usage()
        ├─ Collect Network: psutil.net_io_counters()
        │
        ▼
  Create MetricEntry objects
        │
        ├─ name: "system.cpu.usage_percent"
        ├─ value: 45.2
        ├─ timestamp: "2024-01-10T10:00:00Z"
        ├─ labels: {}
        │
        ▼
  Buffer in memory
        │
        ▼
  Batch when: size=50 OR time=20s
        │
        ▼
  HTTP POST to Ingestion API
        │
        ▼
  Ingestion Service
        │
        ├─ Validate
        ├─ Authenticate
        │
        ▼
  Write to Kafka topic: metrics.raw
        │
        ▼
  Metrics Processor
        │
        ├─ Aggregate by service
        ├─ Compute rolling averages
        ├─ Calculate p50, p95, p99
        ├─ Detect anomalies
        │
        ▼
  Write to OpenSearch
        │
        ├─ Index: metrics-2024-01
        ├─ Pre-aggregated data
        │
        ▼
  Query Service
        │
        ├─ Search metrics
        ├─ Filter by time range
        ├─ Aggregate by labels
        │
        ▼
  Grafana Dashboard
        │
        ├─ Graph: CPU over time
        ├─ Alert: CPU > 80%
```

### 3. Query Flow

```
User opens Grafana Dashboard
        │
        ▼
  Grafana sends query to Query API
        │
        ├─ GET /logs/search?service=api&level=ERROR&time=last-1h
        │
        ▼
  Query Service (FastAPI)
        │
        ├─ Authenticate user
        ├─ Parse query parameters
        ├─ Build OpenSearch query
        │
        ▼
  Check Redis cache
        │
        ├─ Cache hit? → Return cached result
        ├─ Cache miss? → Continue
        │
        ▼
  Query OpenSearch
        │
        ├─ Index: logs-2024-01-10
        ├─ Filter: service=api AND level=ERROR
        ├─ Time range: last 1 hour
        ├─ Sort: timestamp DESC
        ├─ Limit: 100
        │
        ▼
  OpenSearch returns results
        │
        ├─ 1,234 matching logs
        ├─ Paginated (100 per page)
        │
        ▼
  Cache result in Redis (5 min TTL)
        │
        ▼
  Return JSON to Grafana
        │
        ├─ Format for visualization
        │
        ▼
  Grafana renders graph/table
```

---

## Component Details

### Collection Layer

**Log Agent:**
- **Language:** Python (async)
- **Dependencies:** aiofiles, httpx
- **Resource Usage:** ~50MB RAM, <1% CPU
- **Deployment:** One per host (sidecar or systemd service)

**Metrics Agent:**
- **Language:** Python (async)
- **Dependencies:** psutil, httpx
- **Resource Usage:** ~30MB RAM, <1% CPU
- **Collection Interval:** 10 seconds (configurable)
- **Deployment:** One per host

### Ingestion Layer

**Ingestion Service:**
- **Framework:** FastAPI
- **Endpoints:** 
  - POST /logs (accepts log batches)
  - POST /metrics (accepts metric batches)
  - GET /health (health check)
- **Features:**
  - API key authentication
  - Rate limiting (1000 req/min per API key)
  - Schema validation (Pydantic)
  - Async Kafka producer
- **Deployment:** 3+ instances (horizontal scaling)
- **Resource Usage:** ~200MB RAM per instance

### Message Bus Layer

**Kafka / Redpanda:**
- **Topics:**
  - `logs.raw` - Raw log batches (3 partitions)
  - `metrics.raw` - Raw metric batches (3 partitions)
  - `events.raw` - Events (3 partitions)
- **Retention:** 7 days
- **Replication:** 3x
- **Throughput:** 100K messages/sec
- **Deployment:** 3 broker cluster

### Stream Processing Layer

**Log Processor:**
- **Language:** Python
- **Framework:** aiokafka consumer
- **Operations:**
  - Parse log message
  - Extract structured fields (JSON parsing)
  - Add labels
  - Normalize timestamps
  - Filter out debug logs (production)
- **Deployment:** 3+ instances (consumer group)
- **Throughput:** 10K logs/sec per instance

**Metrics Processor:**
- **Operations:**
  - Aggregate by service/host
  - Compute rolling windows (1min, 5min, 15min)
  - Calculate percentiles (p50, p95, p99)
  - Detect anomalies (z-score)
  - Downsample high-frequency metrics
- **Deployment:** 3+ instances

### Storage Layer

**OpenSearch (Hot Storage):**
- **Indices:**
  - `logs-YYYY-MM-DD` (daily indices)
  - `metrics-YYYY-MM` (monthly indices)
- **Retention:** 7 days
- **Shards:** 3 primary, 1 replica
- **Deployment:** 3 node cluster
- **Disk:** 500GB per node

**S3/MinIO (Warm Storage):**
- **Format:** Parquet (compressed)
- **Structure:** 
  - `s3://bucket/logs/YYYY/MM/DD/`
  - `s3://bucket/metrics/YYYY/MM/`
- **Retention:** 30 days
- **Compression:** ~10x

**Redis (Cache):**
- **Use Cases:**
  - Query result caching (5 min TTL)
  - Rate limiting counters
  - Recent aggregations
- **Deployment:** Master-replica (2 nodes)
- **Memory:** 8GB

### Query Layer

**Query Service:**
- **Framework:** FastAPI
- **Endpoints:**
  - GET /logs/search
  - GET /metrics/query
  - GET /services
- **Features:**
  - Full-text search
  - Time range filters
  - Aggregations
  - Pagination
- **Deployment:** 3+ instances
- **Caching:** Redis for hot queries

### Visualization Layer

**Grafana:**
- **Dashboards:**
  - Error rate by service
  - CPU/Memory usage
  - Disk usage
  - Network throughput
  - Log search interface
- **Alerts:**
  - Error rate > 5%
  - CPU > 80% for 5 minutes
  - Disk > 90%
- **Authentication:** OAuth/LDAP

---

## Deployment Architecture

### Development Environment

```
┌────────────────────────────────────────────┐
│           Docker Compose                   │
│                                            │
│  ┌──────────┐  ┌──────────┐               │
│  │Ingestion │  │  Query   │               │
│  │ Service  │  │ Service  │               │
│  └────┬─────┘  └────┬─────┘               │
│       │             │                      │
│  ┌────┴─────────────┴──────┐              │
│  │      Redpanda           │              │
│  │  (single instance)      │              │
│  └────┬───────────────────┘               │
│       │                                    │
│  ┌────┴──────┐  ┌──────────┐              │
│  │OpenSearch │  │  Redis   │              │
│  │(1 node)   │  │(1 node)  │              │
│  └───────────┘  └──────────┘              │
│                                            │
│  ┌──────────┐                              │
│  │ Grafana  │                              │
│  └──────────┘                              │
└────────────────────────────────────────────┘
```

### Production Environment

```
┌─────────────────────────────────────────────────────────────────┐
│                          AWS / Cloud                             │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                   Load Balancer (ALB)                   │     │
│  └─────────────┬──────────────────────┬───────────────────┘     │
│                │                      │                          │
│      ┌─────────▼─────────┐  ┌────────▼────────┐                │
│      │  Auto Scaling     │  │  Auto Scaling   │                │
│      │  Group:           │  │  Group:         │                │
│      │  Ingestion (3-10) │  │  Query (3-10)   │                │
│      └─────────┬─────────┘  └────────┬────────┘                │
│                │                      │                          │
│  ┌─────────────┴──────────────────────┴─────────────┐           │
│  │           Managed Kafka (MSK)                     │           │
│  │           - 3 brokers                             │           │
│  │           - Multi-AZ                              │           │
│  └────────────────────┬──────────────────────────────┘           │
│                       │                                          │
│  ┌────────────────────┴──────────────────────────────┐           │
│  │         OpenSearch Service (Managed)              │           │
│  │         - 3 data nodes (m5.large)                 │           │
│  │         - 3 master nodes                          │           │
│  │         - Multi-AZ                                │           │
│  └────────────────────┬──────────────────────────────┘           │
│                       │                                          │
│  ┌────────────────────┴──────────────────────────────┐           │
│  │               ElastiCache (Redis)                 │           │
│  │               - Multi-AZ                          │           │
│  └───────────────────────────────────────────────────┘           │
│                                                                   │
│  ┌───────────────────────────────────────────────────┐           │
│  │                    S3 Buckets                     │           │
│  │  - observability-logs                             │           │
│  │  - observability-metrics                          │           │
│  │  Lifecycle: Standard → IA → Glacier               │           │
│  └───────────────────────────────────────────────────┘           │
└───────────────────────────────────────────────────────────────────┘
```

---

## Scalability Considerations

### Vertical Scaling Limits

| Component        | Current  | Max (Single Node) | Notes                |
|------------------|----------|-------------------|----------------------|
| Ingestion        | 1K/s     | 10K/s            | CPU bound            |
| Kafka            | 100K/s   | 1M/s             | Disk I/O bound       |
| Processors       | 10K/s    | 50K/s            | CPU bound            |
| OpenSearch Node  | 5K/s     | 20K/s            | Disk I/O bound       |
| Query Service    | 100 q/s  | 500 q/s          | OpenSearch limited   |

### Horizontal Scaling Strategy

**Ingestion Service:**
- Add more instances behind load balancer
- Stateless, can scale to 100+ instances
- Bottleneck: Kafka write throughput

**Kafka:**
- Add more brokers (up to 10-20)
- Increase partitions per topic
- Bottleneck: Network bandwidth

**Stream Processors:**
- Add more consumer instances
- Auto-scale based on consumer lag
- One instance per partition max

**OpenSearch:**
- Add more data nodes
- Shard indices across nodes
- Increase replica count for read scaling
- Bottleneck: Heap memory, disk I/O

**Query Service:**
- Add more instances
- Use Redis for caching hot queries
- Implement query result pagination

### Performance Targets

| Metric                   | Target        | Notes                      |
|--------------------------|---------------|----------------------------|
| Log ingestion rate       | 100K logs/s   | Peak capacity              |
| Metric ingestion rate    | 1M metrics/s  | Peak capacity              |
| End-to-end latency (p95) | < 5 seconds   | Log write → searchable     |
| Query latency (p95)      | < 500ms       | Simple queries             |
| Data retention (hot)     | 7 days        | OpenSearch                 |
| Data retention (warm)    | 30 days       | S3                         |
| Storage cost             | $0.10/GB/mo   | Compressed in S3           |

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Security Layers                        │
│                                                           │
│  1. Network Layer:                                       │
│     ├─ VPC with private subnets                         │
│     ├─ Security groups (least privilege)                │
│     └─ TLS/SSL for all external traffic                 │
│                                                           │
│  2. Authentication:                                      │
│     ├─ API keys for agents (X-API-Key header)           │
│     ├─ OAuth/LDAP for Grafana users                     │
│     └─ Service accounts for internal services           │
│                                                           │
│  3. Authorization:                                       │
│     ├─ RBAC in Grafana (viewer/editor/admin)            │
│     ├─ Tenant isolation in data                         │
│     └─ Rate limiting per API key                        │
│                                                           │
│  4. Data Protection:                                     │
│     ├─ Encryption at rest (S3, OpenSearch)              │
│     ├─ Encryption in transit (TLS)                      │
│     ├─ PII masking in logs                              │
│     └─ Sensitive field filtering                        │
│                                                           │
│  5. Audit:                                               │
│     ├─ Access logs                                       │
│     ├─ Query logs                                        │
│     └─ Configuration changes tracked                    │
└─────────────────────────────────────────────────────────┘
```

---

## Cost Estimation (AWS, 1TB/day)

| Component           | Instance Type | Count | Monthly Cost |
|---------------------|---------------|-------|--------------|
| Ingestion Service   | t3.medium     | 3     | $100         |
| Query Service       | t3.medium     | 3     | $100         |
| Stream Processors   | t3.medium     | 3     | $100         |
| MSK (Kafka)         | kafka.m5.large| 3     | $750         |
| OpenSearch          | m5.large      | 3     | $450         |
| ElastiCache (Redis) | cache.t3.small| 2     | $50          |
| S3 Storage          | Standard      | 10TB  | $230         |
| Data Transfer       | -             | -     | $200         |
| **Total**           |               |       | **~$2,000**  |

*Note: Actual costs vary based on usage patterns, retention, and optimization.*

---

## Disaster Recovery

**RPO (Recovery Point Objective):** < 5 minutes
**RTO (Recovery Time Objective):** < 30 minutes

**Backup Strategy:**
1. Kafka: 3x replication across AZs
2. OpenSearch: Automated snapshots to S3 (hourly)
3. Configuration: Infrastructure as Code (Terraform)
4. S3: Cross-region replication

**Failure Scenarios:**

| Failure               | Impact          | Recovery                   |
|-----------------------|-----------------|----------------------------|
| Single ingestion pod  | None            | Auto-replaced by k8s       |
| Kafka broker down     | None            | Automatic failover         |
| OpenSearch node down  | Degraded reads  | Automatic re-shard         |
| AZ failure            | None            | Multi-AZ deployment        |
| Region failure        | Service down    | Failover to backup region  |

---

This architecture is designed to scale from development (single machine) to production (handling billions of events per day) while maintaining reliability and cost-effectiveness.