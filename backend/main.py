from collections import defaultdict, deque
from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from config import get_settings
from database import get_db
from init_db import bootstrap
from models import AccessAudit, SecureContent, Subscription, SubscriptionPlan, User
from schemas import (
    ContentCreate,
    ContentListItem,
    ContentRead,
    LoginRequest,
    PlanCreate,
    PlanRead,
    SubscriptionCreate,
    SubscriptionRead,
    Token,
    UserCreate,
    UserRead,
)
from security import create_access_token, decrypt_content, decode_access_token, encrypt_content, hash_password, verify_password

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)
auth_scheme = HTTPBearer(auto_error=False)
rate_limit_buckets: dict[str, deque[datetime]] = defaultdict(deque)


@app.on_event("startup")
def on_startup() -> None:
    bootstrap()


if settings.enforce_https_redirect:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list or ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def apply_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response


def record_audit(db: Session, request: Request, action: str, user_id: int | None = None) -> None:
    client_ip = request.client.host if request.client else "unknown"
    db.add(AccessAudit(user_id=user_id, path=request.url.path, action=action, ip_address=client_ip))
    db.commit()


def enforce_rate_limit(identifier: str) -> None:
    now = datetime.utcnow()
    bucket = rate_limit_buckets[identifier]
    while bucket and (now - bucket[0]).total_seconds() > settings.login_rate_window_seconds:
        bucket.popleft()
    if len(bucket) >= settings.login_rate_limit:
        raise HTTPException(status_code=429, detail="Too many login attempts. Please retry later.")
    bucket.append(now)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        user_id = int(decode_access_token(credentials.credentials))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")
    return user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")
    return current_user


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.post(f"{settings.api_prefix}/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_admin=payload.email.lower() == settings.admin_bootstrap_email.lower(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    record_audit(db, request, "user.register", user.id)
    return user


@app.post(f"{settings.api_prefix}/auth/token", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> Token:
    identifier = request.client.host if request.client else payload.email.lower()
    enforce_rate_limit(identifier)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        record_audit(db, request, "auth.failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    token = create_access_token(str(user.id))
    record_audit(db, request, "auth.success", user.id)
    return Token(access_token=token)


@app.get(f"{settings.api_prefix}/users/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.get(f"{settings.api_prefix}/plans", response_model=list[PlanRead])
def list_plans(db: Session = Depends(get_db)) -> list[SubscriptionPlan]:
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.price_cents.asc()).all()


@app.post(f"{settings.api_prefix}/plans", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
def create_plan(payload: PlanCreate, db: Session = Depends(get_db), _: User = Depends(get_admin_user)) -> SubscriptionPlan:
    plan = SubscriptionPlan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@app.post(f"{settings.api_prefix}/subscriptions", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_subscription(
    payload: SubscriptionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Subscription:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == payload.plan_slug, SubscriptionPlan.is_active.is_(True)).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    starts_at = datetime.utcnow()
    subscription = Subscription(
        user_id=current_user.id,
        plan_id=plan.id,
        status="active",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(days=plan.billing_cycle_days),
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    subscription.plan = plan
    record_audit(db, request, f"subscription.created:{plan.slug}", current_user.id)
    return subscription


@app.get(f"{settings.api_prefix}/subscriptions/me", response_model=list[SubscriptionRead])
def list_my_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Subscription]:
    return (
        db.query(Subscription)
        .options(joinedload(Subscription.plan))
        .filter(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .all()
    )


@app.post(f"{settings.api_prefix}/content", response_model=ContentListItem, status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
) -> SecureContent:
    content = SecureContent(
        title=payload.title,
        slug=payload.slug,
        summary=payload.summary,
        encrypted_body=encrypt_content(payload.body),
        access_level=payload.access_level,
        is_published=payload.is_published,
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    record_audit(db, request, f"content.created:{payload.slug}", admin_user.id)
    return content


@app.get(f"{settings.api_prefix}/content", response_model=list[ContentListItem])
def list_content(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[SecureContent]:
    query = db.query(SecureContent).filter(SecureContent.is_published.is_(True))
    if not current_user.is_admin:
        query = query.filter(SecureContent.access_level == "subscriber")
    return query.order_by(SecureContent.created_at.desc()).all()


@app.get(f"{settings.api_prefix}/content/{{slug}}", response_model=ContentRead)
def read_content(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContentRead:
    content = db.query(SecureContent).filter(SecureContent.slug == slug, SecureContent.is_published.is_(True)).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.access_level == "admin" and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    has_active_subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
            Subscription.ends_at > datetime.utcnow(),
        )
        .first()
    )
    if content.access_level == "subscriber" and not (current_user.is_admin or has_active_subscription):
        raise HTTPException(status_code=403, detail="Active subscription required")

    record_audit(db, request, f"content.read:{slug}", current_user.id)
    return ContentRead(
        title=content.title,
        slug=content.slug,
        summary=content.summary,
        access_level=content.access_level,
        is_published=content.is_published,
        created_at=content.created_at,
        body=decrypt_content(content.encrypted_body),
    )
