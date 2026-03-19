from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=12, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=120)
    price_cents: int = Field(ge=0)
    billing_cycle_days: int = Field(default=30, ge=1, le=366)
    description: str = Field(min_length=5)
    is_active: bool = True


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    price_cents: int
    billing_cycle_days: int
    description: str
    is_active: bool


class SubscriptionCreate(BaseModel):
    plan_slug: str


class SubscriptionRead(BaseModel):
    id: int
    status: str
    starts_at: datetime
    ends_at: datetime
    plan: PlanRead

    model_config = ConfigDict(from_attributes=True)


class ContentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    slug: str = Field(min_length=3, max_length=255)
    summary: str = Field(min_length=8)
    body: str = Field(min_length=32)
    access_level: str = Field(default="subscriber", pattern="^(subscriber|admin)$")
    is_published: bool = True


class ContentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    slug: str
    summary: str
    access_level: str
    is_published: bool
    created_at: datetime


class ContentRead(ContentListItem):
    body: str
