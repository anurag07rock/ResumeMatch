from datetime import UTC, datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from pydantic import BaseModel, ConfigDict, Field

DataType = TypeVar("DataType")

class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Machine-readable standardized error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Union[Dict[str, Any], List[Any], str]] = Field(
        default=None,
        description="Structured contextual diagnostic details or validation error list"
    )

class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    error: ErrorDetail
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: Optional[str] = Field(default=None)

# Alias for compatibility with prompt specification
ErrorEnvelope = ErrorResponse

class SuccessResponse(BaseModel, Generic[DataType]):
    model_config = ConfigDict(extra="ignore")

    data: DataType

# Alias
ResponseEnvelope = SuccessResponse
