import os
import re
import pickle
import numpy as np
from huggingface_hub import hf_hub_download

HF_REPO  = "hadimaree/iiot-model"
HF_TOKEN = os.getenv("HF_TOKEN")

_session   = None
_tokenizer = None


def _load_resources():
    global _session, _tokenizer

    if _session is not None:
        return

    import onnxruntime as ort

    model_path = hf_hub_download(
        repo_id   = HF_REPO,
        filename  = "lstm_model.onnx",
        repo_type = "model",
        token     = HF_TOKEN
    )

    tokenizer_path = hf_hub_download(
        repo_id   = HF_REPO,
        filename  = "tokenizer.pkl",
        repo_type = "model",
        token     = HF_TOKEN
    )

    _session = ort.InferenceSession(model_path)

    with open(tokenizer_path, "rb") as f:
        _tokenizer = pickle.load(f)

    print("✅ Sentiment ONNX model loaded")


def _pad_sequences(sequences, maxlen=100):
    """pad_sequences بدون keras"""
    result = np.zeros((len(sequences), maxlen), dtype=np.float32)
    for i, seq in enumerate(sequences):
        if len(seq) > maxlen:
            result[i] = seq[:maxlen]
        else:
            result[i, maxlen - len(seq):] = seq
    return result


def _clean_text(text: str) -> str:
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
        text = text.lower()
        text = re.sub(r"[^a-z\s]", "", text)
        return text


def analyze_sentiment(text: str) -> dict:
    try:
        _load_resources()

        cleaned  = _clean_text(text)
        sequence = _tokenizer.texts_to_sequences([cleaned])
        padded   = _pad_sequences(sequence, maxlen=100)

        input_name = _session.get_inputs()[0].name
        score = float(_session.run(None, {input_name: padded})[0][0][0])

        sentiment = "positive" if score > 0.5 else "negative"

        return {"sentiment": sentiment, "score": round(score, 4)}

    except Exception as e:
        print(f"⚠️ ONNX sentiment error: {e}, fallback")
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