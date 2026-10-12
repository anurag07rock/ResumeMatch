from datetime import datetime
import re
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class UserRegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(..., max_length=255, description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Plaintext password meeting complexity criteria (uppercase, digits, special characters)",
    )
    full_name: Optional[str] = Field(default=None, max_length=255, description="Full name of user")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        cleaned = v.lower().strip()
        if not EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid email address format.")
        return cleaned


class UserLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(..., max_length=255, description="User email address")
    password: str = Field(..., min_length=1, description="Account password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        cleaned = v.lower().strip()
        if not EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid email address format.")
        return cleaned


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str = Field(..., description="Cryptographically signed Bearer access token")
    refresh_token: str = Field(..., description="Cryptographically signed refresh token")
    token_type: str = Field(default="bearer", description="Token authentication scheme")
    expires_in: Optional[int] = Field(default=None, description="Access token expiry duration in seconds")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID = Field(..., description="Primary user UUID")
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = Field(default=None, description="User full name")
    is_active: bool = Field(default=True, description="Account active status")
    created_at: datetime = Field(..., description="Account creation timestamp")
