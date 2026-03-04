import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from tkinter import scrolledtext, ttk
from urllib import error, request
from urllib.parse import urlparse
from typing import Any, Dict

# 侧边栏主进程：
# - 读取 JSON 配置
# - 启动 worker 监听目标会话
# - 处理消息事件并执行翻译
# - 以“聊天气泡”风格展示（支持自己消息右对齐）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = os.path.dirname(sys.executable) if IS_FROZEN else ROOT_DIR
BUNDLE_DIR = getattr(sys, "_MEIPASS", ROOT_DIR)
DEFAULT_CONFIG_PATH = os.path.join(APP_DIR, "config", "listener.json")
# 匹配 “发送人: 正文” / “发送人：正文”
SENDER_PREFIX_RE = re.compile(r"^\s*([^:：]{1,40})[:：]\s*(.+?)\s*$")
# 过滤图片占位文本（例如 [图片] / [Images]）
IMAGE_PLACEHOLDER_RE = re.compile(r"^\[\s*(图片|image|images|photo)\s*\]$", re.IGNORECASE)


def load_local_env():
    for env_path in (
        os.path.join(APP_DIR, ".env.local"),
        os.path.join(ROOT_DIR, ".env.local"),
    ):
        if not os.path.exists(env_path):
            continue
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            return
        except Exception:
            continue


load_local_env()


def ensure_default_config() -> str:
    target = DEFAULT_CONFIG_PATH
    if os.path.exists(target):
        return target

    os.makedirs(os.path.dirname(target), exist_ok=True)
    candidates = [
        os.path.join(BUNDLE_DIR, "config", "listener.json"),
        os.path.join(ROOT_DIR, "config", "listener.json"),
    ]
    for src in candidates:
        if not os.path.exists(src):
            continue
        try:
            with open(src, "r", encoding="utf-8") as f_src, open(
                target, "w", encoding="utf-8"
            ) as f_dst:
                f_dst.write(f_src.read())
            return target
        except Exception:
            continue
    raise RuntimeError(f"missing config template: {candidates}")


def run_embedded_worker_if_requested() -> bool:
    if "--worker-mode" not in sys.argv:
        return False
    worker_argv = [arg for arg in sys.argv[1:] if arg != "--worker-mode"]
    try:
        from examples import group_listener_worker as worker_entry
    except Exception as e:
        print(f"[sidebar] load embedded worker failed: {e}", file=sys.stderr)
        raise SystemExit(2)
    worker_entry.main(worker_argv)
    return True


def load_json_config(path: str) -> Dict[str, Any]:
    # 仅接受 object 根节点，避免把数组/字符串误当配置。
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise RuntimeError(f"config root must be object: {path}")
    return raw


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "on"):
            return True
        if v in ("0", "false", "no", "off"):
            return False
    return default


def as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def normalize_targets(value: Any) -> list[str]:
    # 归一化 targets：去空、去重、保序。
    if not isinstance(value, list):
        return []
    targets = []
    for item in value:
        name = str(item or "").strip()
        if name and name not in targets:
            targets.append(name)
    return targets


def split_sender_and_body(text: str) -> tuple[str, str, bool]:
    # 返回 (发送人, 正文, 是否视为自己发出)：
    # - 匹配到“发送人: 正文” -> 非自己消息
    # - 其余情况 -> 视为自己消息（右对齐显示）
    s = str(text or "").strip()
    if not s:
        return "", "", True
    if "://" in s:
        # URL 文本里常见冒号，不能误判为“发送人:正文”。
        return "", s, True
    m = SENDER_PREFIX_RE.match(s)
    if not m:
        return "", s, True
    sender = (m.group(1) or "").strip()
    body = (m.group(2) or "").strip()
    if sender.lower() in ("http", "https", "ftp") or sender.isdigit():
        # 防止把协议头或纯数字时间片段误识别为发送人。
        return "", s, True
    if not body:
        return "", s, True
    return sender, body, False


def is_image_placeholder(text: str) -> bool:
    return bool(IMAGE_PLACEHOLDER_RE.match(str(text or "").strip()))


class TranslatorBase:
    def translate(self, text: str) -> str:
        raise NotImplementedError


class PassthroughTranslator(TranslatorBase):
    def translate(self, text: str) -> str:
        return text


