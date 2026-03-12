import argparse
import atexit
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict

if __package__:
    from .sidebar_shared import (
        CHAT_CACHE_LIMIT,
        DEDUPE_CACHE_MAX_KEYS,
        DEDUPE_CACHE_TTL_SECONDS,
        DEDUPE_CLEANUP_INTERVAL_SECONDS,
        DEFAULT_CONFIG_PATH,
        DEFAULT_LISTEN_INTERVAL_SECONDS,
        DEFAULT_SIDEBAR_WIDTH,
        MIN_LISTEN_INTERVAL_SECONDS,
        MIN_SIDEBAR_WIDTH,
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
        TRANSLATE_PENDING_TEXT,
        TRANSLATE_QUEUE_DROP_LOG_INTERVAL_SECONDS,
        TRANSLATE_QUEUE_MAXSIZE,
        UI_DRAIN_INTERVAL_MS,
        WORKER_FORCE_KILL_TIMEOUT_SECONDS,
        WORKER_STOP_TIMEOUT_SECONDS,
        as_bool,
        as_non_negative_float,
        is_filtered_link_message,
        is_filtered_placeholder,
        is_frozen_app,
        load_json_config,
        normalize_message_for_dedupe,
        normalize_targets,
        read_config_float,
        read_config_int,
        save_listener_targets_config,
        split_sender_and_body,
        validate_float_min,
        validate_int_min,
        validate_positive_float,
    )
    from .sidebar_runtime_support import (
        acquire_target_lock,
        append_log_file,
        build_worker_status_text,
        cleanup_stale_target_locks,
        compute_worker_restart_delay,
        release_managed_target_locks,
        release_target_lock_path,
        resolve_log_file_path,
        set_managed_target_lock_paths,
        start_worker_process,
        stderr_reader,
        stdout_reader,
    )
    from .sidebar_tts import check_tts_dependency_packaging, create_tts_player
    from .sidebar_translate_runtime import (
        build_translate_fallback,
        build_translator_runtime_text,
        create_translator,
        normalize_translate_provider,
        validate_translate_config,
    )
    from .sidebar_ui import SidebarMessage, SidebarUI
else:
    from sidebar_shared import (
        CHAT_CACHE_LIMIT,
        DEDUPE_CACHE_MAX_KEYS,
        DEDUPE_CACHE_TTL_SECONDS,
        DEDUPE_CLEANUP_INTERVAL_SECONDS,
        DEFAULT_CONFIG_PATH,
        DEFAULT_LISTEN_INTERVAL_SECONDS,
        DEFAULT_SIDEBAR_WIDTH,
        MIN_LISTEN_INTERVAL_SECONDS,
        MIN_SIDEBAR_WIDTH,
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
        TRANSLATE_PENDING_TEXT,
        TRANSLATE_QUEUE_DROP_LOG_INTERVAL_SECONDS,
        TRANSLATE_QUEUE_MAXSIZE,
        UI_DRAIN_INTERVAL_MS,
        WORKER_FORCE_KILL_TIMEOUT_SECONDS,
        WORKER_STOP_TIMEOUT_SECONDS,
        as_bool,
        as_non_negative_float,
        is_filtered_link_message,
        is_filtered_placeholder,
        is_frozen_app,
        load_json_config,
        normalize_message_for_dedupe,
        normalize_targets,
        read_config_float,
        read_config_int,
        save_listener_targets_config,
        split_sender_and_body,
        validate_float_min,
        validate_int_min,
        validate_positive_float,
    )
    from sidebar_runtime_support import (
        acquire_target_lock,
        append_log_file,
        build_worker_status_text,
        cleanup_stale_target_locks,
        compute_worker_restart_delay,
        release_managed_target_locks,
        release_target_lock_path,
        resolve_log_file_path,
        set_managed_target_lock_paths,
        start_worker_process,
        stderr_reader,
        stdout_reader,
    )
    from sidebar_tts import check_tts_dependency_packaging, create_tts_player
    from sidebar_translate_runtime import (
        build_translate_fallback,
        build_translator_runtime_text,
        create_translator,
        normalize_translate_provider,
        validate_translate_config,
    )
    from sidebar_ui import SidebarMessage, SidebarUI

