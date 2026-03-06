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
from wechat_auto.controls import (
    find_message_list,
    find_session_list,
    is_meaningful_message_text,
    normalize_session_name,
)


TIME_LINE_RE = re.compile(r"^(?:昨天|今天|星期[一二三四五六日天])?\s*\d{1,2}:\d{2}$")
UNREAD_PREFIX_RE = re.compile(r"^\[\d+条\]\s*")
UNREAD_COUNT_RE = re.compile(r"^\[(\d+)条\]\s*")
EMIT_DEBOUNCE_SECONDS = 0.8
EMIT_CACHE_TTL_SECONDS = 120.0
EMIT_CACHE_MAX_KEYS = 600
EMIT_CLEANUP_INTERVAL_SECONDS = 30.0


def emit(event: dict):
    print(json.dumps(event, ensure_ascii=False), flush=True)


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


def find_target_session_raw(window, target_name: str) -> str:
    session_list = find_session_list(window)
    if not session_list or not session_list.Exists(0.3):
        return ""
    for item in session_list.GetChildren():
        current_name = normalize_session_name(item.Name or "")
        if current_name == target_name:
            return item.Name or ""
    return ""


def get_last_message_signature(window):
    # 读取当前聊天区最后一个“有意义”的文本，用于增量检测。
    msg_list = find_message_list(window)
    if not msg_list or not msg_list.Exists(0.3):
        return None
    items = msg_list.GetChildren()
    if not items:
        return (0, "")

    final_text = ""
    for item in reversed(items):
        cands = []
        name = (item.Name or "").strip()
        if name:
            cands.append(name)
        try:
            for child in item.GetChildren():
                t = (child.Name or "").strip()
                if t:
                    cands.append(t)
        except Exception:
            pass

        for t in cands:
            if is_meaningful_message_text(t):
                final_text = t
                break
        if final_text:
            break

    return (len(items), final_text)


def wait_initial_chat_signature(window, timeout_seconds: float = 4.0):
    end = time.time() + timeout_seconds
    while time.time() < end:
        sig = get_last_message_signature(window)
        if sig:
            return sig
        time.sleep(0.4)
    return None


