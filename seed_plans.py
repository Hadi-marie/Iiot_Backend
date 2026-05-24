"""
شغّل هذا السكريبت مرة واحدة فقط لإضافة الخطط للداتابيز:
    python seed_plans.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models.plan import Plan

db = SessionLocal()

# تحقق إذا الخطط موجودة مسبقاً
existing = db.query(Plan).count()
if existing > 0:
    print("✅ Plans already exist — skipping")
    db.close()
    exit()

plans = [
    Plan(
        name           = "pro",
        price          = 150.00,
        duration_days  = 30,
        model_filename = "lgbm_wavelet_final.pkl",
        threshold      = 0.8,
        is_active      = True
    ),
    Plan(
        name           = "premium",
        price          = 250.00,
        duration_days  = 30,
        model_filename = "lgbm_premium_final.pkl",  # يتحدث لما يجهز الموديل
        threshold      = 0.494,
        is_active      = False  # معطل لحد ما يجهز الموديل الثاني
    )
]

db.add_all(plans)
db.commit()
print("✅ Plans seeded successfully!")
print("   - Pro: $150/month (threshold: 0.8)")
print("   - Premium: $250/month (threshold: 0.494) — disabled until model is ready")
db.close()