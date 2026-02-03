"""Test tenant admin endpoints."""


def test_create_tenant(client):
    response = client.post(
        "/api/v1/admin/tenants",
        json={"name": "Acme Corp", "rate_limit": 50},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert data["rate_limit"] == 50
    assert data["api_key"].startswith("llm-gw-")
    assert data["tenant_id"]


def test_get_tenant_usage(client, test_tenant):
    response = client.get(f"/api/v1/admin/tenants/{test_tenant.id}/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == test_tenant.id
    assert data["period_days"] == 30
    assert isinstance(data["usage_by_provider"], list)
