from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CAPTURE_LEVEL_PREVIEW = "preview"
CAPTURE_LEVEL_FULL = "full"
SESSION_PREVIEW_SOURCE = "session_preview"


def normalize_session_id(name: str) -> str:
    return str(name or "").strip()


def infer_capture_level(source: str) -> str:
    normalized = str(source or "").strip().lower()
    if normalized == SESSION_PREVIEW_SOURCE:
        return CAPTURE_LEVEL_PREVIEW
    return CAPTURE_LEVEL_FULL


@dataclass
class RuntimeMessage:
    message_id: str
    session_id: str
    session_name: str
    sender_name: str
    text_original: str
    text_translated: str
    text_display: str
    created_at: str
    source: str
    capture_level: str
    is_self: bool = False
    pending_translation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionState:
    session_id: str
    session_name: str
    unread_count: int = 0
    latest_preview: str = ""
    last_message_id: str = ""
    updated_at: str = ""
    has_preview_only_messages: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeState:
    worker_state: str = "idle"
    worker_detail: str = ""
    active_session_id: str = ""
    monitor_scope: str = "all_sessions"
    message_fidelity: str = "preview_only"
    session_order: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TranslationState:
    enabled: bool = False
    provider: str = ""
    pending_count: int = 0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TTSState:
    auto_read_enabled: bool = False
    provider: str = ""
    available: bool = False
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeEvent:
    event_type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event_type,
            "payload": dict(self.payload),
        }


def build_message(
    *,
    message_id: str,
    session_name: str,
    created_at: str,
    source: str,
    text_original: str,
    text_translated: str = "",
    text_display: str = "",
    sender_name: str = "",
    is_self: bool = False,
    pending_translation: bool = False,
) -> RuntimeMessage:
    session_id = normalize_session_id(session_name)
    translated = str(text_translated or "")
    display = str(text_display or translated or text_original or "")
    return RuntimeMessage(
        message_id=str(message_id or "").strip(),
        session_id=session_id,
        session_name=str(session_name or "").strip(),
        sender_name=str(sender_name or "").strip(),
        text_original=str(text_original or ""),
        text_translated=translated,
        text_display=display,
        created_at=str(created_at or ""),
        source=str(source or "").strip(),
        capture_level=infer_capture_level(source),
        is_self=bool(is_self),
        pending_translation=bool(pending_translation),
    )
