from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import ContentVisibility, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class PlanCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_-]+$")
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=1000)
    price_cents: int = Field(ge=0)
    duration_days: int = Field(ge=1, le=3650)
    is_active: bool = True


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    description: str
    price_cents: int
    duration_days: int
    is_active: bool


class SubscriptionCreateRequest(BaseModel):
    user_id: int
    plan_id: int
    auto_renew: bool = False


class SubscriptionResponse(BaseModel):
    id: int
    plan_code: str
    plan_title: str
    starts_at: datetime
    expires_at: datetime
    auto_renew: bool
    is_active: bool


class ContentCreateRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=3, max_length=160)
    summary: str = Field(min_length=10, max_length=500)
    body: str = Field(min_length=10)
    visibility: ContentVisibility = ContentVisibility.public


class ContentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    summary: str
    visibility: ContentVisibility
    created_at: datetime
    updated_at: datetime


class ContentDetailResponse(ContentListResponse):
    body: str


class HealthResponse(BaseModel):
    app: str
    environment: str
    database: str
    remote_database_host: str
    secure_content_encryption: bool


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str
    detail: str
    ip_address: str | None
    created_at: datetime
