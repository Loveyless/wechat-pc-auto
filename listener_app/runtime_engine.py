from __future__ import annotations

import itertools
import queue
import threading
from datetime import datetime
from typing import Any

from .runtime_models import RuntimeEvent, build_message, normalize_session_id
from .runtime_store import RuntimeStore


class ListenerRuntime:
    def __init__(self, *, message_limit: int = 200):
        self.store = RuntimeStore(message_limit=message_limit)
        self._event_lock = threading.RLock()
        self._subscribers: set[queue.Queue[RuntimeEvent]] = set()
        self._sequence = itertools.count(1)

    def subscribe(self, maxsize: int = 256) -> queue.Queue[RuntimeEvent]:
        q: queue.Queue[RuntimeEvent] = queue.Queue(maxsize=max(1, int(maxsize)))
        with self._event_lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue[RuntimeEvent]) -> None:
        with self._event_lock:
            self._subscribers.discard(q)

    def snapshot(self) -> dict[str, Any]:
        return self.store.snapshot()

    def list_sessions(self) -> list[dict[str, Any]]:
        return self.store.list_sessions()

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        return self.store.get_session_messages(session_id)

    def set_runtime_options(
        self,
        *,
        translate_enabled: bool,
        translate_provider: str,
        tts_auto_read_enabled: bool,
        tts_provider: str = "",
        tts_available: bool = False,
    ) -> None:
        self.store.set_translation_state(
            enabled=translate_enabled,
            provider=translate_provider,
        )
        self.store.set_tts_state(
            auto_read_enabled=tts_auto_read_enabled,
            provider=tts_provider,
            available=tts_available,
        )

    def publish_status(self, state: str, detail: str) -> None:
        self.store.set_runtime_state(worker_state=state, worker_detail=detail)
        self._publish("backend.state", {"state": state, "detail": detail})

    def publish_log(self, value: str) -> None:
        self._publish("backend.log", {"value": str(value or "")})

    def record_preview_message(
        self,
        *,
        session_name: str,
        text: str,
        created_at: str | None = None,
        sender_name: str = "",
        is_self: bool = False,
    ) -> dict[str, Any]:
        created = str(created_at or datetime.now().strftime("%H:%M:%S"))
        message = build_message(
            message_id=f"msg-{next(self._sequence)}",
            session_name=session_name,
            created_at=created,
            source="session_preview",
            text_original=text,
            sender_name=sender_name,
            is_self=is_self,
            pending_translation=True,
        )
        self.store.append_message(message)
        payload = message.to_dict()
        self._publish("message.created", payload)
        self._publish("session.upsert", self._build_session_payload(session_name))
        return payload

    def record_render_message(
        self,
        *,
        session_name: str,
        message_id: str,
        text_original: str,
        text_translated: str,
        text_display: str,
        created_at: str,
        source: str,
        sender_name: str = "",
        is_self: bool = False,
        pending_translation: bool = False,
    ) -> dict[str, Any]:
        message = build_message(
            message_id=message_id,
            session_name=session_name,
            created_at=created_at,
            source=source,
            text_original=text_original,
            text_translated=text_translated,
            text_display=text_display,
            sender_name=sender_name,
            is_self=is_self,
            pending_translation=pending_translation,
        )
        replaced = self.store.replace_message(message)
        if not replaced:
            self.store.append_message(message)
        payload = message.to_dict()
        self._publish("translation.updated", payload)
        self._publish("session.upsert", self._build_session_payload(session_name))
        return payload

    def _build_session_payload(self, session_name: str) -> dict[str, Any]:
        session_id = normalize_session_id(session_name)
        sessions = {item["session_id"]: item for item in self.store.list_sessions()}
        return sessions.get(session_id, {"session_id": session_id, "session_name": session_name})

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = RuntimeEvent(event_type=event_type, payload=payload)
        with self._event_lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                continue
