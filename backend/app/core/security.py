from datetime import UTC, datetime, timedelta
import re
from typing import Any, Dict, Optional, Union
import bcrypt
import jwt
from app.core.config import settings

class SecurityError(Exception):
    """Base exception for security operations."""
    pass

class TokenError(SecurityError):
    """Base exception for JWT processing failures."""
    pass

class TokenExpiredError(TokenError):
    """Raised when a JWT has expired."""
    pass

class InvalidTokenError(TokenError):
    """Raised when a JWT is invalid, malformed, or tampered with."""
    pass

class PasswordComplexityError(SecurityError, ValueError):
    """Raised when a password fails complexity requirements."""
    pass


def validate_password_strength(password: str) -> None:
    """
    Validates minimum password requirements per docs/SECURITY.md:
    - At least 8 characters in length
    - Contains at least one uppercase letter
    - Contains at least one number
    - Contains at least one special symbol
    """
    if not password or len(password) < 8:
        raise PasswordComplexityError("Password must be at least 8 characters long.")
    if len(password.encode("utf-8")) > 72:
        raise PasswordComplexityError("Password must not exceed 72 bytes.")
    if not re.search(r"[A-Z]", password):
        raise PasswordComplexityError("Password must contain at least one uppercase letter.")
    if not re.search(r"[0-9]", password):
        raise PasswordComplexityError("Password must contain at least one numeric digit.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\/`~]", password):
        raise PasswordComplexityError("Password must contain at least one special symbol.")


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using bcrypt with work factor >= 12.
    Validates password complexity before hashing.
    """
    validate_password_strength(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored bcrypt hash.
    Safely returns False on invalid formats or hash mismatches.
    """
    if not password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generates a cryptographically signed JWT access token.
    Payload:
        - sub: str(subject)
        - exp: UTC expiration datetime
        - type: "access"
    """
    now = datetime.now(UTC)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generates a cryptographically signed JWT refresh token.
    Payload:
        - sub: str(subject)
        - exp: UTC expiration datetime
        - type: "refresh"
    """
    now = datetime.now(UTC)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token.
    Raises:
        - TokenExpiredError: If the token is expired
        - InvalidTokenError: If the token is invalid or malformed
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired.") from e
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}") from e