class DeepLXTranslator(TranslatorBase):
    def __init__(
        self,
        url: str,
        source_lang: str = "auto",
        target_lang: str = "EN",
        timeout_seconds: float = 8.0,
    ):
        self.url = url.rstrip("/")
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.timeout_seconds = timeout_seconds

    def translate(self, text: str) -> str:
        payload = json.dumps(
            {
                "text": text,
                "source_lang": self.source_lang,
                "target_lang": self.target_lang,
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json,text/plain,*/*",
            # 某些 DeepLX 网关会按 UA/请求特征做风控，Python 默认 UA 可能被 403 拦截。
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        parsed = urlparse(self.url)
        if parsed.netloc.lower().endswith("deeplx.org"):
            headers["Origin"] = "https://api.deeplx.org"
            headers["Referer"] = "https://api.deeplx.org/"
        req = request.Request(
            self.url,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
        except error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            raise RuntimeError(
                f"DeepLX request failed: HTTP {e.code}, body={body[:120]}"
            ) from e
        except error.URLError as e:
            raise RuntimeError(f"DeepLX request failed: {e}") from e

        try:
            body = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"DeepLX response invalid JSON: {raw[:200]}") from e

        if isinstance(body, dict):
            for key in ("data", "translation", "text"):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            translations = body.get("translations")
            if isinstance(translations, list) and translations:
                first = translations[0]
                if isinstance(first, dict):
                    text_value = first.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        return text_value.strip()

        raise RuntimeError(f"DeepLX response unsupported: {raw[:200]}")


@dataclass
class SidebarMessage:
    chat_name: str
    text_en: str
    created_at: str
    is_self: bool


def append_log_file(path: str, line: str):
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
    except Exception:
        pass


def create_translator(
    enabled: bool,
    provider: str,
    deeplx_url: str,
    source_lang: str,
    target_lang: str,
    timeout_seconds: float,
) -> TranslatorBase:
    if not enabled:
        return PassthroughTranslator()
    if provider.lower() != "deeplx":
        return PassthroughTranslator()
    if not deeplx_url:
        return PassthroughTranslator()
    return DeepLXTranslator(
        url=deeplx_url,
        source_lang=source_lang,
        target_lang=target_lang,
        timeout_seconds=timeout_seconds,
    )


def build_translate_fallback(cn_text: str, err: Exception, behavior: str) -> str:
    reason = str(err).replace("\n", " ").strip()
    if len(reason) > 200:
        reason = reason[:200]
    if behavior == "show_cn":
        return cn_text
    if behavior == "show_reason":
        return f"translate_failed: {reason}"
    return f"{cn_text} (translate_failed: {reason})"


class SidebarUI:
    def __init__(self, title: str, width: int, side: str, topmost: bool, show_chat_name: bool):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.attributes("-topmost", bool(topmost))
        self.show_chat_name = bool(show_chat_name)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        height = max(480, screen_h - 80)
        x = screen_w - width - 16 if side == "right" else 16
        y = 24
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.status_var = tk.StringVar(value="starting...")
        header = ttk.Frame(self.root, padding=8)
        header.pack(fill=tk.X)
        ttk.Label(header, text="WeChat Message Sidebar", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        ttk.Label(header, textvariable=self.status_var).pack(anchor="w")

        self.text = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED
        )
        self.text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        # 左右两套样式：别人消息靠左，自己消息靠右。
        self.text.tag_configure("msg_left", justify=tk.LEFT, lmargin1=8, lmargin2=8, rmargin=40)
        self.text.tag_configure("msg_right", justify=tk.RIGHT, lmargin1=40, lmargin2=40, rmargin=8)
        self.text.tag_configure("meta_left", justify=tk.LEFT, foreground="#666666")
        self.text.tag_configure("meta_right", justify=tk.RIGHT, foreground="#666666")

    def set_status(self, text: str):
        self.status_var.set(text)

    def append_message(self, msg: SidebarMessage):
        self.text.configure(state=tk.NORMAL)
        # 根据 is_self 决定气泡左右对齐。
        meta_tag = "meta_right" if msg.is_self else "meta_left"
        msg_tag = "msg_right" if msg.is_self else "msg_left"
        header = f"[{msg.created_at}]"
        # 单目标监听时隐藏 chat_name；多目标时才展示会话名，避免视觉噪声。
        if self.show_chat_name and msg.chat_name:
            header += f" [{msg.chat_name}]"
        self.text.insert(tk.END, header + "\n", meta_tag)
        # 按需求：正文区不再显示 CN/EN 标签，也不显示 source=session_preview。
        self.text.insert(tk.END, f"{msg.text_en}\n\n", msg_tag)
        self.text.see(tk.END)
        self.text.configure(state=tk.DISABLED)

    def append_log(self, line: str):
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, f"{line}\n")
        self.text.see(tk.END)
        self.text.configure(state=tk.DISABLED)


def start_worker_process(
    target: str,
    interval: float,
    mode: str,
    debug: bool,
    focus_refresh: bool,
    load_retry_seconds: float,
) -> subprocess.Popen:
    # 使用 UTF-8 管道，避免中文在父子进程间错码。
    cmd = [sys.executable]
    if IS_FROZEN:
        # 打包模式：复用同一个 exe 进入内嵌 worker 角色。
        cmd.extend(
            [
                "--worker-mode",
                "--target",
                target,
                "--interval",
                str(interval),
                "--load-retry-seconds",
                str(load_retry_seconds),
                "--mode",
                mode,
            ]
        )
    else:
        worker = os.path.join(ROOT_DIR, "examples", "group_listener_worker.py")
        cmd.extend(
            [
                "-X",
                "utf8",
                "-u",
                worker,
                "--target",
                target,
                "--interval",
                str(interval),
                "--load-retry-seconds",
                str(load_retry_seconds),
                "--mode",
                mode,
            ]
        )
    if debug:
        cmd.append("--debug")
    if focus_refresh:
        cmd.append("--focus-refresh")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.Popen(
        cmd,
        cwd=APP_DIR if IS_FROZEN else ROOT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


def stdout_reader(proc: subprocess.Popen, q: "queue.Queue[dict]"):
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                q.put(event)
            else:
                q.put({"type": "log", "value": f"worker non-dict event: {line}"})
        except json.JSONDecodeError:
            q.put({"type": "log", "value": f"worker raw: {line}"})


def stderr_reader(proc: subprocess.Popen, q: "queue.Queue[dict]"):
    assert proc.stderr is not None
    for raw in proc.stderr:
        line = raw.rstrip()
        if line:
            q.put({"type": "log", "value": f"worker stderr: {line}"})


def main():
    default_config_path = DEFAULT_CONFIG_PATH
    if not os.path.exists(default_config_path):
        try:
            default_config_path = ensure_default_config()
        except Exception:
            # 延后到 load_json_config 时给出统一错误信息。
            default_config_path = DEFAULT_CONFIG_PATH

    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", default=default_config_path, help="JSON config path")
    pre_args, _ = pre_parser.parse_known_args()

    try:
        config = load_json_config(pre_args.config)
    except Exception as e:
        print(f"[sidebar] load config failed: {e}", file=sys.stderr)
        raise SystemExit(2)

    listen_cfg = config.get("listen", {}) if isinstance(config.get("listen", {}), dict) else {}
    translate_cfg = (
        config.get("translate", {}) if isinstance(config.get("translate", {}), dict) else {}
    )
    display_cfg = config.get("display", {}) if isinstance(config.get("display", {}), dict) else {}
    logging_cfg = config.get("logging", {}) if isinstance(config.get("logging", {}), dict) else {}

    # 当前版本只消费第一个 target；保留数组是为了后续平滑扩展多目标。
    targets = normalize_targets(listen_cfg.get("targets"))
    if not targets:
        print("[sidebar] config listen.targets is empty", file=sys.stderr)
        raise SystemExit(2)
    if len(targets) > 1:
        print(
            f"[sidebar] multiple targets configured, current version uses first only: {targets[0]!r}",
            flush=True,
        )
    default_target = targets[0]
    default_mode = str(listen_cfg.get("mode", "session"))
    if default_mode not in ("chat", "session", "mixed"):
        default_mode = "session"
    default_side = str(display_cfg.get("side", "right"))
    if default_side not in ("left", "right"):
        default_side = "right"

    parser = argparse.ArgumentParser(
        parents=[pre_parser],
        description="Sidebar listener: monitor target chat and show translated output.",
    )
    parser.add_argument("--target", default=default_target, help="target chat/group name")
    parser.add_argument(
        "--interval",
        type=float,
        default=as_float(listen_cfg.get("interval_seconds"), 1.0),
        help="poll interval seconds",
    )
    parser.add_argument(
        "--mode",
        choices=["chat", "session", "mixed"],
        default=default_mode,
        help="chat=listen opened target chat; session=listen session preview; mixed=both",
    )
    parser.add_argument(
        "--focus-refresh",
        action="store_true",
        default=as_bool(listen_cfg.get("focus_refresh"), False),
        help="force worker to switch focus to WeChat each poll",
    )
    parser.add_argument(
        "--load-retry-seconds",
        type=float,
        default=as_float(listen_cfg.get("load_retry_seconds"), 10.0),
        help="retry interval when WeChat is not ready at startup",
    )
    parser.add_argument(
        "--deeplx-url",
        default=str(translate_cfg.get("deeplx_url") or os.getenv("DEEPLX_URL", "")),
        help="DeepLX endpoint, e.g. https://api.deeplx.org/<key>/translate",
    )
    parser.add_argument(
        "--translate-enabled",
        choices=["true", "false"],
        default="true" if as_bool(translate_cfg.get("enabled"), True) else "false",
        help="enable translation",
    )
    parser.add_argument(
        "--translate-provider",
        choices=["deeplx", "passthrough"],
        default=str(translate_cfg.get("provider", "deeplx")).lower(),
        help="translation provider",
    )
    parser.add_argument(
        "--source-lang",
        default=str(translate_cfg.get("source_lang", "auto")),
        help="translation source language",
    )
    parser.add_argument(
        "--target-lang",
        default=str(translate_cfg.get("target_lang", "EN")),
        help="translation target language",
    )
    parser.add_argument(
        "--translate-timeout",
        type=float,
        default=as_float(translate_cfg.get("timeout_seconds"), 8.0),
        help="translation timeout seconds",
    )
    parser.add_argument(
        "--english-only",
        choices=["true", "false"],
        default="true" if as_bool(display_cfg.get("english_only"), True) else "false",
        help="show translated line only",
    )
    parser.add_argument(
        "--translate-fail-behavior",
        choices=["show_cn_with_reason", "show_cn", "show_reason"],
        default=str(display_cfg.get("on_translate_fail", "show_cn_with_reason")),
        help="fallback behavior on translation failure",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=as_int(display_cfg.get("width"), 460),
        help="sidebar width",
    )
    parser.add_argument(
        "--side",
        choices=["left", "right"],
        default=default_side,
        help="sidebar dock side",
    )
    parser.add_argument(
        "--topmost",
        action="store_true",
        default=as_bool(display_cfg.get("topmost"), False),
        help="keep sidebar always on top",
    )
    parser.add_argument(
        "--log-file",
        default=str(logging_cfg.get("file", "")),
        help="optional log output file path",
    )
    parser.add_argument("--worker-debug", action="store_true", help="enable worker debug logs")
    args = parser.parse_args()

    target_group = (args.target or "").strip()
    if not target_group:
        print("[sidebar] empty target", file=sys.stderr)
        raise SystemExit(2)

    translate_enabled = as_bool(args.translate_enabled, True)
    english_only = as_bool(args.english_only, True)

    ui = SidebarUI(
        title=f"WeChat EN Sidebar - {target_group}",
        width=args.width,
        side=args.side,
        topmost=args.topmost,
        show_chat_name=len(targets) > 1,
    )
    translator = create_translator(
        enabled=translate_enabled,
        provider=args.translate_provider,
        deeplx_url=args.deeplx_url,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        timeout_seconds=args.translate_timeout,
    )
    if translate_enabled and args.translate_provider == "deeplx" and args.deeplx_url:
        ui.set_status(f"running (deeplx=enabled, mode={args.mode})")
    elif translate_enabled:
        ui.set_status(f"running (translator={args.translate_provider}, mode={args.mode})")
    else:
        ui.set_status(f"running (translator=disabled, mode={args.mode})")
    if args.mode in ("chat", "mixed"):
        ui.append_log("warning: chat/mixed 会主动打开会话；仅监听请用 mode=session")

    append_log_file(args.log_file, "sidebar start")
    event_queue: "queue.Queue[dict]" = queue.Queue()
    emitted = set()

    proc = start_worker_process(
        target_group,
        args.interval,
        args.mode,
        args.worker_debug,
        args.focus_refresh,
        args.load_retry_seconds,
    )
    append_log_file(args.log_file, f"worker start pid={proc.pid}")

    t_out = threading.Thread(target=stdout_reader, args=(proc, event_queue), daemon=True)
    t_err = threading.Thread(target=stderr_reader, args=(proc, event_queue), daemon=True)
    t_out.start()
    t_err.start()

    def handle_event(event: dict):
        kind = event.get("type")
        if kind == "status":
            value = str(event.get("value", ""))
            ui.set_status(value)
            ui.append_log(f"status: {value}")
            append_log_file(args.log_file, f"status: {value}")
            return

        if kind == "log":
            value = str(event.get("value", ""))
            ui.append_log(value)
            append_log_file(args.log_file, value)
            return

        if kind != "message":
            ui.append_log(f"unknown event: {event}")
            append_log_file(args.log_file, f"unknown event: {event}")
            return

        # source 仅用于去重/日志，不进入 UI 展示。
        source = str(event.get("source", ""))
        chat_name = str(event.get("chat_name", target_group))
        cn_text = str(event.get("text", "")).strip()
        if not cn_text:
            return

        # 1) 先拆发送人和正文（发送人姓名不翻译）。
        sender_name, body_cn, is_self = split_sender_and_body(cn_text)
        if not body_cn:
            return
        # 2) 图片占位消息直接过滤（例如 [图片]），不渲染到侧边栏。
        if is_image_placeholder(body_cn):
            append_log_file(args.log_file, f"skip image placeholder: {chat_name} {cn_text}")
            return

        # 去重键包含 chat/source/sender/body，避免重复刷新导致重复显示。
        dedupe_key = f"{chat_name}::{source}::{sender_name}::{body_cn}"
        if dedupe_key in emitted:
            return
        emitted.add(dedupe_key)

        # 3) 只翻译正文 body，发送人前缀保持原样。
        rendered_body = body_cn
        if translate_enabled:
            try:
                rendered_body = translator.translate(body_cn)
            except Exception as e:
                rendered_body = build_translate_fallback(
                    body_cn, e, args.translate_fail_behavior
                )
                ui.append_log(f"translate fallback: {e}")
                append_log_file(args.log_file, f"translate fallback: {e}")
        rendered_text = rendered_body
        if sender_name:
            rendered_text = f"{sender_name}: {rendered_body}"
        # english_only=false 时才追加 CN 行；默认 english_only=true 直接替换原文展示。
        if not english_only and rendered_body != body_cn:
            cn_line = f"{sender_name}: {body_cn}" if sender_name else body_cn
            rendered_text = f"{rendered_text}\nCN: {cn_line}"

        created_at = str(event.get("created_at") or datetime.now().strftime("%H:%M:%S"))
        msg = SidebarMessage(
            chat_name=chat_name,
            text_en=rendered_text,
            created_at=created_at,
            is_self=is_self,
        )
        ui.append_message(msg)
        append_log_file(
            args.log_file,
            (
                f"[{created_at}] chat={chat_name} source={source} sender={sender_name or 'self'} "
                f"en={rendered_text}"
            ),
        )

    def drain_queue():
        try:
            while True:
                event = event_queue.get_nowait()
                handle_event(event)
        except queue.Empty:
            pass

        if proc.poll() is not None:
            ui.set_status(f"worker exited ({proc.returncode})")
            ui.append_log(f"worker exited ({proc.returncode})")
            append_log_file(args.log_file, f"worker exited ({proc.returncode})")
            return

        ui.root.after(200, drain_queue)

    def on_close():
        try:
            if proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
        ui.root.destroy()

    ui.root.protocol("WM_DELETE_WINDOW", on_close)
    ui.root.after(200, drain_queue)
    ui.root.mainloop()


if __name__ == "__main__":
    if run_embedded_worker_if_requested():
        raise SystemExit(0)
    main()
