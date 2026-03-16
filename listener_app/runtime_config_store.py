from __future__ import annotations

import copy
import os
from typing import Any

if __package__:
    from .runtime_config import DEEPLX_ENV_FIELD, load_runtime_config
    from .sidebar_shared import (
        SUPPORTED_TRANSLATE_PROVIDERS,
        load_json_config,
        save_json_config_atomic,
        validate_positive_float,
    )
    from .sidebar_translate_runtime import normalize_translate_provider, validate_translate_config
    from .sidebar_tts import (
        DEFAULT_TTS_PROVIDER,
        DOUBAO_TTS_DEFAULT_ACCESS_TOKEN_ENV_KEY,
        DOUBAO_TTS_DEFAULT_APPID_ENV_KEY,
        DOUBAO_TTS_DEFAULT_CONFIG_PATH,
        DOUBAO_TTS_DEFAULT_ENDPOINT,
        DOUBAO_TTS_DEFAULT_LOUDNESS_RATE,
        DOUBAO_TTS_DEFAULT_SAMPLE_RATE,
        DOUBAO_TTS_DEFAULT_SPEECH_RATE,
        SUPPORTED_TTS_PROVIDERS,
        TENCENT_CLOUD_TTS_DEFAULT_CONFIG_PATH,
        TENCENT_CLOUD_TTS_DEFAULT_ENDPOINT,
        TENCENT_CLOUD_TTS_DEFAULT_MODEL_TYPE,
        TENCENT_CLOUD_TTS_DEFAULT_PRIMARY_LANGUAGE,
        TENCENT_CLOUD_TTS_DEFAULT_PROJECT_ID,
        TENCENT_CLOUD_TTS_DEFAULT_SAMPLE_RATE,
        TENCENT_CLOUD_TTS_DEFAULT_SECRET_ID_ENV_KEY,
        TENCENT_CLOUD_TTS_DEFAULT_SECRET_KEY_ENV_KEY,
        TENCENT_CLOUD_TTS_DEFAULT_SEGMENT_RATE,
        TENCENT_CLOUD_TTS_DEFAULT_SPEED,
        TENCENT_CLOUD_TTS_DEFAULT_VOLUME,
        load_doubao_tts_settings_from_payload,
        load_tencent_cloud_tts_settings_from_payload,
        normalize_tts_provider,
        resolve_config_file_path,
    )
else:
    from runtime_config import DEEPLX_ENV_FIELD, load_runtime_config
    from sidebar_shared import (
        SUPPORTED_TRANSLATE_PROVIDERS,
        load_json_config,
        save_json_config_atomic,
        validate_positive_float,
    )
    from sidebar_translate_runtime import normalize_translate_provider, validate_translate_config
    from sidebar_tts import (
        DEFAULT_TTS_PROVIDER,
        DOUBAO_TTS_DEFAULT_ACCESS_TOKEN_ENV_KEY,
        DOUBAO_TTS_DEFAULT_APPID_ENV_KEY,
        DOUBAO_TTS_DEFAULT_CONFIG_PATH,
        DOUBAO_TTS_DEFAULT_ENDPOINT,
        DOUBAO_TTS_DEFAULT_LOUDNESS_RATE,
        DOUBAO_TTS_DEFAULT_SAMPLE_RATE,
        DOUBAO_TTS_DEFAULT_SPEECH_RATE,
        SUPPORTED_TTS_PROVIDERS,
        TENCENT_CLOUD_TTS_DEFAULT_CONFIG_PATH,
        TENCENT_CLOUD_TTS_DEFAULT_ENDPOINT,
        TENCENT_CLOUD_TTS_DEFAULT_MODEL_TYPE,
        TENCENT_CLOUD_TTS_DEFAULT_PRIMARY_LANGUAGE,
        TENCENT_CLOUD_TTS_DEFAULT_PROJECT_ID,
        TENCENT_CLOUD_TTS_DEFAULT_SAMPLE_RATE,
        TENCENT_CLOUD_TTS_DEFAULT_SECRET_ID_ENV_KEY,
        TENCENT_CLOUD_TTS_DEFAULT_SECRET_KEY_ENV_KEY,
        TENCENT_CLOUD_TTS_DEFAULT_SEGMENT_RATE,
        TENCENT_CLOUD_TTS_DEFAULT_SPEED,
        TENCENT_CLOUD_TTS_DEFAULT_VOLUME,
        load_doubao_tts_settings_from_payload,
        load_tencent_cloud_tts_settings_from_payload,
        normalize_tts_provider,
        resolve_config_file_path,
    )

