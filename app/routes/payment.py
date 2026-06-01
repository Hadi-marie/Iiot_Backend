import os
import stripe

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.coree.security import get_current_admin

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
FRONTEND_URL   = os.getenv("FRONTEND_URL", "http://localhost:3000")

router = APIRouter()


class CreateSessionRequest(BaseModel):
    plan_name: str  # "pro" | "premium"


# ── جلب الخطط المتاحة ─────────────────────────────────────────────────────────
@router.get("/plans")
def get_plans(db: Session = Depends(get_db)):
    plans = db.query(Plan).filter(Plan.is_active == True).all()
    return [
        {
            "plan_id":       p.plan_id,
            "name":          p.name,
            "price":         float(p.price),
            "duration_days": p.duration_days,
            "threshold":     float(p.threshold)
        }
        for p in plans
    ]


# ── إنشاء جلسة الدفع ─────────────────────────────────────────────────────────
@router.post("/create-session")
def create_checkout_session(
    data: CreateSessionRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    plan = db.query(Plan).filter(
        Plan.name      == data.plan_name.lower(),
        Plan.is_active == True
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency":     "usd",
                    "product_data": {"name": f"IIoT Security — {plan.name.capitalize()} Plan"},
                    "unit_amount":  int(plan.price * 100),
                },
                "quantity": 1,
            }
        ],
        metadata={
            "company_id": str(current_admin.company_id),
            "plan_id":    str(plan.plan_id)
        },
        success_url=f"{FRONTEND_URL}/payment/success",
        cancel_url=f"{FRONTEND_URL}/payment/cancel",
    )

    return {"url": session.url}


# ── Stripe Webhook ────────────────────────────────────────────────────────────
@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):

    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]

        # ✅ الطريقة الصحيحة مع Stripe API الجديد
        if session.payment_status != "paid":
            return {"status": "ignored"}

        company_id = session.metadata.company_id if session.metadata else None
        plan_id    = session.metadata.plan_id    if session.metadata else None

        if not company_id or not plan_id:
            raise HTTPException(status_code=400, detail="Missing metadata")

        plan = db.query(Plan).filter(Plan.plan_id == int(plan_id)).first()

        if not plan:
            raise HTTPException(status_code=400, detail="Plan not found")

        # إلغاء الاشتراك القديم
        old_sub = db.query(Subscription).filter(
            Subscription.company_id == int(company_id),
            Subscription.status     == "active"
        ).first()

        if old_sub:
            old_sub.status = "cancelled"

        # إنشاء اشتراك جديد
        db.add(Subscription(
            company_id = int(company_id),
            plan_id    = int(plan_id),
            status     = "active",
            start_date = datetime.utcnow(),
            end_date   = datetime.utcnow() + timedelta(days=plan.duration_days),
            price      = session.amount_total / 100 if session.amount_total else 0
        ))
        db.commit()

    return {"status": "ok"}


# ── حالة الاشتراك الحالي ──────────────────────────────────────────────────────
@router.get("/subscription")
def get_subscription(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    subscription = db.query(Subscription).filter(
        Subscription.company_id == current_admin.company_id,
        Subscription.status     == "active"
    ).order_by(Subscription.end_date.desc()).first()

    if not subscription:
        return {"status": "no_subscription"}

    plan = db.query(Plan).filter(
        Plan.plan_id == subscription.plan_id
    ).first()

    return {
        "status":     subscription.status,
        "plan":       plan.name if plan else "unknown",
        "start_date": subscription.start_date.isoformat(),
        "end_date":   subscription.end_date.isoformat(),
        "price":      float(subscription.price)
    }


@router.get("/cancel")
def payment_cancel():
    return {"message": "Payment canceled"}