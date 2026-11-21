"""Request and response validation for the HTTPS backend."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class AIRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=24000)
    response_schema: dict[str, Any]
    image_base64: str | None = Field(default=None, max_length=8_500_000)
    image_mime_type: Literal["image/png", "image/jpeg"] | None = None


class ProfileRequest(BaseModel):
    profile: dict[str, Any]


class OpportunitySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    career: str = Field(default="", max_length=120)
    category: Literal["college", "event", "internship", "summer_program", "research", "other"] = "other"
    location: str = Field(default="", max_length=120)
    education_level: str = Field(default="", max_length=80)
    limit: int = Field(default=10, ge=1, le=20)


class OpportunitySaveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    source_url: str = Field(min_length=8, max_length=2048)
    source_name: str = Field(default="", max_length=200)
    category: str = Field(default="other", max_length=80)
    location: str | None = Field(default=None, max_length=200)
    deadline: str | None = Field(default=None, max_length=100)
    eligibility: str = Field(default="Not verified; check the official source.", max_length=500)
    retrieved_at: datetime | None = None


class OpportunityStatusRequest(BaseModel):
    application_status: Literal["Saved", "Considering", "Applied", "Not pursuing"]


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)
