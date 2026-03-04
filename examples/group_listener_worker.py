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


def emit(event: dict):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def extract_session_preview(raw_name: str) -> str:
    # 从会话列表条目里提取预览正文，过滤“时间/免打扰/置顶”等噪音信息。
    if not raw_name:
        return ""
    lines = [line.strip() for line in raw_name.splitlines() if line.strip()]
    if len(lines) <= 1:
        return ""
    for line in lines[1:]:
        if line in ("已置顶", "消息免打扰"):
            continue
        if TIME_LINE_RE.match(line):
            continue
        line = UNREAD_PREFIX_RE.sub("", line).strip()
        if line:
            return line
    return ""


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
        last_session_sig = find_target_session_raw(window, target_group)
        emitted = set()
        emit({"type": "status", "value": f"running mode={args.mode} target={target_group}"})
        if args.probe:
            emit({"type": "log", "value": f"probe chat_sig={last_chat_sig} session_found={bool(last_session_sig)}"})
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

                if args.mode in ("chat", "mixed"):
                    sig = get_last_message_signature(window)
                    if sig and last_chat_sig is None:
                        last_chat_sig = sig
                        time.sleep(args.interval)
                        continue

                    if sig and last_chat_sig and sig != last_chat_sig:
                        _, text = sig
                        if text:
                            key = f"chat::{text}"
                            if key not in emitted:
                                emitted.add(key)
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
                    if args.debug:
                        emit(
                            {
                                "type": "log",
                                "value": f"debug session_preview={extract_session_preview(session_raw)}",
                            }
                        )
                    if session_raw and last_session_sig and session_raw != last_session_sig:
                        preview = extract_session_preview(session_raw)
                        if preview:
                            key = f"session::{preview}"
                            if key not in emitted:
                                emitted.add(key)
                                emit(
                                    {
                                        "type": "message",
                                        "source": "session_preview",
                                        # chat_name 由 UI 用于多目标展示/去重。
                                        "chat_name": target_group,
                                        "text": preview,
                                        "created_at": now,
                                    }
                                )
                    if session_raw:
                        last_session_sig = session_raw
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
