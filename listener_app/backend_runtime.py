from __future__ import annotations

import argparse
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

if __package__:
    from .runtime_config import DesktopRuntimeConfig, load_runtime_config
    from .runtime_config_store import (
        build_config_snapshot,
        prepare_translate_runtime_config_for_test,
        prepare_tts_runtime_config_for_test,
        save_config_snapshot,
    )
    from .runtime_engine import ListenerRuntime
    from .sidebar_runtime_support import (
        acquire_target_lock,
        append_log_file,
        cleanup_stale_target_locks,
        compute_worker_restart_delay,
        release_managed_target_locks,
        resolve_log_file_path,
        set_managed_target_lock_paths,
        start_worker_process,
        stderr_reader,
        stdout_reader,
        terminate_process_tree,
    )
    from .sidebar_shared import (
        CHAT_CACHE_LIMIT,
        DEDUPE_CACHE_MAX_KEYS,
        DEDUPE_CACHE_TTL_SECONDS,
        DEDUPE_CLEANUP_INTERVAL_SECONDS,
        DEFAULT_CONFIG_PATH,
        DEFAULT_LISTEN_INTERVAL_SECONDS,
        MIN_LISTEN_INTERVAL_SECONDS,
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
        TRANSLATE_QUEUE_DROP_LOG_INTERVAL_SECONDS,
        TRANSLATE_QUEUE_MAXSIZE,
        WORKER_FORCE_KILL_TIMEOUT_SECONDS,
        as_bool,
        as_non_negative_float,
        is_filtered_link_message,
        is_filtered_placeholder,
        load_json_config,
        normalize_message_for_dedupe,
        normalize_targets,
        read_config_float,
        split_sender_and_body,
        validate_float_min,
        validate_positive_float,
    )
    from .sidebar_translate_runtime import (
        build_translate_fallback,
        build_translator_runtime_text,
        create_translator,
        normalize_translate_provider,
        validate_translate_config,
    )
    from .sidebar_tts import (
        create_tts_player,
        normalize_tts_provider,
        run_tts_test_blocking,
    )
else:
    from runtime_config import DesktopRuntimeConfig, load_runtime_config
    from runtime_config_store import (
        build_config_snapshot,
        prepare_translate_runtime_config_for_test,
        prepare_tts_runtime_config_for_test,
        save_config_snapshot,
    )
    from runtime_engine import ListenerRuntime
    from sidebar_runtime_support import (
        acquire_target_lock,
        append_log_file,
        cleanup_stale_target_locks,
        compute_worker_restart_delay,
        release_managed_target_locks,
        resolve_log_file_path,
        set_managed_target_lock_paths,
        start_worker_process,
        stderr_reader,
        stdout_reader,
        terminate_process_tree,
    )
    from sidebar_shared import (
        CHAT_CACHE_LIMIT,
        DEDUPE_CACHE_MAX_KEYS,
        DEDUPE_CACHE_TTL_SECONDS,
        DEDUPE_CLEANUP_INTERVAL_SECONDS,
        DEFAULT_CONFIG_PATH,
        DEFAULT_LISTEN_INTERVAL_SECONDS,
        MIN_LISTEN_INTERVAL_SECONDS,
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
        TRANSLATE_QUEUE_DROP_LOG_INTERVAL_SECONDS,
        TRANSLATE_QUEUE_MAXSIZE,
        WORKER_FORCE_KILL_TIMEOUT_SECONDS,
        as_bool,
        as_non_negative_float,
        is_filtered_link_message,
        is_filtered_placeholder,
        load_json_config,
        normalize_message_for_dedupe,
        normalize_targets,
        read_config_float,
        split_sender_and_body,
        validate_float_min,
        validate_positive_float,
    )
    from sidebar_translate_runtime import (
        build_translate_fallback,
        build_translator_runtime_text,
        create_translator,
        normalize_translate_provider,
        validate_translate_config,
    )
    from sidebar_tts import (
        create_tts_player,
        normalize_tts_provider,
        run_tts_test_blocking,
    )

HEALTH_STATUS_STARTING = "starting"
HEALTH_STATUS_OK = "ok"
HEALTH_STATUS_STARTUP_FAILED = "startup_failed"
HEALTH_STATUS_DEGRADED = "degraded"
DEGRADED_WORKER_STATES = {"worker_backoff", "stopped"}
SETTINGS_TRANSLATE_TEST_TEXT = "这是一条翻译测试消息。"
SETTINGS_TTS_TEST_TEXT = "This is a playback test from WeChat Auto."


