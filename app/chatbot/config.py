from __future__ import annotations

import os
from pathlib import Path

# app/chatbot/config.py — داخل مشروع IIoT
# المسار: iiot-backend/app/chatbot/config.py
CHATBOT_DIR = Path(__file__).resolve().parent        # app/chatbot/
APP_DIR     = CHATBOT_DIR.parent                     # app/
REPO_ROOT   = APP_DIR.parent                         # iiot-backend/


def _get(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


class Settings:

    app_name:    str = _get("APP_NAME",    "IDS AI IIoT RAG Chatbot")
    app_version: str = _get("APP_VERSION", "2.0.0")

    # --- Vector database (Qdrant) ---
    qdrant_url:        str = _get("QDRANT_URL",        "http://localhost:6333")
    qdrant_api_key:    str = _get("QDRANT_API_KEY",    "")
    qdrant_collection: str = _get("QDRANT_COLLECTION", "ids_chatbot")

    # --- Embeddings ---
    embedding_provider:    str = _get("EMBEDDING_PROVIDER", "tfidf").lower()
    embedding_model:       str = _get("EMBEDDING_MODEL",    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    openai_embedding_model:str = _get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    tfidf_components:      int = int(_get("TFIDF_COMPONENTS", "256"))
    tfidf_model_path:      str = _get(
        "TFIDF_MODEL_PATH",
        str(CHATBOT_DIR / "models" / "tfidf_embedder.joblib")
    )

    # --- Knowledge sources ---
    knowledge_docx:     str = _get("KNOWLEDGE_DOCX",     str(REPO_ROOT / "Answers_bot.docx"))
    extra_knowledge_dir:str = _get("EXTRA_KNOWLEDGE_DIR", "")

    # --- Conversation memory ---
    max_history_turns: int = int(_get("MAX_HISTORY_TURNS", "6"))

    # --- Retrieval behaviour ---
    top_k:              int   = int(_get("TOP_K",               "6"))
    qa_match_threshold: float = float(_get("QA_MATCH_THRESHOLD","0.62"))
    min_relevance:      float = float(_get("MIN_RELEVANCE",     "0.40"))
    min_curated_chars:  int   = int(_get("MIN_CURATED_CHARS",   "200"))

    # --- Optional LLM ---
    llm_provider:     str = _get("LLM_PROVIDER",     "none").lower()
    openai_api_key:   str = _get("OPENAI_API_KEY",   "")
    openai_base_url:  str = _get("OPENAI_BASE_URL",  "https://api.openai.com/v1")
    openai_chat_model:str = _get("OPENAI_CHAT_MODEL","gpt-4o-mini")
    ollama_url:       str = _get("OLLAMA_URL",       "http://localhost:11434")
    ollama_model:     str = _get("OLLAMA_MODEL",     "qwen2.5:7b-instruct")

    # --- CORS ---
    cors_origins: str = _get("CORS_ORIGINS", "*")

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider in {"openai", "ollama"}


settings = Settings()