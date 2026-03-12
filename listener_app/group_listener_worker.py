import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

# worker 负责“抓消息并输出事件”，不负责 UI 渲染。
# 事件输出契约：每行一个 JSON，至少包含 type 字段。
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from wechat_auto import WxAuto
from wechat_auto.controls import clear_control_cache, find_session_list, normalize_session_name


TIME_LINE_RE = re.compile(r"^(?:昨天|今天|星期[一二三四五六日天])?\s*\d{1,2}:\d{2}$")
UNREAD_PREFIX_RE = re.compile(r"^\[\d+条\]\s*")
UNREAD_COUNT_RE = re.compile(r"^\[(\d+)条\]\s*")
EMIT_DEBOUNCE_SECONDS = 0.8
EMIT_CACHE_TTL_SECONDS = 120.0
EMIT_CACHE_MAX_KEYS = 600
EMIT_CLEANUP_INTERVAL_SECONDS = 30.0
MIN_LOAD_RETRY_SECONDS = 0.5
DEFAULT_LISTEN_INTERVAL_SECONDS = 0.6
MIN_LISTEN_INTERVAL_SECONDS = 0.2
FOCUS_REFRESH_REPEAT_THRESHOLD = 15
FOCUS_REFRESH_MISSING_TARGET_THRESHOLD = 3
FOCUS_REFRESH_COOLDOWN_SECONDS = 15.0


def configure_std_streams_for_utf8(stdout=None, stderr=None):
    streams = [sys.stdout if stdout is None else stdout, sys.stderr if stderr is None else stderr]
    for stream in streams:
        try:
            if stream and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


configure_std_streams_for_utf8()


def emit(event: dict):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def emit_status(state: str, value: str):
    emit({"type": "status", "state": state, "value": value})


def normalize_targets(raw_targets: list[str]) -> list[str]:
    targets: list[str] = []
    for item in raw_targets:
        name = str(item or "").strip()
        if name and name not in targets:
            targets.append(name)
    return targets


def _iter_session_detail_lines(raw_name: str) -> list[str]:
    if not raw_name:
        return []
    lines = [line.strip() for line in raw_name.splitlines() if line.strip()]
    if len(lines) <= 1:
        return []
    details = []
    for line in lines[1:]:
        if line in ("已置顶", "消息免打扰"):
            continue
        if TIME_LINE_RE.match(line):
            continue
        details.append(line)
    return details


def extract_session_preview(raw_name: str) -> str:
    # 从会话列表条目里提取预览正文，过滤“时间/免打扰/置顶”等噪音信息。
    for line in _iter_session_detail_lines(raw_name):
        line = UNREAD_PREFIX_RE.sub("", line).strip()
        if line:
            return line
    return ""


def extract_session_unread_count(raw_name: str) -> int:
    for line in _iter_session_detail_lines(raw_name):
        match = UNREAD_COUNT_RE.match(line)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return 0
        break
    return 0


def should_emit_session_preview(
    current_preview: str,
    current_unread: int,
    last_preview: str,
    last_unread: int,
) -> bool:
    if not current_preview:
        return False
    if current_preview != last_preview:
        return True
    return current_unread > last_unread


def should_emit(recent_emit_at: dict[str, float], key: str, now_ts: float) -> bool:
    prev_ts = recent_emit_at.get(key)
    if prev_ts is not None and now_ts - prev_ts <= EMIT_DEBOUNCE_SECONDS:
        return False
    recent_emit_at[key] = now_ts
    return True


def compute_poll_sleep_seconds(
    interval_seconds: float,
    cycle_started_at: float,
    cycle_finished_at: float,
) -> float:
    interval = max(MIN_LISTEN_INTERVAL_SECONDS, float(interval_seconds))
    elapsed = max(0.0, float(cycle_finished_at) - float(cycle_started_at))
    remaining = interval - elapsed
    if remaining <= 0:
        return 0.0
    return remaining


def cleanup_recent_emit_cache(recent_emit_at: dict[str, float], now_ts: float):
    expired = [
        key
        for key, ts in recent_emit_at.items()
        if now_ts - ts > EMIT_CACHE_TTL_SECONDS
    ]
    for key in expired:
        recent_emit_at.pop(key, None)

    overflow = len(recent_emit_at) - EMIT_CACHE_MAX_KEYS
    if overflow > 0:
        oldest = sorted(recent_emit_at.items(), key=lambda item: item[1])[:overflow]
        for key, _ in oldest:
            recent_emit_at.pop(key, None)


def build_session_snapshot_signature(session_map: dict[str, str], targets: list[str]) -> str:
    parts = []
    for target in targets:
        parts.append(f"{target}\x1f{session_map.get(target, '')}")
    return "\x1e".join(parts)


