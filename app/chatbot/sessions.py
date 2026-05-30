from __future__ import annotations

import threading
from collections import OrderedDict

from .config import settings

# Simple in-memory conversation store: session_id -> [{"role", "content"}, ...].
# Good enough for a single-process deployment; swap for Redis if you scale out.
_lock = threading.Lock()
_store: "OrderedDict[str, list[dict]]" = OrderedDict()
_MAX_SESSIONS = 2000


def get_history(session_id: str | None) -> list[dict]:
    if not session_id:
        return []
    with _lock:
        return list(_store.get(session_id, []))


def append(session_id: str | None, role: str, content: str) -> None:
    if not session_id or not content:
        return
    with _lock:
        history = _store.get(session_id)
        if history is None:
            history = []
            _store[session_id] = history
        history.append({"role": role, "content": content})
        # Keep only the most recent turns.
        max_messages = settings.max_history_turns * 2
        if len(history) > max_messages:
            del history[: len(history) - max_messages]
        _store.move_to_end(session_id)
        # Evict oldest sessions if the store grows too large.
        while len(_store) > _MAX_SESSIONS:
            _store.popitem(last=False)


def reset(session_id: str | None) -> None:
    if not session_id:
        return
    with _lock:
        _store.pop(session_id, None)
