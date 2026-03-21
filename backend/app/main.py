from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db
from .models import AuditEvent, ContentItem, ContentVisibility, Subscription, SubscriptionPlan, User, UserRole
from .schemas import (
    AuditResponse,
    ContentCreateRequest,
    ContentDetailResponse,
    ContentListResponse,
    HealthResponse,
    LoginRequest,
    PlanCreateRequest,
    PlanResponse,
    RegisterRequest,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    TokenResponse,
    UserResponse,
)
from .security import create_access_token, decode_access_token, decrypt_text, encrypt_text, hash_password, verify_password

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="支持远程 PostgreSQL、订阅鉴权、内容加密和审计日志的安全后台 API。",
)
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        admin = db.query(User).filter(User.email == settings.initial_admin_email).first()
        if not admin:
            db.add(
                User(
                    email=settings.initial_admin_email,
                    full_name="Initial Admin",
                    password_hash=hash_password(settings.initial_admin_password),
                    role=UserRole.admin,
                )
            )
            db.commit()


@app.get("/health", response_model=HealthResponse)
def healthcheck(db: Session = Depends(get_db)) -> HealthResponse:
    db.execute(text("SELECT 1"))
    database_host = urlparse(settings.database_url.replace("postgresql+psycopg", "postgresql")).hostname or "unknown"
    return HealthResponse(
        app=settings.app_name,
        environment=settings.app_env,
        database="ok",
        remote_database_host=database_host,
        secure_content_encryption=settings.fernet_secret != "REPLACE_WITH_FERNET_KEY",
    )


@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> UserResponse:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已注册")

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.member,
    )
    db.add(user)
    db.flush()
    db.add(AuditEvent(user_id=user.id, action="register", detail="新用户注册", ip_address=request.client.host if request.client else None))
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")

    token, expires_in = create_access_token(subject=user.email, role=user.role.value)
    db.add(AuditEvent(user_id=user.id, action="login", detail="用户登录成功", ip_address=request.client.host if request.client else None))
    db.commit()
    return TokenResponse(access_token=token, expires_in=expires_in)



def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    return user



def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user



def has_active_subscription(user: User) -> bool:
    now = datetime.now(UTC).replace(tzinfo=None)
    return any(subscription.expires_at >= now for subscription in user.subscriptions)


@app.get("/api/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@app.get("/api/me/subscriptions", response_model=list[SubscriptionResponse])
def get_my_subscriptions(current_user: User = Depends(get_current_user)) -> list[SubscriptionResponse]:
    now = datetime.now(UTC).replace(tzinfo=None)
    return [
        SubscriptionResponse(
            id=item.id,
            plan_code=item.plan.code,
            plan_title=item.plan.title,
            starts_at=item.starts_at,
            expires_at=item.expires_at,
            auto_renew=item.auto_renew,
            is_active=item.expires_at >= now,
        )
        for item in current_user.subscriptions
    ]


@app.get("/api/content", response_model=list[ContentListResponse])
def list_content(db: Session = Depends(get_db)) -> list[ContentListResponse]:
    items = db.query(ContentItem).order_by(ContentItem.created_at.desc()).all()
    return [ContentListResponse.model_validate(item) for item in items]


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    return db.query(User).filter(User.email == payload["sub"], User.is_active.is_(True)).first()


@app.get("/api/content/{slug}", response_model=ContentDetailResponse)
def get_content(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ContentDetailResponse:
    item = db.query(ContentItem).filter(ContentItem.slug == slug).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内容不存在")

    if item.visibility == ContentVisibility.premium:
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="订阅内容需要先登录")
        db.refresh(current_user)
        if current_user.role != UserRole.admin and not has_active_subscription(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有有效订阅")

    return ContentDetailResponse(
        slug=item.slug,
        title=item.title,
        summary=item.summary,
        visibility=item.visibility,
        created_at=item.created_at,
        updated_at=item.updated_at,
        body=decrypt_text(item.body_encrypted),
    )


@app.post("/api/admin/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> PlanResponse:
    existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="套餐编码已存在")
    plan = SubscriptionPlan(**payload.model_dump())
    db.add(plan)
    db.flush()
    db.add(AuditEvent(user_id=admin.id, action="plan.create", detail=f"创建套餐 {plan.code}", ip_address=request.client.host if request.client else None))
    db.commit()
    db.refresh(plan)
    return PlanResponse.model_validate(plan)


@app.get("/api/admin/plans", response_model=list[PlanResponse])
def admin_list_plans(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[PlanResponse]:
    return [PlanResponse.model_validate(item) for item in db.query(SubscriptionPlan).order_by(SubscriptionPlan.created_at.desc()).all()]


@app.post("/api/admin/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    payload: SubscriptionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SubscriptionResponse:
    user = db.get(User, payload.user_id)
    plan = db.get(SubscriptionPlan, payload.plan_id)
    if not user or not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户或套餐不存在")

    starts_at = datetime.utcnow()
    subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        starts_at=starts_at,
        expires_at=starts_at + timedelta(days=plan.duration_days),
        auto_renew=payload.auto_renew,
    )
    db.add(subscription)
    db.flush()
    db.add(AuditEvent(user_id=admin.id, action="subscription.create", detail=f"为用户 {user.email} 开通 {plan.code}", ip_address=request.client.host if request.client else None))
    db.commit()
    db.refresh(subscription)
    return SubscriptionResponse(
        id=subscription.id,
        plan_code=plan.code,
        plan_title=plan.title,
        starts_at=subscription.starts_at,
        expires_at=subscription.expires_at,
        auto_renew=subscription.auto_renew,
        is_active=True,
    )


@app.post("/api/admin/content", response_model=ContentListResponse, status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ContentListResponse:
    existing = db.query(ContentItem).filter(ContentItem.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="内容 slug 已存在")

    item = ContentItem(
        slug=payload.slug,
        title=payload.title,
        summary=payload.summary,
        body_encrypted=encrypt_text(payload.body),
        visibility=payload.visibility,
    )
    db.add(item)
    db.flush()
    db.add(AuditEvent(user_id=admin.id, action="content.create", detail=f"创建内容 {item.slug}", ip_address=request.client.host if request.client else None))
    db.commit()
    db.refresh(item)
    return ContentListResponse.model_validate(item)


@app.get("/api/admin/audits", response_model=list[AuditResponse])
def list_audits(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[AuditResponse]:
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100).all()
    return [AuditResponse.model_validate(event) for event in events]
