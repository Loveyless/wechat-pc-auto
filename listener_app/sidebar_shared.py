import json
import math
import os
import re
import shutil
import sys
import tempfile
from typing import Any, Dict

SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_bundle_root() -> str:
    return str(getattr(sys, "_MEIPASS", SOURCE_ROOT))


def get_runtime_root() -> str:
    if is_frozen_app():
        return os.path.dirname(os.path.abspath(sys.executable))
    return SOURCE_ROOT


ROOT_DIR = get_runtime_root()
BUNDLE_ROOT = get_bundle_root()
DEFAULT_CONFIG_PATH = os.path.join(ROOT_DIR, "config", "listener.json")
BUNDLED_CONFIG_PATH = os.path.join(BUNDLE_ROOT, "config", "listener.json")
WORKER_EXE_NAME = "group_listener_worker.exe"

# 匹配 “发送人: 正文” / “发送人：正文”
SENDER_PREFIX_RE = re.compile(r"^\s*([^:：]{1,40})[:：]\s*(.+?)\s*$")
# 过滤图片/媒体占位文本（例如 [图片] / [视频] / [Images]）
IMAGE_PLACEHOLDER_RE = re.compile(r"^\[\s*(图片|image|images|photo)\s*\]$", re.IGNORECASE)
VIDEO_PLACEHOLDER_RE = re.compile(r"^\[\s*(视频|video)\s*\]$", re.IGNORECASE)
ANIMATED_EMOTICON_PLACEHOLDER_RE = re.compile(
    r"^\[\s*(动画表情|animated emoticon|emoticon|emoji|sticker)\s*\]$",
    re.IGNORECASE,
)
VOICE_PLACEHOLDER_RE = re.compile(
    r'^\[\s*(语音|voice(?:\s+over)?|audio)\s*\]\s*\d+\s*"*$',
    re.IGNORECASE,
)
GENERIC_BRACKET_PLACEHOLDER_RE = re.compile(r"^\[[^\r\n]+\]$")
HTTP_LINK_RE = re.compile(r"https?://", re.IGNORECASE)
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
MULTI_SPACE_RE = re.compile(r"\s+")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
CJK_TEXT_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS = 20.0
DEDUPE_CACHE_TTL_SECONDS = 600.0
DEDUPE_CACHE_MAX_KEYS = 5000
DEDUPE_CLEANUP_INTERVAL_SECONDS = 30.0
LOG_ROTATE_MAX_BYTES = 10 * 1024 * 1024
LOG_ROTATE_KEEP_FILES = 5
TRANSLATE_QUEUE_MAXSIZE = 300
TRANSLATE_QUEUE_DROP_LOG_INTERVAL_SECONDS = 5.0
DEEPLX_MAX_RETRIES = 2
DEEPLX_RETRY_BACKOFF_SECONDS = 0.6
MIN_SIDEBAR_WIDTH = 280
DEFAULT_SIDEBAR_WIDTH = 470
MIN_LISTEN_INTERVAL_SECONDS = 0.2
CHAT_CACHE_LIMIT = 100
DEFAULT_LISTEN_INTERVAL_SECONDS = 0.6
UI_DRAIN_INTERVAL_MS = 80
TRANSLATE_PENDING_TEXT = "Loading..."
WORKER_RESTART_INITIAL_BACKOFF_SECONDS = 3.0
WORKER_RESTART_MAX_BACKOFF_SECONDS = 30.0
WORKER_STOP_TIMEOUT_SECONDS = 3.0
WORKER_FORCE_KILL_TIMEOUT_SECONDS = 1.0
RUNTIME_LOCK_DIR = os.path.join(ROOT_DIR, "logs", ".runtime")
SUPPORTED_TRANSLATE_PROVIDERS = ("deeplx", "passthrough")


def load_local_env():
    env_path = os.path.join(ROOT_DIR, ".env.local")
    if not os.path.exists(env_path):
        return
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
    except Exception:
        pass


