import argparse
import atexit
import hashlib
import json
import math
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from tkinter import font as tkfont
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
PREFERRED_UI_FONTS = ("Cascadia Code", "JetBrains Mono", "黑体")
DEFAULT_SIDEBAR_HEIGHT = 550
DEFAULT_META_FONT_SIZE = 10
MESSAGE_FONT_EXTRA_PX = 2
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
MULTI_SPACE_RE = re.compile(r"\s+")
MESSAGE_DEDUPE_WINDOW_SECONDS = 2.5
SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS = 20.0
CROSS_SOURCE_MERGE_WINDOW_SECONDS = 3.0
DEDUPE_CACHE_TTL_SECONDS = 600.0
DEDUPE_CACHE_MAX_KEYS = 5000
DEDUPE_CLEANUP_INTERVAL_SECONDS = 30.0
LOG_ROTATE_MAX_BYTES = 10 * 1024 * 1024
LOG_ROTATE_KEEP_FILES = 5
TRANSLATE_QUEUE_MAXSIZE = 300
TRANSLATE_QUEUE_DROP_LOG_INTERVAL_SECONDS = 5.0
MIN_SIDEBAR_WIDTH = 280
CHAT_CACHE_LIMIT = 100
RUNTIME_LOCK_DIR = os.path.join(ROOT_DIR, "logs", ".runtime")
_LOG_WRITE_LOCK = threading.Lock()
_TARGET_LOCK_PATHS: list[str] = []


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


def as_non_negative_float(value: Any, default: float) -> float:
    parsed = as_float(value, default)
    if not math.isfinite(parsed) or parsed < 0:
        return default
    return parsed


def as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def read_config_float(cfg: dict[str, Any], key: str, default: float) -> float:
    if key not in cfg:
        return default
    value = cfg.get(key)
    try:
        return float(value)
    except Exception as e:
        raise RuntimeError(f"{key} must be number, got {value!r}") from e


def read_config_int(cfg: dict[str, Any], key: str, default: int) -> int:
    if key not in cfg:
        return default
    value = cfg.get(key)
    try:
        return int(value)
    except Exception as e:
        raise RuntimeError(f"{key} must be integer, got {value!r}") from e


def validate_positive_float(name: str, value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(f"{name} must be > 0, got {value!r}")
    return value


def validate_int_min(name: str, value: int, minimum: int) -> int:
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}, got {value!r}")
    return value


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


def normalize_message_for_dedupe(text: str) -> str:
    cleaned = ZERO_WIDTH_RE.sub("", str(text or ""))
    cleaned = MULTI_SPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def is_cross_source_equivalent(current_text: str, previous_text: str) -> bool:
    if not current_text or not previous_text:
        return False
    if current_text == previous_text:
        return True
    return current_text.startswith(previous_text) or previous_text.startswith(current_text)


def cleanup_dedupe_cache(cache: Dict[str, float], now_ts: float):
    expired = [key for key, ts in cache.items() if now_ts - ts > DEDUPE_CACHE_TTL_SECONDS]
    for key in expired:
        cache.pop(key, None)

    overflow = len(cache) - DEDUPE_CACHE_MAX_KEYS
    if overflow > 0:
        oldest = sorted(cache.items(), key=lambda item: item[1])[:overflow]
        for key, _ in oldest:
            cache.pop(key, None)


def cleanup_recent_chat_events(cache: dict[str, tuple[str, float, str]], now_ts: float):
    expired = [
        key
        for key, (_, ts, _) in cache.items()
        if now_ts - ts > DEDUPE_CACHE_TTL_SECONDS
    ]
    for key in expired:
        cache.pop(key, None)


def pick_ui_font_family(root: tk.Tk) -> str:
    try:
        available = {name.lower(): name for name in tkfont.families(root)}
    except Exception:
        available = {}

    for font_name in PREFERRED_UI_FONTS:
        chosen = available.get(font_name.lower())
        if chosen:
            return chosen

    return str(tkfont.nametofont("TkDefaultFont").cget("family"))


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
    sender_name: str
    text_en: str
    created_at: str
    is_self: bool


