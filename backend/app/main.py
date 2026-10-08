from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str

class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
    details: str

app = FastAPI(
    title="ResumeMatch API",
    description="Explainable AI-Powered Resume-to-Job Matching Platform",
    version="0.1.0",
)

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Service health check endpoint indicating that the FastAPI backend is running.
    """
    return HealthResponse(
        status="healthy",
        service="resumematch-backend",
        version="0.1.0",
        environment="development",
    )

@app.get("/health/db", response_model=DatabaseHealthResponse, tags=["Health"])
async def database_health_check(
    db: AsyncSession = Depends(get_db)
) -> DatabaseHealthResponse:
    """
    Database readiness check endpoint verifying active connectivity to the database.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        val = result.scalar()
        if val == 1:
            return DatabaseHealthResponse(
                status="healthy",
                database="connected",
                details="Database connection verified successfully",
            )
        raise Exception("Unexpected query result from database")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection unavailable: {str(exc)}",
        )
