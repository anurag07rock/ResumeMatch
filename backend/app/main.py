from fastapi import FastAPI
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str

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
