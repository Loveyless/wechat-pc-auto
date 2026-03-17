from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

if __package__:
    from .sidebar_runtime_support import resolve_log_file_path
    from .sidebar_shared import (
        DEFAULT_CONFIG_PATH,
        DEFAULT_LISTEN_INTERVAL_SECONDS,
        MIN_LISTEN_INTERVAL_SECONDS,
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
        as_bool,
        as_non_negative_float,
        load_json_config,
        normalize_targets,
        read_config_float,
        validate_float_min,
        validate_positive_float,
    )
    from .sidebar_translate_runtime import (
        normalize_translate_provider,
        validate_translate_config,
    )
    from .sidebar_tts import normalize_tts_provider
else:
    from sidebar_runtime_support import resolve_log_file_path
    from sidebar_shared import (
        DEFAULT_CONFIG_PATH,
        DEFAULT_LISTEN_INTERVAL_SECONDS,
        MIN_LISTEN_INTERVAL_SECONDS,
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
        as_bool,
        as_non_negative_float,
        load_json_config,
        normalize_targets,
        read_config_float,
        validate_float_min,
        validate_positive_float,
    )
    from sidebar_translate_runtime import (
        normalize_translate_provider,
        validate_translate_config,
    )
    from sidebar_tts import normalize_tts_provider

DEEPLX_ENV_KEY = "DEEPLX_URL"
DEEPLX_ENV_FIELD = "deeplx_url_env"
OPENAI_COMPATIBLE_PROVIDER = "openai_compatible"


@dataclass(slots=True)
class RuntimeListenConfig:
    mode: str
    targets: list[str]
    interval_seconds: float
    focus_refresh: bool
    worker_debug: bool
    load_retry_seconds: float
    session_preview_dedupe_window_seconds: float


@dataclass(slots=True)
class RuntimeTranslateConfig:
    enabled: bool
    provider: str
    deeplx_url: str
    source_lang: str
    target_lang: str
    timeout_seconds: float
    openai_base_url: str
    openai_model: str
    openai_api_key: str


@dataclass(slots=True)
class RuntimeDisplayConfig:
    english_only: bool
    tts_auto_read_active_chat: bool
    on_translate_fail: str


@dataclass(slots=True)
class RuntimeTTSConfig:
    provider: str
    raw_config: dict[str, Any]


@dataclass(slots=True)
class DesktopRuntimeConfig:
    config_path: str
    config_dir: str
    log_file: str
    raw_config: dict[str, Any]
    listen: RuntimeListenConfig
    translate: RuntimeTranslateConfig
    display: RuntimeDisplayConfig
    tts: RuntimeTTSConfig


def _read_provider_section(payload: dict[str, Any], provider: str) -> dict[str, Any]:
    providers = _read_config_section(payload, "providers")
    value = providers.get(provider, {})
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _resolve_deeplx_url(
    translate_cfg: dict[str, Any],
    deeplx_cfg: dict[str, Any],
) -> str:
    direct_value = str(deeplx_cfg.get("deeplx_url") or translate_cfg.get("deeplx_url") or "").strip()
    if direct_value:
        return direct_value
    env_name = str(deeplx_cfg.get(DEEPLX_ENV_FIELD) or translate_cfg.get(DEEPLX_ENV_FIELD) or "").strip()
    if not env_name:
        return ""
    if env_name != DEEPLX_ENV_KEY:
        raise RuntimeError(f"translate.providers.deeplx.{DEEPLX_ENV_FIELD} must be {DEEPLX_ENV_KEY}")
    return str(os.getenv(env_name, "")).strip()


def _resolve_translate_timeout(
    translate_cfg: dict[str, Any],
    provider_cfg: dict[str, Any],
    provider: str,
) -> float:
    default_timeout = 8.0
    if "timeout_seconds" in provider_cfg:
        timeout_seconds = read_config_float(provider_cfg, "timeout_seconds", default_timeout)
        return validate_positive_float(
            f"translate.providers.{provider}.timeout_seconds",
            timeout_seconds,
        )
    timeout_seconds = read_config_float(translate_cfg, "timeout_seconds", default_timeout)
    return validate_positive_float("translate.timeout_seconds", timeout_seconds)


def _resolve_openai_compatible_fields(
    translate_cfg: dict[str, Any],
) -> tuple[str, str, str, float]:
    provider_cfg = _read_provider_section(translate_cfg, OPENAI_COMPATIBLE_PROVIDER)
    base_url = str(provider_cfg.get("base_url") or "").strip()
    model = str(provider_cfg.get("model") or "").strip()
    api_key = str(provider_cfg.get("api_key") or "").strip()
    timeout_seconds = _resolve_translate_timeout(
        translate_cfg,
        provider_cfg,
        OPENAI_COMPATIBLE_PROVIDER,
    )
    return base_url, model, api_key, timeout_seconds