def should_force_focus_refresh(
    enabled: bool,
    missing_target_polls: int,
    snapshot_repeat_polls: int,
    unread_total: int,
    now_ts: float,
    last_focus_refresh_at: float,
) -> bool:
    if not enabled:
        return False
    if now_ts - last_focus_refresh_at < FOCUS_REFRESH_COOLDOWN_SECONDS:
        return False
    if missing_target_polls >= FOCUS_REFRESH_MISSING_TARGET_THRESHOLD:
        return True
    return unread_total > 0 and snapshot_repeat_polls >= FOCUS_REFRESH_REPEAT_THRESHOLD


def try_focus_refresh(window) -> bool:
    try:
        window.SwitchToThisWindow()
        if window.IsMinimize():
            window.Restore()
            time.sleep(0.2)
            window.SwitchToThisWindow()
        return True
    except Exception:
        return False


def wait_for_wechat_ready(
    wx,
    retry_seconds: float,
    probe: bool = False,
    reconnect: bool = False,
    sleep_fn=time.sleep,
) -> bool:
    wait_state = "reconnecting" if reconnect else "waiting_wechat"
    while not wx.load_wechat():
        emit_status(wait_state, f"wechat not ready, retry in {retry_seconds:.1f}s")
        if probe:
            return False
        sleep_fn(retry_seconds)
    return True


def collect_target_session_map(window, targets: list[str]) -> dict[str, str]:
    session_list = find_session_list(window)
    if not session_list or not session_list.Exists(0.3):
        return {}

    pending = set(targets)
    session_map: dict[str, str] = {}
    for item in session_list.GetChildren():
        current_name = normalize_session_name(item.Name or "")
        if current_name in pending:
            session_map[current_name] = item.Name or ""
            pending.remove(current_name)
            if not pending:
                break
    return session_map


def build_target_state_map(window, targets: list[str]) -> dict[str, dict[str, int | str]]:
    session_map = collect_target_session_map(window, targets)
    state_map: dict[str, dict[str, int | str]] = {}
    for target in targets:
        raw_name = session_map.get(target, "")
        state_map[target] = {
            "preview": extract_session_preview(raw_name),
            "unread": extract_session_unread_count(raw_name),
        }
    return state_map


def connect_runtime(wx, targets: list[str], retry_seconds: float, probe: bool = False, reconnect: bool = False):
    current_reconnect = reconnect
    while True:
        if not wait_for_wechat_ready(
            wx,
            retry_seconds=retry_seconds,
            probe=probe,
            reconnect=current_reconnect,
        ):
            return None

        emit_status("connecting", f"wechat ready, preparing session-only targets={len(targets)}")
        window = wx.window
        clear_control_cache(window)
        return {
            "window": window,
            "target_states": build_target_state_map(window, targets),
        }


def parse_targets(args) -> list[str]:
    targets = list(args.target or [])
    if args.group:
        targets.append(args.group)
    if args.targets_json:
        try:
            parsed = json.loads(args.targets_json)
        except json.JSONDecodeError as e:
            emit({"type": "log", "value": f"fatal: invalid --targets-json: {e}"})
            return []
        if not isinstance(parsed, list):
            emit({"type": "log", "value": "fatal: --targets-json must be JSON array"})
            return []
        targets.extend(parsed)
    return normalize_targets(targets)


