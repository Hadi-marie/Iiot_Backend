from __future__ import annotations

import re
from typing import Any

from . import llm, sessions, vector_store
from .config import settings
from .embeddings import embed_query

_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")


def detect_language(text: str) -> str:
    return "ar" if len(_ARABIC_RE.findall(text)) >= 2 else "en"


SYSTEM_PROMPT_AR = (
    "أنت المساعد الرسمي لمشروع: نظام كشف التسلل (IDS) المعتمد على الذكاء الاصطناعي لحماية "
    "شبكات وأجهزة إنترنت الأشياء الصناعية (IIoT).\n"
    "- يحتوي (السياق) أدناه على الإجابات الرسمية والمعتمدة للمشروع (وصف الخدمة، الأسعار، "
    "الاشتراكات، الدعم، التثبيت، المزايا، الأمان والتوافق). عندما يغطي السياق السؤال، اعتمد "
    "عليه ولا تخترع أو تغيّر أي تفاصيل تجارية مثل الأسعار أو المدد أو معلومات التواصل أو وعود الدعم.\n"
    "- إذا كان السؤال ضمن موضوع المشروع (نظام كشف التسلل، إنترنت الأشياء الصناعية، الأمن "
    "السيبراني الصناعي/OT، أنواع الهجمات وطرق الحماية، الشبكات والخدمة وكيفية عملها) لكنه غير "
    "مغطى في السياق، فأجب بالاعتماد على خبرتك كمختص أمن سيبراني بما يتوافق مع طبيعة المشروع.\n"
    "- إذا كان السؤال خارج موضوع المشروع تمامًا (مثل الطبخ أو الرياضة أو مواضيع عامة لا علاقة "
    "لها)، فلا تجب عنه، واعتذر بلطف موضحًا أنك مختص فقط بمواضيع هذا المشروع (IDS / IIoT / الأمن "
    "السيبراني الصناعي) وادعُ المستخدم لطرح سؤال ضمن الموضوع.\n"
    "- أجب باللغة العربية بأسلوب واضح ومنظم."
)

SYSTEM_PROMPT_EN = (
    "You are the official assistant for a project: an AI-powered Intrusion Detection System "
    "(IDS) that protects Industrial IoT (IIoT) networks and devices.\n"
    "- The CONTEXT below contains the project's official, authoritative answers (service "
    "description, pricing, subscriptions, support, installation, features, security & "
    "compliance). When the CONTEXT covers the question, base your answer on it and NEVER "
    "invent or change factual business details such as prices, durations, contacts, or "
    "support promises.\n"
    "- If the question is within the project's subject area (IDS, IIoT, industrial/OT "
    "cybersecurity, network attacks and defenses, the service and how it works) but not "
    "covered by the CONTEXT, answer helpfully using your expert cybersecurity knowledge, "
    "staying consistent with the project.\n"
    "- If the question is entirely unrelated to this subject area (e.g., cooking, sports, "
    "general chit-chat), do NOT answer it; politely say you can only help with topics about "
    "this IDS/IIoT cybersecurity project and invite a relevant question.\n"
    "- Answer in English, clearly and concisely."
)


def _build_context(passages: list[dict[str, Any]]) -> str:
    blocks = []
    for i, p in enumerate(passages, start=1):
        q = p.get("question")
        head = f"[{i}]" + (f" ({q})" if q else "")
        blocks.append(f"{head}\n{p.get('answer', '')}")
    return "\n\n".join(blocks)


def _build_search_query(message: str, history: list[dict]) -> str:
    """For short follow-ups (e.g. "yes", "اشرح أكثر"), reuse the previous user turn so
    retrieval still finds the right context."""
    if not history:
        return message
    if len(message.split()) > 4:
        return message
    prev_users = [m["content"] for m in history if m.get("role") == "user"]
    if prev_users:
        return f"{prev_users[-1]} {message}"
    return message


