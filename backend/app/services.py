from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import ContentVisibility, Plan, SecureContent, Subscription, SubscriptionStatus, User, UserRole
from .security import decrypt_text, encrypt_text, hash_password


def ensure_bootstrap_admin(db: Session, email: str, password: str) -> None:
    admin = db.query(User).filter(User.email == email).first()
    if admin:
        return

    db.add(
        User(
            email=email,
            full_name='System Administrator',
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    db.commit()


def create_plan(db: Session, payload: dict) -> Plan:
    plan = Plan(**payload)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def create_subscription(db: Session, payload: dict) -> Subscription:
    subscription = Subscription(**payload)
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def create_secure_content(db: Session, payload: dict) -> SecureContent:
    body = payload.pop('body')
    content = SecureContent(**payload, encrypted_body=encrypt_text(body))
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def serialize_secure_content(record: SecureContent) -> dict:
    return {
        'id': record.id,
        'slug': record.slug,
        'title': record.title,
        'summary': record.summary,
        'body': decrypt_text(record.encrypted_body),
        'visibility': record.visibility,
        'is_published': record.is_published,
        'created_at': record.created_at,
        'updated_at': record.updated_at,
    }


def subscription_is_current(subscription: Subscription, today: date | None = None) -> bool:
    effective_today = today or date.today()
    active_statuses = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}
    return (
        subscription.status in active_statuses
        and subscription.start_date <= effective_today <= subscription.end_date
    )


def user_has_paid_access(user: User, today: date | None = None) -> bool:
    for subscription in user.subscriptions:
        if subscription_is_current(subscription, today=today) and subscription.plan.includes_premium_content:
            return True
    return False


def can_read_content(user: User | None, content: SecureContent, today: date | None = None) -> bool:
    if content.visibility == ContentVisibility.PUBLIC:
        return True
    if not user:
        return False
    if user.role == UserRole.ADMIN:
        return True
    if content.visibility == ContentVisibility.SUBSCRIBER:
        return any(subscription_is_current(subscription, today=today) for subscription in user.subscriptions)
    return user_has_paid_access(user, today=today)


def get_dashboard_metrics(db: Session) -> dict[str, int]:
    return {
        'total_users': db.query(func.count(User.id)).scalar() or 0,
        'active_subscriptions': db.query(func.count(Subscription.id)).filter(Subscription.status == SubscriptionStatus.ACTIVE).scalar() or 0,
        'premium_articles': db.query(func.count(SecureContent.id)).filter(SecureContent.visibility == ContentVisibility.PREMIUM).scalar() or 0,
        'published_articles': db.query(func.count(SecureContent.id)).filter(SecureContent.is_published.is_(True)).scalar() or 0,
    }
