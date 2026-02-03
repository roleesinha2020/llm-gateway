# Technical Architecture Document
# Multi-Tenant LLM Gateway
## Version 1.0 | Local Deployment Edition

---

**Document Owner:** Infrastructure Engineering Team  
**Date:** February 2026  
**Status:** Draft - For Implementation  
**Classification:** Internal Use

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [System Components](#2-system-components)
3. [Data Flow](#3-data-flow)
4. [Technology Stack](#4-technology-stack)
5. [Deployment Architecture](#5-deployment-architecture)
6. [Security Architecture](#6-security-architecture)
7. [Scalability & Performance](#7-scalability--performance)
8. [Monitoring & Observability](#8-monitoring--observability)
9. [Disaster Recovery](#9-disaster-recovery)
10. [Future Considerations](#10-future-considerations)

---

## 1. Architecture Overview

### 1.1 High-Level Architecture

The Multi-Tenant LLM Gateway follows a layered architecture pattern with clear separation of concerns:

```
┌──────────────────────────────────────────────────────────┐
│                    Client Applications                    │
│         (Web Apps, Mobile Apps, Backend Services)        │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTPS (X-API-Key header)
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   API Gateway Layer                       │
│                    (FastAPI/Uvicorn)                      │
│  ┌────────────────────────────────────────────────────┐  │
│  │         Authentication & Authorization             │  │
│  └───────────────────┬────────────────────────────────┘  │
│                      ▼                                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │          Rate Limiting Middleware                  │  │
│  └───────────────────┬────────────────────────────────┘  │
│                      ▼                                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │              Caching Layer                         │  │
│  └───────────────────┬────────────────────────────────┘  │
│                      ▼                                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │          Provider Router & Fallback                │  │
│  └───────────────────┬────────────────────────────────┘  │
│                      ▼                                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │        Cost Tracking & Audit Logging               │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────────┬─────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   OpenAI    │  │  Anthropic  │  │    Local    │
│     API     │  │     API     │  │    Model    │
└─────────────┘  └─────────────┘  └─────────────┘

         ┌─────────────────────────────┐
         │   Supporting Services       │
         ├─────────────────────────────┤
         │ • Redis (Cache/Rate Limit)  │
         │ • PostgreSQL (Persistence)  │
         │ • Prometheus (Metrics)      │
         └─────────────────────────────┘
```

### 1.2 Architectural Principles

**1. Separation of Concerns**
- Each layer has a single, well-defined responsibility
- Middleware pattern for cross-cutting concerns
- Provider abstraction isolates vendor-specific logic

**2. Fail-Safe Design**
- Graceful degradation when dependencies are unavailable
- Circuit breaker pattern for provider failures
- Retry mechanisms with exponential backoff

**3. Observability First**
- Structured logging at every layer
- Comprehensive metrics collection
- Distributed tracing capabilities

**4. Security by Default**
- Zero-trust architecture for tenant isolation
- Encrypted communication channels
- Secrets management best practices

**5. Scalability & Performance**
- Stateless application design for horizontal scaling
- Efficient caching strategy
- Asynchronous I/O for high concurrency

---

## 2. System Components

### 2.1 API Gateway (FastAPI Application)

**Purpose:** Central entry point for all LLM requests

**Responsibilities:**
- Request routing and validation
- Authentication and authorization
- Rate limiting enforcement
- Response formatting

**Technology:**
- FastAPI (Python async web framework)
- Uvicorn (ASGI server)
- Pydantic (data validation)

**Key Features:**
- Automatic OpenAPI documentation
- Request/response validation
- Async/await for high concurrency
- Type safety

**Configuration:**
- Environment-based configuration
- Hot-reload in development
- Production-ready settings

### 2.2 Authentication & Authorization Module

**Purpose:** Verify tenant identity and permissions

**Authentication Flow:**
```
1. Client sends request with X-API-Key header
2. Extract API key from header
3. Query database for tenant record
4. Validate tenant status (active/suspended)
5. Attach tenant context to request
6. Proceed to next middleware
```

**Security Features:**
- API key hashing in database
- Automatic key rotation support
- Failed authentication logging
- Rate limiting on auth failures

**Database Schema:**
```sql
tenants
├── id (UUID, PK)
├── name (String)
├── api_key_hash (String, Unique)
├── rate_limit (Integer)
├── monthly_budget (Float, Nullable)
├── is_active (Boolean)
├── created_at (Timestamp)
└── updated_at (Timestamp)
```

### 2.3 Rate Limiting Layer

**Purpose:** Prevent abuse and ensure fair resource allocation

**Algorithm:** Sliding Window Counter

**Implementation:**
```
Redis Key: rate_limit:{tenant_id}
Value: Request count
TTL: 60 seconds (rolling window)

Logic:
1. Increment counter for tenant
2. If counter > limit, return 429
3. Otherwise, allow request
4. Return remaining quota in response header
```

**Features:**
- Per-tenant configurable limits
- Burst allowance
- Graceful degradation if Redis unavailable
- Rate limit headers in response

**Response Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1675360800
Retry-After: 42 (on 429 responses)
```

### 2.4 Caching Layer (Redis)

**Purpose:** Reduce costs and latency for duplicate requests

**Cache Strategy:** Semantic caching with SHA-256 hash keys

**Cache Key Generation:**
```
Input: tenant_id + model + messages + temperature
Hash: SHA-256(input)
Key Format: cache:{hash}
TTL: 3600 seconds (configurable)
```

**Cache Hit Scenario:**
```
1. Generate cache key from request
2. Check Redis for existing entry
3. If found, return cached response immediately
4. Log cache hit metric
5. Skip provider API call
```

**Cache Miss Scenario:**
```
1. Generate cache key from request
2. Redis returns null
3. Proceed to provider API call
4. Store response in Redis with TTL
5. Return response to client
```

**Invalidation Strategy:**
- TTL-based automatic expiration
- Manual flush via admin API
- LRU eviction when memory limit reached

### 2.5 Provider Abstraction Layer

**Purpose:** Unified interface for multiple LLM providers

**Design Pattern:** Strategy Pattern + Factory Pattern

**Provider Interface:**
```python
class BaseLLMProvider:
    - complete(request: LLMRequest) → LLMResponse
    - calculate_cost(tokens) → float
    - health_check() → bool
```

**Supported Providers:**
1. OpenAI (GPT-3.5, GPT-4, GPT-4-Turbo)
2. Anthropic (Claude 3 family)
3. Local Models (Ollama, vLLM)

**Fallback Mechanism:**
```
Primary Provider (e.g., OpenAI)
│
├── Success → Return response
│
├── Failure (5xx, timeout)
    │
    └── Fallback to Secondary (e.g., Anthropic)
        │
        ├── Success → Return response
        │
        └── Failure → Try Tertiary (e.g., Local)
            │
            ├── Success → Return response
            │
            └── Failure → Return 503 error
```

**Health Monitoring:**
- Periodic health checks every 30 seconds
- Circuit breaker pattern
- Automatic re-enabling after recovery

### 2.6 Cost Tracking Module

**Purpose:** Accurate cost attribution per request

**Cost Calculation:**
```
Cost = (prompt_tokens × prompt_price) + 
       (completion_tokens × completion_price)

Pricing (per 1K tokens):
- GPT-4: $0.03 (input) + $0.06 (output)
- GPT-3.5: $0.0015 (input) + $0.002 (output)
- Claude 3 Opus: $0.015 (input) + $0.075 (output)
- Claude 3 Sonnet: $0.003 (input) + $0.015 (output)
```

**Tracking Granularity:**
- Per-request tracking
- Daily aggregation
- Monthly summaries
- Provider breakdown

**Database Schema:**
```sql
requests
├── id (UUID, PK)
├── tenant_id (UUID, FK)
├── provider (String)
├── model (String)
├── prompt_tokens (Integer)
├── completion_tokens (Integer)
├── total_tokens (Integer)
├── cost (Decimal)
├── latency_ms (Integer)
├── status (String)
├── cache_hit (Boolean)
├── error_message (String, Nullable)
├── created_at (Timestamp)
└── INDEX (tenant_id, created_at)

usage_logs
├── id (Integer, PK)
├── tenant_id (UUID, FK)
├── date (Date)
├── total_requests (Integer)
├── total_tokens (Integer)
├── total_cost (Decimal)
├── provider_breakdown (JSONB)
└── INDEX (tenant_id, date)
```

### 2.7 Audit Logging System

**Purpose:** Complete audit trail for compliance

**Log Structure:**
```json
{
  "timestamp": "2026-02-02T10:30:45.123Z",
  "level": "INFO",
  "event": "completion_request",
  "tenant_id": "abc-123",
  "request_id": "req-xyz-789",
  "provider": "openai",
  "model": "gpt-4",
  "tokens": {
    "prompt": 45,
    "completion": 127,
    "total": 172
  },
  "cost": 0.00516,
  "latency_ms": 1247,
  "cache_hit": false,
  "status": "success"
}
```

**Log Levels:**
- DEBUG: Detailed execution traces
- INFO: Normal operations
- WARNING: Degraded performance, rate limits
- ERROR: Failed requests, provider errors
- CRITICAL: System failures

**Storage:**
- Structured JSON logs
- PostgreSQL for queryable history
- Optional: ELK stack integration for advanced analysis

---

## 3. Data Flow

### 3.1 Request Flow Diagram

```
Client Application
    │
    │ 1. POST /api/v1/completions
    │    Headers: X-API-Key: xxx
    │    Body: { model, messages, ... }
    │
    ▼
┌─────────────────────────────────────┐
│   API Gateway (FastAPI)             │
│                                     │
│   2. Extract & validate API key     │
│   3. Query DB for tenant            │
│   4. Attach tenant to request       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Rate Limiter                      │
│                                     │
│   5. Check Redis counter            │
│   6. If over limit → 429 error      │
│   7. Otherwise, increment counter   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Cache Layer                       │
│                                     │
│   8. Generate cache key (SHA-256)   │
│   9. Check Redis for cached resp    │
│   10. If hit → return immediately   │
└──────────────┬──────────────────────┘
               │ (cache miss)
               ▼
┌─────────────────────────────────────┐
│   Provider Router                   │
│                                     │
│   11. Select provider (OpenAI)      │
│   12. Call provider API             │
│   13. If error → fallback to next   │
│   14. Parse response                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Cost Tracker                      │
│                                     │
│   15. Calculate token costs         │
│   16. Record in database            │
│   17. Update daily aggregates       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Response Builder                  │
│                                     │
│   18. Format response JSON          │
│   19. Add metadata (cost, latency)  │
│   20. Cache response in Redis       │
└──────────────┬──────────────────────┘
               │
               ▼
         Return to Client
```

### 3.2 Cache Hit Flow

```
Client Request
    │
    ▼
API Gateway → Auth → Rate Limit
    │
    ▼
Cache Layer
    │
    ├─ Generate Key: cache:abc123...
    ├─ Redis GET
    ├─ Result: {content, model, provider}
    │
    ▼
Response (bypassing provider entirely)
    │
    ├─ cached: true
    ├─ response: {...}
    ├─ cost: 0.00  (no API call!)
    ├─ latency_ms: 12
    │
    ▼
Log to Database (cache_hit=true)
```

### 3.3 Provider Fallback Flow

```
Primary Provider (OpenAI)
    │
    ├─ Attempt API Call
    │
    ├─ Error: Timeout / 5xx
    │
    ▼
Log Error + Switch to Secondary
    │
    ▼
Secondary Provider (Anthropic)
    │
    ├─ Attempt API Call
    │
    ├─ Success!
    │
    ▼
Return Response
    │
    ├─ provider: "anthropic"
    ├─ fallback_count: 1
    ├─ primary_error: "OpenAI timeout"
```

---

## 4. Technology Stack

### 4.1 Core Application

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| API Framework | FastAPI | 0.109+ | Async web framework |
| ASGI Server | Uvicorn | 0.27+ | Production web server |
| Language | Python | 3.11+ | Core application logic |
| Validation | Pydantic | 2.5+ | Data validation & settings |

### 4.2 Data Layer

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Cache | Redis | 7.x | Caching & rate limiting |
| Database | PostgreSQL | 15.x | Persistent storage |
| ORM | SQLAlchemy | 2.0+ | Database abstraction |
| Migrations | Alembic | 1.13+ | Schema versioning |

### 4.3 LLM Providers

| Provider | SDK | Purpose |
|----------|-----|---------|
| OpenAI | openai 1.10+ | GPT models |
| Anthropic | anthropic 0.8+ | Claude models |
| Local | httpx 0.26+ | Custom endpoints |

### 4.4 Infrastructure

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Containerization | Docker | 24.x+ | Application packaging |
| Orchestration | Kubernetes | 1.28+ | Container management |
| IaC | Terraform | 1.6+ | Infrastructure automation |
| Service Mesh | (Optional) | - | Advanced networking |

### 4.5 Monitoring & Observability

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Metrics | Prometheus | 2.48+ | Metrics collection |
| Visualization | Grafana | 10.x+ | Dashboards |
| Logging | structlog | 24.1+ | Structured logging |
| Tracing | (Optional) | - | Distributed tracing |

---

## 5. Deployment Architecture

### 5.1 Local Development (Docker Compose)

```yaml
services:
  gateway:
    - FastAPI application
    - Port: 8000
    - Env: Development
    - Auto-reload enabled
  
  redis:
    - Redis 7-alpine
    - Port: 6379
    - Persistence: Disabled
  
  postgres:
    - PostgreSQL 15-alpine
    - Port: 5432
    - Volume: Local disk
  
  prometheus:
    - Prometheus latest
    - Port: 9090
    - Scrapes gateway:8000/metrics
```

**Resource Requirements:**
- CPU: 2 cores minimum
- RAM: 8GB minimum, 16GB recommended
- Disk: 10GB for containers + logs
- Network: Internet for LLM APIs

### 5.2 Local Kubernetes (minikube/kind)

```
Namespace: llm-gateway

Deployments:
├── gateway (3 replicas)
│   ├── Resource Requests: 250m CPU, 256Mi RAM
│   ├── Resource Limits: 500m CPU, 512Mi RAM
│   ├── Liveness Probe: /health
│   └── Readiness Probe: /health
│
├── redis (1 replica)
│   ├── Resource Requests: 100m CPU, 128Mi RAM
│   └── PersistentVolume: 1Gi
│
└── postgres (StatefulSet, 1 replica)
    ├── Resource Requests: 250m CPU, 512Mi RAM
    └── PersistentVolume: 10Gi

Services:
├── gateway-service (LoadBalancer)
├── redis-service (ClusterIP)
└── postgres-service (ClusterIP)

ConfigMaps:
└── gateway-config (environment variables)

Secrets:
└── gateway-secrets (API keys, DB passwords)
```

**High Availability:**
- Multiple gateway replicas
- Pod anti-affinity rules
- Automatic restart on failure
- Rolling updates for deployments

### 5.3 Production Kubernetes (Cloud)

**Additional Components:**
- Ingress Controller (nginx/traefik)
- Cert-Manager for TLS
- External Secrets Operator
- Horizontal Pod Autoscaler
- Network Policies

**Multi-Region Setup:**
```
Region US-West
├── Kubernetes Cluster 1
│   ├── Gateway Pods (3-10 replicas)
│   ├── Redis Cluster (3 nodes)
│   └── Cloud SQL (managed PostgreSQL)
│
Region US-East
├── Kubernetes Cluster 2
│   ├── Gateway Pods (3-10 replicas)
│   ├── Redis Cluster (3 nodes)
│   └── Cloud SQL (read replica)
│
Global Load Balancer
└── Routes traffic based on geography
```

---

## 6. Security Architecture

### 6.1 Authentication & Authorization

**API Key Management:**
- Keys generated with cryptographically secure random
- Format: `llm-gw-{32-byte-base64}`
- Stored as SHA-256 hashes in database
- Never logged in plain text

**Tenant Isolation:**
- Database-level isolation via tenant_id
- Query filtering enforced at ORM level
- No shared resources between tenants

**Access Control:**
- Admin endpoints require separate authentication
- Tenant endpoints scoped to authenticated tenant
- No cross-tenant data access

### 6.2 Data Security

**In Transit:**
- TLS 1.3 for all external communication
- Internal service mesh (optional)
- Certificate management via cert-manager

**At Rest:**
- PostgreSQL encrypted volumes
- Redis with AUTH password
- Kubernetes secrets encrypted at rest

**Sensitive Data Handling:**
- Provider API keys in Kubernetes secrets
- No PII in logs
- Request/response bodies optional in audit logs

### 6.3 Network Security

**Kubernetes Network Policies:**
```yaml
# Gateway can talk to: Redis, PostgreSQL, Internet
# Redis can receive from: Gateway only
# PostgreSQL can receive from: Gateway only
```

**Firewall Rules:**
- Ingress: Port 443 (HTTPS) only
- Egress: LLM provider APIs + monitoring
- No direct database access from outside

---

## 7. Scalability & Performance

### 7.1 Horizontal Scaling

**Stateless Design:**
- No in-memory session state
- All state in Redis/PostgreSQL
- Any gateway instance can handle any request

**Auto-Scaling Rules:**
```yaml
HorizontalPodAutoscaler:
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### 7.2 Caching Strategy

**Cache Effectiveness:**
- Expected hit rate: 50-70% for typical workloads
- Cost savings: 50-70% reduction in API costs
- Latency improvement: 50ms vs 1500ms

**Cache Warming:**
- Pre-populate cache with common queries
- Background job to maintain hot cache

**Cache Sizing:**
- 1GB Redis = ~100K cached responses
- Automatic LRU eviction

### 7.3 Database Optimization

**Connection Pooling:**
```python
pool_size = 10
max_overflow = 20
pool_pre_ping = True
pool_recycle = 3600
```

**Indexing Strategy:**
- Primary keys on all tables
- Composite index on (tenant_id, created_at)
- Index on provider for analytics queries

**Query Optimization:**
- Aggregate queries use database functions
- Pagination for large result sets
- Read replicas for reporting (production)

### 7.4 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| P50 Latency | <100ms | Prometheus histogram |
| P95 Latency | <200ms | Prometheus histogram |
| P99 Latency | <500ms | Prometheus histogram |
| Throughput | 100 req/sec per pod | Load testing |
| Error Rate | <0.1% | Error counter / total requests |

---

## 8. Monitoring & Observability

### 8.1 Metrics (Prometheus)

**Application Metrics:**
```
# Request metrics
llm_gateway_requests_total{tenant_id, provider, status}
llm_gateway_request_duration_seconds{provider}
llm_gateway_active_requests{provider}

# Business metrics
llm_gateway_tokens_total{tenant_id, provider, type}
llm_gateway_cost_total{tenant_id, provider}
llm_gateway_cache_hits_total{tenant_id}
llm_gateway_rate_limit_exceeded_total{tenant_id}

# Infrastructure metrics
llm_gateway_redis_connections
llm_gateway_db_connection_pool_size
```

**System Metrics (from Kubernetes):**
- CPU usage per pod
- Memory usage per pod
- Network I/O
- Disk I/O

### 8.2 Logging

**Log Aggregation:**
```json
{
  "@timestamp": "2026-02-02T10:30:45.123Z",
  "level": "INFO",
  "logger": "llm_gateway.api.completions",
  "event": "request_completed",
  "tenant_id": "abc-123",
  "request_id": "req-xyz-789",
  "method": "POST",
  "path": "/api/v1/completions",
  "status_code": 200,
  "duration_ms": 1247,
  "provider": "openai",
  "cache_hit": false,
  "cost": 0.00516
}
```

**Log Levels:**
- Production: INFO and above
- Development: DEBUG
- Error tracking: ERROR and CRITICAL to alerting

### 8.3 Health Checks

**Liveness Probe:**
```
GET /health
Response: 200 OK if application is running
```

**Readiness Probe:**
```
GET /health/ready
Response: 200 OK if:
  - Database connection available
  - Redis connection available
  - At least one provider healthy
```

### 8.4 Alerting Rules

**Critical Alerts:**
- Gateway pod crash loop
- Database connection failures
- Redis unavailable
- All providers failing
- Error rate >1%

**Warning Alerts:**
- High latency (P95 >500ms)
- Cache hit rate <30%
- Disk usage >80%
- Memory usage >80%

---

## 9. Disaster Recovery

### 9.1 Backup Strategy

**Database Backups:**
- Automated daily backups
- 30-day retention
- Point-in-time recovery capability
- Backup testing monthly

**Configuration Backups:**
- All manifests in Git
- Secrets in external secret manager
- Infrastructure as Code in Git

### 9.2 Recovery Procedures

**Service Failure:**
```
1. Kubernetes automatically restarts failed pods
2. Health checks prevent traffic to unhealthy pods
3. Rolling deployment ensures zero downtime
```

**Database Failure:**
```
1. Restore from most recent backup
2. Replay transaction logs if available
3. Verify data integrity
4. Restart application pods
```

**Complete Cluster Failure:**
```
1. Provision new cluster via Terraform
2. Restore database from backup
3. Deploy application via kubectl/helm
4. Update DNS to point to new cluster
```

### 9.3 RTO/RPO Targets

| Scenario | RTO (Recovery Time) | RPO (Data Loss) |
|----------|---------------------|-----------------|
| Single pod failure | <30 seconds | None (stateless) |
| Database failure | <15 minutes | <5 minutes |
| Complete cluster loss | <1 hour | <1 hour |

---

## 10. Future Considerations

### 10.1 Planned Enhancements

**Phase 2 Features:**
- Streaming response support
- WebSocket connections for real-time
- Advanced routing (A/B testing, canary)
- Request/response transformation rules

**Phase 3 Features:**
- Multi-region active-active deployment
- GraphQL API support
- Embedding generation endpoints
- Fine-tuning job management

### 10.2 Scalability Roadmap

**Horizontal Scaling:**
- Redis Cluster mode (currently single instance)
- Read replicas for PostgreSQL
- Geo-distributed deployments

**Performance Optimization:**
- Connection pooling tuning
- Query optimization based on usage patterns
- CDN for static documentation

### 10.3 Technology Upgrades

**Short Term (6 months):**
- Upgrade to Python 3.12
- Migrate to Pydantic v2 features
- Implement AsyncPG for faster DB queries

**Long Term (12 months):**
- Consider gRPC for internal services
- Evaluate service mesh (Istio/Linkerd)
- Implement distributed tracing (Jaeger)

---

## Appendix A: Deployment Checklist

### Local Development
- [ ] Docker Desktop installed
- [ ] Clone repository
- [ ] Copy .env.example to .env
- [ ] Set API keys in .env
- [ ] Run `docker-compose up -d`
- [ ] Verify health endpoint: `curl localhost:8000/health`
- [ ] Create test tenant
- [ ] Make test completion request

### Kubernetes Deployment
- [ ] Kubernetes cluster running (minikube/kind/cloud)
- [ ] kubectl configured
- [ ] Update k8s/secrets.yaml with actual secrets
- [ ] Apply manifests: `kubectl apply -f k8s/`
- [ ] Wait for pods to be ready
- [ ] Port-forward or access via LoadBalancer
- [ ] Verify all health checks passing
- [ ] Run integration tests

---

## Appendix B: Troubleshooting Guide

### Common Issues

**Issue:** Gateway returns 503 "All providers failed"
- Check: Provider API keys are valid
- Check: Internet connectivity from cluster
- Check: Provider health check endpoints

**Issue:** High latency on requests
- Check: Redis connection latency
- Check: Database query performance
- Check: Provider API latency
- Check: Pod resource limits

**Issue:** Rate limiting not working
- Check: Redis connection
- Check: Redis memory usage
- Check: Rate limit configuration in DB

---

**Document History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 2026 | Infrastructure Team | Initial release |

