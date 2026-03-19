from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import ConfigError, get_settings
from .database import Base, SessionLocal, engine, get_db
from .models import AuditLog, Plan, Subscription, SubscriptionStatus, User, UserRole
from .schemas import (
    AdminStatsResponse,
    LoginRequest,
    PlanResponse,
    RegisterRequest,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    TokenResponse,
    UserResponse,
)
from .security import (
    create_access_token,
    create_subscription_token,
    decode_access_token,
    decode_subscription_token,
    hash_password,
    verify_password,
)

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


def _seed_default_plans(db: Session) -> bool:
    if db.scalar(select(Plan.id).limit(1)):
        return False

    db.add_all(
        [
            Plan(code="starter", name="Starter", description="个人轻量套餐", price_monthly=6.9, traffic_gb=120, device_limit=3),
            Plan(code="pro", name="Pro", description="家庭/多设备套餐", price_monthly=12.9, traffic_gb=500, device_limit=8),
            Plan(code="ultra", name="Ultra", description="企业订阅与专属线路", price_monthly=29.9, traffic_gb=2048, device_limit=20),
        ]
    )
    return True


def _seed_bootstrap_admin(db: Session) -> bool:
    has_admin = db.scalar(select(User.id).where(User.email == settings.admin_email))
    if has_admin:
        return False
    if not settings.bootstrap_admin_password:
        raise ConfigError(
            "BOOTSTRAP_ADMIN_PASSWORD must be set before the first startup so a new deployment does not ship with a shared admin password"
        )

    password_hash, password_salt = hash_password(settings.bootstrap_admin_password)
    db.add(
        User(
            email=settings.admin_email,
            password_hash=password_hash,
            password_salt=password_salt,
            role=UserRole.admin,
        )
    )
    return True


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        created_admin = _seed_bootstrap_admin(db)
        seeded_plans = _seed_default_plans(db)
        if created_admin or seeded_plans:
            db.commit()


@app.get("/healthz")
def healthcheck(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}



def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.removeprefix("Bearer ").strip()



def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    payload = decode_access_token(token)
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user



def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


@app.post("/api/v1/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    exists = db.scalar(select(User).where(User.email == payload.email.lower()))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    password_hash, password_salt = hash_password(payload.password)
    user = User(email=payload.email.lower(), password_hash=password_hash, password_salt=password_salt)
    db.add(user)
    db.add(AuditLog(actor_email=user.email, action="register", detail="Self-service registration"))
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id, user.email))


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash, user.password_salt):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    db.add(AuditLog(actor_email=user.email, action="login", detail="Password login"))
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.email))


@app.get("/api/v1/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user, from_attributes=True)


@app.get("/api/v1/plans", response_model=list[PlanResponse])
def list_plans(db: Session = Depends(get_db)) -> list[PlanResponse]:
    plans = db.scalars(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_monthly)).all()
    return [PlanResponse.model_validate(plan, from_attributes=True) for plan in plans]


@app.post("/api/v1/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    payload: SubscriptionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    plan = db.get(Plan, payload.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    subscription = Subscription(
        user_id=current_user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.active,
        server_region=payload.server_region.lower(),
        notes=payload.notes,
    )
    db.add(subscription)
    db.add(AuditLog(actor_email=current_user.email, action="create_subscription", detail=f"plan={plan.code}"))
    db.commit()
    db.refresh(subscription)
    secure_link = f"/subscribe/{create_subscription_token(subscription.id, subscription.token_version, subscription.server_region)}"
    return SubscriptionResponse.model_validate({
        "id": subscription.id,
        "plan_id": subscription.plan_id,
        "status": subscription.status,
        "token_version": subscription.token_version,
        "server_region": subscription.server_region,
        "created_at": subscription.created_at,
        "secure_link": secure_link,
    })


@app.get("/api/v1/subscriptions/mine", response_model=list[SubscriptionResponse])
def list_my_subscriptions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SubscriptionResponse]:
    rows = db.scalars(select(Subscription).where(Subscription.user_id == current_user.id).order_by(Subscription.created_at.desc())).all()
    items: list[SubscriptionResponse] = []
    for row in rows:
        items.append(
            SubscriptionResponse.model_validate(
                {
                    "id": row.id,
                    "plan_id": row.plan_id,
                    "status": row.status,
                    "token_version": row.token_version,
                    "server_region": row.server_region,
                    "created_at": row.created_at,
                    "secure_link": f"/subscribe/{create_subscription_token(row.id, row.token_version, row.server_region)}",
                }
            )
        )
    return items


@app.post("/api/v1/subscriptions/{subscription_id}/rotate-link", response_model=SubscriptionResponse)
def rotate_subscription_link(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    subscription = db.scalar(select(Subscription).where(Subscription.id == subscription_id, Subscription.user_id == current_user.id))
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    subscription.token_version += 1
    db.add(AuditLog(actor_email=current_user.email, action="rotate_subscription_link", detail=f"subscription_id={subscription.id}"))
    db.commit()
    db.refresh(subscription)
    return SubscriptionResponse.model_validate(
        {
            "id": subscription.id,
            "plan_id": subscription.plan_id,
            "status": subscription.status,
            "token_version": subscription.token_version,
            "server_region": subscription.server_region,
            "created_at": subscription.created_at,
            "secure_link": f"/subscribe/{create_subscription_token(subscription.id, subscription.token_version, subscription.server_region)}",
        }
    )


@app.get("/subscribe/{signed_token}")
def get_subscription_payload(signed_token: str, db: Session = Depends(get_db)) -> dict[str, object]:
    payload = decode_subscription_token(signed_token)
    subscription = db.get(Subscription, int(payload["sid"]))
    if not subscription or subscription.status != SubscriptionStatus.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription unavailable")
    if subscription.token_version != int(payload["ver"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Subscription link has been rotated")

    plan = db.get(Plan, subscription.plan_id)
    return {
        "subscription_id": subscription.id,
        "region": subscription.server_region,
        "plan": plan.code if plan else None,
        "config": {
            "protocol": "vless",
            "tls": True,
            "transport": "reality",
            "host": f"edge-{subscription.server_region}.example.net",
        },
    }


@app.get("/api/v1/admin/stats", response_model=AdminStatsResponse)
def admin_stats(_: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> AdminStatsResponse:
    users = db.scalar(select(func.count(User.id))) or 0
    subscriptions = db.scalar(select(func.count(Subscription.id))) or 0
    active_subscriptions = db.scalar(select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.active)) or 0
    return AdminStatsResponse(users=users, subscriptions=subscriptions, active_subscriptions=active_subscriptions)