def cleanup_dedupe_cache(cache: Dict[str, float], now_ts: float):
    expired = [key for key, ts in cache.items() if now_ts - ts > DEDUPE_CACHE_TTL_SECONDS]
    for key in expired:
        cache.pop(key, None)

    overflow = len(cache) - DEDUPE_CACHE_MAX_KEYS
    if overflow > 0:
        oldest = sorted(cache.items(), key=lambda item: item[1])[:overflow]
        for key, _ in oldest:
            cache.pop(key, None)


def maybe_show_frozen_error_dialog(message: str, title: str = "wechat_sidebar 启动失败"):
    if not is_frozen_app() or os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        pass


def exit_startup_error(message: str, exit_code: int = 2):
    print(f"[sidebar] {message}", file=sys.stderr)
    maybe_show_frozen_error_dialog(message)
    raise SystemExit(exit_code)

def main():
    parser = argparse.ArgumentParser(
        description="Sidebar listener: monitor target chats in session-only mode and show translated output."
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="JSON config path")
    parser.add_argument(
        "--check-tts-deps",
        action="store_true",
        help="Validate packaged TTS Python dependencies and exit",
    )
    parser.add_argument("--target", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    try:
        config = load_json_config(config_path)
    except Exception as e:
        exit_startup_error(f"load config failed: {e}")

    config_dir = os.path.dirname(config_path)
    listen_cfg = config.get("listen", {}) if isinstance(config.get("listen", {}), dict) else {}
    translate_cfg = (
        config.get("translate", {}) if isinstance(config.get("translate", {}), dict) else {}
    )
    display_cfg = config.get("display", {}) if isinstance(config.get("display", {}), dict) else {}
    tts_cfg = config.get("tts", {}) if isinstance(config.get("tts", {}), dict) else {}
    logging_cfg = config.get("logging", {}) if isinstance(config.get("logging", {}), dict) else {}

    if args.check_tts_deps:
        try:
            ok, detail = check_tts_dependency_packaging(tts_cfg)
        except RuntimeError as e:
            print(f"[sidebar] tts dependency check failed: {e}", file=sys.stderr)
            raise SystemExit(2)
        stream = sys.stdout if ok else sys.stderr
        print(f"[sidebar] {detail}", file=stream, flush=True)
        raise SystemExit(0 if ok else 2)

    targets = normalize_targets(listen_cfg.get("targets"))
    if not targets:
        exit_startup_error("config listen.targets is empty")
    if str(args.target or "").strip():
        forced_target = str(args.target).strip()
        if forced_target not in targets:
            print(
                f"[sidebar] warning: --target not found in config listen.targets: {forced_target}",
                flush=True,
            )
        targets = [forced_target]

    listen_mode = str(listen_cfg.get("mode", "session")).strip().lower()
    if listen_mode and listen_mode != "session":
        exit_startup_error("session-only branch only supports listen.mode=session")
    focus_refresh = as_bool(listen_cfg.get("focus_refresh"), False)
    worker_debug = as_bool(listen_cfg.get("worker_debug"), False)
    load_retry_seconds = as_non_negative_float(listen_cfg.get("load_retry_seconds"), 10.0)
    session_preview_dedupe_window_seconds = as_non_negative_float(
        listen_cfg.get("session_preview_dedupe_window_seconds"),
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
    )

    translate_enabled = as_bool(translate_cfg.get("enabled"), True)
    translate_provider = str(translate_cfg.get("provider", "deeplx"))
    deeplx_url = str(translate_cfg.get("deeplx_url") or os.getenv("DEEPLX_URL", "")).strip()
    source_lang = str(translate_cfg.get("source_lang", "auto"))
    target_lang = str(translate_cfg.get("target_lang", "EN"))

    english_only = as_bool(display_cfg.get("english_only"), True)
    tts_auto_read_active_chat = as_bool(display_cfg.get("tts_auto_read_active_chat"), True)
    translate_fail_behavior = str(display_cfg.get("on_translate_fail", "show_cn_with_reason"))
    if translate_fail_behavior not in ("show_cn_with_reason", "show_cn", "show_reason"):
        translate_fail_behavior = "show_cn_with_reason"
    side = str(display_cfg.get("side", "right"))
    if side not in ("left", "right"):
        side = "right"

    try:
        listen_interval = read_config_float(
            listen_cfg,
            "interval_seconds",
            DEFAULT_LISTEN_INTERVAL_SECONDS,
        )
        translate_timeout = read_config_float(translate_cfg, "timeout_seconds", 8.0)
        width = read_config_int(display_cfg, "width", DEFAULT_SIDEBAR_WIDTH)
        listen_interval = validate_positive_float("listen.interval_seconds", listen_interval)
        listen_interval = validate_float_min(
            "listen.interval_seconds",
            listen_interval,
            MIN_LISTEN_INTERVAL_SECONDS,
        )
        translate_timeout = validate_positive_float("translate.timeout_seconds", translate_timeout)
        width = validate_int_min("display.width", width, MIN_SIDEBAR_WIDTH)
        load_retry_seconds = validate_positive_float(
            "listen.load_retry_seconds",
            load_retry_seconds,
        )
        translate_provider = normalize_translate_provider(translate_provider)
        validate_translate_config(translate_enabled, translate_provider, deeplx_url)
        translator = create_translator(
            enabled=translate_enabled,
            provider=translate_provider,
            deeplx_url=deeplx_url,
            source_lang=source_lang,
            target_lang=target_lang,
            timeout_seconds=translate_timeout,
        )
        translator_runtime_text = build_translator_runtime_text(
            translate_enabled,
            translate_provider,
        )
        tts_player, tts_runtime_text = create_tts_player(
            tts_cfg,
            config_dir=config_dir,
        )
    except RuntimeError as e:
        exit_startup_error(f"invalid config: {e}")

    log_file = resolve_log_file_path(logging_cfg.get("file", ""))
    cleaned_stale_locks = cleanup_stale_target_locks()
    if cleaned_stale_locks > 0:
        print(f"[sidebar] cleaned stale locks: {cleaned_stale_locks}", flush=True)
        append_log_file(log_file, f"cleaned stale locks: {cleaned_stale_locks}")

    running_targets: list[str] = []
    running_target_locks: dict[str, str] = {}
    skipped_targets: list[tuple[str, str]] = []
    for target in targets:
        locked, lock_info = acquire_target_lock(target)
        if not locked:
            skipped_targets.append((target, lock_info))
            print(f"[sidebar] skip target={target}: {lock_info}", flush=True)
            continue
        running_targets.append(target)
        running_target_locks[target] = lock_info
    if not running_targets:
        print("[sidebar] no available targets to start", flush=True)
        return
    set_managed_target_lock_paths(list(running_target_locks.values()))
    atexit.register(release_managed_target_locks)

    ui = SidebarUI(
        width=width,
        side=side,
        targets=running_targets,
        message_limit=CHAT_CACHE_LIMIT,
        tts_player=tts_player,
        tts_auto_read_active_chat=tts_auto_read_active_chat,
    )
    for target, reason in skipped_targets:
        append_log_file(log_file, f"skip target={target}: {reason}")

    append_log_file(log_file, "sidebar start")
    append_log_file(log_file, f"requested targets={targets}")
    append_log_file(log_file, f"running targets={running_targets}")
    append_log_file(log_file, translator_runtime_text)
    append_log_file(log_file, tts_runtime_text)
    append_log_file(log_file, f"tts auto read active chat={tts_auto_read_active_chat}")
    append_log_file(log_file, f"load retry seconds={load_retry_seconds}")
    append_log_file(log_file, f"chat cache limit={CHAT_CACHE_LIMIT}")
    append_log_file(log_file, f"session preview dedupe window={session_preview_dedupe_window_seconds}s")
    event_queue: "queue.Queue[dict]" = queue.Queue()
    runtime_log = lambda line: event_queue.put({"type": "log", "value": str(line or "")})
    if tts_player and hasattr(tts_player, "set_logger"):
        tts_player.set_logger(runtime_log)
    ui.set_runtime_logger(runtime_log)
    translate_queue: "queue.Queue[dict | None]" = queue.Queue(maxsize=TRANSLATE_QUEUE_MAXSIZE)
    dedupe_cache: Dict[str, float] = {}
    last_dedupe_cleanup_at = 0.0
    translate_queue_drop_count = 0
    last_translate_queue_drop_log_at = 0.0
    next_message_sequence = 0
    worker: subprocess.Popen | None = None
    worker_last_handled_exit_pid = 0
    worker_restart_attempt = 0
    worker_restart_deadline = 0.0
    worker_stop_deadline = 0.0
    worker_force_kill_requested = False
    worker_state = "starting"
    worker_detail = "starting worker"
    pending_worker_launch_reason = ""
    closing = False
    ui.set_status(build_worker_status_text(worker_state, worker_detail, len(running_targets)))

    def sync_target_lock_paths():
        set_managed_target_lock_paths(list(running_target_locks.values()))

    def persist_targets_to_config(next_targets: list[str]):
        save_listener_targets_config(config_path, config, next_targets)

    def clear_target_runtime_state(target_name: str):
        prefix = f"{target_name}::"
        stale_keys = [key for key in dedupe_cache if key.startswith(prefix)]
        for key in stale_keys:
            dedupe_cache.pop(key, None)

    def schedule_worker_restart(reason: str, attempt: int):
        nonlocal worker_restart_attempt, worker_restart_deadline, worker_state, worker_detail
        nonlocal worker_stop_deadline, worker_force_kill_requested
        delay = compute_worker_restart_delay(attempt)
        worker_restart_attempt = attempt
        worker_restart_deadline = time.time() + delay
        worker_stop_deadline = 0.0
        worker_force_kill_requested = False
        worker_state = "worker_backoff"
        worker_detail = f"{reason}, retry in {delay:.1f}s"
        backoff_line = f"worker backoff attempt={attempt} delay={delay:.1f}s reason={reason}"
        ui.append_log(backoff_line)
        append_log_file(log_file, backoff_line)

    def launch_worker(reason: str) -> bool:
        nonlocal worker, worker_last_handled_exit_pid, worker_restart_deadline, worker_state, worker_detail
        nonlocal worker_stop_deadline, worker_force_kill_requested
        try:
            worker = start_worker_process(
                running_targets,
                listen_interval,
                worker_debug,
                focus_refresh,
                load_retry_seconds,
            )
        except Exception as e:
            attempt = worker_restart_attempt + 1
            schedule_worker_restart(f"{reason} failed: {e}", attempt)
            return False

        worker_last_handled_exit_pid = 0
        worker_restart_deadline = 0.0
        worker_stop_deadline = 0.0
        worker_force_kill_requested = False
        worker_state = "starting"
        worker_detail = reason
        append_log_file(log_file, f"worker start pid={worker.pid} reason={reason}")
        t_out = threading.Thread(target=stdout_reader, args=(worker, event_queue), daemon=True)
        t_err = threading.Thread(target=stderr_reader, args=(worker, event_queue), daemon=True)
        t_out.start()
        t_err.start()
        return True

    def request_worker_restart(reason: str):
        nonlocal worker, worker_restart_attempt, worker_restart_deadline
        nonlocal worker_state, worker_detail, pending_worker_launch_reason
        nonlocal worker_stop_deadline, worker_force_kill_requested
        restart_reason = str(reason or "targets changed").strip() or "targets changed"
        pending_worker_launch_reason = restart_reason
        worker_restart_attempt = 0
        worker_restart_deadline = 0.0
        worker_state = "restarting"
        worker_detail = restart_reason
        append_log_file(log_file, f"worker restarting: {restart_reason}")
        if worker is None:
            worker_stop_deadline = 0.0
            worker_force_kill_requested = False
            launch_reason = pending_worker_launch_reason
            pending_worker_launch_reason = ""
            launch_worker(launch_reason)
            return
        if worker.poll() is not None:
            worker = None
            worker_stop_deadline = 0.0
            worker_force_kill_requested = False
            launch_reason = pending_worker_launch_reason
            pending_worker_launch_reason = ""
            launch_worker(launch_reason)
            return
        if worker_stop_deadline:
            worker_detail = f"{restart_reason}, waiting previous worker exit"
            return
        try:
            worker.terminate()
            worker_stop_deadline = time.time() + WORKER_STOP_TIMEOUT_SECONDS
            worker_force_kill_requested = False
            append_log_file(
                log_file,
                f"worker terminate requested pid={worker.pid} reason={restart_reason}",
            )
        except Exception:
            try:
                worker.kill()
                worker_stop_deadline = time.time() + WORKER_FORCE_KILL_TIMEOUT_SECONDS
                worker_force_kill_requested = True
                append_log_file(
                    log_file,
                    f"worker kill requested pid={worker.pid} reason={restart_reason}",
                )
            except Exception as e:
                pending_worker_launch_reason = ""
                worker_stop_deadline = 0.0
                worker_force_kill_requested = False
                raise RuntimeError(f"stop worker failed: {e}")

    def handle_add_target_request(raw_target: str):
        target_name = str(raw_target or "").strip()
        if not target_name:
            raise RuntimeError("会话名不能为空")
        if target_name in running_targets:
            raise RuntimeError(f"监听目标已存在：{target_name}")

        locked, lock_info = acquire_target_lock(target_name)
        if not locked:
            raise RuntimeError(f"无法添加：{lock_info}")

        running_targets.append(target_name)
        running_target_locks[target_name] = lock_info
        sync_target_lock_paths()
        ui.add_target(target_name)
        try:
            persist_targets_to_config(running_targets)
        except Exception as e:
            ui.remove_target(target_name)
            if target_name in running_targets:
                running_targets.remove(target_name)
            lock_path = running_target_locks.pop(target_name, "")
            sync_target_lock_paths()
            if lock_path:
                release_target_lock_path(lock_path)
            raise RuntimeError(f"写回配置失败：{e}")

        clear_target_runtime_state(target_name)
        change_line = f"target added: {target_name}"
        ui.append_log(change_line)
        append_log_file(log_file, change_line)
        request_worker_restart(f"targets updated after add: {target_name}")

    def handle_remove_target_request(raw_target: str):
        target_name = str(raw_target or "").strip()
        if not target_name:
            raise RuntimeError("会话名不能为空")
        if target_name not in running_targets:
            raise RuntimeError(f"监听目标不存在：{target_name}")
        if len(running_targets) <= 1:
            raise RuntimeError("至少保留 1 个监听目标；最后一个不允许直接删除")

        next_targets = [item for item in running_targets if item != target_name]
        try:
            persist_targets_to_config(next_targets)
        except Exception as e:
            raise RuntimeError(f"写回配置失败：{e}")

        running_targets[:] = next_targets
        lock_path = running_target_locks.pop(target_name, "")
        sync_target_lock_paths()
        if lock_path:
            release_target_lock_path(lock_path)
        clear_target_runtime_state(target_name)
        ui.remove_target(target_name)
        change_line = f"target removed: {target_name}"
        ui.append_log(change_line)
        append_log_file(log_file, change_line)
        request_worker_restart(f"targets updated after remove: {target_name}")

    ui.set_target_editor_handlers(
        handle_add_target_request,
        handle_remove_target_request,
    )

    launch_worker("starting worker")

    def build_pending_message(
        chat_name: str,
        sender_name: str,
        body_cn: str,
        created_at: str,
        is_self: bool,
        message_id: str,
    ) -> SidebarMessage:
        return SidebarMessage(
            chat_name=chat_name,
            sender_name=sender_name if not is_self else "",
            text_en=TRANSLATE_PENDING_TEXT,
            text_display=TRANSLATE_PENDING_TEXT,
            text_cn=body_cn,
            created_at=created_at,
            is_self=is_self,
            message_id=message_id,
            pending_translation=True,
        )

    def emit_translate_result(
        task: dict,
        text_en: str,
        text_display: str,
        pending_translation: bool = False,
    ):
        event_queue.put(
            {
                "type": "render_message",
                "message_id": str(task.get("message_id", "")),
                "chat_name": task["chat_name"],
                "sender_name": task["sender_name"],
                "is_self": task["is_self"],
                "source": task["source"],
                "created_at": task["created_at"],
                "text_cn": str(task.get("body_cn", "")),
                "text_en": text_en,
                "text_display": text_display,
                "pending_translation": pending_translation,
            }
        )

    def resolve_dropped_translate_task(task: dict):
        if not isinstance(task, dict):
            return
        body_cn = str(task.get("body_cn", ""))
        fallback_text = build_translate_fallback(
            body_cn,
            RuntimeError("translate queue overflow"),
            translate_fail_behavior,
        )
        emit_translate_result(task, fallback_text, fallback_text)

    def enqueue_translate_task(task: dict):
        nonlocal translate_queue_drop_count, last_translate_queue_drop_log_at
        try:
            translate_queue.put_nowait(task)
            return
        except queue.Full:
            pass

        empty_marker = object()
        dropped = empty_marker
        try:
            dropped = translate_queue.get_nowait()
        except queue.Empty:
            pass

        # 队列里如果是停止标记，恢复标记并放弃当前消息，优先保证退出流程可达。
        if dropped is None:
            try:
                translate_queue.put_nowait(None)
            except queue.Full:
                pass
            translate_queue_drop_count += 1
            resolve_dropped_translate_task(task)
        else:
            resolve_dropped_translate_task(dropped)
            try:
                translate_queue.put_nowait(task)
                return
            except queue.Full:
                translate_queue_drop_count += 1
                resolve_dropped_translate_task(task)

        now_ts = time.time()
        if (
            now_ts - last_translate_queue_drop_log_at
            >= TRANSLATE_QUEUE_DROP_LOG_INTERVAL_SECONDS
        ):
            event_queue.put(
                {
                    "type": "log",
                    "value": f"translate queue overflow: dropped={translate_queue_drop_count}",
                }
            )
            last_translate_queue_drop_log_at = now_ts

    def signal_translate_worker_stop():
        try:
            translate_queue.put_nowait(None)
            return
        except queue.Full:
            pass

        try:
            translate_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            translate_queue.put_nowait(None)
        except queue.Full:
            pass

    def translate_worker():
        while True:
            task = translate_queue.get()
            if task is None:
                return

            body_cn = str(task.get("body_cn", ""))
            rendered_body = body_cn
            if translate_enabled:
                try:
                    rendered_body = translator.translate(body_cn)
                except Exception as e:
                    rendered_body = build_translate_fallback(
                        body_cn, e, translate_fail_behavior
                    )
                    event_queue.put({"type": "log", "value": f"translate fallback: {e}"})

            rendered_text = rendered_body
            if not english_only and rendered_body != body_cn:
                rendered_text = f"{rendered_text}\nCN: {body_cn}"

            emit_translate_result(task, rendered_body, rendered_text)

    t_translate = threading.Thread(target=translate_worker, daemon=True)
    t_translate.start()

    def handle_event(event: dict):
        nonlocal last_dedupe_cleanup_at, worker_restart_attempt, worker_restart_deadline
        nonlocal worker_state, worker_detail
        nonlocal next_message_sequence
        kind = event.get("type")
        default_chat_name = running_targets[0] if running_targets else ""
        if kind == "status":
            worker_state = str(event.get("state", "status")).strip() or "status"
            worker_detail = str(event.get("value", ""))
            if worker_state == "running":
                worker_restart_attempt = 0
                worker_restart_deadline = 0.0
            ui.append_log(f"status: {worker_detail}")
            append_log_file(log_file, f"status: {worker_detail}")
            return

        if kind == "log":
            value = str(event.get("value", ""))
            ui.append_log(value)
            append_log_file(log_file, value)
            return

        if kind == "render_message":
            created_at = str(event.get("created_at") or datetime.now().strftime("%H:%M:%S"))
            chat_name = str(event.get("chat_name") or default_chat_name)
            sender_name = str(event.get("sender_name", ""))
            raw_text = str(event.get("text_cn", ""))
            rendered_text = str(event.get("text_en", ""))
            display_text = str(event.get("text_display", rendered_text))
            source = str(event.get("source", ""))
            is_self = bool(event.get("is_self", False))
            message_id = str(event.get("message_id", ""))
            pending_translation = bool(event.get("pending_translation", False))
            msg = SidebarMessage(
                chat_name=chat_name,
                sender_name=sender_name if not is_self else "",
                text_en=rendered_text,
                text_display=display_text,
                text_cn=raw_text,
                created_at=created_at,
                is_self=is_self,
                message_id=message_id,
                pending_translation=pending_translation,
            )
            if not ui.replace_message(msg):
                ui.append_message(msg)
            ui.maybe_auto_read_message(msg)
            append_log_file(
                log_file,
                (
                    f"[{created_at}] chat={chat_name} source={source} sender={sender_name or 'self'} "
                    f"en={rendered_text}"
                ),
            )
            return

        if kind != "message":
            ui.append_log(f"unknown event: {event}")
            append_log_file(log_file, f"unknown event: {event}")
            return

        chat_name = str(event.get("chat_name") or default_chat_name)
        if not chat_name:
            return
        cn_text = str(event.get("text", "")).strip()
        if not cn_text:
            return

        # 1) 先拆发送人和正文（发送人姓名不翻译）。
        sender_name, body_cn, is_self = split_sender_and_body(cn_text)
        if not body_cn:
            return
        # 2) 明显的媒体占位消息直接过滤（例如 [图片] / [视频] / [动画表情] / [语音]）。
        if is_filtered_placeholder(body_cn):
            append_log_file(log_file, f"skip filtered placeholder: {chat_name} {cn_text}")
            return
        # 3) 带显式 http/https 链接的消息直接过滤，不显示也不翻译。
        if is_filtered_link_message(body_cn):
            append_log_file(log_file, f"skip filtered link: {chat_name} {cn_text}")
            return

        normalized_body = normalize_message_for_dedupe(body_cn)
        if not normalized_body:
            return

        now_ts = time.time()

        dedupe_key = f"{chat_name}::{sender_name}::{normalized_body}"
        prev_ts = dedupe_cache.get(dedupe_key)
        if prev_ts is not None and now_ts - prev_ts <= session_preview_dedupe_window_seconds:
            return

        dedupe_cache[dedupe_key] = now_ts

        if now_ts - last_dedupe_cleanup_at >= DEDUPE_CLEANUP_INTERVAL_SECONDS:
            cleanup_dedupe_cache(dedupe_cache, now_ts)
            last_dedupe_cleanup_at = now_ts

        created_at = str(event.get("created_at") or datetime.now().strftime("%H:%M:%S"))
        message_id = f"msg-{next_message_sequence}"
        next_message_sequence += 1

        if translate_enabled and translate_provider == "deeplx":
            ui.append_message(
                build_pending_message(
                    chat_name=chat_name,
                    sender_name=sender_name,
                    body_cn=body_cn,
                    created_at=created_at,
                    is_self=is_self,
                    message_id=message_id,
                )
            )

        enqueue_translate_task(
            {
                "message_id": message_id,
                "chat_name": chat_name,
                "sender_name": sender_name,
                "body_cn": body_cn,
                "is_self": is_self,
                "source": "session_preview",
                "created_at": created_at,
            }
        )

    def drain_queue():
        nonlocal worker, worker_last_handled_exit_pid, worker_state, worker_detail
        nonlocal pending_worker_launch_reason
        nonlocal worker_stop_deadline, worker_force_kill_requested
        try:
            while True:
                event = event_queue.get_nowait()
                handle_event(event)
        except queue.Empty:
            pass

        now_ts = time.time()
        if worker is not None:
            return_code = worker.poll()
            if return_code is not None and worker_last_handled_exit_pid != worker.pid:
                worker_last_handled_exit_pid = worker.pid
                worker = None
                worker_stop_deadline = 0.0
                worker_force_kill_requested = False
                exit_line = f"worker exited code={return_code}"
                ui.append_log(exit_line)
                append_log_file(log_file, exit_line)
                if closing:
                    worker_state = "stopped"
                    worker_detail = f"code={return_code}"
                elif pending_worker_launch_reason:
                    restart_reason = pending_worker_launch_reason
                    pending_worker_launch_reason = ""
                    launch_worker(restart_reason)
                else:
                    attempt = worker_restart_attempt + 1
                    schedule_worker_restart(f"code={return_code}", attempt)
            elif not closing and pending_worker_launch_reason and worker_stop_deadline and now_ts >= worker_stop_deadline:
                restart_reason = pending_worker_launch_reason
                if not worker_force_kill_requested:
                    try:
                        worker.kill()
                        worker_force_kill_requested = True
                        worker_stop_deadline = now_ts + WORKER_FORCE_KILL_TIMEOUT_SECONDS
                        worker_state = "restarting"
                        worker_detail = f"{restart_reason}, forcing previous worker exit"
                        kill_line = f"worker kill requested pid={worker.pid} reason={restart_reason}"
                        ui.append_log(kill_line)
                        append_log_file(log_file, kill_line)
                    except Exception as e:
                        worker_stop_deadline = now_ts + WORKER_FORCE_KILL_TIMEOUT_SECONDS
                        fail_line = f"worker kill request failed pid={worker.pid} reason={restart_reason} error={e}"
                        ui.append_log(fail_line)
                        append_log_file(log_file, fail_line)
                else:
                    worker_stop_deadline = now_ts + WORKER_FORCE_KILL_TIMEOUT_SECONDS
                    worker_state = "restarting"
                    worker_detail = f"{restart_reason}, waiting previous worker exit"

        if not closing and worker_restart_deadline and now_ts >= worker_restart_deadline:
            launch_worker(f"restarting worker attempt={worker_restart_attempt}")

        ui.set_status(build_worker_status_text(worker_state, worker_detail, len(running_targets)))

        ui.root.after(UI_DRAIN_INTERVAL_MS, drain_queue)

    def on_close():
        nonlocal closing, worker_restart_deadline
        closing = True
        worker_restart_deadline = 0.0
        try:
            ui._cancel_pending_tts_body_click()
        except Exception:
            pass
        try:
            if worker is not None and worker.poll() is None:
                worker.terminate()
        except Exception:
            pass
        try:
            signal_translate_worker_stop()
        except Exception:
            pass
        release_managed_target_locks()
        ui.root.destroy()

    ui.root.protocol("WM_DELETE_WINDOW", on_close)
    ui.root.after(UI_DRAIN_INTERVAL_MS, drain_queue)
    ui.root.mainloop()


if __name__ == "__main__":
    main()