def main():
    parser = argparse.ArgumentParser(description="wechat listener worker (session-only)")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="target chat/group name; can be repeated",
    )
    parser.add_argument("--group", default="", help=argparse.SUPPRESS)
    parser.add_argument("--targets-json", default="", help="JSON array of target names")
    parser.add_argument("--interval", type=float, default=DEFAULT_LISTEN_INTERVAL_SECONDS)
    parser.add_argument("--probe", action="store_true", help="init and exit for quick diagnostics")
    parser.add_argument("--debug", action="store_true", help="emit debug logs each poll")
    parser.add_argument(
        "--load-retry-seconds",
        type=float,
        default=10.0,
        help="retry interval when WeChat is not ready or reconnecting",
    )
    parser.add_argument(
        "--focus-refresh",
        action="store_true",
        help="force switch focus to WeChat each poll (more stable, but steals focus)",
    )
    args = parser.parse_args()

    targets = parse_targets(args)
    if not targets:
        emit({"type": "status", "value": "missing targets, use --target/--targets-json"})
        return

    emit({"type": "log", "value": "boot"})
    try:
        wx = WxAuto()
        retry_seconds = max(MIN_LOAD_RETRY_SECONDS, float(args.load_retry_seconds))
        poll_interval = max(MIN_LISTEN_INTERVAL_SECONDS, float(args.interval))
        runtime = connect_runtime(
            wx,
            targets=targets,
            retry_seconds=retry_seconds,
            probe=args.probe,
        )
        if runtime is None:
            return

        window = runtime["window"]
        target_states = runtime["target_states"]
        recent_emit_at: dict[str, float] = {}
        last_emit_cleanup = 0.0
        last_snapshot_signature = ""
        snapshot_repeat_polls = 0
        missing_target_polls = 0
        last_focus_refresh_at = 0.0
        emit_status("running", f"running session-only targets={len(targets)}")
        if args.probe:
            found_count = sum(1 for target in targets if target_states.get(target, {}).get("preview"))
            emit(
                {
                    "type": "log",
                    "value": f"probe targets={len(targets)} found_with_preview={found_count}",
                }
            )
            return

        while True:
            cycle_started_at = time.monotonic()
            should_stop = False
            try:
                if not window or not window.Exists(0.2):
                    emit_status("window_lost", "wechat window lost, reconnecting")
                    runtime = connect_runtime(
                        wx,
                        targets=targets,
                        retry_seconds=retry_seconds,
                        reconnect=True,
                    )
                    if runtime is None:
                        return
                    window = runtime["window"]
                    target_states = runtime["target_states"]
                    recent_emit_at.clear()
                    last_emit_cleanup = 0.0
                    last_snapshot_signature = ""
                    snapshot_repeat_polls = 0
                    missing_target_polls = 0
                    last_focus_refresh_at = 0.0
                    emit_status("running", f"running session-only targets={len(targets)}")
                    continue

                now = datetime.now().strftime("%H:%M:%S")
                now_ts = time.time()
                if now_ts - last_emit_cleanup >= EMIT_CLEANUP_INTERVAL_SECONDS:
                    cleanup_recent_emit_cache(recent_emit_at, now_ts)
                    last_emit_cleanup = now_ts

                session_map = collect_target_session_map(window, targets)
                current_signature = build_session_snapshot_signature(session_map, targets)
                if current_signature == last_snapshot_signature:
                    snapshot_repeat_polls += 1
                else:
                    snapshot_repeat_polls = 0
                    last_snapshot_signature = current_signature

                if len(session_map) < len(targets):
                    missing_target_polls += 1
                else:
                    missing_target_polls = 0

                unread_total = 0
                for target in targets:
                    unread_total += extract_session_unread_count(session_map.get(target, ""))

                if should_force_focus_refresh(
                    args.focus_refresh,
                    missing_target_polls=missing_target_polls,
                    snapshot_repeat_polls=snapshot_repeat_polls,
                    unread_total=unread_total,
                    now_ts=now_ts,
                    last_focus_refresh_at=last_focus_refresh_at,
                ):
                    if try_focus_refresh(window):
                        last_focus_refresh_at = now_ts
                        emit(
                            {
                                "type": "log",
                                "value": (
                                    "focus refresh triggered "
                                    f"missing_target_polls={missing_target_polls} "
                                    f"repeat_polls={snapshot_repeat_polls} unread_total={unread_total}"
                                ),
                            }
                        )
                        session_map = collect_target_session_map(window, targets)
                        last_snapshot_signature = build_session_snapshot_signature(
                            session_map,
                            targets,
                        )
                        snapshot_repeat_polls = 0
                        missing_target_polls = 0 if len(session_map) == len(targets) else 1

                for target in targets:
                    raw_name = session_map.get(target, "")
                    current_preview = extract_session_preview(raw_name)
                    current_unread = extract_session_unread_count(raw_name)
                    previous_state = target_states.setdefault(
                        target,
                        {"preview": "", "unread": 0},
                    )
                    last_preview = str(previous_state.get("preview", ""))
                    last_unread = int(previous_state.get("unread", 0))

                    if args.debug:
                        emit(
                            {
                                "type": "log",
                                "value": (
                                    f"debug target={target} "
                                    f"session_preview={current_preview} unread={current_unread}"
                                ),
                            }
                        )

                    if should_emit_session_preview(
                        current_preview,
                        current_unread,
                        last_preview,
                        last_unread,
                    ):
                        if last_preview and should_emit(
                            recent_emit_at,
                            f"{target}::{current_preview}",
                            now_ts,
                        ):
                            emit(
                                {
                                    "type": "message",
                                    "source": "session_preview",
                                    "chat_name": target,
                                    "text": current_preview,
                                    "created_at": now,
                                }
                            )

                    if current_preview:
                        previous_state["preview"] = current_preview
                        previous_state["unread"] = current_unread
            except KeyboardInterrupt:
                emit_status("stopped", "stopped")
                should_stop = True
            except Exception as e:
                emit({"type": "log", "value": f"worker error: {e}"})

            if should_stop:
                break

            sleep_seconds = compute_poll_sleep_seconds(
                poll_interval,
                cycle_started_at,
                time.monotonic(),
            )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    except Exception as e:
        emit({"type": "log", "value": f"fatal: {e}"})


if __name__ == "__main__":
    main()
