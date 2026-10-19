import os
from typing import Any, List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET_KEYS = {
    "change-this-to-a-super-secret-high-entropy-key-in-production",
    "secret",
    "secret_key",
    "changeme",
    "password",
    "admin",
    "12345678",
    "default",
    "test",
}

INSECURE_DB_PASSWORDS = {
    "resumematch_password",
    "password",
    "postgres",
    "admin",
    "root",
    "123456",
}


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
    SECRET_KEY: str = Field(
        default="change-this-to-a-super-secret-high-entropy-key-in-production",
        description="Stateless JWT signing secret. Must be high-entropy and >= 32 characters in production.",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database Configuration
    DATABASE_PROFILE: str = Field(default="postgres_pgvector")
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Async PostgreSQL connection string e.g. postgresql+asyncpg://user:pass@host:port/db",
    )

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "resumematch_user"
    POSTGRES_PASSWORD: str = Field(
        default="resumematch_password",
        description="PostgreSQL password. Fallback default is strictly permitted only in development.",
    )
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

    # Ingestion & Document Limits (per docs/SECURITY.md)
    MAX_PDF_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB ceiling
    MAX_PDF_PAGES: int = 10                     # 10 pages ceiling

    # Scoring Weights (Canonical Calibrations: Semantic 50%, Skills 30%, Experience 10%, Education 10%)
    WEIGHT_SEMANTIC: float = 0.50
    WEIGHT_SKILLS: float = 0.30
    WEIGHT_EXPERIENCE: float = 0.10
    WEIGHT_EDUCATION: float = 0.10

    # CORS Whitelist (JSON list string or comma-separated string permitted in env)
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Rate Limiting Configuration (per Phase 3 Task 6)
    RATE_LIMITING_ENABLED: bool = True
    AUTH_RATE_LIMIT: str = "5/minute"
    AI_RATE_LIMIT: str = "10/minute"
    DEFAULT_RATE_LIMIT: str = "60/minute"

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
        password = self.POSTGRES_PASSWORD or ""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def get_test_database_url(self) -> str:
        """
        Returns the resolved asynchronous database connection URL for the test suite.
        Must strictly target the dedicated test database. Never logs credentials.
        """
        if self.TEST_DATABASE_URL:
            return self.TEST_DATABASE_URL
        password = self.POSTGRES_PASSWORD or ""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{password}"
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

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_and_validate_cors_origins(cls, v: Any) -> List[str]:
        origins: List[str] = []
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        origins = [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    origins = [item.strip() for item in v.strip("[]").split(",") if item.strip()]
            else:
                origins = [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, (list, tuple)):
            origins = [str(item).strip() for item in v if str(item).strip()]
        else:
            raise ValueError("BACKEND_CORS_ORIGINS must be a list of origin URLs or a comma-separated string.")

        for origin in origins:
            if origin == "*":
                raise ValueError(
                    "Security violation: Wildcard '*' in BACKEND_CORS_ORIGINS is strictly prohibited "
                    "when credentialed requests are allowed."
                )
            if not (origin.startswith("http://") or origin.startswith("https://")):
                raise ValueError(
                    f"Invalid CORS origin '{origin}': Origins must include protocol ('http://' or 'https://')."
                )

        return origins

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        is_prod = self.ENVIRONMENT.lower() == "production"
        if is_prod:
            # 1. SECRET_KEY validation
            secret = (self.SECRET_KEY or "").strip()
            if not secret or secret in INSECURE_SECRET_KEYS:
                raise ValueError(
                    "Production security violation: Insecure or default SECRET_KEY detected. "
                    "A strong, high-entropy SECRET_KEY (minimum 32 characters) must be explicitly configured in production."
                )
            if len(secret) < 32:
                raise ValueError(
                    f"Production security violation: SECRET_KEY is too weak ({len(secret)} characters). "
                    "A minimum of 32 characters is required for HMAC-SHA256 production cryptographic signing."
                )

            # 2. Database credentials validation
            if self.DATABASE_PROFILE == "local_sqlite":
                raise ValueError(
                    "Production configuration violation: 'local_sqlite' is not permitted in production. "
                    "DATABASE_PROFILE must be 'postgres_pgvector'."
                )

            if self.DATABASE_URL:
                from urllib.parse import urlparse
                parsed = urlparse(self.DATABASE_URL)
                db_password = parsed.password or ""
                if not db_password or db_password in INSECURE_DB_PASSWORDS:
                    raise ValueError(
                        "Production database security violation: Insecure or placeholder database password in DATABASE_URL. "
                        "An explicitly supplied, strong database password is required in production."
                    )
            else:
                db_password = (self.POSTGRES_PASSWORD or "").strip()
                if not db_password or db_password in INSECURE_DB_PASSWORDS:
                    raise ValueError(
                        "Production database security violation: Insecure or default POSTGRES_PASSWORD detected. "
                        "An explicitly supplied, strong database password is required in production."
                    )
                if not self.POSTGRES_USER or not self.POSTGRES_USER.strip():
                    raise ValueError(
                        "Production database security violation: POSTGRES_USER must be non-empty in production."
                    )

            # 3. CORS origin validation
            if not self.BACKEND_CORS_ORIGINS:
                raise ValueError(
                    "Production networking violation: BACKEND_CORS_ORIGINS cannot be empty in production."
                )

        return self


settings = Settings()
