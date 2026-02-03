from prometheus_client import Counter, Gauge, Histogram

request_count = Counter(
    "llm_gateway_requests_total",
    "Total requests",
    ["tenant_id", "provider", "status"],
)

request_latency = Histogram(
    "llm_gateway_request_duration_seconds",
    "Request latency",
    ["provider"],
)

token_usage = Counter(
    "llm_gateway_tokens_total",
    "Total tokens used",
    ["tenant_id", "provider", "type"],
)

cost_total = Counter(
    "llm_gateway_cost_total",
    "Total cost in USD",
    ["tenant_id", "provider"],
)

cache_hits = Counter(
    "llm_gateway_cache_hits_total",
    "Cache hits",
    ["tenant_id"],
)

rate_limit_exceeded = Counter(
    "llm_gateway_rate_limit_exceeded_total",
    "Rate limit exceeded",
    ["tenant_id"],
)

active_requests = Gauge(
    "llm_gateway_active_requests",
    "Active requests",
    ["provider"],
)
