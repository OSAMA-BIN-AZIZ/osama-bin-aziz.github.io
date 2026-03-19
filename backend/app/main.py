from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .database import Base, engine, get_db
from .dependencies import get_current_user, require_admin
from .models import Plan, SecureContent, Subscription, User
from .schemas import (
    DashboardMetrics,
    HealthResponse,
    LoginRequest,
    PlanCreate,
    PlanRead,
    SecureContentCreate,
    SecureContentRead,
    SubscriptionCreate,
    SubscriptionRead,
    TokenPair,
    UserCreate,
    UserRead,
)
from .security import create_access_token, create_refresh_token, hash_password, verify_password
from .services import (
    can_read_content,
    create_plan,
    create_secure_content,
    create_subscription,
    ensure_bootstrap_admin,
    get_dashboard_metrics,
    serialize_secure_content,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        ensure_bootstrap_admin(db, settings.admin_bootstrap_email, settings.admin_bootstrap_password)
    yield


app = FastAPI(title=settings.app_name, version='1.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
    allow_headers=['Authorization', 'Content-Type'],
)


def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=['HS256'])
    except JWTError:
        return None
    if payload.get('type') != 'access':
        return None
    subject = payload.get('sub')
    if not subject:
        return None
    return (
        db.query(User)
        .options(joinedload(User.subscriptions).joinedload(Subscription.plan))
        .filter(User.email == subject, User.is_active.is_(True))
        .first()
    )


@app.get('/health', response_model=HealthResponse, tags=['system'])
def healthcheck() -> HealthResponse:
    return HealthResponse(status='ok', app=settings.app_name, environment=settings.app_env)


@app.post('/auth/register', response_model=UserRead, status_code=status.HTTP_201_CREATED, tags=['auth'])
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already registered')

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post('/auth/login', response_model=TokenPair, tags=['auth'])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Incorrect email or password')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account is disabled')

    return TokenPair(
        access_token=create_access_token(user.email, {'role': user.role}),
        refresh_token=create_refresh_token(user.email, {'role': user.role}),
    )


@app.get('/users/me', response_model=UserRead, tags=['users'])
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.get('/admin/dashboard', response_model=DashboardMetrics, tags=['admin'])
def admin_dashboard(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> DashboardMetrics:
    return DashboardMetrics(**get_dashboard_metrics(db))


@app.get('/plans', response_model=list[PlanRead], tags=['plans'])
def list_plans(db: Session = Depends(get_db)) -> list[Plan]:
    return db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.price_monthly.asc()).all()


@app.post('/plans', response_model=PlanRead, status_code=status.HTTP_201_CREATED, tags=['plans'])
def create_plan_endpoint(
    payload: PlanCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Plan:
    exists = db.query(Plan).filter(Plan.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Plan code already exists')
    return create_plan(db, payload.model_dump())


@app.post('/subscriptions', response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED, tags=['subscriptions'])
def create_subscription_endpoint(
    payload: SubscriptionCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Subscription:
    user = db.query(User).filter(User.id == payload.user_id).first()
    plan = db.query(Plan).filter(Plan.id == payload.plan_id).first()
    if not user or not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User or plan not found')
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='End date must be after start date')
    return create_subscription(db, payload.model_dump())


@app.get('/subscriptions/me', response_model=list[SubscriptionRead], tags=['subscriptions'])
def my_subscriptions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Subscription]:
    return db.query(Subscription).filter(Subscription.user_id == current_user.id).order_by(Subscription.end_date.desc()).all()


@app.post('/content', response_model=SecureContentRead, status_code=status.HTTP_201_CREATED, tags=['content'])
def create_content_endpoint(
    payload: SecureContentCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SecureContentRead:
    exists = db.query(SecureContent).filter(SecureContent.slug == payload.slug).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Content slug already exists')
    content = create_secure_content(db, payload.model_dump())
    return SecureContentRead(**serialize_secure_content(content))


@app.get('/content/{slug}', response_model=SecureContentRead, tags=['content'])
def read_content(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> SecureContentRead:
    content = db.query(SecureContent).filter(SecureContent.slug == slug, SecureContent.is_published.is_(True)).first()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    if not can_read_content(current_user, content):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Subscription required for this content')
    return SecureContentRead(**serialize_secure_content(content))


@app.get('/content', response_model=list[SecureContentRead], tags=['content'])
def list_content(db: Session = Depends(get_db), current_user: User | None = Depends(get_current_user_optional)) -> list[SecureContentRead]:
    records = db.query(SecureContent).filter(SecureContent.is_published.is_(True)).order_by(SecureContent.created_at.desc()).all()
    return [SecureContentRead(**serialize_secure_content(record)) for record in records if can_read_content(current_user, record)]


@app.get('/bootstrap/security', tags=['system'])
def security_notes(_: User = Depends(require_admin)) -> dict[str, list[str] | str]:
    return {
        'database': 'Use a dedicated PostgreSQL user, IP allow-listing, TLS, and encrypted backups on the remote DB server.',
        'hardening': [
            'Store .env only on the API host and rotate JWT and encryption keys regularly.',
            'Put the API behind Nginx/Caddy with HTTPS, rate-limits, fail2ban, and WAF rules.',
            'Keep premium content encrypted at rest and never expose raw database credentials to the frontend.',
        ],
    }