def _resolve_effective_tts_config(tts_cfg: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    provider = normalize_tts_provider(tts_cfg.get("provider"))
    effective_tts = dict(tts_cfg)
    provider_cfg = _read_provider_section(tts_cfg, provider)
    if provider == "windows_system":
        effective_tts.pop("config_path", None)
        return provider, effective_tts
    config_path = str(
        provider_cfg.get("config_path") or effective_tts.get("config_path") or ""
    ).strip()
    if config_path:
        effective_tts["config_path"] = config_path
    return provider, effective_tts


def _read_config_section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _normalize_translate_fail_behavior(value: Any) -> str:
    behavior = str(value or "show_cn_with_reason").strip()
    if behavior not in ("show_cn_with_reason", "show_cn", "show_reason"):
        return "show_cn_with_reason"
    return behavior


def load_runtime_config(config_path: str = DEFAULT_CONFIG_PATH) -> DesktopRuntimeConfig:
    normalized_path = os.path.abspath(config_path)
    raw_config = load_json_config(normalized_path)
    config_dir = os.path.dirname(normalized_path)
    listen_cfg = _read_config_section(raw_config, "listen")
    translate_cfg = _read_config_section(raw_config, "translate")
    display_cfg = _read_config_section(raw_config, "display")
    tts_cfg = _read_config_section(raw_config, "tts")
    logging_cfg = _read_config_section(raw_config, "logging")

    targets = normalize_targets(listen_cfg.get("targets"))
    listen_mode = str(listen_cfg.get("mode", "session")).strip().lower() or "session"
    if listen_mode != "session":
        raise RuntimeError("session-only branch only supports listen.mode=session")

    interval_seconds = read_config_float(
        listen_cfg,
        "interval_seconds",
        DEFAULT_LISTEN_INTERVAL_SECONDS,
    )
    interval_seconds = validate_positive_float("listen.interval_seconds", interval_seconds)
    interval_seconds = validate_float_min(
        "listen.interval_seconds",
        interval_seconds,
        MIN_LISTEN_INTERVAL_SECONDS,
    )

    load_retry_seconds = as_non_negative_float(listen_cfg.get("load_retry_seconds"), 10.0)
    load_retry_seconds = validate_positive_float("listen.load_retry_seconds", load_retry_seconds)
    session_preview_dedupe_window_seconds = as_non_negative_float(
        listen_cfg.get("session_preview_dedupe_window_seconds"),
        SESSION_PREVIEW_DEDUPE_WINDOW_SECONDS,
    )

    translate_enabled = as_bool(translate_cfg.get("enabled"), True)
    translate_provider = normalize_translate_provider(translate_cfg.get("provider", "deeplx"))
    deeplx_cfg = _read_provider_section(translate_cfg, "deeplx")
    deeplx_url = _resolve_deeplx_url(translate_cfg, deeplx_cfg)
    deeplx_timeout = _resolve_translate_timeout(translate_cfg, deeplx_cfg, "deeplx")
    openai_base_url, openai_model, openai_api_key, openai_timeout = _resolve_openai_compatible_fields(
        translate_cfg
    )
    timeout_seconds = deeplx_timeout if translate_provider != OPENAI_COMPATIBLE_PROVIDER else openai_timeout
    validate_translate_config(
        translate_enabled,
        translate_provider,
        deeplx_url,
        openai_base_url=openai_base_url,
        openai_model=openai_model,
        openai_api_key=openai_api_key,
    )
    tts_provider, effective_tts_cfg = _resolve_effective_tts_config(tts_cfg)

    display = RuntimeDisplayConfig(
        english_only=as_bool(display_cfg.get("english_only"), True),
        tts_auto_read_active_chat=as_bool(display_cfg.get("tts_auto_read_active_chat"), True),
        on_translate_fail=_normalize_translate_fail_behavior(
            display_cfg.get("on_translate_fail", "show_cn_with_reason")
        ),
    )

    return DesktopRuntimeConfig(
        config_path=normalized_path,
        config_dir=config_dir,
        log_file=resolve_log_file_path(logging_cfg.get("file", "")),
        raw_config=raw_config,
        listen=RuntimeListenConfig(
            mode=listen_mode,
            targets=targets,
            interval_seconds=interval_seconds,
            focus_refresh=as_bool(listen_cfg.get("focus_refresh"), False),
            worker_debug=as_bool(listen_cfg.get("worker_debug"), False),
            load_retry_seconds=load_retry_seconds,
            session_preview_dedupe_window_seconds=session_preview_dedupe_window_seconds,
        ),
        translate=RuntimeTranslateConfig(
            enabled=translate_enabled,
            provider=translate_provider,
            deeplx_url=deeplx_url,
            source_lang=str(translate_cfg.get("source_lang", "auto")),
            target_lang=str(translate_cfg.get("target_lang", "EN")),
            timeout_seconds=timeout_seconds,
            openai_base_url=openai_base_url,
            openai_model=openai_model,
            openai_api_key=openai_api_key,
        ),
        display=display,
        tts=RuntimeTTSConfig(
            provider=tts_provider,
            raw_config=effective_tts_cfg,
        ),
    )
