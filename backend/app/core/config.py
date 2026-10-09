import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Settings
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "ResumeMatch"
    API_V1_STR: str = "/api/v1"
    BACKEND_URL: str = "http://localhost:8000"
    SECRET_KEY: str = Field(default="change-this-to-a-super-secret-high-entropy-key-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database Configuration
    DATABASE_PROFILE: str = Field(default="postgres_pgvector")
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Async PostgreSQL connection string e.g. postgresql+asyncpg://user:pass@host:port/db"
    )

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "resumematch_user"
    POSTGRES_PASSWORD: str = "resumematch_password"
    POSTGRES_DB: str = "resumematch"
    POSTGRES_TEST_DB: str = "resumematch_test"

    TEST_DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Async PostgreSQL connection string for test suite",
    )

    # Optional Local Test/Fallback
    SQLITE_DB_PATH: str = "sqlite+aiosqlite:///./resumematch.db"

    # AI / Embedding Model Settings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    MAX_TOKEN_CHUNK_SIZE: int = 512
    CHUNK_STRIDE: int = 128

    # Scoring Weights
    WEIGHT_SKILLS: float = 0.40
    WEIGHT_SEMANTIC: float = 0.35
    WEIGHT_EXPERIENCE: float = 0.15
    WEIGHT_EDUCATION: float = 0.10

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    def get_database_url(self) -> str:
        """
        Returns the resolved asynchronous database connection URL.
        Never logs credentials.
        """
        if self.DATABASE_PROFILE == "local_sqlite":
            return self.SQLITE_DB_PATH
        
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        # Build PostgreSQL asyncpg URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def get_test_database_url(self) -> str:
        """
        Returns the resolved asynchronous database connection URL for the test suite.
        Must strictly target the dedicated test database. Never logs credentials.
        """
        if self.TEST_DATABASE_URL:
            return self.TEST_DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_TEST_DB}"
        )

    def get_masked_url(self, url: Optional[str] = None) -> str:
        """
        Returns the database URL with the password masked.
        """
        target = url or self.get_database_url()
        from urllib.parse import urlparse, urlunparse
        try:
            parsed = urlparse(target)
            if parsed.password:
                netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
                return urlunparse(parsed._replace(netloc=netloc))
            return target
        except Exception:
            return "postgresql+asyncpg://***"

    @field_validator("DATABASE_PROFILE")
    @classmethod
    def validate_database_profile(cls, v: str) -> str:
        allowed = {"postgres_pgvector", "local_sqlite"}
        if v not in allowed:
            raise ValueError(f"Invalid DATABASE_PROFILE '{v}'. Must be one of {allowed}")
        return v

settings = Settings()
