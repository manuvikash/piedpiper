"""Models for Browserbase validation results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    worker_id: str
    passed: bool
    score: float = 0.0
    checks: list[ValidationCheck] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    logs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
