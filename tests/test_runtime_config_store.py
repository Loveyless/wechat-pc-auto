import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from listener_app.runtime_config_store import (
    ConfigValidationError,
    build_config_snapshot,
    save_config_snapshot,
)


class RuntimeConfigStoreTest(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    def _create_runtime_files(self) -> tuple[Path, Path, tempfile.TemporaryDirectory[str]]:
        temp_dir = tempfile.TemporaryDirectory()
        runtime_root = Path(temp_dir.name)
        listener_path = runtime_root / "listener.json"
        tencent_path = runtime_root / "tencent_tts.json"
        self._write_json(
            listener_path,
            {
                "listen": {
                    "mode": "session",
                    "targets": ["测试群"],
                    "interval_seconds": 0.6,
                    "load_retry_seconds": 1.0,
                },
                "translate": {
                    "enabled": True,
                    "provider": "deeplx",
                    "deeplx_url": "https://deeplx.local",
                    "source_lang": "auto",
                    "target_lang": "EN",
                    "timeout_seconds": 8.0,
                },
                "display": {
                    "english_only": True,
                    "tts_auto_read_active_chat": True,
                    "on_translate_fail": "show_cn_with_reason",
                    "width": 470,
                },
                "tts": {
                    "provider": "tencent_cloud",
                    "config_path": "tencent_tts.json",
                },
                "logging": {
                    "file": "logs/runtime.log",
                },
            },
        )
        self._write_json(
            tencent_path,
            {
                "provider": "tencent_cloud",
                "secret_id": "direct-id",
                "secret_key_env": "TENCENT_TEST_SECRET_KEY",
                "endpoint": "tts.tencentcloudapi.com",
                "region": "",
                "voice_type": 501008,
                "codec": "wav",
                "sample_rate": 16000,
                "speed": 0.0,
                "volume": 0.0,
                "primary_language": 2,
                "model_type": 1,
                "project_id": 0,
                "segment_rate": 0,
                "enable_subtitle": False,
                "request_timeout_seconds": 15.0,
                "extra_flag": "keep-me",
            },
        )
        return listener_path, tencent_path, temp_dir

    def test_build_config_snapshot_masks_secret_values_and_loads_provider_forms(self):
        listener_path, _, temp_dir = self._create_runtime_files()
        self.addCleanup(temp_dir.cleanup)

        with mock.patch.dict(os.environ, {"TENCENT_TEST_SECRET_KEY": "env-secret"}, clear=False):
            snapshot = build_config_snapshot(str(listener_path))

        self.assertEqual(snapshot["translate"]["provider"], "deeplx")
        self.assertNotIn("value", snapshot["translate"]["providers"]["deeplx"]["deeplx_url"])
        self.assertEqual(snapshot["translate"]["providers"]["deeplx"]["deeplx_url"]["source"], "direct")
        self.assertEqual(snapshot["translate"]["providers"]["deeplx"]["timeout_seconds"], 8.0)
        self.assertEqual(snapshot["tts"]["provider"], "tencent_cloud")
        self.assertIn("doubao", snapshot["tts"]["providers"])
        self.assertEqual(
            snapshot["tts"]["providers"]["tencent_cloud"]["config_path"],
            "tencent_tts.json",
        )
        self.assertEqual(
            snapshot["tts"]["providers"]["tencent_cloud"]["secret_id"]["source"],
            "direct",
        )
        self.assertEqual(
            snapshot["tts"]["providers"]["tencent_cloud"]["secret_key"]["source"],
            "env",
        )
        self.assertEqual(
            snapshot["tts"]["providers"]["tencent_cloud"]["secret_key"]["env_key"],
            "TENCENT_TEST_SECRET_KEY",
        )

    def test_save_config_snapshot_preserves_unknown_fields_and_masks_saved_secret_fields(self):
        listener_path, tencent_path, temp_dir = self._create_runtime_files()
        self.addCleanup(temp_dir.cleanup)

        with mock.patch.dict(
            os.environ,
            {
                "DEEPLX_URL": "https://env.deeplx.local",
                "TENCENT_TEST_SECRET_KEY": "env-secret",
            },
            clear=False,
        ):
            saved = save_config_snapshot(
                str(listener_path),
                {
                    "translate": {
                        "enabled": True,
                        "provider": "deeplx",
                        "source_lang": "auto",
                        "target_lang": "EN",
                        "providers": {
                            "deeplx": {
                                "timeout_seconds": 9.0,
                            }
                        },
                    },
                    "display": {
                        "english_only": False,
                        "tts_auto_read_active_chat": False,
                        "on_translate_fail": "show_cn",
                    },
                    "tts": {
                        "provider": "tencent_cloud",
                        "providers": {
                            "tencent_cloud": {
                                "config_path": "tencent_tts.json",
                                "endpoint": "tts.tencentcloudapi.com",
                                "region": "ap-shanghai",
                                "voice_type": 501008,
                                "codec": "wav",
                                "sample_rate": 16000,
                                "speed": 1.0,
                                "volume": 1.0,
                                "primary_language": 2,
                                "model_type": 1,
                                "project_id": 0,
                                "segment_rate": 0,
                                "enable_subtitle": False,
                                "emotion_category": "",
                                "emotion_intensity": 100,
                                "request_timeout_seconds": 15.0,
                            }
                        },
                    },
                    "secret_updates": {
                        "translate": {
                            "deeplx": {
                                "deeplx_url": {
                                    "mode": "env",
                                    "env_key": "DEEPLX_URL",
                                }
                            }
                        },
                        "tts": {
                            "tencent_cloud": {
                                "secret_id": {
                                    "mode": "direct",
                                    "value": "new-secret-id",
                                },
                                "secret_key": {
                                    "mode": "env",
                                    "env_key": "TENCENT_TEST_SECRET_KEY",
                                },
                            }
                        },
                    },
                },
            )

        listener_raw = json.loads(listener_path.read_text(encoding="utf-8"))
        tencent_raw = json.loads(tencent_path.read_text(encoding="utf-8"))
        self.assertEqual(listener_raw["display"]["width"], 470)
        self.assertEqual(listener_raw["display"]["on_translate_fail"], "show_cn")
        self.assertNotIn("deeplx_url", listener_raw["translate"])
        self.assertNotIn("deeplx_url_env", listener_raw["translate"])
        self.assertEqual(
            listener_raw["translate"]["providers"]["deeplx"]["deeplx_url"],
            "",
        )
        self.assertEqual(
            listener_raw["translate"]["providers"]["deeplx"]["deeplx_url_env"],
            "DEEPLX_URL",
        )
        self.assertEqual(
            listener_raw["translate"]["providers"]["deeplx"]["timeout_seconds"],
            9.0,
        )
        self.assertEqual(tencent_raw["extra_flag"], "keep-me")
        self.assertEqual(tencent_raw["secret_id"], "new-secret-id")
        self.assertEqual(tencent_raw["secret_key"], "")
        self.assertEqual(tencent_raw["secret_key_env"], "TENCENT_TEST_SECRET_KEY")
        self.assertNotIn("config_path", listener_raw["tts"])
        self.assertEqual(
            listener_raw["tts"]["providers"]["tencent_cloud"]["config_path"],
            "tencent_tts.json",
        )
        self.assertNotIn("value", saved["tts"]["providers"]["tencent_cloud"]["secret_id"])
        self.assertEqual(saved["translate"]["providers"]["deeplx"]["deeplx_url"]["source"], "env")

    def test_save_config_snapshot_clear_deeplx_url_disables_env_mode(self):
        listener_path, _, temp_dir = self._create_runtime_files()
        self.addCleanup(temp_dir.cleanup)

        with mock.patch.dict(
            os.environ,
            {
                "DEEPLX_URL": "https://env.deeplx.local",
                "TENCENT_TEST_SECRET_KEY": "env-secret",
            },
            clear=False,
        ):
            saved = save_config_snapshot(
                str(listener_path),
                {
                    "translate": {
                        "enabled": False,
                        "provider": "deeplx",
                        "source_lang": "auto",
                        "target_lang": "EN",
                        "providers": {
                            "deeplx": {
                                "timeout_seconds": 8.0,
                            }
                        },
                    },
                    "display": {
                        "english_only": True,
                        "tts_auto_read_active_chat": True,
                        "on_translate_fail": "show_cn_with_reason",
                    },
                    "tts": {
                        "provider": "tencent_cloud",
                        "providers": {
                            "tencent_cloud": {
                                "config_path": "tencent_tts.json",
                                "endpoint": "tts.tencentcloudapi.com",
                                "region": "",
                                "voice_type": 501008,
                                "codec": "wav",
                                "sample_rate": 16000,
                                "speed": 0.0,
                                "volume": 0.0,
                                "primary_language": 2,
                                "model_type": 1,
                                "project_id": 0,
                                "segment_rate": 0,
                                "enable_subtitle": False,
                                "emotion_category": "",
                                "emotion_intensity": 100,
                                "request_timeout_seconds": 15.0,
                            }
                        },
                    },
                    "secret_updates": {
                        "translate": {
                            "deeplx": {
                                "deeplx_url": {
                                    "mode": "clear",
                                }
                            }
                        }
                    },
                },
            )

        listener_raw = json.loads(listener_path.read_text(encoding="utf-8"))
        self.assertEqual(listener_raw["translate"]["providers"]["deeplx"]["deeplx_url"], "")
        self.assertEqual(listener_raw["translate"]["providers"]["deeplx"]["deeplx_url_env"], "")
        self.assertFalse(saved["translate"]["providers"]["deeplx"]["deeplx_url"]["configured"])
        self.assertEqual(saved["translate"]["providers"]["deeplx"]["deeplx_url"]["source"], "unset")

    def test_save_config_snapshot_supports_openai_compatible_provider(self):
        listener_path, _, temp_dir = self._create_runtime_files()
        self.addCleanup(temp_dir.cleanup)

        saved = save_config_snapshot(
            str(listener_path),
            {
                "translate": {
                    "enabled": True,
                    "provider": "openai_compatible",
                    "source_lang": "ZH",
                    "target_lang": "EN",
                    "providers": {
                        "openai_compatible": {
                            "base_url": "https://openrouter.local/v1",
                            "model": "gpt-4o-mini",
                            "timeout_seconds": 11.0,
                        }
                    },
                },
                "display": {
                    "english_only": True,
                    "tts_auto_read_active_chat": True,
                    "on_translate_fail": "show_cn_with_reason",
                },
                "tts": {
                    "provider": "windows_system",
                    "providers": {},
                },
                "secret_updates": {
                    "translate": {
                        "openai_compatible": {
                            "api_key": {
                                "mode": "direct",
                                "value": "openai-token",
                            }
                        }
                    }
                },
            },
        )

        listener_raw = json.loads(listener_path.read_text(encoding="utf-8"))
        self.assertEqual(listener_raw["translate"]["provider"], "openai_compatible")
        self.assertEqual(
            listener_raw["translate"]["providers"]["openai_compatible"]["base_url"],
            "https://openrouter.local/v1",
        )
        self.assertEqual(
            listener_raw["translate"]["providers"]["openai_compatible"]["model"],
            "gpt-4o-mini",
        )
        self.assertEqual(
            listener_raw["translate"]["providers"]["openai_compatible"]["api_key"],
            "openai-token",
        )
        self.assertEqual(
            listener_raw["translate"]["providers"]["openai_compatible"]["timeout_seconds"],
            11.0,
        )
        self.assertEqual(
            saved["translate"]["providers"]["openai_compatible"]["api_key"]["source"],
            "direct",
        )

    def test_save_config_snapshot_rejects_openai_env_mode(self):
        listener_path, _, temp_dir = self._create_runtime_files()
        self.addCleanup(temp_dir.cleanup)

        with self.assertRaises(ConfigValidationError) as ctx:
            save_config_snapshot(
                str(listener_path),
                {
                    "translate": {
                        "enabled": True,
                        "provider": "openai_compatible",
                        "source_lang": "ZH",
                        "target_lang": "EN",
                        "providers": {
                            "openai_compatible": {
                                "base_url": "https://openrouter.local/v1",
                                "model": "gpt-4o-mini",
                                "timeout_seconds": 11.0,
                            }
                        },
                    },
                    "display": {
                        "english_only": True,
                        "tts_auto_read_active_chat": True,
                        "on_translate_fail": "show_cn_with_reason",
                    },
                    "tts": {
                        "provider": "windows_system",
                        "providers": {},
                    },
                    "secret_updates": {
                        "translate": {
                            "openai_compatible": {
                                "api_key": {
                                    "mode": "env",
                                    "env_key": "OPENAI_API_KEY",
                                }
                            }
                        }
                    },
                },
            )

        self.assertEqual(
            ctx.exception.field_errors["translate.providers.openai_compatible.api_key"],
            "env mode is not supported",
        )

    def test_save_config_snapshot_rejects_invalid_payload_without_mutating_files(self):
        listener_path, tencent_path, temp_dir = self._create_runtime_files()
        self.addCleanup(temp_dir.cleanup)
        before_listener = listener_path.read_text(encoding="utf-8")
        before_tencent = tencent_path.read_text(encoding="utf-8")

        with mock.patch.dict(os.environ, {"TENCENT_TEST_SECRET_KEY": "env-secret"}, clear=False):
            with self.assertRaises(ConfigValidationError):
                save_config_snapshot(
                    str(listener_path),
                    {
                        "translate": {
                            "enabled": True,
                            "provider": "deeplx",
                            "source_lang": "auto",
                            "target_lang": "EN",
                            "providers": {
                                "deeplx": {
                                    "timeout_seconds": 8.0,
                                }
                            },
                        },
                        "display": {
                            "english_only": True,
                            "tts_auto_read_active_chat": True,
                            "on_translate_fail": "show_cn_with_reason",
                        },
                        "tts": {
                            "provider": "tencent_cloud",
                            "providers": {
                                "tencent_cloud": {
                                    "config_path": "tencent_tts.json",
                                    "voice_type": 0,
                                }
                            },
                        },
                    },
                )

        self.assertEqual(listener_path.read_text(encoding="utf-8"), before_listener)
        self.assertEqual(tencent_path.read_text(encoding="utf-8"), before_tencent)


if __name__ == "__main__":
    unittest.main()
