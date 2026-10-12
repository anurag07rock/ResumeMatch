from app.api.v1.auth import router as auth_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.matches import router as matches_router
from app.api.v1.resumes import router as resumes_router

__all__ = ["auth_router", "resumes_router", "jobs_router", "matches_router"]
