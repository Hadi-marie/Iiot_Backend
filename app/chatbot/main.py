from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import llm, rag_engine, sessions, vector_store
from .config import settings
from .knowledge_loader import parse_answers_docx

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(
    title=settings.app_name,
    description="RAG-powered Arabic/English chatbot for an AI IDS protecting IIoT networks.",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, examples=["شو هي خدمتكم بالضبط؟"])
    session_id: str | None = Field(default=None, description="Conversation id for memory.")
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceItem(BaseModel):
    type: str | None = None
    question: str | None = None
    category: str | None = None
    source: str | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    language: str
    mode: str
    matched_question: str | None
    category: str | None
    confidence: float
    sources: list[SourceItem]


@app.get("/")
def home() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "vector_db": {
            "url": settings.qdrant_url,
            "collection": settings.qdrant_collection,
            "indexed_documents": vector_store.count(),
            "ready": vector_store.collection_exists(),
        },
        "embedding_model": settings.embedding_model,
        "llm": {"provider": settings.llm_provider, "available": llm.llm_available()},
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    return rag_engine.answer(
        request.message, top_k=request.top_k, session_id=request.session_id
    )


@app.post("/chat/reset")
def chat_reset(session_id: str) -> dict:
    sessions.reset(session_id)
    return {"status": "ok", "session_id": session_id}


@app.get("/questions")
def questions() -> dict:
    pairs = parse_answers_docx()
    return {
        "count": len(pairs),
        "questions": [
            {"id": p.qid, "question": p.question, "category": p.category} for p in pairs
        ],
    }