DEEPLX_ENV_KEY = "DEEPLX_URL"
CONFIG_APPLY_STRATEGY = "restart_required"
SUPPORTED_TRANSLATE_FAIL_BEHAVIORS = (
    "show_cn_with_reason",
    "show_cn",
    "show_reason",
)


class ConfigValidationError(RuntimeError):
    def __init__(self, message: str, *, field_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.field_errors = dict(field_errors or {})


def build_config_snapshot(config_path: str) -> dict[str, Any]:
    runtime_config = load_runtime_config(config_path)
    listener_raw = load_json_config(runtime_config.config_path)
    translate_cfg = _read_section(listener_raw, "translate")
    tts_cfg = _read_section(listener_raw, "tts")

    doubao_path, doubao_resolved_path = _provider_config_paths("doubao", tts_cfg, runtime_config.config_dir)
    tencent_path, tencent_resolved_path = _provider_config_paths(
        "tencent_cloud",
        tts_cfg,
        runtime_config.config_dir,
    )
    doubao_raw = _load_optional_json(doubao_resolved_path, _default_doubao_provider_payload())
    tencent_raw = _load_optional_json(tencent_resolved_path, _default_tencent_provider_payload())

    return {
        "translate": {
            "enabled": runtime_config.translate.enabled,
            "provider": runtime_config.translate.provider,
            "available_providers": list(SUPPORTED_TRANSLATE_PROVIDERS),
            "source_lang": runtime_config.translate.source_lang,
            "target_lang": runtime_config.translate.target_lang,
            "timeout_seconds": runtime_config.translate.timeout_seconds,
            "deeplx_url": _build_secret_status(
                translate_cfg,
                "deeplx_url",
                DEEPLX_ENV_FIELD,
                default_env_key=DEEPLX_ENV_KEY,
            ),
        },
        "display": {
            "english_only": runtime_config.display.english_only,
            "tts_auto_read_active_chat": runtime_config.display.tts_auto_read_active_chat,
            "on_translate_fail": runtime_config.display.on_translate_fail,
        },
        "tts": {
            "provider": runtime_config.tts.provider,
            "available_providers": list(SUPPORTED_TTS_PROVIDERS),
            "providers": {
                "windows_system": {},
                "doubao": _build_doubao_provider_snapshot(doubao_raw),
                "tencent_cloud": _build_tencent_provider_snapshot(tencent_raw),
            },
        },
        "runtime": _build_runtime_meta(runtime_config.config_path),
    }


def save_config_snapshot(config_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    runtime_config = load_runtime_config(config_path)
    listener_path = runtime_config.config_path
    listener_raw = load_json_config(listener_path)
    config_dir = runtime_config.config_dir

    translate_payload = _read_section(payload, "translate")
    display_payload = _read_section(payload, "display")
    tts_payload = _read_section(payload, "tts")
    secret_updates = _read_section(payload, "secret_updates")
    translate_secret_updates = _read_section(secret_updates, "translate")
    tts_secret_updates = _read_section(secret_updates, "tts")

    next_listener = copy.deepcopy(listener_raw)
    next_translate = _read_section(next_listener, "translate")
    next_display = _read_section(next_listener, "display")
    next_tts = _read_section(next_listener, "tts")

    translate_enabled = _read_bool(
        translate_payload,
        "enabled",
        runtime_config.translate.enabled,
        field_path="translate.enabled",
    )
    translate_provider = _read_translate_provider(translate_payload, runtime_config.translate.provider)
    translate_source_lang = _read_string(
        translate_payload,
        "source_lang",
        runtime_config.translate.source_lang,
        field_path="translate.source_lang",
    )
    translate_target_lang = _read_string(
        translate_payload,
        "target_lang",
        runtime_config.translate.target_lang,
        field_path="translate.target_lang",
    )
    translate_timeout = _read_float(
        translate_payload,
        "timeout_seconds",
        runtime_config.translate.timeout_seconds,
        field_path="translate.timeout_seconds",
    )
    translate_timeout = validate_positive_float("translate.timeout_seconds", translate_timeout)
    next_translate["enabled"] = translate_enabled
    next_translate["provider"] = translate_provider
    next_translate["source_lang"] = translate_source_lang
    next_translate["target_lang"] = translate_target_lang
    next_translate["timeout_seconds"] = translate_timeout
    _apply_secret_update(
        next_translate,
        key="deeplx_url",
        env_key_field=DEEPLX_ENV_FIELD,
        update=translate_secret_updates.get("deeplx_url"),
        field_path="translate.deeplx_url",
        default_env_key=DEEPLX_ENV_KEY,
        allow_custom_env_key=False,
    )
    effective_deeplx_url = _resolve_effective_secret_value(
        next_translate,
        "deeplx_url",
        DEEPLX_ENV_FIELD,
        default_env_key=DEEPLX_ENV_KEY,
    )
    try:
        validate_translate_config(translate_enabled, translate_provider, effective_deeplx_url)
    except RuntimeError as exc:
        raise _wrap_translate_validation_error(exc) from exc

    next_display["english_only"] = _read_bool(
        display_payload,
        "english_only",
        runtime_config.display.english_only,
        field_path="display.english_only",
    )
    next_display["tts_auto_read_active_chat"] = _read_bool(
        display_payload,
        "tts_auto_read_active_chat",
        runtime_config.display.tts_auto_read_active_chat,
        field_path="display.tts_auto_read_active_chat",
    )
    on_translate_fail = _read_string(
        display_payload,
        "on_translate_fail",
        runtime_config.display.on_translate_fail,
        field_path="display.on_translate_fail",
    ).strip() or "show_cn_with_reason"
    if on_translate_fail not in SUPPORTED_TRANSLATE_FAIL_BEHAVIORS:
        raise _field_error(
            "display.on_translate_fail",
            "must be one of show_cn_with_reason, show_cn, show_reason",
        )
    next_display["on_translate_fail"] = on_translate_fail

    selected_provider = _read_tts_provider(tts_payload, runtime_config.tts.provider)
    next_tts["provider"] = selected_provider
    next_provider_raw: dict[str, Any] | None = None
    provider_path = ""
    provider_resolved_path = ""
    previous_provider_raw: dict[str, Any] | None = None

    if selected_provider == "doubao":
        provider_path, provider_resolved_path = _provider_config_paths(
            "doubao",
            _read_section(listener_raw, "tts"),
            config_dir,
        )
        previous_provider_raw = _load_optional_json(
            provider_resolved_path,
            _default_doubao_provider_payload(),
        )
        provider_payloads = _read_section(tts_payload, "providers")
        next_provider_raw = _build_next_doubao_provider_payload(
            base_payload=previous_provider_raw,
            payload=_read_section(provider_payloads, "doubao"),
            secret_updates=_read_section(tts_secret_updates, "doubao"),
        )
        try:
            load_doubao_tts_settings_from_payload(next_provider_raw)
        except RuntimeError as exc:
            raise _wrap_provider_validation_error("doubao", exc) from exc
        next_tts["config_path"] = provider_path
    elif selected_provider == "tencent_cloud":
        provider_path, provider_resolved_path = _provider_config_paths(
            "tencent_cloud",
            _read_section(listener_raw, "tts"),
            config_dir,
        )
        previous_provider_raw = _load_optional_json(
            provider_resolved_path,
            _default_tencent_provider_payload(),
        )
        provider_payloads = _read_section(tts_payload, "providers")
        next_provider_raw = _build_next_tencent_provider_payload(
            base_payload=previous_provider_raw,
            payload=_read_section(provider_payloads, "tencent_cloud"),
            secret_updates=_read_section(tts_secret_updates, "tencent_cloud"),
        )
        try:
            load_tencent_cloud_tts_settings_from_payload(next_provider_raw)
        except RuntimeError as exc:
            raise _wrap_provider_validation_error("tencent_cloud", exc) from exc
        next_tts["config_path"] = provider_path
    else:
        next_tts.pop("config_path", None)

    next_listener["translate"] = next_translate
    next_listener["display"] = next_display
    next_listener["tts"] = next_tts
    _persist_config_files(
        listener_path=listener_path,
        listener_payload=next_listener,
        provider_path=provider_resolved_path,
        provider_payload=next_provider_raw,
        previous_provider_payload=previous_provider_raw,
    )
    return build_config_snapshot(listener_path)


def _build_runtime_meta(config_path: str) -> dict[str, Any]:
    return {
        "config_path": config_path,
        "apply_strategy": CONFIG_APPLY_STRATEGY,
        "restart_required": True,
        "hot_reload_supported": False,
    }


def _build_doubao_provider_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    payload = _default_doubao_provider_payload()
    payload.update(raw)
    return {
        "endpoint": str(payload.get("endpoint") or DOUBAO_TTS_DEFAULT_ENDPOINT),
        "resource_id": str(payload.get("resource_id") or ""),
        "speaker": str(payload.get("speaker") or ""),
        "audio_format": str(payload.get("audio_format") or "wav"),
        "sample_rate": int(payload.get("sample_rate") or DOUBAO_TTS_DEFAULT_SAMPLE_RATE),
        "speech_rate": int(payload.get("speech_rate") or DOUBAO_TTS_DEFAULT_SPEECH_RATE),
        "loudness_rate": int(payload.get("loudness_rate") or DOUBAO_TTS_DEFAULT_LOUDNESS_RATE),
        "use_cache": bool(payload.get("use_cache", False)),
        "uid": str(payload.get("uid") or "wechat-pc-auto"),
        "connect_timeout_seconds": float(payload.get("connect_timeout_seconds") or 10.0),
        "appid": _build_secret_status(
            payload,
            "appid",
            "appid_env",
            default_env_key=DOUBAO_TTS_DEFAULT_APPID_ENV_KEY,
        ),
        "access_token": _build_secret_status(
            payload,
            "access_token",
            "access_token_env",
            default_env_key=DOUBAO_TTS_DEFAULT_ACCESS_TOKEN_ENV_KEY,
        ),
    }


def _build_tencent_provider_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    payload = _default_tencent_provider_payload()
    payload.update(raw)
    return {
        "endpoint": str(payload.get("endpoint") or TENCENT_CLOUD_TTS_DEFAULT_ENDPOINT),
        "region": str(payload.get("region") or ""),
        "voice_type": int(payload.get("voice_type") or 0),
        "codec": str(payload.get("codec") or "wav"),
        "sample_rate": int(payload.get("sample_rate") or TENCENT_CLOUD_TTS_DEFAULT_SAMPLE_RATE),
        "speed": float(payload.get("speed") or TENCENT_CLOUD_TTS_DEFAULT_SPEED),
        "volume": float(payload.get("volume") or TENCENT_CLOUD_TTS_DEFAULT_VOLUME),
        "primary_language": int(
            payload.get("primary_language") or TENCENT_CLOUD_TTS_DEFAULT_PRIMARY_LANGUAGE
        ),
        "model_type": int(payload.get("model_type") or TENCENT_CLOUD_TTS_DEFAULT_MODEL_TYPE),
        "project_id": int(payload.get("project_id") or TENCENT_CLOUD_TTS_DEFAULT_PROJECT_ID),
        "segment_rate": int(payload.get("segment_rate") or TENCENT_CLOUD_TTS_DEFAULT_SEGMENT_RATE),
        "enable_subtitle": bool(payload.get("enable_subtitle", False)),
        "emotion_category": str(payload.get("emotion_category") or ""),
        "emotion_intensity": int(payload.get("emotion_intensity") or 100),
        "request_timeout_seconds": float(payload.get("request_timeout_seconds") or 15.0),
        "secret_id": _build_secret_status(
            payload,
            "secret_id",
            "secret_id_env",
            default_env_key=TENCENT_CLOUD_TTS_DEFAULT_SECRET_ID_ENV_KEY,
        ),
        "secret_key": _build_secret_status(
            payload,
            "secret_key",
            "secret_key_env",
            default_env_key=TENCENT_CLOUD_TTS_DEFAULT_SECRET_KEY_ENV_KEY,
        ),
    }


def _build_next_doubao_provider_payload(
    *,
    base_payload: dict[str, Any],
    payload: dict[str, Any],
    secret_updates: dict[str, Any],
) -> dict[str, Any]:
    next_payload = copy.deepcopy(base_payload)
    next_payload["provider"] = "doubao"
    next_payload["endpoint"] = _read_string(
        payload,
        "endpoint",
        str(next_payload.get("endpoint") or DOUBAO_TTS_DEFAULT_ENDPOINT),
        field_path="tts.providers.doubao.endpoint",
    )
    next_payload["resource_id"] = _read_string(
        payload,
        "resource_id",
        str(next_payload.get("resource_id") or ""),
        field_path="tts.providers.doubao.resource_id",
    )
    next_payload["speaker"] = _read_string(
        payload,
        "speaker",
        str(next_payload.get("speaker") or ""),
        field_path="tts.providers.doubao.speaker",
    )
    next_payload["audio_format"] = _read_string(
        payload,
        "audio_format",
        str(next_payload.get("audio_format") or "wav"),
        field_path="tts.providers.doubao.audio_format",
    )
    next_payload["sample_rate"] = _read_int(
        payload,
        "sample_rate",
        int(next_payload.get("sample_rate") or DOUBAO_TTS_DEFAULT_SAMPLE_RATE),
        field_path="tts.providers.doubao.sample_rate",
    )
    next_payload["speech_rate"] = _read_int(
        payload,
        "speech_rate",
        int(next_payload.get("speech_rate") or DOUBAO_TTS_DEFAULT_SPEECH_RATE),
        field_path="tts.providers.doubao.speech_rate",
    )
    next_payload["loudness_rate"] = _read_int(
        payload,
        "loudness_rate",
        int(next_payload.get("loudness_rate") or DOUBAO_TTS_DEFAULT_LOUDNESS_RATE),
        field_path="tts.providers.doubao.loudness_rate",
    )
    next_payload["use_cache"] = _read_bool(
        payload,
        "use_cache",
        bool(next_payload.get("use_cache", False)),
        field_path="tts.providers.doubao.use_cache",
    )
    next_payload["uid"] = _read_string(
        payload,
        "uid",
        str(next_payload.get("uid") or "wechat-pc-auto"),
        field_path="tts.providers.doubao.uid",
    )
    next_payload["connect_timeout_seconds"] = _read_float(
        payload,
        "connect_timeout_seconds",
        float(next_payload.get("connect_timeout_seconds") or 10.0),
        field_path="tts.providers.doubao.connect_timeout_seconds",
    )
    _apply_secret_update(
        next_payload,
        key="appid",
        env_key_field="appid_env",
        update=secret_updates.get("appid"),
        field_path="tts.providers.doubao.appid",
        default_env_key=DOUBAO_TTS_DEFAULT_APPID_ENV_KEY,
    )
    _apply_secret_update(
        next_payload,
        key="access_token",
        env_key_field="access_token_env",
        update=secret_updates.get("access_token"),
        field_path="tts.providers.doubao.access_token",
        default_env_key=DOUBAO_TTS_DEFAULT_ACCESS_TOKEN_ENV_KEY,
    )
    return next_payload


def _build_next_tencent_provider_payload(
    *,
    base_payload: dict[str, Any],
    payload: dict[str, Any],
    secret_updates: dict[str, Any],
) -> dict[str, Any]:
    next_payload = copy.deepcopy(base_payload)
    next_payload["provider"] = "tencent_cloud"
    next_payload["endpoint"] = _read_string(
        payload,
        "endpoint",
        str(next_payload.get("endpoint") or TENCENT_CLOUD_TTS_DEFAULT_ENDPOINT),
        field_path="tts.providers.tencent_cloud.endpoint",
    )
    next_payload["region"] = _read_string(
        payload,
        "region",
        str(next_payload.get("region") or ""),
        field_path="tts.providers.tencent_cloud.region",
    )
    next_payload["voice_type"] = _read_int(
        payload,
        "voice_type",
        int(next_payload.get("voice_type") or 0),
        field_path="tts.providers.tencent_cloud.voice_type",
    )
    next_payload["codec"] = _read_string(
        payload,
        "codec",
        str(next_payload.get("codec") or "wav"),
        field_path="tts.providers.tencent_cloud.codec",
    )
    next_payload["sample_rate"] = _read_int(
        payload,
        "sample_rate",
        int(next_payload.get("sample_rate") or TENCENT_CLOUD_TTS_DEFAULT_SAMPLE_RATE),
        field_path="tts.providers.tencent_cloud.sample_rate",
    )
    next_payload["speed"] = _read_float(
        payload,
        "speed",
        float(next_payload.get("speed") or TENCENT_CLOUD_TTS_DEFAULT_SPEED),
        field_path="tts.providers.tencent_cloud.speed",
    )
    next_payload["volume"] = _read_float(
        payload,
        "volume",
        float(next_payload.get("volume") or TENCENT_CLOUD_TTS_DEFAULT_VOLUME),
        field_path="tts.providers.tencent_cloud.volume",
    )
    next_payload["primary_language"] = _read_int(
        payload,
        "primary_language",
        int(next_payload.get("primary_language") or TENCENT_CLOUD_TTS_DEFAULT_PRIMARY_LANGUAGE),
        field_path="tts.providers.tencent_cloud.primary_language",
    )
    next_payload["model_type"] = _read_int(
        payload,
        "model_type",
        int(next_payload.get("model_type") or TENCENT_CLOUD_TTS_DEFAULT_MODEL_TYPE),
        field_path="tts.providers.tencent_cloud.model_type",
    )
    next_payload["project_id"] = _read_int(
        payload,
        "project_id",
        int(next_payload.get("project_id") or TENCENT_CLOUD_TTS_DEFAULT_PROJECT_ID),
        field_path="tts.providers.tencent_cloud.project_id",
    )
    next_payload["segment_rate"] = _read_int(
        payload,
        "segment_rate",
        int(next_payload.get("segment_rate") or TENCENT_CLOUD_TTS_DEFAULT_SEGMENT_RATE),
        field_path="tts.providers.tencent_cloud.segment_rate",
    )
    next_payload["enable_subtitle"] = _read_bool(
        payload,
        "enable_subtitle",
        bool(next_payload.get("enable_subtitle", False)),
        field_path="tts.providers.tencent_cloud.enable_subtitle",
    )
    next_payload["emotion_category"] = _read_string(
        payload,
        "emotion_category",
        str(next_payload.get("emotion_category") or ""),
        field_path="tts.providers.tencent_cloud.emotion_category",
    )
    next_payload["emotion_intensity"] = _read_int(
        payload,
        "emotion_intensity",
        int(next_payload.get("emotion_intensity") or 100),
        field_path="tts.providers.tencent_cloud.emotion_intensity",
    )
    next_payload["request_timeout_seconds"] = _read_float(
        payload,
        "request_timeout_seconds",
        float(next_payload.get("request_timeout_seconds") or 15.0),
        field_path="tts.providers.tencent_cloud.request_timeout_seconds",
    )
    _apply_secret_update(
        next_payload,
        key="secret_id",
        env_key_field="secret_id_env",
        update=secret_updates.get("secret_id"),
        field_path="tts.providers.tencent_cloud.secret_id",
        default_env_key=TENCENT_CLOUD_TTS_DEFAULT_SECRET_ID_ENV_KEY,
    )
    _apply_secret_update(
        next_payload,
        key="secret_key",
        env_key_field="secret_key_env",
        update=secret_updates.get("secret_key"),
        field_path="tts.providers.tencent_cloud.secret_key",
        default_env_key=TENCENT_CLOUD_TTS_DEFAULT_SECRET_KEY_ENV_KEY,
    )
    return next_payload


def _persist_config_files(
    *,
    listener_path: str,
    listener_payload: dict[str, Any],
    provider_path: str,
    provider_payload: dict[str, Any] | None,
    previous_provider_payload: dict[str, Any] | None,
) -> None:
    if provider_payload is None or not provider_path:
        save_json_config_atomic(listener_path, listener_payload)
        return

    save_json_config_atomic(provider_path, provider_payload)
    try:
        save_json_config_atomic(listener_path, listener_payload)
    except Exception:
        if previous_provider_payload is not None:
            save_json_config_atomic(provider_path, previous_provider_payload)
        raise


def _build_secret_status(
    raw: dict[str, Any],
    key: str,
    env_key_field: str,
    *,
    default_env_key: str = "",
) -> dict[str, Any]:
    direct_value = str(raw.get(key) or "").strip()
    env_name = _resolve_secret_env_name(raw, env_key_field, default_env_key=default_env_key)
    env_value = str(os.getenv(env_name, "")).strip() if env_name else ""
    if direct_value:
        payload: dict[str, Any] = {"configured": True, "source": "direct"}
    elif env_name:
        payload = {"configured": bool(env_value), "source": "env"}
    else:
        payload = {"configured": False, "source": "unset"}
    if env_name:
        payload["env_key"] = env_name
    return payload


def _apply_secret_update(
    raw: dict[str, Any],
    *,
    key: str,
    env_key_field: str,
    update: Any,
    field_path: str,
    default_env_key: str = "",
    allow_custom_env_key: bool = True,
) -> None:
    if update is None:
        return
    if not isinstance(update, dict):
        raise _field_error(field_path, "must be object")
    mode = str(update.get("mode") or "").strip().lower()
    if mode not in {"keep", "direct", "env", "clear"}:
        raise _field_error(field_path, "mode must be keep, direct, env, or clear")
    if mode == "keep":
        return
    if mode == "clear":
        raw[key] = ""
        if env_key_field:
            raw[env_key_field] = ""
        return
    if mode == "direct":
        value = str(update.get("value") or "").strip()
        if not value:
            raise _field_error(field_path, "direct value is required")
        raw[key] = value
        if env_key_field:
            raw[env_key_field] = ""
        return

    env_key = str(update.get("env_key") or default_env_key).strip()
    if not env_key:
        raise _field_error(field_path, "env_key is required")
    if not allow_custom_env_key and env_key != default_env_key:
        raise _field_error(field_path, f"env_key must be {default_env_key}")
    raw[key] = ""
    if env_key_field:
        raw[env_key_field] = env_key


def _resolve_effective_secret_value(
    raw: dict[str, Any],
    key: str,
    env_key_field: str,
    *,
    default_env_key: str = "",
) -> str:
    direct_value = str(raw.get(key) or "").strip()
    if direct_value:
        return direct_value
    env_name = _resolve_secret_env_name(raw, env_key_field, default_env_key=default_env_key)
    if env_name:
        return str(os.getenv(env_name, "")).strip()
    return ""


def _resolve_secret_env_name(
    raw: dict[str, Any],
    env_key_field: str,
    *,
    default_env_key: str = "",
) -> str:
    if env_key_field:
        return str(raw.get(env_key_field) or "").strip()
    return str(default_env_key or "").strip()


def _provider_config_paths(
    provider: str,
    tts_cfg: dict[str, Any],
    config_dir: str,
) -> tuple[str, str]:
    current_provider = str(tts_cfg.get("provider") or DEFAULT_TTS_PROVIDER).strip().lower()
    if provider == "doubao":
        config_path = (
            str(tts_cfg.get("config_path") or DOUBAO_TTS_DEFAULT_CONFIG_PATH).strip()
            if current_provider == "doubao"
            else DOUBAO_TTS_DEFAULT_CONFIG_PATH
        )
    elif provider == "tencent_cloud":
        config_path = (
            str(tts_cfg.get("config_path") or TENCENT_CLOUD_TTS_DEFAULT_CONFIG_PATH).strip()
            if current_provider == "tencent_cloud"
            else TENCENT_CLOUD_TTS_DEFAULT_CONFIG_PATH
        )
    else:
        return "", ""
    resolved_path = resolve_config_file_path(config_path, base_dir=config_dir)
    return config_path, resolved_path


def _load_optional_json(path: str, defaults: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(defaults)
    if path and os.path.isfile(path):
        payload.update(load_json_config(path))
    return payload


def _default_doubao_provider_payload() -> dict[str, Any]:
    return {
        "provider": "doubao",
        "endpoint": DOUBAO_TTS_DEFAULT_ENDPOINT,
        "appid": "",
        "appid_env": DOUBAO_TTS_DEFAULT_APPID_ENV_KEY,
        "access_token": "",
        "access_token_env": DOUBAO_TTS_DEFAULT_ACCESS_TOKEN_ENV_KEY,
        "resource_id": "",
        "speaker": "",
        "audio_format": "wav",
        "sample_rate": DOUBAO_TTS_DEFAULT_SAMPLE_RATE,
        "speech_rate": DOUBAO_TTS_DEFAULT_SPEECH_RATE,
        "loudness_rate": DOUBAO_TTS_DEFAULT_LOUDNESS_RATE,
        "use_cache": False,
        "uid": "wechat-pc-auto",
        "connect_timeout_seconds": 10.0,
    }


def _default_tencent_provider_payload() -> dict[str, Any]:
    return {
        "provider": "tencent_cloud",
        "secret_id": "",
        "secret_id_env": TENCENT_CLOUD_TTS_DEFAULT_SECRET_ID_ENV_KEY,
        "secret_key": "",
        "secret_key_env": TENCENT_CLOUD_TTS_DEFAULT_SECRET_KEY_ENV_KEY,
        "endpoint": TENCENT_CLOUD_TTS_DEFAULT_ENDPOINT,
        "region": "",
        "voice_type": 0,
        "codec": "wav",
        "sample_rate": TENCENT_CLOUD_TTS_DEFAULT_SAMPLE_RATE,
        "speed": TENCENT_CLOUD_TTS_DEFAULT_SPEED,
        "volume": TENCENT_CLOUD_TTS_DEFAULT_VOLUME,
        "primary_language": TENCENT_CLOUD_TTS_DEFAULT_PRIMARY_LANGUAGE,
        "model_type": TENCENT_CLOUD_TTS_DEFAULT_MODEL_TYPE,
        "project_id": TENCENT_CLOUD_TTS_DEFAULT_PROJECT_ID,
        "segment_rate": TENCENT_CLOUD_TTS_DEFAULT_SEGMENT_RATE,
        "enable_subtitle": False,
        "emotion_category": "",
        "emotion_intensity": 100,
        "request_timeout_seconds": 15.0,
    }


def _read_section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _read_bool(payload: dict[str, Any], key: str, current: bool, *, field_path: str) -> bool:
    if key not in payload:
        return bool(current)
    value = payload.get(key)
    if not isinstance(value, bool):
        raise _field_error(field_path, "must be boolean")
    return value


def _read_string(payload: dict[str, Any], key: str, current: str, *, field_path: str) -> str:
    if key not in payload:
        return str(current or "")
    value = payload.get(key)
    if not isinstance(value, str):
        raise _field_error(field_path, "must be string")
    return value


def _read_float(payload: dict[str, Any], key: str, current: float, *, field_path: str) -> float:
    if key not in payload:
        return float(current)
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _field_error(field_path, "must be number")
    return float(value)


def _read_int(payload: dict[str, Any], key: str, current: int, *, field_path: str) -> int:
    if key not in payload:
        return int(current)
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _field_error(field_path, "must be integer")
    return value


def _read_translate_provider(payload: dict[str, Any], current: str) -> str:
    value = current if "provider" not in payload else payload.get("provider")
    try:
        return normalize_translate_provider(value)
    except RuntimeError as exc:
        raise _field_error("translate.provider", str(exc)) from exc


def _read_tts_provider(payload: dict[str, Any], current: str) -> str:
    value = current if "provider" not in payload else payload.get("provider")
    try:
        return normalize_tts_provider(value)
    except RuntimeError as exc:
        raise _field_error("tts.provider", str(exc)) from exc


def _field_error(field_path: str, message: str) -> ConfigValidationError:
    return ConfigValidationError("config validation failed", field_errors={field_path: message})


def _wrap_translate_validation_error(exc: RuntimeError) -> ConfigValidationError:
    message = str(exc)
    if "DEEPLX_URL" in message or "deeplx_url" in message or "deeplx_url_env" in message:
        return _field_error("translate.deeplx_url", message)
    return _field_error("translate", message)


def _wrap_provider_validation_error(provider: str, exc: RuntimeError) -> ConfigValidationError:
    message = str(exc)
    if message.startswith(f"{provider}."):
        field_name = message.split(" must", 1)[0].split(".", 1)[1]
        return _field_error(f"tts.providers.{provider}.{field_name}", message)
    mapping = {
        "doubao appid/appid_env is required": "tts.providers.doubao.appid",
        "doubao access_token/access_token_env is required": "tts.providers.doubao.access_token",
        "doubao resource_id is required": "tts.providers.doubao.resource_id",
        "doubao speaker is required": "tts.providers.doubao.speaker",
        "doubao endpoint is required": "tts.providers.doubao.endpoint",
        "doubao audio_format must be 'wav' for current Windows playback path, got": "tts.providers.doubao.audio_format",
        "tencent_cloud secret_id/secret_id_env is required": "tts.providers.tencent_cloud.secret_id",
        "tencent_cloud secret_key/secret_key_env is required": "tts.providers.tencent_cloud.secret_key",
        "tencent_cloud endpoint is required": "tts.providers.tencent_cloud.endpoint",
        "tencent_cloud codec must be 'wav' for current Windows playback path, got": "tts.providers.tencent_cloud.codec",
    }
    for prefix, field_path in mapping.items():
        if message.startswith(prefix):
            return _field_error(field_path, message)
    return _field_error(f"tts.providers.{provider}", message)
