# LLM Gateway

A multi-tenant API gateway for Large Language Model providers. Routes requests to OpenAI and Anthropic with automatic provider fallback, per-tenant rate limiting, response caching, cost tracking, and Prometheus metrics.

## Features

- **Multi-provider routing** — OpenAI and Anthropic with automatic fallback
- **Multi-tenancy** — Isolated API keys, rate limits, and budgets per tenant
- **Rate limiting** — Per-tenant request throttling via Redis
- **Response caching** — Redis-backed prompt cache to reduce costs
- **Cost tracking** — Per-request cost calculation and per-tenant usage reporting
- **Observability** — Prometheus metrics and Grafana dashboard
- **Streaming support** — SSE streaming for completion responses

## Project Structure

```
├── src/
│   ├── api/                 # API endpoints
│   │   ├── admin.py         # Tenant management & usage stats
│   │   └── completions.py   # LLM completion routing
│   ├── core/                # Core modules
│   │   ├── config.py        # Pydantic settings
│   │   ├── database.py      # SQLAlchemy engine & session
│   │   ├── metrics.py       # Prometheus metric definitions
│   │   ├── models.py        # Tenant, Request, UsageLog models
│   │   └── redis_client.py  # Async Redis client
│   ├── middleware/           # Request middleware
│   │   ├── auth.py          # API key authentication
│   │   └── rate_limiter.py  # Redis-based rate limiting
│   ├── providers/           # LLM provider integrations
│   │   ├── base.py          # Abstract base + request/response models
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── provider_factory.py
│   └── main.py              # FastAPI app entrypoint
├── tests/                   # Test suite
├── k8s/                     # Kubernetes manifests
├── terraform/               # Terraform IaC
├── grafana/dashboards/      # Grafana dashboard JSON
├── docs/                    # Documentation
├── docker-compose.yml
├── Dockerfile
└── prometheus.yml
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for containerized setup)
- At least one LLM provider API key (OpenAI or Anthropic)

### Local Development

```bash
# Clone the repository
git clone https://github.com/roleesinha2020/llm-gateway.git
cd llm-gateway

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# Start dependencies (Redis + Postgres)
docker compose up -d redis postgres

# Run the server
uvicorn src.main:app --reload --port 8000
```

### Docker Compose

```bash
cp .env.example .env
# Edit .env with your API keys

docker compose up --build
```

This starts the gateway on port 8000 along with Redis, PostgreSQL, and Prometheus.

## API Usage

### Create a Tenant

```bash
curl -X POST "http://localhost:8000/api/v1/admin/tenants?name=my-app&rate_limit=100"
```

Save the returned `api_key` from the response.

### Send a Completion Request

```bash
curl -X POST http://localhost:8000/api/v1/completions \
  -H "X-API-Key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

### Check Usage

```bash
curl "http://localhost:8000/api/v1/admin/tenants/<tenant_id>/usage?days=30"
```

### Health Check

```bash
curl http://localhost:8000/health
```

See [docs/API.md](docs/API.md) for full API documentation.

## Testing

```bash
pytest -v
```

Runs 8 tests covering health checks, tenant admin, authentication, completions, caching, and rate limiting. Tests use an in-memory SQLite database and mocked Redis/providers — no external services required.

## Monitoring

| Service    | URL                    |
|------------|------------------------|
| Gateway    | http://localhost:8000  |
| Prometheus | http://localhost:9090  |
| Metrics    | http://localhost:8000/metrics |

Import `grafana/dashboards/llm-gateway.json` into Grafana to get a pre-built dashboard with panels for request rate, latency percentiles, cost by tenant, cache hit rate, rate limit violations, token usage, and active requests.

## Kubernetes Deployment

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/deployment.yaml
```

## Terraform Deployment

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

terraform init
terraform plan
terraform apply
```

## Configuration

All configuration is via environment variables. See [.env.example](.env.example) for the full list:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production` | Application secret key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `REDIS_HOST` | `localhost` | Redis hostname |
| `POSTGRES_HOST` | `localhost` | PostgreSQL hostname |
| `DEFAULT_RATE_LIMIT` | `100` | Requests per minute per tenant |
| `CACHE_TTL` | `3600` | Cache TTL in seconds |
| `LOG_LEVEL` | `INFO` | Logging level |

## Tech Stack

- **Framework:** FastAPI + Uvicorn
- **Database:** PostgreSQL + SQLAlchemy 2.0
- **Cache/Rate Limiting:** Redis
- **LLM SDKs:** openai, anthropic
- **Metrics:** prometheus-client
- **IaC:** Terraform, Kubernetes
- **Testing:** pytest
