import asyncio
import base64
import importlib
import json
import math
import os
import queue
import struct
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

if __package__:
    from .sidebar_shared import (
        ROOT_DIR,
        as_bool,
        is_speakable_english_text,
        load_json_config,
        normalize_tts_text,
        read_config_float,
        read_config_int,
        summarize_tts_text,
        validate_float_range,
        validate_int_choices,
        validate_int_min,
        validate_int_range,
        validate_positive_float,
    )
else:
    from sidebar_shared import (
        ROOT_DIR,
        as_bool,
        is_speakable_english_text,
        load_json_config,
        normalize_tts_text,
        read_config_float,
        read_config_int,
        summarize_tts_text,
        validate_float_range,
        validate_int_choices,
        validate_int_min,
        validate_int_range,
        validate_positive_float,
    )

PREFERRED_ENGLISH_TTS_VOICES = ("Microsoft Zira Desktop", "Microsoft David Desktop")
SUPPORTED_TTS_PROVIDERS = ("windows_system", "doubao", "tencent_cloud")
DEFAULT_TTS_PROVIDER = "tencent_cloud"
DOUBAO_TTS_DEFAULT_CONFIG_PATH = os.path.join("config", "doubao_tts.json")
DOUBAO_TTS_DEFAULT_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/tts/unidirectional/stream"
DOUBAO_TTS_SUPPORTED_SAMPLE_RATES = (8000, 16000, 22050, 24000, 32000, 44100, 48000)
DOUBAO_TTS_DEFAULT_SAMPLE_RATE = 32000
DOUBAO_TTS_DEFAULT_SPEECH_RATE = -15
DOUBAO_TTS_DEFAULT_LOUDNESS_RATE = 0
TENCENT_CLOUD_TTS_DEFAULT_CONFIG_PATH = os.path.join("config", "tencent_tts.json")
TENCENT_CLOUD_TTS_DEFAULT_ENDPOINT = "tts.tencentcloudapi.com"
TENCENT_CLOUD_TTS_SUPPORTED_SAMPLE_RATES = (8000, 16000, 24000)
TENCENT_CLOUD_TTS_SUPPORTED_PRIMARY_LANGUAGES = (1, 2)
TENCENT_CLOUD_TTS_SUPPORTED_SEGMENT_RATES = (0, 1, 2)
TENCENT_CLOUD_TTS_DEFAULT_SAMPLE_RATE = 16000
TENCENT_CLOUD_TTS_DEFAULT_SPEED = 0.0
TENCENT_CLOUD_TTS_DEFAULT_VOLUME = 0.0
TENCENT_CLOUD_TTS_DEFAULT_MODEL_TYPE = 1
TENCENT_CLOUD_TTS_DEFAULT_PROJECT_ID = 0
TENCENT_CLOUD_TTS_DEFAULT_PRIMARY_LANGUAGE = 2
TENCENT_CLOUD_TTS_DEFAULT_SEGMENT_RATE = 0
DOUBAO_HEADER_FIXED = bytes([0x11, 0x10, 0x10, 0x00])
DOUBAO_MSG_TYPE_FULL_SERVER_RESPONSE = 0x9
DOUBAO_MSG_TYPE_AUDIO_ONLY_SERVER = 0xB
DOUBAO_MSG_TYPE_ERROR = 0xF
DOUBAO_FLAG_POSITIVE_SEQ = 0x1
DOUBAO_FLAG_NEGATIVE_SEQ = 0x3
DOUBAO_FLAG_WITH_EVENT = 0x4
DOUBAO_EVENT_CONNECTION_STARTED = 50
DOUBAO_EVENT_CONNECTION_FAILED = 51
DOUBAO_EVENT_CONNECTION_FINISHED = 52
DOUBAO_EVENT_SESSION_FINISHED = 152
DOUBAO_EVENT_SESSION_FAILED = 153


def resolve_config_file_path(path: Any, *, base_dir: str = ROOT_DIR) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    candidates: list[str] = []
    if base_dir:
        candidates.append(os.path.join(base_dir, raw))
    candidates.append(os.path.join(ROOT_DIR, raw))
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.exists(normalized):
            return normalized
    return os.path.normpath(candidates[0])


def read_secret_config_value(cfg: dict[str, Any], key: str, env_key: str) -> str:
    value = str(cfg.get(key) or "").strip()
    if value:
        return value
    env_name = str(cfg.get(env_key) or "").strip()
    if env_name:
        return str(os.getenv(env_name, "")).strip()
    return ""


def normalize_tts_provider(value: Any) -> str:
    provider = str(value or DEFAULT_TTS_PROVIDER).strip().lower()
    provider = provider or DEFAULT_TTS_PROVIDER
    if provider not in SUPPORTED_TTS_PROVIDERS:
        raise RuntimeError(
            f"tts.provider must be one of {', '.join(SUPPORTED_TTS_PROVIDERS)}, got {value!r}"
        )
    return provider


