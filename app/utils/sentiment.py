import os
import re
import pickle

import numpy as np
from huggingface_hub import hf_hub_download

HF_REPO  = "hadimaree/iiot-model"
HF_TOKEN = os.getenv("HF_TOKEN")

# ── تحميل الموديل والـ tokenizer عند الإقلاع ─────────────────────────────────
_model     = None
_tokenizer = None


def _load_resources():
    global _model, _tokenizer

    if _model is not None:
        return

    from tensorflow.keras.models import load_model
    from tensorflow.keras.layers import LSTM, Dense, Embedding, Bidirectional

    model_path = hf_hub_download(
        repo_id   = HF_REPO,
        filename  = "lstm_model.h5",
        repo_type = "model",
        token     = HF_TOKEN
    )

    tokenizer_path = hf_hub_download(
        repo_id   = HF_REPO,
        filename  = "tokenizer.pkl",
        repo_type = "model",
        token     = HF_TOKEN
    )

    _model = load_model(
        model_path,
        custom_objects={
            "LSTM":         LSTM,
            "Dense":        Dense,
            "Embedding":    Embedding,
            "Bidirectional": Bidirectional
        },
        compile=False
    )

    with open(tokenizer_path, "rb") as f:
        _tokenizer = pickle.load(f)

    print("✅ Sentiment LSTM model loaded")


def _clean_text(text: str) -> str:
    """تنظيف النص قبل التحليل"""
    try:
        import nltk
        from nltk.corpus import stopwords
        from nltk.stem import PorterStemmer
        nltk.download("stopwords", quiet=True)
        stop_words = set(stopwords.words("english"))
        ps = PorterStemmer()
        text = text.lower()
        text = re.sub(r"[^a-z\s]", "", text)
        words = text.split()
        words = [ps.stem(w) for w in words if w not in stop_words]
        return " ".join(words)
    except Exception:
        # fallback بدون stemming
        text = text.lower()
        text = re.sub(r"[^a-z\s]", "", text)
        return text


def analyze_sentiment(text: str) -> dict:
    """
    يحلل نص باستخدام LSTM ويرجع:
    - sentiment: "positive" | "negative"
    - score: 0.0 - 1.0
    """
    try:
        _load_resources()

        from tensorflow.keras.preprocessing.sequence import pad_sequences

        cleaned   = _clean_text(text)
        sequence  = _tokenizer.texts_to_sequences([cleaned])
        padded    = pad_sequences(sequence, maxlen=100)
        score     = float(_model.predict(padded, verbose=0)[0][0])

        sentiment = "positive" if score > 0.5 else "negative"

        return {
            "sentiment": sentiment,
            "score":     round(score, 4)
        }

    except Exception as e:
        print(f"⚠️ LSTM sentiment error: {e}, falling back to basic")
        # fallback بسيط إذا فشل الموديل
        positive_words = ["good", "great", "excellent", "amazing", "helpful", "perfect"]
        negative_words = ["bad", "terrible", "awful", "poor", "problem", "issue", "slow"]

        text_lower = text.lower()
        pos = sum(1 for w in positive_words if w in text_lower)
        neg = sum(1 for w in negative_words if w in text_lower)

        if pos > neg:
            return {"sentiment": "positive", "score": 0.7}
        elif neg > pos:
            return {"sentiment": "negative", "score": 0.3}
        else:
            return {"sentiment": "neutral", "score": 0.5}