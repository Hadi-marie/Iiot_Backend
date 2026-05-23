from fastapi import HTTPException
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.subscription import Subscription


def check_subscription(db: Session, company_id: int):

    subscription = db.query(Subscription).filter(
        Subscription.company_id == company_id,
        Subscription.status == "active"
    ).order_by(Subscription.end_date.desc()).first()

    if not subscription:
        raise HTTPException(
            status_code=403,
            detail="No active subscription"
        )

    if subscription.end_date < datetime.utcnow():
        subscription.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Subscription expired"
        )

    return subscription