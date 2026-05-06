import stripe
from fastapi import APIRouter, Depends
from app.coree.security import get_current_admin
from datetime import datetime, timedelta
from app.models.subscription import Subscription
from app.db import get_db
from sqlalchemy.orm import Session

# # 🔥 مفتاح Stripe

import os
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
router = APIRouter()


# 🎯 إنشاء جلسة الدفع
@router.post("/create-session")
def create_checkout_session(current_admin=Depends(get_current_admin)):

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "IIoT Subscription",
                    },
                    "unit_amount": 1000,  # 10$
                },
                "quantity": 1,
            }
        ],
        # 🔥 نحفظ company_id داخل Stripe
        metadata={
            "company_id": current_admin.company_id
        },
        success_url="http://localhost:8000/payment/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://localhost:8000/payment/cancel",
    )

    return {"url": session.url}


# 🎯 بعد نجاح الدفع
@router.get("/success")
def payment_success(
    session_id: str,
    db: Session = Depends(get_db)
):

    session = stripe.checkout.Session.retrieve(session_id)

    # ❌ إذا الدفع مو مكتمل
    if session.payment_status != "paid":
        return {"message": "Payment not completed"}

    # 🔥 نجيب company_id من metadata
    company_id = session.metadata["company_id"]

    # 🔥 إنشاء الاشتراك
    new_subscription = Subscription(
        company_id=company_id,
        status="active",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        price=session.amount_total / 100
    )

    db.add(new_subscription)
    db.commit()

    return {
        "message": "Subscription created",
        "company_id": company_id
    }


# ❌ إذا ألغى الدفع
@router.get("/cancel")
def payment_cancel():
    return {"message": "Payment canceled"}