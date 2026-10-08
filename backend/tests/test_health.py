import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_health_check_returns_healthy_status() -> None:
    """
    Verify that the GET /health endpoint returns 200 OK and healthy status payload.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "resumematch-backend"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"
