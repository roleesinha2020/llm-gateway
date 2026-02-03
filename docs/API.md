# LLM Gateway API Documentation

## Authentication

All requests require an API key in the header:
```
X-API-Key: your-api-key
```

## Endpoints

### GET /health

Health check endpoint. No authentication required.

**Response:**
```json
{"status": "healthy", "service": "llm-gateway"}
```

---

### POST /api/v1/completions

Create a completion request. Routes to the first available provider with automatic fallback.

**Request Body:**
```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

**Response (200):**
```json
{
  "cached": false,
  "response": {
    "content": "Hello! How can I help you?",
    "model": "gpt-4",
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18,
    "finish_reason": "stop",
    "provider": "openai"
  },
  "cost": 0.000036,
  "latency_ms": 1250,
  "rate_limit_remaining": 99
}
```

**Error Responses:**
- `401` — Missing or invalid API key
- `429` — Rate limit exceeded (includes `Retry-After: 60` header)
- `503` — All providers failed

---

### POST /api/v1/admin/tenants

Create a new tenant.

**Query Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | string | required | Tenant name |
| `rate_limit` | int | 100 | Max requests per minute |
| `monthly_budget` | float | null | Monthly budget cap in USD |

**Response (200):**
```json
{
  "tenant_id": "uuid",
  "name": "My App",
  "api_key": "llm-gw-...",
  "rate_limit": 100
}
```

---

### GET /api/v1/admin/tenants/{tenant_id}/usage

Get usage statistics for a tenant over a time period.

**Query Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `days` | int | 30 | Lookback period in days |

**Response (200):**
```json
{
  "tenant_id": "uuid",
  "period_days": 30,
  "usage_by_provider": [
    {
      "provider": "openai",
      "requests": 150,
      "tokens": 45000,
      "cost": 0.09,
      "avg_latency_ms": 1100.5
    }
  ]
}
```

---

### GET /metrics

Prometheus metrics endpoint (no authentication). Exposes:
- `llm_gateway_requests_total` — request count by tenant, provider, status
- `llm_gateway_request_duration_seconds` — latency histogram by provider
- `llm_gateway_tokens_total` — token usage by tenant, provider, type
- `llm_gateway_cost_total` — cumulative cost by tenant, provider
- `llm_gateway_cache_hits_total` — cache hit count by tenant
- `llm_gateway_rate_limit_exceeded_total` — rate limit violations by tenant
- `llm_gateway_active_requests` — in-flight requests by provider
