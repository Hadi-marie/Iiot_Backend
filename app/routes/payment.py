import os
import stripe

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from dotenv import load_dotenv

from app.db import get_db
from app.models.subscription import Subscription
from app.coree.security import get_current_admin

load_dotenv()

stripe.api_key         = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET         = os.getenv("STRIPE_WEBHOOK_SECRET")
SUBSCRIPTION_PRICE_USD = 10   # دولار
SUBSCRIPTION_DAYS      = 30

router = APIRouter()


# ── إنشاء جلسة الدفع ─────────────────────────────────────────────────────────
@router.post("/create-session")
def create_checkout_session(current_admin=Depends(get_current_admin)):

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "IIoT Security Subscription"},
                    "unit_amount": SUBSCRIPTION_PRICE_USD * 100,
                },
                "quantity": 1,
            }
        ],
        metadata={"company_id": str(current_admin.company_id)},
        success_url="http://localhost:3000/payment/success",
        cancel_url="http://localhost:3000/payment/cancel",
    )

    return {"url": session.url}


# ── Stripe Webhook ────────────────────────────────────────────────────────────
# ✅ هذا هو الطريق الصحيح الآمن — Stripe يستدعيه مباشرة بعد الدفع
# مش redirect من المتصفح (اللي كان قابلاً للتلاعب)
@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):

    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # التحقق من صحة الـ webhook
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # معالجة حدث الدفع الناجح فقط
    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]

        if session.get("payment_status") != "paid":
            return {"status": "ignored"}

        company_id = session.get("metadata", {}).get("company_id")

        if not company_id:
            raise HTTPException(status_code=400, detail="Missing company_id in metadata")

        db.add(Subscription(
            company_id = int(company_id),
            status     = "active",
            start_date = datetime.utcnow(),
            end_date   = datetime.utcnow() + timedelta(days=SUBSCRIPTION_DAYS),
            price      = session.get("amount_total", 0) / 100
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

    return {
        "status":     subscription.status,
        "start_date": subscription.start_date.isoformat(),
        "end_date":   subscription.end_date.isoformat(),
        "price":      float(subscription.price)
    }


# ── صفحة الإلغاء (fallback) ───────────────────────────────────────────────────
@router.get("/cancel")
def payment_cancel():
    return {"message": "Payment canceled"}