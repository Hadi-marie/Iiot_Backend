import pickle
import numpy as np
import os

# ── تحميل الموديل عند بدء التشغيل ────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR   = os.path.join(BASE_DIR, "..", "ml")


def _load(filename):
    with open(os.path.join(ML_DIR, filename), "rb") as f:
        return pickle.load(f)


model            = _load("lgbm_wavelet_final.pkl")
scaler           = _load("scaler.pkl")
selected_feats   = _load("selected_feats.pkl")
optimal_threshold = _load("optimal_threshold.pkl")

# الـ features المطلوبة بالترتيب الصح
REQUIRED_FEATURES = selected_feats


def predict_attack(network_data: dict) -> dict:
    """
    يستقبل dict فيه بيانات الشبكة ويرجع نتيجة التحليل.

    Parameters:
        network_data: dict يحتوي على الـ features (28 feature)

    Returns:
        {
            "is_attack": bool,
            "probability": float,
            "action": "block" | "alert" | "normal"
        }
    """

    # ── استخراج الـ features بالترتيب الصح ───────────────────────────
    try:
        values = [float(network_data.get(feat, 0)) for feat in REQUIRED_FEATURES]
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid feature value: {e}")

    # ── تحويل لـ numpy array وتطبيق الـ scaler ────────────────────────
    X      = np.array(values).reshape(1, -1)
    X_scaled = scaler.transform(X)

    # ── التنبؤ ────────────────────────────────────────────────────────
    probability = float(model.predict_proba(X_scaled)[0][1])
    is_attack   = probability >= optimal_threshold

    # ── تحديد الإجراء ─────────────────────────────────────────────────
    if not is_attack:
        action = "normal"
    elif probability >= 0.85:
        action = "block"   # هجوم واضح → حظر فوري
    else:
        action = "alert"   # مشبوه → تنبيه فقط

    return {
        "is_attack":   is_attack,
        "probability": round(probability, 4),
        "action":      action
    }