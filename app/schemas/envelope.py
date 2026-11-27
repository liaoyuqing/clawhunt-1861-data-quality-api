"""Unified response envelope.

Every endpoint returns {code, message, data, request_id} so the dashboard shell can
share one error-handling path across modules.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: int = Field(default=0, description="0 means success, non-zero is a business error code")
    message: str = Field(default="ok")
    data: T | None = None
    request_id: str = Field(default="", description="Trace id echoed from the X-Request-Id header")


class ErrorBody(BaseModel):
    code: int
    message: str
    data: None = None
    request_id: str = ""