@dataclass(slots=True)
class BackendSettings:
    config_path: str
    config_dir: str
    log_file: str
    targets: list[str]
    listen_interval: float
    focus_refresh: bool
    worker_debug: bool
    load_retry_seconds: float
    session_preview_dedupe_window_seconds: float
    translate_enabled: bool
    translate_provider: str
    translate_fail_behavior: str
    translator: Any
    tts_auto_read_active_chat: bool
    tts_provider: str
    tts_player: Any | None
    translator_runtime_text: str
    tts_runtime_text: str
    english_only: bool


class BackendHealthState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._startup_complete = False
        self._startup_failed = False
        self._startup_detail = "backend startup pending"
        self._runtime_state = "idle"
        self._runtime_detail = ""

    def mark_starting(self, detail: str) -> None:
        with self._lock:
            self._startup_complete = False
            self._startup_failed = False
            self._startup_detail = str(detail or "").strip() or "backend startup pending"

    def mark_ready(self) -> None:
        with self._lock:
            self._startup_complete = True
            self._startup_failed = False
            if not self._startup_detail:
                self._startup_detail = "backend runtime ready"

    def mark_startup_failed(self, detail: str) -> None:
        with self._lock:
            self._startup_complete = False
            self._startup_failed = True
            self._startup_detail = str(detail or "").strip() or "backend startup failed"
            self._runtime_state = HEALTH_STATUS_STARTUP_FAILED
            self._runtime_detail = self._startup_detail

    def update_runtime(self, worker_state: str, detail: str) -> None:
        with self._lock:
            clean_state = str(worker_state or "").strip()
            if clean_state:
                self._runtime_state = clean_state
            self._runtime_detail = str(detail or "")

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            status = self._status_locked()
            detail = self._detail_locked(status)
            return {
                "status": status,
                "detail": detail,
                "worker_state": self._runtime_state,
            }

    def _status_locked(self) -> str:
        if self._startup_failed:
            return HEALTH_STATUS_STARTUP_FAILED
        if not self._startup_complete:
            return HEALTH_STATUS_STARTING
        if self._runtime_state in DEGRADED_WORKER_STATES:
            return HEALTH_STATUS_DEGRADED
        return HEALTH_STATUS_OK

    def _detail_locked(self, status: str) -> str:
        if status == HEALTH_STATUS_STARTUP_FAILED:
            return self._startup_detail
        if status == HEALTH_STATUS_STARTING:
            return self._startup_detail or self._runtime_detail or "backend startup pending"
        return self._runtime_detail or "backend runtime ready"


def cleanup_dedupe_cache(cache: dict[str, float], now_ts: float) -> None:
    expired = [key for key, ts in cache.items() if now_ts - ts > DEDUPE_CACHE_TTL_SECONDS]
    for key in expired:
        cache.pop(key, None)

    overflow = len(cache) - DEDUPE_CACHE_MAX_KEYS
    if overflow > 0:
        oldest = sorted(cache.items(), key=lambda item: item[1])[:overflow]
        for key, _ in oldest:
            cache.pop(key, None)


def load_backend_settings(config_path: str) -> BackendSettings:
    runtime_config = load_runtime_config(config_path)
    translator = create_translator(
        enabled=runtime_config.translate.enabled,
        provider=runtime_config.translate.provider,
        deeplx_url=runtime_config.translate.deeplx_url,
        source_lang=runtime_config.translate.source_lang,
        target_lang=runtime_config.translate.target_lang,
        timeout_seconds=runtime_config.translate.timeout_seconds,
        openai_base_url=runtime_config.translate.openai_base_url,
        openai_model=runtime_config.translate.openai_model,
        openai_api_key=runtime_config.translate.openai_api_key,
    )
    tts_player, tts_runtime_text = create_tts_player(
        runtime_config.tts.raw_config,
        config_dir=runtime_config.config_dir,
    )

    return BackendSettings(
        config_path=runtime_config.config_path,
        config_dir=runtime_config.config_dir,
        log_file=runtime_config.log_file,
        targets=list(runtime_config.listen.targets),
        listen_interval=runtime_config.listen.interval_seconds,
        focus_refresh=runtime_config.listen.focus_refresh,
        worker_debug=runtime_config.listen.worker_debug,
        load_retry_seconds=runtime_config.listen.load_retry_seconds,
        session_preview_dedupe_window_seconds=(
            runtime_config.listen.session_preview_dedupe_window_seconds
        ),
        translate_enabled=runtime_config.translate.enabled,
        translate_provider=runtime_config.translate.provider,
        translate_fail_behavior=runtime_config.display.on_translate_fail,
        translator=translator,
        tts_auto_read_active_chat=runtime_config.display.tts_auto_read_active_chat,
        tts_provider=runtime_config.tts.provider,
        tts_player=tts_player,
        translator_runtime_text=build_translator_runtime_text(
            runtime_config.translate.enabled,
            runtime_config.translate.provider,
            openai_base_url=runtime_config.translate.openai_base_url,
            openai_model=runtime_config.translate.openai_model,
        ),
        tts_runtime_text=tts_runtime_text,
        english_only=runtime_config.display.english_only,
    )