def should_emit(recent_emit_at: dict[str, float], key: str, now_ts: float) -> bool:
    # 仅抑制短时间抖动重复；不做全生命周期永久去重。
    prev_ts = recent_emit_at.get(key)
    if prev_ts is not None and now_ts - prev_ts <= EMIT_DEBOUNCE_SECONDS:
        return False
    recent_emit_at[key] = now_ts
    return True


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="wechat listener worker")
    parser.add_argument("--target", default="", help="target chat/group name")
    parser.add_argument("--group", default="", help=argparse.SUPPRESS)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--mode",
        choices=["chat", "session", "mixed"],
        default="session",
        help="chat=listen opened target chat; session=listen session preview; mixed=both",
    )
    parser.add_argument("--probe", action="store_true", help="init and exit for quick diagnostics")
    parser.add_argument("--debug", action="store_true", help="emit debug logs each poll")
    parser.add_argument(
        "--load-retry-seconds",
        type=float,
        default=10.0,
        help="retry interval when WeChat is not ready at startup",
    )
    parser.add_argument(
        "--focus-refresh",
        action="store_true",
        help="force switch focus to WeChat each poll (more stable, but steals focus)",
    )
    args = parser.parse_args(argv)
    # 兼容老参数 --group，但以 --target 为主。
    target_group = (args.target or args.group).strip()
    if not target_group:
        emit({"type": "status", "value": "missing target, use --target <name>"})
        return

    emit({"type": "log", "value": "boot"})
    try:
        wx = WxAuto()
        retry_seconds = max(0.5, float(args.load_retry_seconds))
        while not wx.load_wechat():
            emit(
                {
                    "type": "status",
                    "value": f"wechat not ready, retry in {retry_seconds:.1f}s",
                }
            )
            if args.probe:
                return
            time.sleep(retry_seconds)

        if args.mode in ("chat", "mixed"):
            # chat/mixed 会主动打开目标会话；session 模式不会触发该行为。
            if not wx.chat_with(target_group):
                emit({"type": "status", "value": f"open target failed: {target_group}"})
                return

        window = wx.window
        last_chat_sig = wait_initial_chat_signature(window, timeout_seconds=4.0)
        initial_session_raw = find_target_session_raw(window, target_group)
        last_session_preview = extract_session_preview(initial_session_raw)
        last_session_unread = extract_session_unread_count(initial_session_raw)
        recent_emit_at = {}
        last_emit_cleanup = 0.0
        emit({"type": "status", "value": f"running mode={args.mode} target={target_group}"})
        if args.probe:
            emit(
                {
                    "type": "log",
                    "value": (
                        f"probe chat_sig={last_chat_sig} "
                        f"session_found={bool(last_session_preview)}"
                    ),
                }
            )
            return

        while True:
            try:
                if not window or not window.Exists(0.2):
                    emit({"type": "status", "value": "wechat window lost"})
                    time.sleep(args.interval)
                    continue

                # 可选：强制刷新窗口可访问树（会抢焦点）
                if args.focus_refresh:
                    try:
                        window.SwitchToThisWindow()
                        if window.IsMinimize():
                            window.Restore()
                            time.sleep(0.2)
                            window.SwitchToThisWindow()
                    except Exception:
                        pass

                now = datetime.now().strftime("%H:%M:%S")
                now_ts = time.time()
                if now_ts - last_emit_cleanup >= EMIT_CLEANUP_INTERVAL_SECONDS:
                    cleanup_recent_emit_cache(recent_emit_at, now_ts)
                    last_emit_cleanup = now_ts

                if args.mode in ("chat", "mixed"):
                    sig = get_last_message_signature(window)
                    if sig and last_chat_sig is None:
                        last_chat_sig = sig
                        time.sleep(args.interval)
                        continue

                    if sig and last_chat_sig and sig != last_chat_sig:
                        _, text = sig
                        if text and should_emit(recent_emit_at, f"{target_group}::{text}", now_ts):
                            emit(
                                {
                                    "type": "message",
                                    "source": "chat",
                                    # chat_name 是给 UI 层标记会话来源用的稳定字段。
                                    "chat_name": target_group,
                                    "text": text,
                                    "created_at": now,
                                }
                            )
                    if sig:
                        last_chat_sig = sig

                if args.mode in ("session", "mixed"):
                    # session 模式基于会话列表预览变化触发。
                    session_raw = find_target_session_raw(window, target_group)
                    current_preview = extract_session_preview(session_raw)
                    current_unread = extract_session_unread_count(session_raw)
                    if args.debug:
                        emit(
                            {
                                "type": "log",
                                "value": (
                                    f"debug session_preview={current_preview} "
                                    f"unread={current_unread}"
                                ),
                            }
                        )
                    # session 只关心预览正文和未读增量，忽略时间/置顶/免打扰噪音。
                    if should_emit_session_preview(
                        current_preview,
                        current_unread,
                        last_session_preview,
                        last_session_unread,
                    ):
                        if last_session_preview and should_emit(
                            recent_emit_at,
                            f"{target_group}::{current_preview}",
                            now_ts,
                        ):
                            emit(
                                {
                                    "type": "message",
                                    "source": "session_preview",
                                    # chat_name 由 UI 用于多目标展示/去重。
                                    "chat_name": target_group,
                                    "text": current_preview,
                                    "created_at": now,
                                }
                            )
                    if current_preview:
                        last_session_preview = current_preview
                        last_session_unread = current_unread
            except KeyboardInterrupt:
                emit({"type": "status", "value": "stopped"})
                break
            except Exception as e:
                emit({"type": "log", "value": f"worker error: {e}"})

            time.sleep(args.interval)
    except Exception as e:
        emit({"type": "log", "value": f"fatal: {e}"})


if __name__ == "__main__":
    main()