def append_message_with_limit(cache: list[SidebarMessage], msg: SidebarMessage, limit: int):
    cache.append(msg)
    if limit <= 0:
        cache.clear()
        return
    overflow = len(cache) - limit
    if overflow > 0:
        del cache[:overflow]


def append_log_file(path: str, line: str):
    if not path:
        return
    try:
        with _LOG_WRITE_LOCK:
            rotate_log_file_if_needed(path)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line.rstrip() + "\n")
    except Exception:
        pass


def resolve_log_file_path(path: Any) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    base_dir = APP_DIR if IS_FROZEN else ROOT_DIR
    resolved = raw if os.path.isabs(raw) else os.path.join(base_dir, raw)
    normalized = os.path.normpath(resolved)
    parent = os.path.dirname(normalized)
    if parent:
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception:
            pass
    return normalized


def rotate_log_file_if_needed(path: str):
    try:
        if not os.path.exists(path):
            return
        if os.path.getsize(path) < LOG_ROTATE_MAX_BYTES:
            return
    except Exception:
        return

    try:
        oldest = f"{path}.{LOG_ROTATE_KEEP_FILES}"
        if os.path.exists(oldest):
            os.remove(oldest)
    except Exception:
        pass

    for idx in range(LOG_ROTATE_KEEP_FILES - 1, 0, -1):
        src = f"{path}.{idx}"
        dst = f"{path}.{idx + 1}"
        try:
            if os.path.exists(src):
                os.replace(src, dst)
        except Exception:
            pass

    try:
        os.replace(path, f"{path}.1")
    except Exception:
        pass


def _target_lock_path(target: str) -> str:
    os.makedirs(RUNTIME_LOCK_DIR, exist_ok=True)
    digest = hashlib.sha1(target.strip().lower().encode("utf-8")).hexdigest()[:12]
    return os.path.join(RUNTIME_LOCK_DIR, f"target_{digest}.lock")


def _read_lock_payload(lock_path: str) -> dict[str, Any]:
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _get_pid_start_token(pid: int) -> str:
    if pid <= 0 or os.name != "nt":
        return ""
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetProcessTimes.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        kernel32.GetProcessTimes.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        creation = FILETIME()
        exit_time = FILETIME()
        kernel_time = FILETIME()
        user_time = FILETIME()
        ok = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        kernel32.CloseHandle(handle)
        if not ok:
            return ""

        ticks = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        return str(ticks)
    except Exception:
        return ""


def _is_lock_owner_alive(lock_payload: dict[str, Any]) -> bool:
    pid = as_int(lock_payload.get("pid"), 0)
    if not _is_pid_alive(pid):
        return False

    expected_token = str(lock_payload.get("start_token", "")).strip()
    if not expected_token:
        return True

    current_token = _get_pid_start_token(pid)
    if not current_token:
        # 无法读取启动时间时退化为 PID 存活判断，避免误删活动锁。
        return True
    return current_token == expected_token


def is_target_already_running(target: str) -> bool:
    lock_path = _target_lock_path(target)
    if not os.path.exists(lock_path):
        return False
    lock_payload = _read_lock_payload(lock_path)
    if _is_lock_owner_alive(lock_payload):
        return True
    try:
        os.remove(lock_path)
    except Exception:
        pass
    return False