def answer(message: str, top_k: int | None = None, session_id: str | None = None) -> dict[str, Any]:
    lang = detect_language(message)
    k = top_k or settings.top_k
    history = sessions.get_history(session_id)

    query_vector = embed_query(_build_search_query(message, history))
    results = vector_store.search(query_vector, top_k=max(k, 8))

    qa_hits = [r for r in results if r.get("doc_type") == "qa"]
    best_qa = qa_hits[0] if qa_hits else None
    top_score = results[0]["score"] if results else 0.0

    sources = [
        {
            "type": r.get("doc_type"),
            "question": r.get("question"),
            "category": r.get("category"),
            "source": r.get("source"),
            "score": round(r.get("score", 0.0), 3),
        }
        for r in results[:k]
    ]

    def _record(result: dict[str, Any]) -> dict[str, Any]:
        sessions.append(session_id, "user", message)
        sessions.append(session_id, "assistant", result.get("answer", ""))
        return result

    strong_curated = best_qa is not None and best_qa["score"] >= settings.qa_match_threshold
    # A strong match is only returned verbatim if its answer is substantial; short stubs
    # (whose real content is in an adjacent table) are composed by the LLM from context.
    substantial_curated = strong_curated and len(best_qa["answer"]) >= settings.min_curated_chars
    # A short follow-up ("yes", "اشرح أكثر") must always go to the LLM with history.
    is_followup = bool(history) and len(message.split()) <= 4

    # --------------------------------------------------------------------------
    # LLM path: answers EVERY on-topic question (covered or not by the docx), keeps
    # the conversation context, and politely refuses off-topic questions.
    # --------------------------------------------------------------------------
    if settings.llm_enabled and llm.llm_available():
        # For a strong, substantial Arabic curated hit (personal/business facts), return the
        # exact authoritative answer verbatim so prices/support details are never altered.
        if substantial_curated and lang == "ar" and not is_followup:
            return _record({
                "answer": best_qa["answer"],
                "language": lang,
                "mode": "curated",
                "matched_question": best_qa["question"],
                "category": best_qa.get("category"),
                "confidence": round(best_qa["score"], 3),
                "sources": sources,
            })

        # Only feed reasonably relevant context to avoid misleading the model.
        relevant = [r for r in results[:k] if r.get("score", 0.0) >= settings.min_relevance * 0.6]
        context = _build_context(relevant) if relevant else "(no directly matching context)"
        system_prompt = SYSTEM_PROMPT_AR if lang == "ar" else SYSTEM_PROMPT_EN
        label = "السؤال" if lang == "ar" else "QUESTION"

        messages = [{"role": "system", "content": system_prompt}]
        for turn in history[-(settings.max_history_turns * 2):]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": f"CONTEXT:\n{context}\n\n{label}: {message}"})

        generated = llm.generate_chat(messages)
        if generated:
            return _record({
                "answer": generated,
                "language": lang,
                "mode": f"llm:{settings.llm_provider}",
                "matched_question": best_qa["question"] if best_qa else None,
                "category": best_qa.get("category") if best_qa else None,
                "confidence": round(top_score, 3),
                "sources": sources,
            })

    # --------------------------------------------------------------------------
    # Offline extractive mode (no LLM configured / reachable).
    # --------------------------------------------------------------------------
    if top_score < settings.min_relevance:
        fallback = (
            "لم أجد معلومة مرتبطة بسؤالك في قاعدة معرفة المشروع. حاول إعادة صياغة السؤال "
            "حول نظام كشف التسلل، الهجمات، أجهزة IIoT، التثبيت، التقارير، أو الدعم."
            if lang == "ar"
            else "I couldn't find anything related in the project knowledge base. Try rephrasing "
            "your question about the IDS, attacks, IIoT devices, installation, reports, or support."
        )
        return _record({
            "answer": fallback,
            "language": lang,
            "mode": "no_match",
            "matched_question": None,
            "category": None,
            "confidence": round(top_score, 3),
            "sources": sources,
        })

    if substantial_curated:
        return _record({
            "answer": best_qa["answer"],
            "language": lang,
            "mode": "curated",
            "matched_question": best_qa["question"],
            "category": best_qa.get("category"),
            "confidence": round(best_qa["score"], 3),
            "sources": sources,
        })

    top_passages = results[:3]
    stitched = "\n\n".join(p.get("answer", "") for p in top_passages if p.get("answer"))
    prefix = (
        "أقرب معلومة وجدتها في قاعدة المعرفة:\n\n"
        if lang == "ar"
        else "Closest information I found in the knowledge base:\n\n"
    )
    return _record({
        "answer": prefix + stitched,
        "language": lang,
        "mode": "retrieval",
        "matched_question": best_qa["question"] if best_qa else None,
        "category": best_qa.get("category") if best_qa else None,
        "confidence": round(top_score, 3),
        "sources": sources,
    })
