import json
import time
from urllib import error, request
from urllib.parse import urlparse
from typing import Any

if __package__:
    from .sidebar_shared import (
        DEEPLX_MAX_RETRIES,
        DEEPLX_RETRY_BACKOFF_SECONDS,
        SUPPORTED_TRANSLATE_PROVIDERS,
    )
else:
    from sidebar_shared import (
        DEEPLX_MAX_RETRIES,
        DEEPLX_RETRY_BACKOFF_SECONDS,
        SUPPORTED_TRANSLATE_PROVIDERS,
    )


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
        retry_attempts: int = DEEPLX_MAX_RETRIES,
        retry_backoff_seconds: float = DEEPLX_RETRY_BACKOFF_SECONDS,
    ):
        self.url = url.rstrip("/")
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = max(0, int(retry_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))

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
        raw = ""
        total_attempts = self.retry_attempts + 1
        for attempt in range(1, total_attempts + 1):
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    raw = resp.read().decode("utf-8", errors="ignore")
                break
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
                if attempt >= total_attempts:
                    raise RuntimeError(
                        f"DeepLX request failed after {total_attempts} attempts: {e}"
                    ) from e
                if self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds * attempt)

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


def normalize_translate_provider(value: Any) -> str:
    provider = str(value or "deeplx").strip().lower() or "deeplx"
    if provider not in SUPPORTED_TRANSLATE_PROVIDERS:
        supported = ", ".join(SUPPORTED_TRANSLATE_PROVIDERS)
        raise RuntimeError(f"translate.provider must be one of: {supported}")
    return provider


def validate_translate_config(enabled: bool, provider: str, deeplx_url: str):
    if not enabled:
        return
    if provider == "deeplx" and not str(deeplx_url or "").strip():
        raise RuntimeError(
            "translate.enabled=true and provider=deeplx require translate.deeplx_url or DEEPLX_URL"
        )


def build_translator_runtime_text(enabled: bool, provider: str) -> str:
    if not enabled:
        return "translator=passthrough reason=translate.disabled"
    if provider == "passthrough":
        return "translator=passthrough reason=provider=passthrough"
    return (
        f"translator=deeplx attempts={DEEPLX_MAX_RETRIES + 1} "
        f"retry_backoff={DEEPLX_RETRY_BACKOFF_SECONDS:.1f}s"
    )


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
    if provider == "passthrough":
        return PassthroughTranslator()
    if provider != "deeplx":
        raise RuntimeError(f"unsupported translator provider: {provider}")
    if not deeplx_url:
        raise RuntimeError(
            "translate.enabled=true and provider=deeplx require translate.deeplx_url or DEEPLX_URL"
        )
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