def acquire_target_lock(target: str) -> tuple[bool, str]:
    lock_path = _target_lock_path(target)
    if os.path.exists(lock_path):
        existing = _read_lock_payload(lock_path)
        if _is_lock_owner_alive(existing):
            pid = as_int(existing.get("pid"), 0)
            return False, f"target already running pid={pid}"
        try:
            os.remove(lock_path)
        except Exception:
            pass

    start_token = _get_pid_start_token(os.getpid())
    payload = {
        "pid": os.getpid(),
        "target": target,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if start_token:
        payload["start_token"] = start_token
    try:
        with open(lock_path, "x", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except FileExistsError:
        existing = _read_lock_payload(lock_path)
        if _is_lock_owner_alive(existing):
            pid = as_int(existing.get("pid"), 0)
            return False, f"target already running pid={pid}"
        try:
            with open(lock_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            return False, f"target lock create failed: {e}"
    except Exception as e:
        return False, f"target lock create failed: {e}"
    return True, lock_path


def release_target_lock():
    global _TARGET_LOCK_PATHS
    lock_paths = list(_TARGET_LOCK_PATHS)
    _TARGET_LOCK_PATHS = []
    for path in lock_paths:
        if not path:
            continue
        try:
            lock_payload = _read_lock_payload(path)
            pid = as_int(lock_payload.get("pid"), 0)
            expected_token = str(lock_payload.get("start_token", "")).strip()
            current_token = _get_pid_start_token(os.getpid())
            same_process = pid == os.getpid()
            if expected_token and current_token and expected_token != current_token:
                same_process = False
            if same_process and os.path.exists(path):
                os.remove(path)
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
    def __init__(
        self,
        title: str,
        width: int,
        side: str,
        targets: list[str],
        message_limit: int,
    ):
        self.root = tk.Tk()
        self.root.title(title)
        self.ui_font_family = pick_ui_font_family(self.root)
        self.root.option_add("*Font", (self.ui_font_family, DEFAULT_META_FONT_SIZE))
        # 置顶只允许通过面板按钮切换；启动默认非置顶。
        self.topmost_var = tk.BooleanVar(value=False)
        self.root.attributes("-topmost", self.topmost_var.get())
        self.status_var = tk.StringVar(value="starting...")
        self.message_limit = max(1, int(message_limit))
        self.chat_order: list[str] = []
        self.chat_messages: dict[str, list[SidebarMessage]] = {}
        self.unread_counts: dict[str, int] = {}
        self.active_chat = ""

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        height = min(DEFAULT_SIDEBAR_HEIGHT, max(320, screen_h - 80))
        if side == "right":
            x = screen_w - width - 16
        else:
            x = 16
        max_x = max(0, screen_w - width - 8)
        x = min(max(0, x), max_x)
        y = 24
        max_y = max(24, screen_h - height - 24)
        if y > max_y:
            y = max_y
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        controls = ttk.Frame(self.root, padding=(8, 6, 8, 4))
        controls.pack(fill=tk.X)
        ttk.Checkbutton(
            controls,
            text="置顶",
            variable=self.topmost_var,
            command=self.toggle_topmost,
        ).pack(side=tk.LEFT)
        ttk.Label(controls, textvariable=self.status_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        content = ttk.Frame(self.root)
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        left_panel = ttk.Frame(content, width=180)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left_panel.pack_propagate(False)
        self.target_list = tk.Listbox(
            left_panel,
            exportselection=False,
            activestyle="none",
            font=(self.ui_font_family, DEFAULT_META_FONT_SIZE),
        )
        self.target_list.pack(fill=tk.BOTH, expand=True)
        self.target_list.bind("<<ListboxSelect>>", self._on_target_selected)

        self.text = scrolledtext.ScrolledText(
            content,
            wrap=tk.WORD,
            font=(self.ui_font_family, DEFAULT_META_FONT_SIZE),
            state=tk.DISABLED,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 左右两套样式：别人消息靠左，自己消息靠右。
        message_font_size = DEFAULT_META_FONT_SIZE + MESSAGE_FONT_EXTRA_PX
        self.text.tag_configure(
            "msg_left",
            justify=tk.LEFT,
            lmargin1=8,
            lmargin2=8,
            rmargin=40,
            font=(self.ui_font_family, message_font_size),
        )
        self.text.tag_configure(
            "msg_right",
            justify=tk.RIGHT,
            lmargin1=40,
            lmargin2=40,
            rmargin=8,
            font=(self.ui_font_family, message_font_size),
        )
        self.text.tag_configure("meta_left", justify=tk.LEFT, foreground="#666666")
        self.text.tag_configure("meta_right", justify=tk.RIGHT, foreground="#666666")

        for target in targets:
            self._ensure_chat(target)
        if self.chat_order:
            self.switch_chat(self.chat_order[0])

    def set_status(self, text: str):
        self.status_var.set(text)

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())

    def _ensure_chat(self, chat_name: str):
        name = str(chat_name or "").strip()
        if not name:
            return
        if name not in self.chat_messages:
            self.chat_messages[name] = []
            self.unread_counts[name] = 0
            self.chat_order.append(name)
            self._refresh_target_list()

    def _format_chat_label(self, chat_name: str) -> str:
        unread = self.unread_counts.get(chat_name, 0)
        if unread > 0:
            return f"{chat_name} ({unread})"
        return chat_name

    def _refresh_target_list(self):
        self.target_list.delete(0, tk.END)
        for chat_name in self.chat_order:
            self.target_list.insert(tk.END, self._format_chat_label(chat_name))
        if self.active_chat in self.chat_order:
            idx = self.chat_order.index(self.active_chat)
            self.target_list.selection_clear(0, tk.END)
            self.target_list.selection_set(idx)
            self.target_list.activate(idx)

    def _on_target_selected(self, _event=None):
        selection = self.target_list.curselection()
        if not selection:
            return
        idx = int(selection[0])
        if idx < 0 or idx >= len(self.chat_order):
            return
        self.switch_chat(self.chat_order[idx])

    def switch_chat(self, chat_name: str):
        name = str(chat_name or "").strip()
        if not name:
            return
        self._ensure_chat(name)
        self.active_chat = name
        self.unread_counts[name] = 0
        self._refresh_target_list()
        self._render_active_chat()

    def _insert_message_content(self, msg: SidebarMessage):
        # 根据 is_self 决定气泡左右对齐。
        meta_tag = "meta_right" if msg.is_self else "meta_left"
        msg_tag = "msg_right" if msg.is_self else "msg_left"
        header = f"[{msg.created_at}]"
        if msg.sender_name:
            header += f" {msg.sender_name}"
        self.text.insert(tk.END, header + "\n", meta_tag)
        # 按需求：正文区不再显示 CN/EN 标签，也不显示 source=session_preview。
        self.text.insert(tk.END, f"{msg.text_en}\n", msg_tag)

    def _insert_message(self, msg: SidebarMessage):
        self.text.configure(state=tk.NORMAL)
        self._insert_message_content(msg)
        self.text.configure(state=tk.DISABLED)

    def _render_active_chat(self):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        for msg in self.chat_messages.get(self.active_chat, []):
            self._insert_message_content(msg)
        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)

    def append_message(self, msg: SidebarMessage):
        self._ensure_chat(msg.chat_name)
        cache = self.chat_messages[msg.chat_name]
        append_message_with_limit(cache, msg, self.message_limit)
        if msg.chat_name != self.active_chat:
            self.unread_counts[msg.chat_name] = self.unread_counts.get(msg.chat_name, 0) + 1
            self._refresh_target_list()
            return
        self._render_active_chat()

    def append_log(self, line: str):
        self.status_var.set(str(line or ""))


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


def stdout_reader(proc: subprocess.Popen, q: "queue.Queue[dict]", worker_target: str = ""):
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                if worker_target:
                    event.setdefault("worker_target", worker_target)
                q.put(event)
            else:
                q.put(
                    {
                        "type": "log",
                        "value": f"worker non-dict event: {line}",
                        "worker_target": worker_target,
                    }
                )
        except json.JSONDecodeError:
            q.put({"type": "log", "value": f"worker raw: {line}", "worker_target": worker_target})


def stderr_reader(proc: subprocess.Popen, q: "queue.Queue[dict]", worker_target: str = ""):
    assert proc.stderr is not None
    for raw in proc.stderr:
        line = raw.rstrip()
        if line:
            q.put(
                {
                    "type": "log",
                    "value": f"worker stderr: {line}",
                    "worker_target": worker_target,
                }
            )


def main():
    default_config_path = DEFAULT_CONFIG_PATH
    if not os.path.exists(default_config_path):
        try:
            default_config_path = ensure_default_config()
        except Exception:
            # 延后到 load_json_config 时给出统一错误信息。
            default_config_path = DEFAULT_CONFIG_PATH
    global _TARGET_LOCK_PATHS
    parser = argparse.ArgumentParser(
        description="Sidebar listener: monitor target chat and show translated output."
    )
    parser.add_argument("--config", default=default_config_path, help="JSON config path")
    parser.add_argument("--target", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    try:
        config = load_json_config(config_path)
    except Exception as e:
        print(f"[sidebar] load config failed: {e}", file=sys.stderr)
        raise SystemExit(2)

    listen_cfg = config.get("listen", {}) if isinstance(config.get("listen", {}), dict) else {}
    translate_cfg = (
        config.get("translate", {}) if isinstance(config.get("translate", {}), dict) else {}
    )
    display_cfg = config.get("display", {}) if isinstance(config.get("display", {}), dict) else {}
    logging_cfg = config.get("logging", {}) if isinstance(config.get("logging", {}), dict) else {}

    targets = normalize_targets(listen_cfg.get("targets"))
    if not targets:
        print(
            "[sidebar] config listen.targets is empty",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if str(args.target or "").strip():
        forced_target = str(args.target).strip()
        if forced_target not in targets:
            print(
                f"[sidebar] warning: --target not found in config listen.targets: {forced_target}",
                flush=True,
            )
        targets = [forced_target]

    listen_mode = str(listen_cfg.get("mode", "session"))
    if listen_mode not in ("chat", "session", "mixed"):
        listen_mode = "session"
    focus_refresh = as_bool(listen_cfg.get("focus_refresh"), False)
    worker_debug = as_bool(listen_cfg.get("worker_debug"), False)
    load_retry_seconds = as_float(listen_cfg.get("load_retry_seconds"), 10.0)
    message_dedupe_window_seconds = as_non_negative_float(
        listen_cfg.get("dedupe_window_seconds"),
        MESSAGE_DEDUPE_WINDOW_SECONDS,
    )
    session_preview_dedupe_window_seconds = as_non_negative_float(
        listen_cfg.get("session_preview_dedupe_window_seconds"),
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
    )
    cross_source_merge_window_seconds = as_non_negative_float(
        listen_cfg.get("cross_source_merge_window_seconds"),
        CROSS_SOURCE_MERGE_WINDOW_SECONDS,
    )
    if len(targets) > 1:
        if listen_mode != "session":
            print(
                "[sidebar] multi-target requires listen.mode=session",
                file=sys.stderr,
            )
            raise SystemExit(2)
        if focus_refresh:
            print(
                "[sidebar] multi-target requires listen.focus_refresh=false",
                file=sys.stderr,
            )
            raise SystemExit(2)

    translate_enabled = as_bool(translate_cfg.get("enabled"), True)
    translate_provider = str(translate_cfg.get("provider", "deeplx")).lower()
    if translate_provider not in ("deeplx", "passthrough"):
        translate_provider = "deeplx"
    deeplx_url = str(translate_cfg.get("deeplx_url") or os.getenv("DEEPLX_URL", ""))
    source_lang = str(translate_cfg.get("source_lang", "auto"))
    target_lang = str(translate_cfg.get("target_lang", "EN"))

    english_only = as_bool(display_cfg.get("english_only"), True)
    translate_fail_behavior = str(display_cfg.get("on_translate_fail", "show_cn_with_reason"))
    if translate_fail_behavior not in ("show_cn_with_reason", "show_cn", "show_reason"):
        translate_fail_behavior = "show_cn_with_reason"
    side = str(display_cfg.get("side", "right"))
    if side not in ("left", "right"):
        side = "right"

    try:
        listen_interval = read_config_float(listen_cfg, "interval_seconds", 1.0)
        translate_timeout = read_config_float(translate_cfg, "timeout_seconds", 8.0)
        width = read_config_int(display_cfg, "width", 420)
        listen_interval = validate_positive_float("listen.interval_seconds", listen_interval)
        translate_timeout = validate_positive_float("translate.timeout_seconds", translate_timeout)
        width = validate_int_min("display.width", width, MIN_SIDEBAR_WIDTH)
    except RuntimeError as e:
        print(f"[sidebar] invalid config: {e}", file=sys.stderr)
        raise SystemExit(2)

    log_file = resolve_log_file_path(logging_cfg.get("file", ""))

    running_targets: list[str] = []
    skipped_targets: list[tuple[str, str]] = []
    locked_paths: list[str] = []
    for target in targets:
        locked, lock_info = acquire_target_lock(target)
        if not locked:
            skipped_targets.append((target, lock_info))
            print(f"[sidebar] skip target={target}: {lock_info}", flush=True)
            continue
        running_targets.append(target)
        locked_paths.append(lock_info)
    if not running_targets:
        print("[sidebar] no available targets to start", flush=True)
        return
    _TARGET_LOCK_PATHS = locked_paths
    atexit.register(release_target_lock)

    ui = SidebarUI(
        title=f"WeChat Sidebar mode={listen_mode}",
        width=width,
        side=side,
        targets=running_targets,
        message_limit=CHAT_CACHE_LIMIT,
    )
    translator = create_translator(
        enabled=translate_enabled,
        provider=translate_provider,
        deeplx_url=deeplx_url,
        source_lang=source_lang,
        target_lang=target_lang,
        timeout_seconds=translate_timeout,
    )
    ui.set_status(f"running mode={listen_mode} targets={len(running_targets)}")
    if listen_mode in ("chat", "mixed"):
        ui.append_log("warning: chat/mixed 会主动打开会话；仅监听请用 mode=session")
    for target, reason in skipped_targets:
        append_log_file(log_file, f"skip target={target}: {reason}")

    append_log_file(log_file, "sidebar start")
    append_log_file(log_file, f"requested targets={targets}")
    append_log_file(log_file, f"running targets={running_targets}")
    append_log_file(log_file, f"chat cache limit={CHAT_CACHE_LIMIT}")
    append_log_file(
        log_file,
        (
            "dedupe windows: "
            f"message={message_dedupe_window_seconds}s "
            f"session_preview={session_preview_dedupe_window_seconds}s "
            f"cross_source={cross_source_merge_window_seconds}s"
        ),
    )
    event_queue: "queue.Queue[dict]" = queue.Queue()
    translate_queue: "queue.Queue[dict | None]" = queue.Queue(maxsize=TRANSLATE_QUEUE_MAXSIZE)
    dedupe_cache: Dict[str, float] = {}
    recent_chat_events: dict[str, tuple[str, float, str]] = {}
    last_dedupe_cleanup_at = 0.0
    translate_queue_drop_count = 0
    last_translate_queue_drop_log_at = 0.0
    workers: dict[str, subprocess.Popen] = {}
    exited_workers: set[str] = set()
    for target in running_targets:
        worker = start_worker_process(
            target,
            listen_interval,
            listen_mode,
            worker_debug,
            focus_refresh,
            load_retry_seconds,
        )
        workers[target] = worker
        append_log_file(log_file, f"worker start target={target} pid={worker.pid}")
        t_out = threading.Thread(
            target=stdout_reader, args=(worker, event_queue, target), daemon=True
        )
        t_err = threading.Thread(
            target=stderr_reader, args=(worker, event_queue, target), daemon=True
        )
        t_out.start()
        t_err.start()

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
        else:
            try:
                translate_queue.put_nowait(task)
                return
            except queue.Full:
                translate_queue_drop_count += 1

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

            event_queue.put(
                {
                    "type": "render_message",
                    "chat_name": task["chat_name"],
                    "sender_name": task["sender_name"],
                    "is_self": task["is_self"],
                    "source": task["source"],
                    "created_at": task["created_at"],
                    "text_en": rendered_text,
                }
            )

    t_translate = threading.Thread(target=translate_worker, daemon=True)
    t_translate.start()

    def handle_event(event: dict):
        nonlocal last_dedupe_cleanup_at
        kind = event.get("type")
        worker_target = str(event.get("worker_target", "")).strip()
        log_prefix = f"[{worker_target}] " if worker_target else ""
        default_chat_name = worker_target or (running_targets[0] if running_targets else "")
        if kind == "status":
            value = str(event.get("value", ""))
            ui.append_log(f"{log_prefix}status: {value}")
            append_log_file(log_file, f"{log_prefix}status: {value}")
            return

        if kind == "log":
            value = str(event.get("value", ""))
            ui.append_log(f"{log_prefix}{value}")
            append_log_file(log_file, f"{log_prefix}{value}")
            return

        if kind == "render_message":
            created_at = str(event.get("created_at") or datetime.now().strftime("%H:%M:%S"))
            chat_name = str(event.get("chat_name") or default_chat_name)
            sender_name = str(event.get("sender_name", ""))
            rendered_text = str(event.get("text_en", ""))
            source = str(event.get("source", ""))
            is_self = bool(event.get("is_self", False))
            msg = SidebarMessage(
                chat_name=chat_name,
                sender_name=sender_name if not is_self else "",
                text_en=rendered_text,
                created_at=created_at,
                is_self=is_self,
            )
            ui.append_message(msg)
            append_log_file(
                log_file,
                (
                    f"[{created_at}] chat={chat_name} source={source} sender={sender_name or 'self'} "
                    f"en={rendered_text}"
                ),
            )
            return

        if kind != "message":
            ui.append_log(f"{log_prefix}unknown event: {event}")
            append_log_file(log_file, f"{log_prefix}unknown event: {event}")
            return

        # source 仅用于去重归并与日志，不进入 UI 展示。
        source = str(event.get("source", ""))
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
        # 2) 图片占位消息直接过滤（例如 [图片]），不渲染到侧边栏。
        if is_image_placeholder(body_cn):
            append_log_file(log_file, f"skip image placeholder: {chat_name} {cn_text}")
            return

        normalized_body = normalize_message_for_dedupe(body_cn)
        if not normalized_body:
            return

        now_ts = time.time()

        # 先做来源感知去重窗口：session_preview 使用更长窗口抑制重复预览抖动。
        dedupe_key = f"{chat_name}::{sender_name}::{normalized_body}"
        prev_ts = dedupe_cache.get(dedupe_key)
        dedupe_window = (
            session_preview_dedupe_window_seconds
            if source == "session_preview"
            else message_dedupe_window_seconds
        )
        if prev_ts is not None and now_ts - prev_ts <= dedupe_window:
            return

        # mixed 模式下 chat/session_preview 双来源近实时重叠时，合并为一条。
        prev_chat = recent_chat_events.get(chat_name)
        if prev_chat:
            prev_body, prev_body_ts, prev_source = prev_chat
            if source != prev_source and now_ts - prev_body_ts <= cross_source_merge_window_seconds:
                if is_cross_source_equivalent(normalized_body, prev_body):
                    return

        dedupe_cache[dedupe_key] = now_ts
        recent_chat_events[chat_name] = (normalized_body, now_ts, source)

        if now_ts - last_dedupe_cleanup_at >= DEDUPE_CLEANUP_INTERVAL_SECONDS:
            cleanup_dedupe_cache(dedupe_cache, now_ts)
            cleanup_recent_chat_events(recent_chat_events, now_ts)
            last_dedupe_cleanup_at = now_ts

        enqueue_translate_task(
            {
                "chat_name": chat_name,
                "sender_name": sender_name,
                "body_cn": body_cn,
                "is_self": is_self,
                "source": source,
                "created_at": str(event.get("created_at") or datetime.now().strftime("%H:%M:%S")),
            }
        )

    def drain_queue():
        try:
            while True:
                event = event_queue.get_nowait()
                handle_event(event)
        except queue.Empty:
            pass

        for target, worker in workers.items():
            if target in exited_workers:
                continue
            return_code = worker.poll()
            if return_code is None:
                continue
            exited_workers.add(target)
            exit_line = f"worker exited target={target} code={return_code}"
            ui.append_log(exit_line)
            append_log_file(log_file, exit_line)
            if len(exited_workers) == len(workers):
                ui.set_status(f"all workers exited mode={listen_mode}")

        ui.root.after(200, drain_queue)

    def on_close():
        for worker in workers.values():
            try:
                if worker.poll() is None:
                    worker.terminate()
            except Exception:
                pass
        try:
            signal_translate_worker_stop()
        except Exception:
            pass
        release_target_lock()
        ui.root.destroy()

    ui.root.protocol("WM_DELETE_WINDOW", on_close)
    ui.root.after(200, drain_queue)
    ui.root.mainloop()


if __name__ == "__main__":
    if run_embedded_worker_if_requested():
        raise SystemExit(0)
    main()
