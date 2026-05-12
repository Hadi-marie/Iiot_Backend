import joblib
import os
import numpy as np
from huggingface_hub import hf_hub_download

HF_REPO  = "hadimaree/iiot-model"
HF_TOKEN = os.getenv("HF_TOKEN")


def _load(filename):
    path = hf_hub_download(
        repo_id   = HF_REPO,
        filename  = filename,
        repo_type = "model",
        token     = HF_TOKEN
    )
    return joblib.load(path)


model             = _load("lgbm_wavelet_final.pkl")
scaler            = _load("scaler.pkl")
selected_feats    = _load("selected_feats.pkl")
optimal_threshold = _load("optimal_threshold.pkl")

REQUIRED_FEATURES = selected_feats


def predict_attack(network_data: dict) -> dict:
    try:
        values = [float(network_data.get(feat, 0)) for feat in REQUIRED_FEATURES]
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid feature value: {e}")

    X        = np.array(values).reshape(1, -1)
    X_scaled = scaler.transform(X)

    probability = float(model.predict_proba(X_scaled)[0][1])
    is_attack   = probability >= optimal_threshold

    if not is_attack:
        action = "normal"
    elif probability >= 0.85:
        action = "block"
    else:
        action = "alert"

    return {
        "is_attack":   is_attack,
        "probability": round(probability, 4),
        "action":      action
    }