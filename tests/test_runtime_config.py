import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from listener_app.runtime_config import load_runtime_config


class RuntimeConfigTest(unittest.TestCase):
    def _write_config(self, payload: dict) -> str:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "listener.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
        return str(path)

    def test_load_runtime_config_normalizes_supported_main_path_fields(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                    "targets": ["群一", "群一", "群二"],
                    "interval_seconds": 0.8,
                    "focus_refresh": True,
                    "worker_debug": True,
                    "load_retry_seconds": 12.0,
                    "session_preview_dedupe_window_seconds": 30.0,
                },
                "translate": {
                    "enabled": False,
                    "provider": "PASSTHROUGH",
                    "timeout_seconds": 9.0,
                },
                "display": {
                    "english_only": False,
                    "tts_auto_read_active_chat": False,
                    "on_translate_fail": "unexpected",
                    "width": 520,
                    "side": "left",
                },
                "tts": {
                    "provider": "WINDOWS_SYSTEM",
                },
                "logging": {
                    "file": "logs/runtime.log",
                },
            }
        )

        config = load_runtime_config(config_path)

        self.assertEqual(config.listen.targets, ["群一", "群二"])
        self.assertEqual(config.listen.interval_seconds, 0.8)
        self.assertTrue(config.listen.focus_refresh)
        self.assertTrue(config.listen.worker_debug)
        self.assertEqual(config.translate.provider, "passthrough")
        self.assertEqual(config.translate.timeout_seconds, 9.0)
        self.assertFalse(config.display.english_only)
        self.assertFalse(config.display.tts_auto_read_active_chat)
        self.assertEqual(config.display.on_translate_fail, "show_cn_with_reason")
        self.assertEqual(config.tts.provider, "windows_system")
        self.assertTrue(config.log_file.endswith("logs\\runtime.log"))

    def test_load_runtime_config_allows_empty_targets_for_main_path(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                    "targets": [],
                },
                "translate": {
                    "enabled": False,
                    "provider": "passthrough",
                },
                "display": {},
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        config = load_runtime_config(config_path)

        self.assertEqual(config.listen.targets, [])

    def test_load_runtime_config_rejects_non_session_mode(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "chat",
                },
                "translate": {
                    "enabled": False,
                    "provider": "passthrough",
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        with self.assertRaisesRegex(RuntimeError, "listen.mode=session"):
            load_runtime_config(config_path)

    def test_load_runtime_config_requires_deeplx_url_when_enabled(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": True,
                    "provider": "deeplx",
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        with mock.patch.dict(os.environ, {"DEEPLX_URL": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "deeplx_url"):
                load_runtime_config(config_path)

    def test_load_runtime_config_supports_explicit_deeplx_env_field(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": True,
                    "provider": "deeplx",
                    "deeplx_url_env": "DEEPLX_URL",
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        with mock.patch.dict(os.environ, {"DEEPLX_URL": "https://env.deeplx.local"}, clear=False):
            config = load_runtime_config(config_path)

        self.assertEqual(config.translate.deeplx_url, "https://env.deeplx.local")

    def test_load_runtime_config_blank_deeplx_env_disables_env_mode(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": True,
                    "provider": "deeplx",
                    "deeplx_url_env": "",
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        with mock.patch.dict(os.environ, {"DEEPLX_URL": "https://env.deeplx.local"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "deeplx_url_env"):
                load_runtime_config(config_path)

    def test_load_runtime_config_rejects_custom_deeplx_env_key(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": True,
                    "provider": "deeplx",
                    "deeplx_url_env": "CUSTOM_DEEPLX_URL",
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        with mock.patch.dict(os.environ, {"CUSTOM_DEEPLX_URL": "https://env.deeplx.local"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "must be DEEPLX_URL"):
                load_runtime_config(config_path)

    def test_load_runtime_config_keeps_legacy_display_fields_in_raw_payload_only(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": False,
                    "provider": "passthrough",
                },
                "display": {
                    "width": 540,
                    "side": "weird-side",
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        runtime_config = load_runtime_config(config_path)

        self.assertEqual(runtime_config.raw_config["display"]["width"], 540)
        self.assertEqual(runtime_config.raw_config["display"]["side"], "weird-side")
        self.assertEqual(runtime_config.display.on_translate_fail, "show_cn_with_reason")


if __name__ == "__main__":
    unittest.main()
