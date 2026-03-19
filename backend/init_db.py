from database import Base, engine, SessionLocal
from models import SubscriptionPlan

DEFAULT_PLANS = [
    {
        "name": "Starter",
        "slug": "starter",
        "price_cents": 9900,
        "billing_cycle_days": 30,
        "description": "适合入门用户，支持基础内容访问与工单支持。",
    },
    {
        "name": "Premium",
        "slug": "premium",
        "price_cents": 29900,
        "billing_cycle_days": 30,
        "description": "适合订阅站点运营，支持高级内容、优先支持与审计日志。",
    },
]


def bootstrap() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        for plan in DEFAULT_PLANS:
            exists = session.query(SubscriptionPlan).filter_by(slug=plan["slug"]).first()
            if not exists:
                session.add(SubscriptionPlan(**plan))
        session.commit()


if __name__ == "__main__":
    bootstrap()
