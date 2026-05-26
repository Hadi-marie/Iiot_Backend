import joblib
import os
import numpy as np
from huggingface_hub import hf_hub_download

HF_REPO  = "hadimaree/iiot-model"
HF_TOKEN = os.getenv("HF_TOKEN")

# إعدادات كل خطة
PLAN_CONFIG = {
    "pro": {
        "model_filename":  "lgbm_wavelet_final.pkl",
        "scaler_filename": "scaler.pkl",
        "feats_filename":  "selected_feats.pkl",
        "threshold":       0.8
    },
    "premium": {
        "model_filename":  "lgbm_premium_final.pkl",
        "scaler_filename": "premium_scaler.pkl",
        "feats_filename":  "premium_selected_feats.pkl",
        "threshold":       0.494
    }
}


def _load_file(filename):
    path = hf_hub_download(
        repo_id   = HF_REPO,
        filename  = filename,
        repo_type = "model",
        token     = HF_TOKEN
    )
    return joblib.load(path)


# cache لكل الموارد
_cache: dict = {}


def _get_resources(plan_name: str):
    """جلب model + scaler + features حسب الخطة مع caching"""
    plan = plan_name.lower() if plan_name else "pro"

    if plan not in PLAN_CONFIG:
        plan = "pro"

    if plan not in _cache:
        config = PLAN_CONFIG[plan]
        try:
            _cache[plan] = {
                "model":   _load_file(config["model_filename"]),
                "scaler":  _load_file(config["scaler_filename"]),
                "feats":   _load_file(config["feats_filename"]),
            }
        except Exception as e:
            # fallback للـ pro إذا ما وجد الموديل
            if plan != "pro":
                print(f"⚠️ Failed to load {plan} model, falling back to pro: {e}")
                _cache[plan] = _get_resources("pro")
            else:
                raise

    return _cache[plan]


# تحميل الـ pro عند الإقلاع
_pro = _get_resources("pro")
REQUIRED_FEATURES = _pro["feats"]


def predict_attack(network_data: dict, plan_name: str = "pro") -> dict:
    """
    يستقبل بيانات الشبكة والخطة ويرجع نتيجة التحليل.

    Parameters:
        network_data: dict يحتوي على الـ 28 feature
        plan_name: "pro" | "premium"
    """
    resources  = _get_resources(plan_name)
    model      = resources["model"]
    scaler     = resources["scaler"]
    feats      = resources["feats"]
    threshold  = float(PLAN_CONFIG.get(plan_name, PLAN_CONFIG["pro"])["threshold"])

    try:
        values = [float(network_data.get(feat, 0)) for feat in feats]
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid feature value: {e}")

    X        = np.array(values).reshape(1, -1)
    X_scaled = scaler.transform(X)

    probability = float(model.predict_proba(X_scaled)[0][1])
    is_attack   = probability >= threshold

    if not is_attack:
        action = "normal"
    elif probability >= 0.95:
        action = "block"
    else:
        action = "alert"

    return {
        "is_attack":   is_attack,
        "probability": round(probability, 4),
        "action":      action,
        "plan":        plan_name,
        "threshold":   threshold
    }