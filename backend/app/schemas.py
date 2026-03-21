from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import ContentVisibility, SubscriptionStatus, UserRole


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r'^[a-z0-9_-]+$')
    name: str = Field(min_length=2, max_length=120)
    description: str = ''
    price_monthly: Decimal = Field(gt=0)
    currency: str = Field(default='USD', min_length=3, max_length=8)
    max_devices: int = Field(default=2, ge=1, le=50)
    includes_premium_content: bool = False
    is_active: bool = True


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str
    price_monthly: Decimal
    currency: str
    max_devices: int
    includes_premium_content: bool
    is_active: bool
    created_at: datetime


class SubscriptionCreate(BaseModel):
    user_id: int
    plan_id: int
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    start_date: date
    end_date: date
    external_reference: str | None = Field(default=None, max_length=120)


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    plan_id: int
    status: SubscriptionStatus
    start_date: date
    end_date: date
    external_reference: str | None
    created_at: datetime


class SecureContentCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=120, pattern=r'^[a-z0-9-]+$')
    title: str = Field(min_length=3, max_length=160)
    summary: str = ''
    body: str = Field(min_length=20)
    visibility: ContentVisibility = ContentVisibility.SUBSCRIBER
    is_published: bool = False


class SecureContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: str
    body: str
    visibility: ContentVisibility
    is_published: bool
    created_at: datetime
    updated_at: datetime


class DashboardMetrics(BaseModel):
    total_users: int
    active_subscriptions: int
    premium_articles: int
    published_articles: int
