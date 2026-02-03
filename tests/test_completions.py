"""Test the completions endpoint with mocked providers and Redis."""

from unittest.mock import AsyncMock, patch

from src.providers.base import LLMResponse


def test_missing_api_key(client):
    """Request without API key should return 401."""
    response = client.post(
        "/api/v1/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 401


def test_invalid_api_key(client):
    """Request with wrong API key should return 401."""
    response = client.post(
        "/api/v1/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"X-API-Key": "bad-key"},
    )
    assert response.status_code == 401


def test_successful_completion(client, test_tenant, mock_redis):
    """Mock a provider and verify end-to-end completion flow."""
    fake_response = LLMResponse(
        content="Hello! How can I help?",
        model="gpt-4",
        prompt_tokens=10,
        completion_tokens=8,
        total_tokens=18,
        finish_reason="stop",
        provider="openai",
    )

    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=fake_response)
    mock_provider.calculate_cost = lambda pt, ct: (pt + ct) / 1000 * 0.002

    with patch(
        "src.api.completions.ProviderFactory.get_provider",
        return_value=mock_provider,
    ):
        response = client.post(
            "/api/v1/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers={"X-API-Key": "test-api-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is False
    assert data["response"]["content"] == "Hello! How can I help?"
    assert data["response"]["provider"] == "openai"
    assert "cost" in data
    assert "latency_ms" in data
    assert data["rate_limit_remaining"] == 99


def test_cache_hit(client, test_tenant, mock_redis):
    """When cache returns data, should return cached response."""
    mock_redis.get_cache = AsyncMock(
        return_value={
            "content": "Cached answer",
            "model": "gpt-4",
            "provider": "openai",
        }
    )

    response = client.post(
        "/api/v1/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is True
    assert data["response"]["content"] == "Cached answer"


def test_rate_limit_exceeded(client, test_tenant, mock_redis):
    """When rate limit is exceeded, should return 429."""
    mock_redis.check_rate_limit = AsyncMock(return_value=(False, 0))

    response = client.post(
        "/api/v1/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 429
