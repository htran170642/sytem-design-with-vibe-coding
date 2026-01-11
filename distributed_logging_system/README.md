# 🔍 Distributed Observability Platform (POC)

A production-like distributed logging and metrics platform built in Python for learning system design and distributed systems concepts.

## 🎯 Goals

- Learn distributed systems design
- Understand real-time data pipelines
- Practice production-quality code
- Prepare for senior engineering interviews

## 🏗️ Architecture

```
Agents → Ingestion API → Kafka → Processors → Storage (OpenSearch/S3) → Query API → Grafana
```

### Components

1. **Agents**: Collect logs and metrics from applications
2. **Ingestion Service**: FastAPI service for receiving data
3. **Message Bus**: Kafka/Redpanda for reliable message delivery
4. **Stream Processors**: Parse, transform, and enrich data
5. **Storage**: OpenSearch (hot), S3/MinIO (warm/cold)
6. **Query API**: FastAPI service for querying data
7. **Visualization**: Grafana dashboards

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Docker & Docker Compose (optional, for Phase 3+)
- Make (optional, but recommended)

### Installation

**Recommended: Using virtual environment**

```bash
# Clone the repository
git clone <your-repo-url>
cd observability-platform-poc

# Create and activate virtual environment
make venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# Install dependencies and setup
make install-dev
make setup

# Verify installation
make verify
```

**For detailed setup instructions, see [docs/SETUP.md](docs/SETUP.md)**

### Running Services

```bash
# Start infrastructure (Kafka, OpenSearch, etc.)
make docker-up

# Run ingestion service
make run-ingestion

# Run query service (in another terminal)
make run-query

# Run log agent (in another terminal)
make run-agent-logs

# Run metrics agent (in another terminal)
make run-agent-metrics
```

## 📁 Project Structure

```
observability-platform-poc/
├── observability/
│   ├── agents/           # Data collection agents
│   ├── ingestion/        # Ingestion API service
│   ├── processing/       # Stream processors
│   ├── storage/          # Storage layer abstractions
│   ├── api/              # Query API service
│   ├── common/           # Shared utilities
│   └── tests/            # Tests
├── config/               # Configuration files
├── scripts/              # Utility scripts
├── docs/                 # Documentation
├── docker-compose.yml    # Docker services
└── pyproject.toml        # Dependencies
```

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test
pytest tests/unit/test_ingestion.py
```

## 🎨 Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Pre-commit hooks (runs automatically on commit)
pre-commit run --all-files
```

## 📊 Features

### Phase 1: Data Collection ✅
- [x] Log agent with file tailing
- [x] Metrics agent with system stats
- [x] Batching and buffering
- [x] Retry with exponential backoff

### Phase 2: Ingestion Service ✅
- [x] FastAPI endpoints
- [x] Schema validation
- [x] Rate limiting
- [x] API key authentication

### Phase 3+: In Progress 🚧
- [ ] Kafka integration
- [ ] Stream processing
- [ ] Storage layer
- [ ] Query API
- [ ] Grafana dashboards

## 🔧 Configuration

Edit `.env` file to configure:

- Service ports
- Kafka connection
- OpenSearch credentials
- S3/MinIO settings
- Retention policies
- Rate limits

## 📚 Learning Resources

- [System Design Primer](https://github.com/donnemartin/system-design-primer)
- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [OpenSearch Documentation](https://opensearch.org/docs/latest/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## 🎤 Interview Talking Points

1. **Scalability**: How the system handles 100K events/second
2. **Reliability**: Retry mechanisms, dead letter queues
3. **Consistency**: Trade-offs in distributed storage
4. **Monitoring**: Observability of the observability system
5. **Security**: Authentication, encryption, data masking

## 📝 TODO

See [TODO.md](TODO.md) for detailed implementation roadmap.

## 📄 License

MIT License - feel free to use for learning purposes.

## 🙏 Acknowledgments

Built for learning distributed systems and preparing for technical interviews.