def ensure_runtime_layout(
    runtime_root: str = ROOT_DIR,
    bundled_config_path: str = BUNDLED_CONFIG_PATH,
) -> str:
    config_dir = os.path.join(runtime_root, "config")
    logs_dir = os.path.join(runtime_root, "logs")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    runtime_config_path = os.path.join(config_dir, "listener.json")
    bundled_config = str(bundled_config_path or "").strip()
    bundled_config_dir = os.path.dirname(bundled_config) if bundled_config else ""
    if bundled_config_dir and os.path.isdir(bundled_config_dir):
        for name in os.listdir(bundled_config_dir):
            if not str(name).lower().endswith(".json"):
                continue
            source_path = os.path.join(bundled_config_dir, name)
            target_path = os.path.join(config_dir, name)
            if os.path.isfile(source_path) and not os.path.exists(target_path):
                shutil.copy2(source_path, target_path)
    return runtime_config_path


ensure_runtime_layout()
load_local_env()


def load_json_config(path: str) -> Dict[str, Any]:
    # 仅接受 object 根节点，避免把数组/字符串误当配置。
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise RuntimeError(f"config root must be object: {path}")
    return raw


def save_json_config_atomic(path: str, payload: Dict[str, Any]):
    normalized = os.path.abspath(path)
    parent = os.path.dirname(normalized)
    if parent:
        os.makedirs(parent, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix="listener.",
        suffix=".tmp",
        dir=parent or None,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, normalized)
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise


def save_listener_targets_config(path: str, config: Dict[str, Any], targets: list[str]):
    normalized_targets = normalize_targets(targets)
    if not normalized_targets:
        raise RuntimeError("listen.targets cannot be empty")

    payload = dict(config)
    listen_cfg = payload.get("listen", {})
    if not isinstance(listen_cfg, dict):
        listen_cfg = {}
    else:
        listen_cfg = dict(listen_cfg)
    listen_cfg["targets"] = normalized_targets
    payload["listen"] = listen_cfg

    save_json_config_atomic(path, payload)
    config.clear()
    config.update(payload)


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


def validate_float_min(name: str, value: float, minimum: float) -> float:
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}, got {value!r}")
    return value


def validate_float_range(name: str, value: float, minimum: float, maximum: float) -> float:
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} must be in [{minimum}, {maximum}], got {value!r}")
    return value


def validate_int_min(name: str, value: int, minimum: int) -> int:
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}, got {value!r}")
    return value


def validate_int_range(name: str, value: int, minimum: int, maximum: int) -> int:
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} must be in [{minimum}, {maximum}], got {value!r}")
    return value


def validate_int_choices(name: str, value: int, choices: tuple[int, ...]) -> int:
    if value not in choices:
        joined = ", ".join(str(item) for item in choices)
        raise RuntimeError(f"{name} must be one of [{joined}], got {value!r}")
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


def is_filtered_placeholder(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    return any(
        pattern.match(value)
        for pattern in (
            IMAGE_PLACEHOLDER_RE,
            VIDEO_PLACEHOLDER_RE,
            ANIMATED_EMOTICON_PLACEHOLDER_RE,
            VOICE_PLACEHOLDER_RE,
            GENERIC_BRACKET_PLACEHOLDER_RE,
        )
    )


def is_filtered_link_message(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    return bool(HTTP_LINK_RE.search(value))


def normalize_message_for_dedupe(text: str) -> str:
    cleaned = ZERO_WIDTH_RE.sub("", str(text or ""))
    cleaned = MULTI_SPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def normalize_tts_text(text: str) -> str:
    return MULTI_SPACE_RE.sub(" ", str(text or "")).strip()


def summarize_tts_text(text: str, max_chars: int = 48) -> str:
    normalized = normalize_tts_text(text)
    if not normalized:
        return ""
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars] + "..."


def is_speakable_english_text(text: str) -> bool:
    value = normalize_tts_text(text)
    if not value or value == TRANSLATE_PENDING_TEXT:
        return False
    if "translate_failed:" in value.lower():
        return False
    if CJK_TEXT_RE.search(value):
        return False
    return bool(ASCII_LETTER_RE.search(value))

