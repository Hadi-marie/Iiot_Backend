from __future__ import annotations

import re

_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06dc\u06df-\u06e8\u06ea-\u06ed]")
_TATWEEL = "\u0640"
_NON_TOKEN = re.compile(r"[^\w\s\u0600-\u06ff]", re.UNICODE)

_ARABIC_MAP = {
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي",
    "ة": "ه",
    "ؤ": "و",
    "\u200f": "", "\u200e": "",
}


def normalize(text: str) -> str:
    """Language-aware normalization for Arabic + English used by the TF-IDF embedder."""
    if not text:
        return ""
    text = text.lower()
    text = _DIACRITICS.sub("", text)
    text = text.replace(_TATWEEL, "")
    for src, dst in _ARABIC_MAP.items():
        text = text.replace(src, dst)
    text = _NON_TOKEN.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
