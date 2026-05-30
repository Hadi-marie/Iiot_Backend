from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.chatbot import llm, rag_engine, sessions, vector_store
from app.chatbot.config import settings
from app.chatbot.knowledge_loader import parse_answers_docx

router = APIRouter()


class ChatRequest(BaseModel):
    message:    str      = Field(..., min_length=1)
    session_id: str | None = Field(default=None)
    top_k:      int | None = Field(default=None, ge=1, le=20)


class SourceItem(BaseModel):
    type:     str | None = None
    question: str | None = None
    category: str | None = None
    source:   str | None = None
    score:    float | None = None


class ChatResponse(BaseModel):
    answer:           str
    language:         str
    mode:             str
    matched_question: str | None
    category:         str | None
    confidence:       float
    sources:          list[SourceItem]


@router.get("/health")
def chatbot_health() -> dict:
    return {
        "status": "ok",
        "vector_db": {
            "ready":             vector_store.collection_exists(),
            "indexed_documents": vector_store.count(),
        },
        "llm": {"provider": settings.llm_provider, "available": llm.llm_available()},
    }


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    return rag_engine.answer(
        request.message,
        top_k=request.top_k,
        session_id=request.session_id
    )


@router.post("/chat/reset")
def chat_reset(session_id: str) -> dict:
    sessions.reset(session_id)
    return {"status": "ok", "session_id": session_id}


@router.get("/questions")
def questions() -> dict:
    pairs = parse_answers_docx()
    return {
        "count":     len(pairs),
        "questions": [
            {"id": p.qid, "question": p.question, "category": p.category}
            for p in pairs
        ],
    }