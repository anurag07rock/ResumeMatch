from datetime import UTC, datetime, timedelta
import uuid
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.core.config import Settings, settings
from app.core.dependencies import verify_tenant_ownership
from app.core.security import (
    InvalidTokenError,
    PasswordComplexityError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.models.user import User


class TestPasswordSecurity:
    """Tests password complexity, bcrypt hashing, and verification."""

    def test_validate_password_strength_valid(self):
        # Meets: length >= 8, uppercase, digit, special char
        validate_password_strength("StrongP@ssw0rd")
        validate_password_strength("MySecure#123")

    def test_validate_password_strength_too_short(self):
        with pytest.raises(PasswordComplexityError, match="at least 8 characters"):
            validate_password_strength("Sh0rt!")

    def test_validate_password_strength_no_uppercase(self):
        with pytest.raises(PasswordComplexityError, match="uppercase"):
            validate_password_strength("lowercase123!@#")

    def test_validate_password_strength_no_digits(self):
        with pytest.raises(PasswordComplexityError, match="numeric digit"):
            validate_password_strength("NoDigitsHere!@#")

    def test_validate_password_strength_no_symbols(self):
        with pytest.raises(PasswordComplexityError, match="special symbol"):
            validate_password_strength("NoSymbols12345")

    def test_hash_password_produces_bcrypt_hash(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert hashed != password

    def test_verify_password_success(self):
        password = "ValidSecret999$"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_wrong_password(self):
        password = "ValidSecret999$"
        hashed = hash_password(password)
        assert verify_password("WrongPassword999$", hashed) is False

    def test_verify_password_empty_or_invalid(self):
        assert verify_password("", "$2b$12$invalidhash") is False
        assert verify_password("Password123!", "") is False
        assert verify_password("Password123!", "not-a-valid-hash") is False


class TestJWTSecurity:
    """Tests JWT creation, payload structure, decoding, and expiration enforcement."""

    def test_create_access_token(self):
        user_id = str(uuid.uuid4())
        token = create_access_token(subject=user_id)
        assert isinstance(token, str)

        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_refresh_token(self):
        user_id = str(uuid.uuid4())
        token = create_refresh_token(subject=user_id)
        assert isinstance(token, str)

        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_token_expiration_rejected(self):
        user_id = str(uuid.uuid4())
        # Negative delta => already expired
        expired_token = create_access_token(
            subject=user_id,
            expires_delta=timedelta(seconds=-10),
        )
        with pytest.raises(TokenExpiredError, match="expired"):
            decode_token(expired_token)

    def test_invalid_token_rejected(self):
        with pytest.raises(InvalidTokenError):
            decode_token("completely.invalid.token")

    def test_tampered_token_rejected(self):
        user_id = str(uuid.uuid4())
        valid_token = create_access_token(subject=user_id)
        parts = valid_token.split(".")
        # Tamper payload part
        tampered_token = f"{parts[0]}.eyJob2d1cyI6ICJkYXRhIn0.{parts[2]}"
        with pytest.raises(InvalidTokenError):
            decode_token(tampered_token)


class TestTenantOwnership:
    """Tests tenant isolation guard."""

    def test_verify_tenant_ownership_owner_allowed(self):
        user_id = uuid.uuid4()
        user = User(id=user_id, email="user@example.com", is_superuser=False)
        # Should not raise
        verify_tenant_ownership(user_id, user)

    def test_verify_tenant_ownership_superuser_allowed_for_any_resource(self):
        admin_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        admin = User(id=admin_id, email="admin@example.com", is_superuser=True)
        # Should not raise
        verify_tenant_ownership(other_user_id, admin)

    def test_verify_tenant_ownership_other_user_forbidden(self):
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        user1 = User(id=user1_id, email="user1@example.com", is_superuser=False)
        with pytest.raises(HTTPException) as exc_info:
            verify_tenant_ownership(user2_id, user1)
        assert exc_info.value.status_code == 403


class TestProductionConfigValidation:
    """Tests production security validations, credential requirements, and CORS parsing."""

    def test_development_defaults_allowed(self):
        cfg = Settings(
            ENVIRONMENT="development",
            _env_file=None,
        )
        assert cfg.ENVIRONMENT == "development"
        assert cfg.SECRET_KEY.startswith("change-this")
        assert cfg.POSTGRES_PASSWORD == "resumematch_password"
        assert "http://localhost:3000" in cfg.BACKEND_CORS_ORIGINS

    def test_production_rejects_default_secret_key(self):
        with pytest.raises(ValidationError, match="Insecure or default SECRET_KEY detected"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="change-this-to-a-super-secret-high-entropy-key-in-production",
                POSTGRES_PASSWORD="a-very-strong-production-db-password-1234",
                _env_file=None,
            )

    def test_production_rejects_short_secret_key(self):
        with pytest.raises(ValidationError, match="SECRET_KEY is too weak"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="short-secret-key-too-brief",
                POSTGRES_PASSWORD="a-very-strong-production-db-password-1234",
                _env_file=None,
            )

    def test_production_rejects_default_postgres_password(self):
        with pytest.raises(ValidationError, match="Insecure or default POSTGRES_PASSWORD detected"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                POSTGRES_PASSWORD="resumematch_password",
                _env_file=None,
            )

    def test_production_rejects_insecure_database_url_password(self):
        with pytest.raises(ValidationError, match="Insecure or placeholder database password in DATABASE_URL"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                DATABASE_URL="postgresql+asyncpg://prod_user:resumematch_password@db:5432/resumematch",
                _env_file=None,
            )

    def test_production_rejects_sqlite_profile(self):
        with pytest.raises(ValidationError, match="'local_sqlite' is not permitted in production"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                POSTGRES_PASSWORD="a-very-strong-production-db-password-1234",
                DATABASE_PROFILE="local_sqlite",
                _env_file=None,
            )

    def test_cors_rejects_wildcard(self):
        with pytest.raises(ValidationError, match="Wildcard '\\*' in BACKEND_CORS_ORIGINS is strictly prohibited"):
            Settings(
                BACKEND_CORS_ORIGINS=["*"],
                _env_file=None,
            )

    def test_cors_origin_parsing_from_comma_string(self):
        cfg = Settings(
            BACKEND_CORS_ORIGINS="https://app.resumematch.ai, https://admin.resumematch.ai",
            _env_file=None,
        )
        assert cfg.BACKEND_CORS_ORIGINS == [
            "https://app.resumematch.ai",
            "https://admin.resumematch.ai",
        ]

    def test_cors_origin_parsing_from_json_string(self):
        cfg = Settings(
            BACKEND_CORS_ORIGINS='["https://app.resumematch.ai", "https://api.resumematch.ai"]',
            _env_file=None,
        )
        assert cfg.BACKEND_CORS_ORIGINS == [
            "https://app.resumematch.ai",
            "https://api.resumematch.ai",
        ]

    def test_cors_rejects_origin_without_protocol(self):
        with pytest.raises(ValidationError, match="Origins must include protocol"):
            Settings(
                BACKEND_CORS_ORIGINS=["app.resumematch.ai"],
                _env_file=None,
            )

    def test_production_valid_configuration_accepted(self):
        valid_secret = "k" * 32
        cfg = Settings(
            ENVIRONMENT="production",
            SECRET_KEY=valid_secret,
            POSTGRES_USER="prod_user",
            POSTGRES_PASSWORD="custom_prod_db_pass_12345!",
            BACKEND_CORS_ORIGINS=["https://app.resumematch.ai"],
            _env_file=None,
        )
        assert cfg.ENVIRONMENT == "production"
        assert cfg.SECRET_KEY == valid_secret
        assert cfg.POSTGRES_PASSWORD == "custom_prod_db_pass_12345!"
        assert cfg.BACKEND_CORS_ORIGINS == ["https://app.resumematch.ai"]
        assert cfg.get_masked_url().startswith("postgresql+asyncpg://prod_user:***@")