class BackendRuntimeService:
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH, *, message_limit: int = CHAT_CACHE_LIMIT):
        self.config_path = os.path.abspath(config_path)
        self.runtime = ListenerRuntime(message_limit=message_limit)
        self.health = BackendHealthState()
        self.settings: BackendSettings | None = None
        self.event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.translate_queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=TRANSLATE_QUEUE_MAXSIZE)
        self._closing = threading.Event()
        self._worker: Any | None = None
        self._worker_last_handled_exit_pid = 0
        self._worker_restart_attempt = 0
        self._worker_restart_deadline = 0.0
        self._runtime_thread: threading.Thread | None = None
        self._translate_thread: threading.Thread | None = None
        self._reader_threads: list[threading.Thread] = []
        self._dedupe_cache: dict[str, float] = {}
        self._last_dedupe_cleanup_at = 0.0
        self._translate_pending = 0
        self._translate_pending_lock = threading.Lock()
        self._running_targets: list[str] = []
        self._running_target_locks: dict[str, str] = {}
        self._next_message_sequence = 0

    def snapshot(self) -> dict[str, Any]:
        return self.runtime.snapshot()

    def list_sessions(self) -> list[dict[str, Any]]:
        return self.runtime.list_sessions()

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        return self.runtime.get_session_messages(session_id)

    def set_active_session(self, session_id: str) -> None:
        self.runtime.set_active_session(session_id)

    def set_tts_auto_read_enabled(self, enabled: bool) -> dict[str, Any]:
        settings = self.settings
        if settings is None:
            raise RuntimeError("backend runtime not started")
        next_enabled = bool(enabled)
        settings.tts_auto_read_active_chat = next_enabled
        self.runtime.set_tts_auto_read_enabled(next_enabled)
        active_session_id = str(self.snapshot().get("runtime", {}).get("active_session_id", ""))
        self.runtime.publish_tts_event(
            action="toggle_auto_read",
            session_id=active_session_id,
            accepted=True,
            detail="",
            auto_read_enabled=next_enabled,
        )
        self._log_line(
            f"tts auto_read {'enabled' if next_enabled else 'disabled'} by runtime api"
        )
        return self.snapshot().get("tts", {})

    def get_config_snapshot(self) -> dict[str, Any]:
        return build_config_snapshot(self.config_path)

    def save_config_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        return save_config_snapshot(self.config_path, payload)

    def get_health_snapshot(self) -> dict[str, str]:
        return self.health.snapshot()

    def test_translate_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        with prepare_translate_runtime_config_for_test(self.config_path, payload) as runtime_config:
            force_enabled = runtime_config.translate.provider != "passthrough"
            translator = create_translator(
                enabled=force_enabled,
                provider=runtime_config.translate.provider,
                deeplx_url=runtime_config.translate.deeplx_url,
                source_lang=runtime_config.translate.source_lang,
                target_lang=runtime_config.translate.target_lang,
                timeout_seconds=runtime_config.translate.timeout_seconds,
                openai_base_url=runtime_config.translate.openai_base_url,
                openai_model=runtime_config.translate.openai_model,
                openai_api_key=runtime_config.translate.openai_api_key,
            )
            try:
                output_text = translator.translate(SETTINGS_TRANSLATE_TEST_TEXT)
            except Exception as exc:
                self._log_line(
                    f"translate settings test failed provider={runtime_config.translate.provider} error={exc}"
                )
                raise RuntimeError(str(exc)) from exc
            detail = build_translator_runtime_text(
                force_enabled,
                runtime_config.translate.provider,
                openai_base_url=runtime_config.translate.openai_base_url,
                openai_model=runtime_config.translate.openai_model,
            )
            self._log_line(
                f"translate settings test ok provider={runtime_config.translate.provider} chars={len(output_text)}"
            )
            return {
                "provider": runtime_config.translate.provider,
                "input_text": SETTINGS_TRANSLATE_TEST_TEXT,
                "output_text": output_text,
                "detail": detail,
            }

    def test_tts_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        with prepare_tts_runtime_config_for_test(self.config_path, payload) as runtime_config:
            player, runtime_text = create_tts_player(
                runtime_config.tts.raw_config,
                config_dir=runtime_config.config_dir,
            )
            if player is None:
                raise RuntimeError(runtime_text or "tts unavailable")
            if hasattr(player, "set_logger"):
                player.set_logger(self._log_line)
            try:
                ok = bool(run_tts_test_blocking(player, SETTINGS_TTS_TEST_TEXT))
            except Exception as exc:
                self._log_line(
                    f"tts settings test failed provider={runtime_config.tts.provider} error={exc}"
                )
                raise RuntimeError(str(exc)) from exc
            if not ok:
                last_error = str(getattr(player, "_last_error", "") or "").strip()
                detail = last_error or "tts rejected"
                self._log_line(
                    f"tts settings test rejected provider={runtime_config.tts.provider} detail={detail}"
                )
                raise RuntimeError(detail)
            self._log_line(f"tts settings test ok provider={runtime_config.tts.provider}")
            return {
                "provider": runtime_config.tts.provider,
                "input_text": SETTINGS_TTS_TEST_TEXT,
                "detail": runtime_text,
            }

    def mark_startup_failed(self, detail: str) -> None:
        self.health.mark_startup_failed(detail)

    def start(self) -> None:
        if self._runtime_thread and self._runtime_thread.is_alive():
            return
        self.health.mark_starting("initializing backend runtime")
        self.settings = load_backend_settings(self.config_path)
        stale_count = cleanup_stale_target_locks()
        if stale_count > 0:
            self._log_line(f"cleaned stale locks: {stale_count}")

        self._running_targets = []
        self._running_target_locks = {}
        for target in self.settings.targets:
            locked, lock_info = acquire_target_lock(target)
            if not locked:
                raise RuntimeError(f"acquire target lock failed for {target}: {lock_info}")
            self._running_targets.append(target)
            self._running_target_locks[target] = lock_info
        set_managed_target_lock_paths(list(self._running_target_locks.values()))

        if self.settings.tts_player and hasattr(self.settings.tts_player, "set_logger"):
            self.settings.tts_player.set_logger(self._log_line)

        self.runtime.set_runtime_options(
            translate_enabled=self.settings.translate_enabled,
            translate_provider=self.settings.translate_provider,
            tts_auto_read_enabled=self.settings.tts_auto_read_active_chat,
            tts_provider=self.settings.tts_provider,
            tts_available=self.settings.tts_player is not None,
        )
        self.runtime.set_runtime_contract(
            monitor_scope="all_sessions",
            message_fidelity="preview_only",
        )
        self._publish_runtime_status("starting", "starting worker")
        self._log_line(self.settings.translator_runtime_text)
        self._log_line(self.settings.tts_runtime_text)
        self._log_line(
            "backend scope=all_sessions"
            + (
                f" dev_target_locks={self._running_targets}"
                if self._running_targets
                else ""
            )
        )

        self._translate_thread = threading.Thread(target=self._translate_worker, daemon=True)
        self._translate_thread.start()
        self._launch_worker("starting worker")
        self._runtime_thread = threading.Thread(target=self._runtime_loop, daemon=True)
        self._runtime_thread.start()
        self.health.mark_ready()
        self._sync_health_from_runtime()

    def stop(self) -> None:
        self._closing.set()
        self._worker_restart_deadline = 0.0
        worker = self._worker
        self._worker = None
        if worker is not None:
            try:
                terminate_process_tree(worker)
            except Exception:
                pass
        self._signal_translate_worker_stop()
        if self._runtime_thread and self._runtime_thread.is_alive():
            self._runtime_thread.join(timeout=2)
        if self._translate_thread and self._translate_thread.is_alive():
            self._translate_thread.join(timeout=2)
        for thread in self._reader_threads:
            if thread.is_alive():
                thread.join(timeout=1)
        release_managed_target_locks()
        self._publish_runtime_status("stopped", "backend stopped")

    def wait(self, timeout: float | None = None) -> None:
        thread = self._runtime_thread
        if thread is None:
            return
        thread.join(timeout=timeout)

    def _log_line(self, line: str) -> None:
        value = str(line or "").strip()
        if not value:
            return
        if self.settings is not None:
            append_log_file(self.settings.log_file, value)
        self.runtime.publish_log(value)

    def _launch_worker(self, reason: str) -> bool:
        assert self.settings is not None
        try:
            self._worker = start_worker_process(
                self._running_targets,
                self.settings.listen_interval,
                self.settings.worker_debug,
                self.settings.focus_refresh,
                self.settings.load_retry_seconds,
                all_sessions=True,
            )
        except Exception as exc:
            attempt = self._worker_restart_attempt + 1
            self._schedule_worker_restart(f"{reason} failed: {exc}", attempt)
            return False

        self._worker_last_handled_exit_pid = 0
        self._worker_restart_deadline = 0.0
        self._publish_runtime_status("starting", reason)
        self._log_line(f"worker start pid={getattr(self._worker, 'pid', 0)} reason={reason}")
        stdout_thread = threading.Thread(
            target=stdout_reader,
            args=(self._worker, self.event_queue),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=stderr_reader,
            args=(self._worker, self.event_queue),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        self._reader_threads.extend([stdout_thread, stderr_thread])
        return True

    def _schedule_worker_restart(self, reason: str, attempt: int) -> None:
        delay = compute_worker_restart_delay(attempt)
        self._worker_restart_attempt = attempt
        self._worker_restart_deadline = time.time() + delay
        self._publish_runtime_status("worker_backoff", f"{reason}, retry in {delay:.1f}s")
        self._log_line(f"worker backoff attempt={attempt} delay={delay:.1f}s reason={reason}")

    def _publish_runtime_status(self, state: str, detail: str) -> None:
        self.runtime.publish_status(state, detail)
        self._sync_health_from_runtime()

    def _sync_health_from_runtime(self) -> None:
        snapshot = self.runtime.snapshot().get("runtime", {})
        self.health.update_runtime(
            str(snapshot.get("worker_state", "")),
            str(snapshot.get("worker_detail", "")),
        )

    def _runtime_loop(self) -> None:
        while not self._closing.is_set():
            try:
                event = self.event_queue.get(timeout=0.1)
            except queue.Empty:
                event = None
            if isinstance(event, dict):
                self._handle_event(event)
            self._handle_worker_state()

    def _handle_worker_state(self) -> None:
        now_ts = time.time()
        worker = self._worker
        if worker is not None:
            return_code = worker.poll()
            pid = getattr(worker, "pid", 0)
            if return_code is not None and self._worker_last_handled_exit_pid != pid:
                self._worker_last_handled_exit_pid = pid
                self._worker = None
                exit_line = f"worker exited code={return_code}"
                self._log_line(exit_line)
                if not self._closing.is_set():
                    attempt = self._worker_restart_attempt + 1
                    self._schedule_worker_restart(f"code={return_code}", attempt)
                return
        if (
            not self._closing.is_set()
            and self._worker_restart_deadline
            and now_ts >= self._worker_restart_deadline
        ):
            self._launch_worker(f"restarting worker attempt={self._worker_restart_attempt}")

    def _handle_event(self, event: dict[str, Any]) -> None:
        assert self.settings is not None
        kind = str(event.get("type", "")).strip()
        default_chat_name = self._running_targets[0] if self._running_targets else ""
        if kind == "status":
            state = str(event.get("state", "status")).strip() or "status"
            detail = str(event.get("value", ""))
            if state == "running":
                self._worker_restart_attempt = 0
                self._worker_restart_deadline = 0.0
            self._publish_runtime_status(state, detail)
            self._log_line(f"status: {detail}")
            return

        if kind == "session_snapshot":
            items = event.get("items")
            if not isinstance(items, list):
                self.runtime.publish_error(
                    source="backend_runtime",
                    message="invalid session_snapshot payload",
                    detail=str(event),
                )
                return
            normalized_items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                session_name = str(item.get("chat_name") or item.get("session_name") or "").strip()
                if not session_name:
                    continue
                normalized_items.append(
                    {
                        "session_name": session_name,
                        "latest_preview": str(item.get("preview", "")),
                        "unread_count": item.get("unread", 0),
                        "updated_at": str(item.get("updated_at", "")),
                        "preview_only": True,
                    }
                )
            self.runtime.sync_session_snapshot(normalized_items)
            return

        if kind == "log":
            self._log_line(str(event.get("value", "")))
            return

        if kind == "render_message":
            payload = self.runtime.record_render_message(
                session_name=str(event.get("chat_name") or default_chat_name),
                message_id=str(event.get("message_id", "")),
                text_original=str(event.get("text_cn", "")),
                text_translated=str(event.get("text_en", "")),
                text_display=str(event.get("text_display", event.get("text_en", ""))),
                created_at=str(event.get("created_at") or datetime.now().strftime("%H:%M:%S")),
                source=str(event.get("source", "")),
                sender_name=str(event.get("sender_name", "")),
                is_self=bool(event.get("is_self", False)),
                pending_translation=bool(event.get("pending_translation", False)),
            )
            self._maybe_auto_tts(payload)
            return

        if kind != "message":
            self.runtime.publish_error(
                source="backend_runtime",
                message="unknown event",
                detail=str(event),
            )
            self._log_line(f"unknown event: {event}")
            return

        chat_name = str(event.get("chat_name") or default_chat_name).strip()
        if not chat_name:
            return
        cn_text = str(event.get("text", "")).strip()
        if not cn_text:
            return

        sender_name, body_cn, is_self = split_sender_and_body(cn_text)
        if not body_cn:
            return
        if is_filtered_placeholder(body_cn) or is_filtered_link_message(body_cn):
            return

        normalized_body = normalize_message_for_dedupe(body_cn)
        if not normalized_body:
            return

        now_ts = time.time()
        dedupe_key = f"{chat_name}::{sender_name}::{normalized_body}"
        prev_ts = self._dedupe_cache.get(dedupe_key)
        if (
            prev_ts is not None
            and now_ts - prev_ts <= self.settings.session_preview_dedupe_window_seconds
        ):
            return
        self._dedupe_cache[dedupe_key] = now_ts
        if now_ts - self._last_dedupe_cleanup_at >= DEDUPE_CLEANUP_INTERVAL_SECONDS:
            cleanup_dedupe_cache(self._dedupe_cache, now_ts)
            self._last_dedupe_cleanup_at = now_ts

        created_at = str(event.get("created_at") or datetime.now().strftime("%H:%M:%S"))
        message_id = f"msg-{self._next_message_sequence}"
        self._next_message_sequence += 1
        preview_payload = self.runtime.record_preview_message(
            session_name=chat_name,
            text=body_cn,
            created_at=created_at,
            sender_name=sender_name,
            is_self=is_self,
        )
        self._enqueue_translate_task(
            {
                "message_id": preview_payload["message_id"] or message_id,
                "chat_name": chat_name,
                "sender_name": sender_name,
                "body_cn": body_cn,
                "is_self": is_self,
                "source": "session_preview",
                "created_at": created_at,
            }
        )

    def _enqueue_translate_task(self, task: dict[str, Any]) -> None:
        try:
            self.translate_queue.put_nowait(task)
            self._adjust_translate_pending(1)
            return
        except queue.Full:
            pass

        dropped = object()
        try:
            dropped = self.translate_queue.get_nowait()
        except queue.Empty:
            pass

        if dropped is None:
            try:
                self.translate_queue.put_nowait(None)
            except queue.Full:
                pass
            self._resolve_dropped_translate_task(task)
        else:
            if isinstance(dropped, dict):
                self._adjust_translate_pending(-1)
                self._resolve_dropped_translate_task(dropped)
            try:
                self.translate_queue.put_nowait(task)
                self._adjust_translate_pending(1)
                return
            except queue.Full:
                self._resolve_dropped_translate_task(task)

        self._log_line(
            f"translate queue overflow interval={TRANSLATE_QUEUE_DROP_LOG_INTERVAL_SECONDS:.1f}s"
        )
        self.runtime.publish_error(
            source="translate",
            message="queue overflow",
            detail="translate queue reached maxsize",
        )

    def _signal_translate_worker_stop(self) -> None:
        try:
            self.translate_queue.put_nowait(None)
            return
        except queue.Full:
            pass

        try:
            dropped = self.translate_queue.get_nowait()
            if isinstance(dropped, dict):
                self._adjust_translate_pending(-1)
        except queue.Empty:
            pass
        try:
            self.translate_queue.put_nowait(None)
        except queue.Full:
            pass

    def _adjust_translate_pending(self, delta: int) -> None:
        with self._translate_pending_lock:
            self._translate_pending = max(0, self._translate_pending + int(delta))
            self.runtime.update_translation_state(pending_count=self._translate_pending)

    def _resolve_dropped_translate_task(self, task: dict[str, Any]) -> None:
        body_cn = str(task.get("body_cn", ""))
        fallback_text = build_translate_fallback(
            body_cn,
            RuntimeError("translate queue overflow"),
            self.settings.translate_fail_behavior,
        )
        self.runtime.publish_error(
            source="translate",
            message="queue overflow",
            detail=body_cn[:120],
        )
        self.runtime.record_render_message(
            session_name=str(task.get("chat_name", "")),
            message_id=str(task.get("message_id", "")),
            text_original=body_cn,
            text_translated=fallback_text,
            text_display=fallback_text,
            created_at=str(task.get("created_at", "")),
            source=str(task.get("source", "session_preview")),
            sender_name=str(task.get("sender_name", "")),
            is_self=bool(task.get("is_self", False)),
            pending_translation=False,
        )

    def _translate_worker(self) -> None:
        assert self.settings is not None
        while True:
            task = self.translate_queue.get()
            if task is None:
                return
            self._adjust_translate_pending(-1)
            body_cn = str(task.get("body_cn", ""))
            rendered_body = body_cn
            last_error = ""
            if self.settings.translate_enabled:
                try:
                    rendered_body = self.settings.translator.translate(body_cn)
                except Exception as exc:
                    last_error = str(exc)
                    rendered_body = build_translate_fallback(
                        body_cn,
                        exc,
                        self.settings.translate_fail_behavior,
                    )
                    self.runtime.publish_error(
                        source="translate",
                        message="translate fallback",
                        detail=last_error,
                    )
                    self._log_line(f"translate fallback: {exc}")

            rendered_text = rendered_body
            if not self.settings.english_only and rendered_body != body_cn:
                rendered_text = f"{rendered_text}\nCN: {body_cn}"

            self.runtime.update_translation_state(last_error=last_error)
            payload = self.runtime.record_render_message(
                session_name=str(task.get("chat_name", "")),
                message_id=str(task.get("message_id", "")),
                text_original=body_cn,
                text_translated=rendered_body,
                text_display=rendered_text,
                created_at=str(task.get("created_at", "")),
                source=str(task.get("source", "session_preview")),
                sender_name=str(task.get("sender_name", "")),
                is_self=bool(task.get("is_self", False)),
                pending_translation=False,
            )
            self._maybe_auto_tts(payload)

    def _maybe_auto_tts(self, message_payload: dict[str, Any]) -> None:
        assert self.settings is not None
        if not self.settings.tts_auto_read_active_chat or self.settings.tts_player is None:
            return
        active_session_id = str(self.snapshot().get("runtime", {}).get("active_session_id", ""))
        if not active_session_id or active_session_id != str(message_payload.get("session_id", "")):
            return
        speak_async = getattr(self.settings.tts_player, "speak_async", None)
        if not callable(speak_async):
            return
        text = str(message_payload.get("text_display") or message_payload.get("text_translated") or "")
        if not text:
            return
        message_id = str(message_payload.get("message_id", ""))
        session_id = str(message_payload.get("session_id", ""))
        try:
            ok = bool(speak_async(text))
        except Exception as exc:
            self.runtime.update_tts_state(last_error=str(exc))
            self.runtime.publish_tts_event(
                action="autoplay",
                session_id=session_id,
                message_id=message_id,
                accepted=False,
                detail=str(exc),
            )
            self.runtime.publish_error(
                source="tts",
                message="playback failed",
                detail=str(exc),
            )
            self._log_line(f"tts failed: {exc}")
            return
        self.runtime.update_tts_state(available=ok, last_error="" if ok else "tts rejected")
        self.runtime.publish_tts_event(
            action="autoplay",
            session_id=session_id,
            message_id=message_id,
            accepted=ok,
            detail="" if ok else "tts rejected",
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tk-free backend runtime for the desktop shell.")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="JSON config path")
    return parser
