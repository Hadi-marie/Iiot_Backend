from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.feedback import Feedback
from app.coree.security import get_current_admin, get_current_super_admin
from app.utils.subscription import check_subscription
from app.utils.sentiment import analyze_sentiment

router = APIRouter()


class FeedbackCreate(BaseModel):
    content: str


# ── إرسال تعليق (للشركات المشتركة) ──────────────────────────────────────────
@router.post("/", status_code=201)
def submit_feedback(
    data: FeedbackCreate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    if not data.content or len(data.content.strip()) < 5:
        raise HTTPException(status_code=400, detail="Feedback too short")

    if len(data.content) > 1000:
        raise HTTPException(status_code=400, detail="Feedback too long (max 1000 chars)")

    result = analyze_sentiment(data.content)

    new_feedback = Feedback(
        company_id      = current_admin.company_id,
        admin_id        = current_admin.admin_id,
        content         = data.content.strip(),
        sentiment       = result["sentiment"],
        sentiment_score = result["score"]
    )
    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)

    return {
        "message":         "Feedback submitted successfully",
        "feedback_id":     new_feedback.feedback_id,
        "sentiment":       result["sentiment"],
        "sentiment_score": result["score"]
    }


# ── جلب تعليقات شركتك ────────────────────────────────────────────────────────
@router.get("/my")
def get_my_feedback(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    feedbacks = db.query(Feedback).filter(
        Feedback.company_id == current_admin.company_id
    ).order_by(Feedback.created_at.desc()).all()

    return [
        {
            "feedback_id":     f.feedback_id,
            "content":         f.content,
            "sentiment":       f.sentiment,
            "sentiment_score": float(f.sentiment_score),
            "created_at":      f.created_at.isoformat()
        }
        for f in feedbacks
    ]


# ── كل التعليقات (Super Admin فقط) ───────────────────────────────────────────
@router.get("/all")
def get_all_feedback(
    sentiment: str | None = Query(None, description="positive / negative / neutral"),
    limit:     int        = Query(50, ge=1, le=200),
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    query = db.query(Feedback)

    if sentiment:
        query = query.filter(Feedback.sentiment == sentiment)

    feedbacks = query.order_by(Feedback.created_at.desc()).limit(limit).all()

    return [
        {
            "feedback_id":     f.feedback_id,
            "company_id":      f.company_id,
            "content":         f.content,
            "sentiment":       f.sentiment,
            "sentiment_score": float(f.sentiment_score),
            "created_at":      f.created_at.isoformat()
        }
        for f in feedbacks
    ]


# ── إحصائيات (Super Admin فقط) ───────────────────────────────────────────────
@router.get("/stats")
def get_feedback_stats(
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    total    = db.query(Feedback).count()
    positive = db.query(Feedback).filter(Feedback.sentiment == "positive").count()
    negative = db.query(Feedback).filter(Feedback.sentiment == "negative").count()
    neutral  = db.query(Feedback).filter(Feedback.sentiment == "neutral").count()

    return {
        "total":        total,
        "positive":     positive,
        "negative":     negative,
        "neutral":      neutral,
        "positive_pct": round(positive / total * 100, 1) if total > 0 else 0,
        "negative_pct": round(negative / total * 100, 1) if total > 0 else 0,
    }