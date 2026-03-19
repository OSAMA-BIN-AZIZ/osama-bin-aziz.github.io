from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from .models import SubscriptionStatus, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime


class PlanResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str
    price_monthly: float
    traffic_gb: int
    device_limit: int


class SubscriptionCreateRequest(BaseModel):
    plan_id: int
    server_region: str = Field(min_length=2, max_length=32, default="sg")
    notes: str | None = Field(default=None, max_length=500)


class SubscriptionResponse(BaseModel):
    id: int
    plan_id: int
    status: SubscriptionStatus
    token_version: int
    server_region: str
    created_at: datetime
    secure_link: str | None = None


class AdminStatsResponse(BaseModel):
    users: int
    subscriptions: int
    active_subscriptions: int
