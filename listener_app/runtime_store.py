from __future__ import annotations

import threading
from typing import Any

from .runtime_models import (
    CAPTURE_LEVEL_PREVIEW,
    RuntimeMessage,
    RuntimeState,
    SessionState,
    TTSState,
    TranslationState,
    normalize_session_id,
)


class RuntimeStore:
    def __init__(self, message_limit: int = 200):
        self._lock = threading.RLock()
        self._message_limit = max(1, int(message_limit))
        self._runtime_state = RuntimeState()
        self._translation_state = TranslationState()
        self._tts_state = TTSState()
        self._sessions: dict[str, SessionState] = {}
        self._messages: dict[str, list[RuntimeMessage]] = {}
        self._message_index: dict[str, tuple[str, int]] = {}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "runtime": self._runtime_state.to_dict(),
                "translation": self._translation_state.to_dict(),
                "tts": self._tts_state.to_dict(),
                "sessions": [self._sessions[session_id].to_dict() for session_id in self._runtime_state.session_order if session_id in self._sessions],
            }

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._sessions[session_id].to_dict() for session_id in self._runtime_state.session_order if session_id in self._sessions]

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        normalized = normalize_session_id(session_id)
        with self._lock:
            return [item.to_dict() for item in self._messages.get(normalized, [])]

    def set_runtime_state(
        self,
        *,
        worker_state: str | None = None,
        worker_detail: str | None = None,
        active_session_id: str | None = None,
    ) -> None:
        with self._lock:
            if worker_state is not None:
                self._runtime_state.worker_state = str(worker_state or "idle").strip() or "idle"
            if worker_detail is not None:
                self._runtime_state.worker_detail = str(worker_detail or "")
            if active_session_id is not None:
                self._runtime_state.active_session_id = normalize_session_id(active_session_id)

    def set_translation_state(
        self,
        *,
        enabled: bool | None = None,
        provider: str | None = None,
        pending_count: int | None = None,
        last_error: str | None = None,
    ) -> None:
        with self._lock:
            if enabled is not None:
                self._translation_state.enabled = bool(enabled)
            if provider is not None:
                self._translation_state.provider = str(provider or "").strip()
            if pending_count is not None:
                self._translation_state.pending_count = max(0, int(pending_count))
            if last_error is not None:
                self._translation_state.last_error = str(last_error or "")

    def set_tts_state(
        self,
        *,
        auto_read_enabled: bool | None = None,
        provider: str | None = None,
        available: bool | None = None,
        last_error: str | None = None,
    ) -> None:
        with self._lock:
            if auto_read_enabled is not None:
                self._tts_state.auto_read_enabled = bool(auto_read_enabled)
            if provider is not None:
                self._tts_state.provider = str(provider or "").strip()
            if available is not None:
                self._tts_state.available = bool(available)
            if last_error is not None:
                self._tts_state.last_error = str(last_error or "")

    def upsert_session(
        self,
        *,
        session_name: str,
        updated_at: str,
        latest_preview: str = "",
        unread_count: int | None = None,
        preview_only: bool = False,
    ) -> SessionState:
        session_id = normalize_session_id(session_name)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionState(session_id=session_id, session_name=session_name)
                self._sessions[session_id] = session
                self._runtime_state.session_order.append(session_id)
            session.session_name = str(session_name or "").strip()
            session.updated_at = str(updated_at or "")
            if latest_preview:
                session.latest_preview = str(latest_preview or "")
            if unread_count is not None:
                session.unread_count = max(0, int(unread_count))
            if preview_only:
                session.has_preview_only_messages = True
            return session

    def append_message(self, message: RuntimeMessage) -> RuntimeMessage:
        with self._lock:
            session = self.upsert_session(
                session_name=message.session_name,
                updated_at=message.created_at,
                latest_preview=message.text_original,
                preview_only=message.capture_level == CAPTURE_LEVEL_PREVIEW,
            )
            session.last_message_id = message.message_id
            cache = self._messages.setdefault(message.session_id, [])
            cache.append(message)
            if len(cache) > self._message_limit:
                overflow = len(cache) - self._message_limit
                removed = cache[:overflow]
                del cache[:overflow]
                for item in removed:
                    self._message_index.pop(item.message_id, None)
                for idx, item in enumerate(cache):
                    self._message_index[item.message_id] = (message.session_id, idx)
            self._message_index[message.message_id] = (message.session_id, len(cache) - 1)
            return message

    def replace_message(self, message: RuntimeMessage) -> bool:
        with self._lock:
            location = self._message_index.get(message.message_id)
            if not location:
                return False
            session_id, idx = location
            cache = self._messages.get(session_id)
            if cache is None or idx >= len(cache):
                return False
            cache[idx] = message
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_message_id = message.message_id
                session.updated_at = message.created_at
                if message.text_original:
                    session.latest_preview = message.text_original
            return True
