import pytest
from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient
from app.db.session import get_db
from app.main import app

@pytest.mark.asyncio
async def test_health_check_returns_healthy_status() -> None:
    """
    Verify that the GET /health endpoint returns 200 OK and healthy status payload
    without requiring external database connectivity.
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

@pytest.mark.asyncio
async def test_database_health_check_reports_unavailable_when_db_down() -> None:
    """
    Verify that GET /health/db returns 503 Service Unavailable when the database
    is offline.  Uses a dependency override to deterministically simulate a
    connection failure regardless of the host's actual PostgreSQL state.
    """

    async def _broken_db():
        """Yields a mock session whose execute() raises, simulating a dead DB."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = ConnectionRefusedError(
            "simulated: database is offline"
        )
        yield mock_session

    app.dependency_overrides[get_db] = _broken_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/health/db")

        assert response.status_code == 503
        data = response.json()
        assert "Database connection unavailable" in data["detail"]
    finally:
        # Always restore the real dependency, even if the test fails.
        app.dependency_overrides.pop(get_db, None)