def pick_preferred_tts_voice(voices: list[dict[str, str]]) -> str:
    if not voices:
        return ""
    names: dict[str, str] = {}
    for voice in voices:
        name = str(voice.get("name") or "").strip()
        if name:
            names[name.lower()] = name

    for preferred in PREFERRED_ENGLISH_TTS_VOICES:
        chosen = names.get(preferred.lower())
        if chosen:
            return chosen

    for voice in voices:
        name = str(voice.get("name") or "").strip()
        culture = str(voice.get("culture") or "").lower()
        if name and culture.startswith("en"):
            return name
    return ""


def list_windows_tts_voices() -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    command = (
        "$ErrorActionPreference='Stop';"
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$voices=$s.GetInstalledVoices() | ForEach-Object {"
        "  $info=$_.VoiceInfo;"
        "  [PSCustomObject]@{name=$info.Name; culture=$info.Culture.Name; gender=$info.Gender.ToString()}"
        "};"
        "$voices | ConvertTo-Json -Compress"
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    voices: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            voices.append(
                {
                    "name": str(item.get("name") or "").strip(),
                    "culture": str(item.get("culture") or "").strip(),
                    "gender": str(item.get("gender") or "").strip(),
                }
            )
    return voices

def probe_python_module(module_name: str, *, required_attr: str = "") -> str:
    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        return f"missing Python module '{module_name}': {e}"
    if required_attr:
        attr = getattr(module, required_attr, None)
        if not callable(attr):
            return f"Python module '{module_name}' missing callable '{required_attr}'"
    return ""


def probe_doubao_websocket_runtime() -> str:
    return probe_python_module("websockets", required_attr="connect")


def probe_tencent_cloud_tts_runtime() -> str:
    checks = (
        ("tencentcloud.common.credential", "Credential"),
        ("tencentcloud.common.profile.client_profile", "ClientProfile"),
        ("tencentcloud.common.profile.http_profile", "HttpProfile"),
        (
            "tencentcloud.common.exception.tencent_cloud_sdk_exception",
            "TencentCloudSDKException",
        ),
        ("tencentcloud.tts.v20190823.tts_client", "TtsClient"),
        ("tencentcloud.tts.v20190823.models", "TextToVoiceRequest"),
    )
    for module_name, attr_name in checks:
        error_text = probe_python_module(module_name, required_attr=attr_name)
        if error_text:
            return error_text
    return ""


def play_wav_bytes_on_windows(audio_data: bytes) -> bool:
    import winsound

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            temp_path = f.name
            f.write(audio_data)
        winsound.PlaySound(temp_path, winsound.SND_FILENAME)
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
    return True


class WindowsSystemTTS:
    def __init__(self, voice_name: str = ""):
        self.voice_name = str(voice_name or "").strip()
        self._lock = threading.Lock()
        self._voice_probe_done = bool(self.voice_name)
        self._queue: "queue.SimpleQueue[str | None]" = queue.SimpleQueue()
        self._worker_started = False
        self._last_error = ""
        self._logger: Callable[[str], None] | None = None

    @classmethod
    def create_default(cls) -> "WindowsSystemTTS | None":
        if os.name != "nt":
            return None
        return cls()

    def _resolve_voice_name(self) -> str:
        with self._lock:
            if self._voice_probe_done:
                return self.voice_name
            self.voice_name = pick_preferred_tts_voice(list_windows_tts_voices())
            self._voice_probe_done = True
            if not self.voice_name:
                self._last_error = "no english system voice detected"
                self._emit_log("tts failed backend=windows_system reason=no english system voice detected")
            return self.voice_name

    def set_logger(self, logger: Callable[[str], None] | None):
        with self._lock:
            self._logger = logger

    def _emit_log(self, line: str):
        logger = self._logger
        if not logger:
            return
        try:
            logger(str(line or ""))
        except Exception:
            pass

    def _run_speak_blocking(self, payload: str) -> bool:
        voice_name = self._resolve_voice_name()
        if not voice_name:
            return False
        preview = summarize_tts_text(payload)
        self._emit_log(
            f"tts synthesize start backend=windows_system voice={voice_name} chars={len(payload)} preview={preview}"
        )
        command = (
            "$ErrorActionPreference='Stop';"
            "Add-Type -AssemblyName System.Speech;"
            "$text=[Console]::In.ReadToEnd();"
            "if([string]::IsNullOrWhiteSpace($text)){exit 1};"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            "$s.SelectVoice($env:WX_SIDEBAR_TTS_VOICE);"
            "$s.Volume=100;"
            "$s.Rate=0;"
            "$s.Speak($text);"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = os.environ.copy()
        env["WX_SIDEBAR_TTS_VOICE"] = voice_name
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                input=payload,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=creationflags,
                check=False,
            )
        except Exception as e:
            self._last_error = str(e)
            self._emit_log(f"tts failed backend=windows_system error={self._last_error}")
            return False
        if result.returncode != 0:
            self._last_error = f"tts process exited code={result.returncode}"
            self._emit_log(f"tts failed backend=windows_system error={self._last_error}")
            return False
        self._last_error = ""
        self._emit_log(
            f"tts played backend=windows_system voice={voice_name} chars={len(payload)} preview={preview}"
        )
        return True

    def _ensure_worker_started(self):
        with self._lock:
            if self._worker_started:
                return
            self._worker_started = True
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def _worker_loop(self):
        while True:
            payload = self._queue.get()
            if payload is None:
                return
            self._run_speak_blocking(payload)

    def speak_async(self, text: str) -> bool:
        if os.name != "nt":
            self._emit_log("tts rejected backend=windows_system reason=non_windows")
            return False
        payload = normalize_tts_text(text)
        if not is_speakable_english_text(payload):
            self._emit_log(
                f"tts rejected backend=windows_system reason=non_speakable preview={summarize_tts_text(payload)}"
            )
            return False
        self._ensure_worker_started()
        self._queue.put(payload)
        self._emit_log(
            f"tts queued backend=windows_system chars={len(payload)} preview={summarize_tts_text(payload)}"
        )
        return True


@dataclass(frozen=True)
class DoubaoTTSSettings:
    endpoint: str
    appid: str
    access_token: str
    resource_id: str
    speaker: str
    audio_format: str = "wav"
    sample_rate: int = DOUBAO_TTS_DEFAULT_SAMPLE_RATE
    speech_rate: int = DOUBAO_TTS_DEFAULT_SPEECH_RATE
    loudness_rate: int = DOUBAO_TTS_DEFAULT_LOUDNESS_RATE
    use_cache: bool = False
    uid: str = "wechat-pc-auto"
    connect_timeout_seconds: float = 10.0


@dataclass(frozen=True)
class DoubaoWSMessage:
    msg_type: int
    flag: int
    event: int = 0
    error_code: int = 0
    payload: bytes = b""


@dataclass(frozen=True)
class TencentCloudTTSSettings:
    secret_id: str
    secret_key: str
    voice_type: int
    endpoint: str = TENCENT_CLOUD_TTS_DEFAULT_ENDPOINT
    region: str = ""
    codec: str = "wav"
    sample_rate: int = TENCENT_CLOUD_TTS_DEFAULT_SAMPLE_RATE
    speed: float = TENCENT_CLOUD_TTS_DEFAULT_SPEED
    volume: float = TENCENT_CLOUD_TTS_DEFAULT_VOLUME
    primary_language: int = TENCENT_CLOUD_TTS_DEFAULT_PRIMARY_LANGUAGE
    model_type: int = TENCENT_CLOUD_TTS_DEFAULT_MODEL_TYPE
    project_id: int = TENCENT_CLOUD_TTS_DEFAULT_PROJECT_ID
    segment_rate: int = TENCENT_CLOUD_TTS_DEFAULT_SEGMENT_RATE
    enable_subtitle: bool = False
    emotion_category: str = ""
    emotion_intensity: int = 100
    request_timeout_seconds: float = 15.0


def load_doubao_tts_settings(config_path: str, *, base_dir: str = ROOT_DIR) -> DoubaoTTSSettings:
    resolved_path = resolve_config_file_path(config_path, base_dir=base_dir)
    if not resolved_path or not os.path.isfile(resolved_path):
        raise RuntimeError(f"tts config not found: {config_path!r}")
    raw = load_json_config(resolved_path)
    provider = str(raw.get("provider") or "doubao").strip().lower()
    if provider and provider != "doubao":
        raise RuntimeError(f"doubao config provider must be 'doubao', got {provider!r}")

    endpoint = str(raw.get("endpoint") or DOUBAO_TTS_DEFAULT_ENDPOINT).strip()
    appid = read_secret_config_value(raw, "appid", "appid_env")
    access_token = read_secret_config_value(raw, "access_token", "access_token_env")
    resource_id = str(raw.get("resource_id") or "").strip()
    speaker = str(raw.get("speaker") or "").strip()
    audio_format = str(raw.get("audio_format") or "wav").strip().lower()
    sample_rate = read_config_int(raw, "sample_rate", DOUBAO_TTS_DEFAULT_SAMPLE_RATE)
    speech_rate = read_config_int(raw, "speech_rate", DOUBAO_TTS_DEFAULT_SPEECH_RATE)
    loudness_rate = read_config_int(raw, "loudness_rate", DOUBAO_TTS_DEFAULT_LOUDNESS_RATE)
    use_cache = as_bool(raw.get("use_cache"), False)
    uid = str(raw.get("uid") or "wechat-pc-auto").strip() or "wechat-pc-auto"
    connect_timeout_seconds = read_config_float(raw, "connect_timeout_seconds", 10.0)

    if not endpoint:
        raise RuntimeError("doubao endpoint is required")
    if not appid:
        raise RuntimeError("doubao appid/appid_env is required")
    if not access_token:
        raise RuntimeError("doubao access_token/access_token_env is required")
    if not resource_id:
        raise RuntimeError("doubao resource_id is required")
    if not speaker:
        raise RuntimeError("doubao speaker is required")
    if audio_format != "wav":
        raise RuntimeError(
            f"doubao audio_format must be 'wav' for current Windows playback path, got {audio_format!r}"
        )
    sample_rate = validate_int_choices(
        "doubao.sample_rate", sample_rate, DOUBAO_TTS_SUPPORTED_SAMPLE_RATES
    )
    speech_rate = validate_int_range("doubao.speech_rate", speech_rate, -50, 100)
    loudness_rate = validate_int_range("doubao.loudness_rate", loudness_rate, -50, 100)
    connect_timeout_seconds = validate_positive_float(
        "doubao.connect_timeout_seconds",
        connect_timeout_seconds,
    )
    return DoubaoTTSSettings(
        endpoint=endpoint,
        appid=appid,
        access_token=access_token,
        resource_id=resource_id,
        speaker=speaker,
        audio_format=audio_format,
        sample_rate=sample_rate,
        speech_rate=speech_rate,
        loudness_rate=loudness_rate,
        use_cache=use_cache,
        uid=uid,
        connect_timeout_seconds=connect_timeout_seconds,
    )


def load_tencent_cloud_tts_settings(
    config_path: str,
    *,
    base_dir: str = ROOT_DIR,
) -> TencentCloudTTSSettings:
    resolved_path = resolve_config_file_path(config_path, base_dir=base_dir)
    if not resolved_path or not os.path.isfile(resolved_path):
        raise RuntimeError(f"tts config not found: {config_path!r}")
    raw = load_json_config(resolved_path)
    provider = str(raw.get("provider") or "tencent_cloud").strip().lower()
    if provider and provider != "tencent_cloud":
        raise RuntimeError(
            f"tencent_cloud config provider must be 'tencent_cloud', got {provider!r}"
        )

    endpoint = str(raw.get("endpoint") or TENCENT_CLOUD_TTS_DEFAULT_ENDPOINT).strip()
    region = str(raw.get("region") or "").strip()
    secret_id = read_secret_config_value(raw, "secret_id", "secret_id_env")
    secret_key = read_secret_config_value(raw, "secret_key", "secret_key_env")
    voice_type = read_config_int(raw, "voice_type", 0)
    codec = str(raw.get("codec") or "wav").strip().lower()
    sample_rate = read_config_int(raw, "sample_rate", TENCENT_CLOUD_TTS_DEFAULT_SAMPLE_RATE)
    speed = read_config_float(raw, "speed", TENCENT_CLOUD_TTS_DEFAULT_SPEED)
    volume = read_config_float(raw, "volume", TENCENT_CLOUD_TTS_DEFAULT_VOLUME)
    primary_language = read_config_int(
        raw,
        "primary_language",
        TENCENT_CLOUD_TTS_DEFAULT_PRIMARY_LANGUAGE,
    )
    model_type = read_config_int(raw, "model_type", TENCENT_CLOUD_TTS_DEFAULT_MODEL_TYPE)
    project_id = read_config_int(raw, "project_id", TENCENT_CLOUD_TTS_DEFAULT_PROJECT_ID)
    segment_rate = read_config_int(raw, "segment_rate", TENCENT_CLOUD_TTS_DEFAULT_SEGMENT_RATE)
    enable_subtitle = as_bool(raw.get("enable_subtitle"), False)
    emotion_category = str(raw.get("emotion_category") or "").strip()
    emotion_intensity = read_config_int(raw, "emotion_intensity", 100)
    request_timeout_seconds = read_config_float(raw, "request_timeout_seconds", 15.0)

    if not endpoint:
        raise RuntimeError("tencent_cloud endpoint is required")
    if not secret_id:
        raise RuntimeError("tencent_cloud secret_id/secret_id_env is required")
    if not secret_key:
        raise RuntimeError("tencent_cloud secret_key/secret_key_env is required")
    voice_type = validate_int_min("tencent_cloud.voice_type", voice_type, 1)
    if codec != "wav":
        raise RuntimeError(
            f"tencent_cloud codec must be 'wav' for current Windows playback path, got {codec!r}"
        )
    sample_rate = validate_int_choices(
        "tencent_cloud.sample_rate",
        sample_rate,
        TENCENT_CLOUD_TTS_SUPPORTED_SAMPLE_RATES,
    )
    speed = validate_float_range("tencent_cloud.speed", speed, -2.0, 6.0)
    volume = validate_float_range("tencent_cloud.volume", volume, -10.0, 10.0)
    primary_language = validate_int_choices(
        "tencent_cloud.primary_language",
        primary_language,
        TENCENT_CLOUD_TTS_SUPPORTED_PRIMARY_LANGUAGES,
    )
    model_type = validate_int_choices("tencent_cloud.model_type", model_type, (1,))
    project_id = validate_int_min("tencent_cloud.project_id", project_id, 0)
    segment_rate = validate_int_choices(
        "tencent_cloud.segment_rate",
        segment_rate,
        TENCENT_CLOUD_TTS_SUPPORTED_SEGMENT_RATES,
    )
    if emotion_category:
        emotion_intensity = validate_int_range(
            "tencent_cloud.emotion_intensity",
            emotion_intensity,
            50,
            200,
        )
    request_timeout_seconds = validate_positive_float(
        "tencent_cloud.request_timeout_seconds",
        request_timeout_seconds,
    )
    return TencentCloudTTSSettings(
        secret_id=secret_id,
        secret_key=secret_key,
        voice_type=voice_type,
        endpoint=endpoint,
        region=region,
        codec=codec,
        sample_rate=sample_rate,
        speed=speed,
        volume=volume,
        primary_language=primary_language,
        model_type=model_type,
        project_id=project_id,
        segment_rate=segment_rate,
        enable_subtitle=enable_subtitle,
        emotion_category=emotion_category,
        emotion_intensity=emotion_intensity,
        request_timeout_seconds=request_timeout_seconds,
    )


def build_doubao_ws_headers(settings: DoubaoTTSSettings, connect_id: str) -> dict[str, str]:
    return {
        "X-Api-App-Key": settings.appid,
        "X-Api-Access-Key": settings.access_token,
        "X-Api-Resource-Id": settings.resource_id,
        "X-Api-Connect-Id": connect_id,
    }


def build_doubao_tts_request_payload(settings: DoubaoTTSSettings, text: str) -> dict[str, Any]:
    req_params: dict[str, Any] = {
        "text": text,
        "speaker": settings.speaker,
        "audio_params": {
            "format": settings.audio_format,
            "sample_rate": settings.sample_rate,
            "speech_rate": settings.speech_rate,
            "loudness_rate": settings.loudness_rate,
        },
    }
    if settings.use_cache:
        req_params["additions"] = {
            "cache_config": {
                "text_type": 1,
                "use_cache": True,
            }
        }
    return {
        "user": {
            "uid": settings.uid,
        },
        "req_params": req_params,
    }


def build_doubao_tts_runtime_fields(settings: DoubaoTTSSettings, config_path: str) -> str:
    return (
        f"backend=doubao config={config_path} "
        f"resource_id={settings.resource_id} speaker={settings.speaker} format={settings.audio_format} "
        f"sample_rate={settings.sample_rate} speech_rate={settings.speech_rate} "
        f"loudness_rate={settings.loudness_rate} use_cache={settings.use_cache}"
    )


def build_tencent_cloud_tts_request_payload(
    settings: TencentCloudTTSSettings,
    text: str,
    session_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Text": text,
        "SessionId": session_id,
        "Volume": settings.volume,
        "Speed": settings.speed,
        "ProjectId": settings.project_id,
        "ModelType": settings.model_type,
        "VoiceType": settings.voice_type,
        "PrimaryLanguage": settings.primary_language,
        "SampleRate": settings.sample_rate,
        "Codec": settings.codec,
        "EnableSubtitle": settings.enable_subtitle,
        "SegmentRate": settings.segment_rate,
    }
    if settings.emotion_category:
        payload["EmotionCategory"] = settings.emotion_category
        payload["EmotionIntensity"] = settings.emotion_intensity
    return payload


def build_tencent_cloud_tts_runtime_fields(
    settings: TencentCloudTTSSettings,
    config_path: str,
) -> str:
    region = settings.region or "-"
    fields = (
        f"backend=tencent_cloud config={config_path} endpoint={settings.endpoint} "
        f"region={region} voice_type={settings.voice_type} format={settings.codec} "
        f"sample_rate={settings.sample_rate} speed={settings.speed} volume={settings.volume} "
        f"primary_language={settings.primary_language} segment_rate={settings.segment_rate} "
        f"subtitle={settings.enable_subtitle}"
    )
    if settings.emotion_category:
        fields += (
            f" emotion_category={settings.emotion_category}"
            f" emotion_intensity={settings.emotion_intensity}"
        )
    return fields


def format_tencent_cloud_sdk_exception(exc: Exception) -> str:
    code = str(getattr(exc, "code", "") or "").strip()
    message = str(getattr(exc, "message", "") or str(exc)).strip()
    request_id = str(getattr(exc, "requestId", "") or "").strip()
    parts = []
    if code:
        parts.append(f"code={code}")
    if message:
        parts.append(f"message={message}")
    if request_id:
        parts.append(f"request_id={request_id}")
    return " ".join(parts) if parts else str(exc)


def build_doubao_full_client_request_frame(payload: bytes) -> bytes:
    return DOUBAO_HEADER_FIXED + struct.pack(">I", len(payload)) + payload


def find_wav_data_chunk_offset(audio_data: bytes) -> int:
    offset = 12
    total = len(audio_data)
    while offset + 8 <= total:
        chunk_id = audio_data[offset : offset + 4]
        chunk_size = struct.unpack("<I", audio_data[offset + 4 : offset + 8])[0]
        if chunk_id == b"data":
            return offset
        if chunk_size == 0xFFFFFFFF:
            break
        next_offset = offset + 8 + chunk_size + (chunk_size & 1)
        if next_offset <= offset or next_offset > total:
            break
        offset = next_offset
    return audio_data.find(b"data", 12)


def normalize_wav_size_fields(audio_data: bytes) -> bytes:
    if len(audio_data) < 12 or audio_data[:4] != b"RIFF" or audio_data[8:12] != b"WAVE":
        return audio_data

    normalized = bytearray(audio_data)
    struct.pack_into("<I", normalized, 4, max(0, len(normalized) - 8))

    data_offset = find_wav_data_chunk_offset(audio_data)
    if data_offset < 0 or data_offset + 8 > len(normalized):
        return bytes(normalized)

    actual_data_size = max(0, len(normalized) - data_offset - 8)
    struct.pack_into("<I", normalized, data_offset + 4, actual_data_size)
    return bytes(normalized)


def parse_doubao_ws_message(data: bytes) -> DoubaoWSMessage:
    if len(data) < 8:
        raise RuntimeError(f"doubao ws message too short: {len(data)}")
    header_size = 4 * (data[0] & 0x0F)
    if header_size < 4 or len(data) < header_size + 4:
        raise RuntimeError(f"invalid doubao ws header size: {header_size}")

    msg_type = data[1] >> 4
    flag = data[1] & 0x0F
    pos = header_size
    event = 0
    error_code = 0

    if msg_type in (DOUBAO_MSG_TYPE_FULL_SERVER_RESPONSE, DOUBAO_MSG_TYPE_AUDIO_ONLY_SERVER):
        if flag in (DOUBAO_FLAG_POSITIVE_SEQ, DOUBAO_FLAG_NEGATIVE_SEQ):
            pos += 4
    elif msg_type == DOUBAO_MSG_TYPE_ERROR:
        error_code = struct.unpack(">I", data[pos : pos + 4])[0]
        pos += 4

    if flag == DOUBAO_FLAG_WITH_EVENT:
        event = struct.unpack(">i", data[pos : pos + 4])[0]
        pos += 4
        if event not in (
            DOUBAO_EVENT_CONNECTION_STARTED,
            DOUBAO_EVENT_CONNECTION_FAILED,
            DOUBAO_EVENT_CONNECTION_FINISHED,
        ):
            session_id_size = struct.unpack(">I", data[pos : pos + 4])[0]
            pos += 4 + session_id_size
        if event in (
            DOUBAO_EVENT_CONNECTION_STARTED,
            DOUBAO_EVENT_CONNECTION_FAILED,
            DOUBAO_EVENT_CONNECTION_FINISHED,
        ):
            connect_id_size = struct.unpack(">I", data[pos : pos + 4])[0]
            pos += 4 + connect_id_size

    payload_size = struct.unpack(">I", data[pos : pos + 4])[0]
    pos += 4
    payload = data[pos : pos + payload_size]
    return DoubaoWSMessage(
        msg_type=msg_type,
        flag=flag,
        event=event,
        error_code=error_code,
        payload=payload,
    )


class DoubaoWebsocketTTS:
    def __init__(self, settings: DoubaoTTSSettings):
        self.settings = settings
        self._lock = threading.Lock()
        self._queue: "queue.SimpleQueue[str | None]" = queue.SimpleQueue()
        self._worker_started = False
        self._last_error = ""
        self._logger: Callable[[str], None] | None = None

    @classmethod
    def create_from_config(cls, config_path: str, *, base_dir: str = ROOT_DIR) -> "DoubaoWebsocketTTS":
        if os.name != "nt":
            raise RuntimeError("doubao tts playback currently only supports Windows")
        settings = load_doubao_tts_settings(config_path, base_dir=base_dir)
        return cls(settings)

    def _ensure_worker_started(self):
        with self._lock:
            if self._worker_started:
                return
            self._worker_started = True
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def set_logger(self, logger: Callable[[str], None] | None):
        with self._lock:
            self._logger = logger

    def _emit_log(self, line: str):
        logger = self._logger
        if not logger:
            return
        try:
            logger(str(line or ""))
        except Exception:
            pass

    def _worker_loop(self):
        while True:
            payload = self._queue.get()
            if payload is None:
                return
            self._run_speak_blocking(payload)

    async def _synthesize_audio(self, payload: str) -> bytes:
        import websockets

        connect_id = str(uuid.uuid4())
        headers = build_doubao_ws_headers(self.settings, connect_id)
        endpoint_host = urlparse(self.settings.endpoint).netloc or self.settings.endpoint
        preview = summarize_tts_text(payload)
        self._emit_log(
            f"tts synthesize start backend=doubao endpoint={endpoint_host} chars={len(payload)} preview={preview}"
        )
        request_payload = build_doubao_tts_request_payload(self.settings, payload)
        request_frame = build_doubao_full_client_request_frame(
            json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        )
        websocket = await websockets.connect(
            self.settings.endpoint,
            additional_headers=headers,
            max_size=10 * 1024 * 1024,
            open_timeout=self.settings.connect_timeout_seconds,
        )
        try:
            await websocket.send(request_frame)
            audio_data = bytearray()
            while True:
                response = await websocket.recv()
                if isinstance(response, str):
                    raise RuntimeError(f"unexpected doubao text frame: {response}")
                message = parse_doubao_ws_message(response)
                if message.msg_type == DOUBAO_MSG_TYPE_AUDIO_ONLY_SERVER:
                    audio_data.extend(message.payload)
                    continue
                if message.msg_type == DOUBAO_MSG_TYPE_FULL_SERVER_RESPONSE:
                    if message.event == DOUBAO_EVENT_SESSION_FINISHED:
                        break
                    if message.event in (DOUBAO_EVENT_CONNECTION_FAILED, DOUBAO_EVENT_SESSION_FAILED):
                        detail = message.payload.decode("utf-8", "ignore").strip()
                        raise RuntimeError(detail or f"doubao session failed event={message.event}")
                    continue
                if message.msg_type == DOUBAO_MSG_TYPE_ERROR:
                    detail = message.payload.decode("utf-8", "ignore").strip()
                    raise RuntimeError(f"doubao error code={message.error_code}: {detail}")
            if not audio_data:
                raise RuntimeError("doubao returned empty audio")
            normalized_audio = normalize_wav_size_fields(bytes(audio_data))
            self._emit_log(
                f"tts synthesize success backend=doubao bytes={len(normalized_audio)} chars={len(payload)} preview={preview}"
            )
            return normalized_audio
        finally:
            await websocket.close()

    def _play_wav_bytes(self, audio_data: bytes) -> bool:
        return play_wav_bytes_on_windows(audio_data)

    def _run_speak_blocking(self, payload: str) -> bool:
        preview = summarize_tts_text(payload)
        try:
            audio_data = asyncio.run(self._synthesize_audio(payload))
            self._play_wav_bytes(audio_data)
        except Exception as e:
            self._last_error = str(e)
            self._emit_log(
                f"tts failed backend=doubao error={self._last_error} preview={preview}"
            )
            return False
        self._last_error = ""
        self._emit_log(
            f"tts played backend=doubao bytes={len(audio_data)} chars={len(payload)} preview={preview}"
        )
        return True

    def speak_async(self, text: str) -> bool:
        if os.name != "nt":
            self._emit_log("tts rejected backend=doubao reason=non_windows")
            return False
        payload = normalize_tts_text(text)
        if not is_speakable_english_text(payload):
            self._emit_log(
                f"tts rejected backend=doubao reason=non_speakable preview={summarize_tts_text(payload)}"
            )
            return False
        self._ensure_worker_started()
        self._queue.put(payload)
        self._emit_log(
            f"tts queued backend=doubao chars={len(payload)} preview={summarize_tts_text(payload)}"
        )
        return True


class TencentCloudSDKTTS:
    def __init__(self, settings: TencentCloudTTSSettings):
        self.settings = settings
        self._lock = threading.Lock()
        self._queue: "queue.SimpleQueue[str | None]" = queue.SimpleQueue()
        self._worker_started = False
        self._last_error = ""
        self._logger: Callable[[str], None] | None = None

    @classmethod
    def create_from_config(
        cls,
        config_path: str,
        *,
        base_dir: str = ROOT_DIR,
    ) -> "TencentCloudSDKTTS":
        if os.name != "nt":
            raise RuntimeError("tencent_cloud tts playback currently only supports Windows")
        settings = load_tencent_cloud_tts_settings(config_path, base_dir=base_dir)
        return cls(settings)

    def _ensure_worker_started(self):
        with self._lock:
            if self._worker_started:
                return
            self._worker_started = True
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def set_logger(self, logger: Callable[[str], None] | None):
        with self._lock:
            self._logger = logger

    def _emit_log(self, line: str):
        logger = self._logger
        if not logger:
            return
        try:
            logger(str(line or ""))
        except Exception:
            pass

    def _worker_loop(self):
        while True:
            payload = self._queue.get()
            if payload is None:
                return
            self._run_speak_blocking(payload)

    def _synthesize_audio(self, payload: str) -> tuple[bytes, str, str]:
        credential_module = importlib.import_module("tencentcloud.common.credential")
        client_profile_module = importlib.import_module(
            "tencentcloud.common.profile.client_profile"
        )
        http_profile_module = importlib.import_module("tencentcloud.common.profile.http_profile")
        tts_client_module = importlib.import_module("tencentcloud.tts.v20190823.tts_client")
        tts_models_module = importlib.import_module("tencentcloud.tts.v20190823.models")

        preview = summarize_tts_text(payload)
        self._emit_log(
            f"tts synthesize start backend=tencent_cloud endpoint={self.settings.endpoint} chars={len(payload)} preview={preview}"
        )
        credential_obj = credential_module.Credential(
            self.settings.secret_id,
            self.settings.secret_key,
        )
        http_profile = http_profile_module.HttpProfile(
            endpoint=self.settings.endpoint,
            reqTimeout=max(1, int(math.ceil(self.settings.request_timeout_seconds))),
        )
        client_profile = client_profile_module.ClientProfile(httpProfile=http_profile)
        client = tts_client_module.TtsClient(
            credential_obj,
            self.settings.region,
            client_profile,
        )

        session_id = str(uuid.uuid4())
        request_payload = build_tencent_cloud_tts_request_payload(
            self.settings,
            payload,
            session_id,
        )
        request_model = tts_models_module.TextToVoiceRequest()
        request_model.Text = request_payload["Text"]
        request_model.SessionId = request_payload["SessionId"]
        request_model.Volume = request_payload["Volume"]
        request_model.Speed = request_payload["Speed"]
        request_model.ProjectId = request_payload["ProjectId"]
        request_model.ModelType = request_payload["ModelType"]
        request_model.VoiceType = request_payload["VoiceType"]
        request_model.PrimaryLanguage = request_payload["PrimaryLanguage"]
        request_model.SampleRate = request_payload["SampleRate"]
        request_model.Codec = request_payload["Codec"]
        request_model.EnableSubtitle = request_payload["EnableSubtitle"]
        request_model.SegmentRate = request_payload["SegmentRate"]
        if "EmotionCategory" in request_payload:
            request_model.EmotionCategory = request_payload["EmotionCategory"]
            request_model.EmotionIntensity = request_payload["EmotionIntensity"]

        response = client.TextToVoice(request_model)
        request_id = str(getattr(response, "RequestId", "") or "").strip()
        response_session_id = str(getattr(response, "SessionId", "") or session_id).strip()
        encoded_audio = str(getattr(response, "Audio", "") or "").strip()
        if not encoded_audio:
            raise RuntimeError(
                f"tencent_cloud returned empty audio request_id={request_id or '-'}"
            )
        try:
            audio_data = base64.b64decode(encoded_audio)
        except Exception as e:
            raise RuntimeError(
                f"tencent_cloud returned invalid base64 audio request_id={request_id or '-'}"
            ) from e
        if not audio_data:
            raise RuntimeError(
                f"tencent_cloud decoded empty audio request_id={request_id or '-'}"
            )
        self._emit_log(
            f"tts synthesize success backend=tencent_cloud request_id={request_id or '-'} "
            f"session_id={response_session_id or '-'} bytes={len(audio_data)} chars={len(payload)} preview={preview}"
        )
        return audio_data, request_id, response_session_id

    def _play_wav_bytes(self, audio_data: bytes) -> bool:
        return play_wav_bytes_on_windows(audio_data)

    def _run_speak_blocking(self, payload: str) -> bool:
        preview = summarize_tts_text(payload)
        request_id = ""
        response_session_id = ""
        try:
            audio_data, request_id, response_session_id = self._synthesize_audio(payload)
            self._play_wav_bytes(audio_data)
        except Exception as e:
            self._last_error = format_tencent_cloud_sdk_exception(e)
            self._emit_log(
                f"tts failed backend=tencent_cloud error={self._last_error} preview={preview}"
            )
            return False
        self._last_error = ""
        self._emit_log(
            f"tts played backend=tencent_cloud request_id={request_id or '-'} "
            f"session_id={response_session_id or '-'} bytes={len(audio_data)} chars={len(payload)} preview={preview}"
        )
        return True

    def speak_async(self, text: str) -> bool:
        if os.name != "nt":
            self._emit_log("tts rejected backend=tencent_cloud reason=non_windows")
            return False
        payload = normalize_tts_text(text)
        if not is_speakable_english_text(payload):
            self._emit_log(
                f"tts rejected backend=tencent_cloud reason=non_speakable preview={summarize_tts_text(payload)}"
            )
            return False
        self._ensure_worker_started()
        self._queue.put(payload)
        self._emit_log(
            f"tts queued backend=tencent_cloud chars={len(payload)} preview={summarize_tts_text(payload)}"
        )
        return True


def create_tts_player(
    tts_cfg: dict[str, Any],
    *,
    config_dir: str = ROOT_DIR,
) -> tuple[Any | None, str]:
    provider = normalize_tts_provider(tts_cfg.get("provider", DEFAULT_TTS_PROVIDER))
    if provider == "windows_system":
        player = WindowsSystemTTS.create_default()
        if player:
            return (
                player,
                "tts configured backend=windows_system voice_probe=lazy preferred=Microsoft Zira Desktop,Microsoft David Desktop",
            )
        return None, "tts unavailable: no english system voice detected"

    if provider == "doubao":
        config_path = str(tts_cfg.get("config_path") or DOUBAO_TTS_DEFAULT_CONFIG_PATH).strip()
        resolved_config_path = resolve_config_file_path(config_path, base_dir=config_dir)
        settings = load_doubao_tts_settings(config_path, base_dir=config_dir)
        runtime_fields = build_doubao_tts_runtime_fields(settings, resolved_config_path)
        dependency_error = probe_doubao_websocket_runtime()
        if dependency_error:
            return None, f"tts unavailable {runtime_fields} reason={dependency_error}"
        player = DoubaoWebsocketTTS(settings)
        return (
            player,
            f"tts configured {runtime_fields}",
        )

    config_path = str(tts_cfg.get("config_path") or TENCENT_CLOUD_TTS_DEFAULT_CONFIG_PATH).strip()
    resolved_config_path = resolve_config_file_path(config_path, base_dir=config_dir)
    settings = load_tencent_cloud_tts_settings(config_path, base_dir=config_dir)
    runtime_fields = build_tencent_cloud_tts_runtime_fields(settings, resolved_config_path)
    dependency_error = probe_tencent_cloud_tts_runtime()
    if dependency_error:
        return None, f"tts unavailable {runtime_fields} reason={dependency_error}"
    player = TencentCloudSDKTTS(settings)
    return (
        player,
        f"tts configured {runtime_fields}",
    )


def check_tts_dependency_packaging(
    tts_cfg: dict[str, Any],
) -> tuple[bool, str]:
    provider = normalize_tts_provider(tts_cfg.get("provider", DEFAULT_TTS_PROVIDER))
    if provider == "windows_system":
        return True, "tts dependency check passed backend=windows_system"
    if provider == "doubao":
        dependency_error = probe_doubao_websocket_runtime()
        if dependency_error:
            return False, f"tts dependency check failed backend=doubao reason={dependency_error}"
        return True, "tts dependency check passed backend=doubao module=websockets"
    dependency_error = probe_tencent_cloud_tts_runtime()
    if dependency_error:
        return False, f"tts dependency check failed backend=tencent_cloud reason={dependency_error}"
    return True, "tts dependency check passed backend=tencent_cloud module=tencentcloud"
