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
        self.assertEqual(config.translate.timeout_seconds, 8.0)

    def test_load_runtime_config_supports_provider_aware_deeplx_fields(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": True,
                    "provider": "deeplx",
                    "source_lang": "auto",
                    "target_lang": "EN",
                    "providers": {
                        "deeplx": {
                            "deeplx_url_env": "DEEPLX_URL",
                            "timeout_seconds": 12.0,
                        }
                    },
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        with mock.patch.dict(os.environ, {"DEEPLX_URL": "https://env.deeplx.local"}, clear=False):
            config = load_runtime_config(config_path)

        self.assertEqual(config.translate.deeplx_url, "https://env.deeplx.local")
        self.assertEqual(config.translate.timeout_seconds, 12.0)

    def test_load_runtime_config_supports_openai_compatible_provider(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": True,
                    "provider": "openai_compatible",
                    "source_lang": "ZH",
                    "target_lang": "EN",
                    "providers": {
                        "openai_compatible": {
                            "base_url": "https://openrouter.local/v1",
                            "model": "gpt-4o-mini",
                            "api_key": "test-key",
                            "timeout_seconds": 15.0,
                        }
                    },
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        config = load_runtime_config(config_path)

        self.assertEqual(config.translate.provider, "openai_compatible")
        self.assertEqual(config.translate.openai_base_url, "https://openrouter.local/v1")
        self.assertEqual(config.translate.openai_model, "gpt-4o-mini")
        self.assertEqual(config.translate.openai_api_key, "test-key")
        self.assertEqual(config.translate.timeout_seconds, 15.0)

    def test_load_runtime_config_rejects_incomplete_openai_compatible_provider(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": True,
                    "provider": "openai_compatible",
                    "providers": {
                        "openai_compatible": {
                            "base_url": "https://openrouter.local/v1",
                            "model": "",
                            "api_key": "test-key",
                            "timeout_seconds": 15.0,
                        }
                    },
                },
                "tts": {
                    "provider": "windows_system",
                },
            }
        )

        with self.assertRaisesRegex(RuntimeError, "openai_compatible.*model"):
            load_runtime_config(config_path)

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

    def test_load_runtime_config_resolves_tts_provider_config_path_from_provider_map(self):
        config_path = self._write_config(
            {
                "listen": {
                    "mode": "session",
                },
                "translate": {
                    "enabled": False,
                    "provider": "passthrough",
                },
                "tts": {
                    "provider": "tencent_cloud",
                    "providers": {
                        "tencent_cloud": {
                            "config_path": "config/tencent_tts.json",
                        }
                    },
                },
            }
        )

        runtime_config = load_runtime_config(config_path)

        self.assertEqual(runtime_config.tts.provider, "tencent_cloud")
        self.assertEqual(runtime_config.tts.raw_config["config_path"], "config/tencent_tts.json")

    def test_repository_default_config_is_first_launch_safe_without_env(self):
        repo_config_path = Path(__file__).resolve().parents[1] / "config" / "listener.json"

        with mock.patch.dict(
            os.environ,
            {
                "DEEPLX_URL": "",
                "TENCENTCLOUD_SECRET_ID": "",
                "TENCENTCLOUD_SECRET_KEY": "",
            },
            clear=False,
        ):
            runtime_config = load_runtime_config(str(repo_config_path))

        self.assertFalse(runtime_config.translate.enabled)
        self.assertEqual(runtime_config.translate.provider, "deeplx")
        self.assertEqual(runtime_config.translate.deeplx_url, "")
        self.assertEqual(runtime_config.tts.provider, "windows_system")


if __name__ == "__main__":
    unittest.main()
