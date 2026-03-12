import io
import importlib
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock
from urllib import error


class _ModuleProxy:
    def __init__(self, modules):
        object.__setattr__(self, "_owners", {})
        for module in modules:
            for name in dir(module):
                if name.startswith("_"):
                    continue
                self._owners[name] = module

    def __getattr__(self, name):
        owner = self._owners.get(name)
        if owner is None:
            raise AttributeError(name)
        return getattr(owner, name)

    def __setattr__(self, name, value):
        owner = self._owners.get(name)
        if owner is None:
            object.__setattr__(self, name, value)
            return
        setattr(owner, name, value)

    def __delattr__(self, name):
        owner = self._owners.get(name)
        if owner is None:
            object.__delattr__(self, name)
            return
        delattr(owner, name)


def _load_sidebar_module():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    module_names = [
        "listener_app.sidebar_translate_listener",
        "listener_app.sidebar_shared",
        "listener_app.sidebar_translate_runtime",
        "listener_app.sidebar_runtime_support",
        "listener_app.sidebar_tts",
        "listener_app.sidebar_ui",
    ]
    modules = [importlib.import_module(name) for name in module_names]
    return _ModuleProxy(modules)


sidebar = _load_sidebar_module()


class SidebarHelpersTest(unittest.TestCase):
    def test_normalize_message_for_dedupe(self):
        raw = "  hello\u200b   world  "
        self.assertEqual(sidebar.normalize_message_for_dedupe(raw), "hello world")

    def test_build_sidebar_window_title_uses_active_chat_name(self):
        self.assertEqual(sidebar.build_sidebar_window_title("  三元 AI 俱乐部  "), "三元 AI 俱乐部")
        self.assertEqual(sidebar.build_sidebar_window_title(""), "未选择会话")

    def test_validate_positive_float(self):
        self.assertEqual(sidebar.validate_positive_float("x", 0.5), 0.5)
        with self.assertRaises(RuntimeError):
            sidebar.validate_positive_float("x", 0)
        with self.assertRaises(RuntimeError):
            sidebar.validate_positive_float("x", -1)

    def test_validate_float_min(self):
        self.assertEqual(sidebar.validate_float_min("x", 0.6, 0.2), 0.6)
        with self.assertRaises(RuntimeError):
            sidebar.validate_float_min("x", 0.1, 0.2)

    def test_validate_float_range(self):
        self.assertEqual(sidebar.validate_float_range("x", 1.5, -2.0, 6.0), 1.5)
        with self.assertRaises(RuntimeError):
            sidebar.validate_float_range("x", -2.1, -2.0, 6.0)
        with self.assertRaises(RuntimeError):
            sidebar.validate_float_range("x", 6.1, -2.0, 6.0)

    def test_validate_int_min(self):
        self.assertEqual(sidebar.validate_int_min("w", 300, 280), 300)
        with self.assertRaises(RuntimeError):
            sidebar.validate_int_min("w", 200, 280)

    def test_validate_int_range(self):
        self.assertEqual(sidebar.validate_int_range("x", -5, -50, 100), -5)
        with self.assertRaises(RuntimeError):
            sidebar.validate_int_range("x", -51, -50, 100)
        with self.assertRaises(RuntimeError):
            sidebar.validate_int_range("x", 101, -50, 100)

    def test_validate_int_choices(self):
        self.assertEqual(
            sidebar.validate_int_choices("x", 32000, (8000, 16000, 32000)),
            32000,
        )
        with self.assertRaises(RuntimeError):
            sidebar.validate_int_choices("x", 12345, (8000, 16000, 32000))

    def test_read_config_type_validation(self):
        self.assertEqual(sidebar.read_config_float({}, "interval_seconds", 1.0), 1.0)
        self.assertEqual(sidebar.read_config_int({}, "width", 420), 420)

        with self.assertRaises(RuntimeError):
            sidebar.read_config_float({"interval_seconds": "bad"}, "interval_seconds", 1.0)
        with self.assertRaises(RuntimeError):
            sidebar.read_config_int({"width": "bad"}, "width", 420)

    def test_normalize_translate_provider_rejects_invalid_value(self):
        self.assertEqual(sidebar.normalize_translate_provider("DEEPLX"), "deeplx")
        with self.assertRaises(RuntimeError):
            sidebar.normalize_translate_provider("unknown")

    def test_validate_translate_config_requires_deeplx_url_when_enabled(self):
        with self.assertRaises(RuntimeError):
            sidebar.validate_translate_config(True, "deeplx", "")
        sidebar.validate_translate_config(False, "deeplx", "")
        sidebar.validate_translate_config(True, "passthrough", "")

    def test_normalize_tts_provider_rejects_invalid_value(self):
        self.assertEqual(sidebar.normalize_tts_provider("DOUBAO"), "doubao")
        self.assertEqual(sidebar.normalize_tts_provider("TENCENT_CLOUD"), "tencent_cloud")
        self.assertEqual(sidebar.normalize_tts_provider(""), "tencent_cloud")
        with self.assertRaises(RuntimeError):
            sidebar.normalize_tts_provider("unknown")

    def test_resolve_config_file_path_prefers_base_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = pathlib.Path(tmpdir)
            file_path = config_dir / "doubao_tts.json"
            file_path.write_text("{}", encoding="utf-8")

            resolved = sidebar.resolve_config_file_path("doubao_tts.json", base_dir=str(config_dir))

        self.assertEqual(pathlib.Path(resolved), file_path)

    def test_load_doubao_tts_settings_reads_env_backed_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "doubao_tts.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "doubao",
                        "appid_env": "VOLC_TTS_APPID",
                        "access_token_env": "VOLC_TTS_TOKEN",
                        "resource_id": "seed-tts-2.0",
                        "speaker": "zh_female_yingyujiaoxue_uranus_bigtts",
                        "audio_format": "wav",
                        "sample_rate": 32000,
                        "speech_rate": -15,
                        "loudness_rate": 0,
                        "use_cache": True,
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "VOLC_TTS_APPID": "appid-1",
                    "VOLC_TTS_TOKEN": "token-1",
                },
                clear=False,
            ):
                settings = sidebar.load_doubao_tts_settings(str(config_path))

        self.assertEqual(settings.appid, "appid-1")
        self.assertEqual(settings.access_token, "token-1")
        self.assertEqual(settings.audio_format, "wav")
        self.assertEqual(settings.resource_id, "seed-tts-2.0")
        self.assertEqual(settings.sample_rate, 32000)
        self.assertEqual(settings.speech_rate, -15)
        self.assertEqual(settings.loudness_rate, 0)
        self.assertTrue(settings.use_cache)

    def test_load_doubao_tts_settings_rejects_non_wav_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "doubao_tts.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "doubao",
                        "appid": "appid-1",
                        "access_token": "token-1",
                        "resource_id": "seed-tts-2.0",
                        "speaker": "zh_female_yingyujiaoxue_uranus_bigtts",
                        "audio_format": "mp3",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                sidebar.load_doubao_tts_settings(str(config_path))

    def test_load_doubao_tts_settings_rejects_unsupported_sample_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "doubao_tts.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "doubao",
                        "appid": "appid-1",
                        "access_token": "token-1",
                        "resource_id": "seed-tts-2.0",
                        "speaker": "zh_female_yingyujiaoxue_uranus_bigtts",
                        "audio_format": "wav",
                        "sample_rate": 12345,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                sidebar.load_doubao_tts_settings(str(config_path))

    def test_load_doubao_tts_settings_rejects_out_of_range_speech_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "doubao_tts.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "doubao",
                        "appid": "appid-1",
                        "access_token": "token-1",
                        "resource_id": "seed-tts-2.0",
                        "speaker": "zh_female_yingyujiaoxue_uranus_bigtts",
                        "audio_format": "wav",
                        "speech_rate": -51,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                sidebar.load_doubao_tts_settings(str(config_path))

    def test_load_tencent_cloud_tts_settings_reads_env_backed_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "tencent_tts.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "tencent_cloud",
                        "secret_id_env": "TENCENT_SECRET_ID",
                        "secret_key_env": "TENCENT_SECRET_KEY",
                        "voice_type": 101001,
                        "codec": "wav",
                        "sample_rate": 16000,
                        "speed": 1.25,
                        "volume": 2.0,
                        "primary_language": 2,
                        "segment_rate": 1,
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "TENCENT_SECRET_ID": "secret-id-1",
                    "TENCENT_SECRET_KEY": "secret-key-1",
                },
                clear=False,
            ):
                settings = sidebar.load_tencent_cloud_tts_settings(str(config_path))

        self.assertEqual(settings.secret_id, "secret-id-1")
        self.assertEqual(settings.secret_key, "secret-key-1")
        self.assertEqual(settings.voice_type, 101001)
        self.assertEqual(settings.codec, "wav")
        self.assertEqual(settings.sample_rate, 16000)
        self.assertEqual(settings.speed, 1.25)
        self.assertEqual(settings.volume, 2.0)
        self.assertEqual(settings.primary_language, 2)
        self.assertEqual(settings.segment_rate, 1)

    def test_load_tencent_cloud_tts_settings_rejects_non_wav_codec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "tencent_tts.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "tencent_cloud",
                        "secret_id": "secret-id-1",
                        "secret_key": "secret-key-1",
                        "voice_type": 101001,
                        "codec": "mp3",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                sidebar.load_tencent_cloud_tts_settings(str(config_path))

    def test_load_tencent_cloud_tts_settings_rejects_invalid_sample_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "tencent_tts.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "tencent_cloud",
                        "secret_id": "secret-id-1",
                        "secret_key": "secret-key-1",
                        "voice_type": 101001,
                        "sample_rate": 32000,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                sidebar.load_tencent_cloud_tts_settings(str(config_path))

    def test_load_tencent_cloud_tts_settings_rejects_out_of_range_speed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "tencent_tts.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "tencent_cloud",
                        "secret_id": "secret-id-1",
                        "secret_key": "secret-key-1",
                        "voice_type": 101001,
                        "speed": 6.5,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                sidebar.load_tencent_cloud_tts_settings(str(config_path))

    def test_build_doubao_ws_headers_and_payload(self):
        settings = sidebar.DoubaoTTSSettings(
            endpoint="wss://example.invalid/tts",
            appid="appid-1",
            access_token="token-1",
            resource_id="seed-tts-2.0",
            speaker="zh_female_yingyujiaoxue_uranus_bigtts",
            sample_rate=32000,
            speech_rate=-15,
            loudness_rate=0,
            use_cache=True,
        )

        headers = sidebar.build_doubao_ws_headers(settings, "connect-id")
        payload = sidebar.build_doubao_tts_request_payload(settings, "Hello world")

        self.assertEqual(headers["X-Api-App-Key"], "appid-1")
        self.assertEqual(headers["X-Api-Access-Key"], "token-1")
        self.assertEqual(headers["X-Api-Resource-Id"], "seed-tts-2.0")
        self.assertEqual(headers["X-Api-Connect-Id"], "connect-id")
        self.assertEqual(payload["req_params"]["speaker"], settings.speaker)
        self.assertEqual(payload["req_params"]["audio_params"]["format"], "wav")
        self.assertEqual(payload["req_params"]["audio_params"]["sample_rate"], 32000)
        self.assertEqual(payload["req_params"]["audio_params"]["speech_rate"], -15)
        self.assertEqual(payload["req_params"]["audio_params"]["loudness_rate"], 0)
        self.assertTrue(payload["req_params"]["additions"]["cache_config"]["use_cache"])
        self.assertEqual(payload["req_params"]["additions"]["cache_config"]["text_type"], 1)

    def test_build_tencent_cloud_tts_request_payload(self):
        settings = sidebar.TencentCloudTTSSettings(
            secret_id="secret-id-1",
            secret_key="secret-key-1",
            voice_type=101001,
            sample_rate=24000,
            speed=1.25,
            volume=2.0,
            primary_language=2,
            segment_rate=1,
            enable_subtitle=True,
            emotion_category="neutral",
            emotion_intensity=120,
        )

        payload = sidebar.build_tencent_cloud_tts_request_payload(
            settings,
            "Hello world",
            "session-123",
        )

        self.assertEqual(payload["Text"], "Hello world")
        self.assertEqual(payload["SessionId"], "session-123")
        self.assertEqual(payload["VoiceType"], 101001)
        self.assertEqual(payload["SampleRate"], 24000)
        self.assertEqual(payload["Codec"], "wav")
        self.assertEqual(payload["Speed"], 1.25)
        self.assertEqual(payload["Volume"], 2.0)
        self.assertEqual(payload["PrimaryLanguage"], 2)
        self.assertEqual(payload["SegmentRate"], 1)
        self.assertTrue(payload["EnableSubtitle"])
        self.assertEqual(payload["EmotionCategory"], "neutral")
        self.assertEqual(payload["EmotionIntensity"], 120)

    def test_normalize_wav_size_fields_rewrites_streaming_placeholders(self):
        wav_bytes = (
            b"RIFF"
            + b"\xff\xff\xff\xff"
            + b"WAVE"
            + b"fmt "
            + b"\x10\x00\x00\x00"
            + b"\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00"
            + b"data"
            + b"\xff\xff\xff\xff"
            + b"\x01\x02\x03\x04"
        )

        normalized = sidebar.normalize_wav_size_fields(wav_bytes)

        self.assertEqual(normalized[:4], b"RIFF")
        self.assertEqual(int.from_bytes(normalized[4:8], "little"), len(normalized) - 8)
        data_offset = sidebar.find_wav_data_chunk_offset(normalized)
        self.assertEqual(data_offset, 36)
        self.assertEqual(int.from_bytes(normalized[data_offset + 4 : data_offset + 8], "little"), 4)

    def test_create_tts_player_doubao_uses_external_config(self):
        settings = sidebar.DoubaoTTSSettings(
            endpoint="wss://example.invalid/tts",
            appid="appid-1",
            access_token="token-1",
            resource_id="seed-tts-2.0",
            speaker="zh_female_yingyujiaoxue_uranus_bigtts",
            sample_rate=32000,
            speech_rate=-15,
            loudness_rate=0,
            use_cache=False,
        )
        with mock.patch.object(sidebar, "load_doubao_tts_settings", return_value=settings), mock.patch.object(
            sidebar,
            "resolve_config_file_path",
            return_value="D:\\mock\\config\\doubao_tts.json",
        ), mock.patch.object(
            sidebar,
            "probe_doubao_websocket_runtime",
            return_value="",
        ):
            player, runtime_text = sidebar.create_tts_player(
                {
                    "provider": "doubao",
                    "config_path": "config/doubao_tts.json",
                },
                config_dir="D:\\mock",
            )

        self.assertIsInstance(player, sidebar.DoubaoWebsocketTTS)
        self.assertIn("backend=doubao", runtime_text)
        self.assertIn("seed-tts-2.0", runtime_text)
        self.assertIn("sample_rate=32000", runtime_text)
        self.assertIn("speech_rate=-15", runtime_text)
        self.assertIn("loudness_rate=0", runtime_text)
        self.assertIn("use_cache=False", runtime_text)

    def test_create_tts_player_doubao_returns_unavailable_when_websockets_missing(self):
        settings = sidebar.DoubaoTTSSettings(
            endpoint="wss://example.invalid/tts",
            appid="appid-1",
            access_token="token-1",
            resource_id="seed-tts-2.0",
            speaker="zh_female_yingyujiaoxue_uranus_bigtts",
        )
        with mock.patch.object(sidebar, "load_doubao_tts_settings", return_value=settings), mock.patch.object(
            sidebar,
            "resolve_config_file_path",
            return_value="D:\\mock\\config\\doubao_tts.json",
        ), mock.patch.object(
            sidebar,
            "probe_doubao_websocket_runtime",
            return_value="missing Python module 'websockets': No module named 'websockets'",
        ):
            player, runtime_text = sidebar.create_tts_player(
                {
                    "provider": "doubao",
                    "config_path": "config/doubao_tts.json",
                },
                config_dir="D:\\mock",
            )

        self.assertIsNone(player)
        self.assertIn("tts unavailable backend=doubao", runtime_text)
        self.assertIn("missing Python module 'websockets'", runtime_text)

    def test_create_tts_player_tencent_cloud_uses_external_config(self):
        settings = sidebar.TencentCloudTTSSettings(
            secret_id="secret-id-1",
            secret_key="secret-key-1",
            voice_type=101001,
            sample_rate=16000,
            speed=0.0,
            volume=0.0,
        )
        with mock.patch.object(
            sidebar,
            "load_tencent_cloud_tts_settings",
            return_value=settings,
        ), mock.patch.object(
            sidebar,
            "resolve_config_file_path",
            return_value="D:\\mock\\config\\tencent_tts.json",
        ), mock.patch.object(
            sidebar,
            "probe_tencent_cloud_tts_runtime",
            return_value="",
        ):
            player, runtime_text = sidebar.create_tts_player(
                {
                    "provider": "tencent_cloud",
                    "config_path": "config/tencent_tts.json",
                },
                config_dir="D:\\mock",
            )

        self.assertIsInstance(player, sidebar.TencentCloudSDKTTS)
        self.assertIn("backend=tencent_cloud", runtime_text)
        self.assertIn("voice_type=101001", runtime_text)
        self.assertIn("sample_rate=16000", runtime_text)

    def test_create_tts_player_tencent_cloud_returns_unavailable_when_sdk_missing(self):
        settings = sidebar.TencentCloudTTSSettings(
            secret_id="secret-id-1",
            secret_key="secret-key-1",
            voice_type=101001,
        )
        with mock.patch.object(
            sidebar,
            "load_tencent_cloud_tts_settings",
            return_value=settings,
        ), mock.patch.object(
            sidebar,
            "resolve_config_file_path",
            return_value="D:\\mock\\config\\tencent_tts.json",
        ), mock.patch.object(
            sidebar,
            "probe_tencent_cloud_tts_runtime",
            return_value="missing Python module 'tencentcloud.tts.v20190823.tts_client': No module named 'tencentcloud'",
        ):
            player, runtime_text = sidebar.create_tts_player(
                {
                    "provider": "tencent_cloud",
                    "config_path": "config/tencent_tts.json",
                },
                config_dir="D:\\mock",
            )

        self.assertIsNone(player)
        self.assertIn("tts unavailable backend=tencent_cloud", runtime_text)
        self.assertIn("No module named 'tencentcloud'", runtime_text)

    def test_check_tts_dependency_packaging_reports_missing_websockets(self):
        with mock.patch.object(
            sidebar,
            "probe_doubao_websocket_runtime",
            return_value="missing Python module 'websockets': No module named 'websockets'",
        ):
            ok, detail = sidebar.check_tts_dependency_packaging({"provider": "doubao"})

        self.assertFalse(ok)
        self.assertIn("tts dependency check failed backend=doubao", detail)
        self.assertIn("missing Python module 'websockets'", detail)

    def test_check_tts_dependency_packaging_reports_missing_tencent_sdk(self):
        with mock.patch.object(
            sidebar,
            "probe_tencent_cloud_tts_runtime",
            return_value="missing Python module 'tencentcloud.tts.v20190823.tts_client': No module named 'tencentcloud'",
        ):
            ok, detail = sidebar.check_tts_dependency_packaging({"provider": "tencent_cloud"})

        self.assertFalse(ok)
        self.assertIn("tts dependency check failed backend=tencent_cloud", detail)
        self.assertIn("No module named 'tencentcloud'", detail)

    def test_doubao_run_blocking_emits_failure_log(self):
        settings = sidebar.DoubaoTTSSettings(
            endpoint="wss://example.invalid/tts",
            appid="appid-1",
            access_token="token-1",
            resource_id="seed-tts-2.0",
            speaker="zh_female_yingyujiaoxue_uranus_bigtts",
        )
        player = sidebar.DoubaoWebsocketTTS(settings)
        logs = []
        player.set_logger(logs.append)

        async def fake_synthesize(_payload):
            raise RuntimeError("boom")

        player._synthesize_audio = fake_synthesize

        self.assertFalse(player._run_speak_blocking("Hello world"))
        self.assertIn("boom", player._last_error)
        self.assertTrue(any("tts failed backend=doubao" in line for line in logs))

    def test_doubao_run_blocking_emits_success_log(self):
        settings = sidebar.DoubaoTTSSettings(
            endpoint="wss://example.invalid/tts",
            appid="appid-1",
            access_token="token-1",
            resource_id="seed-tts-2.0",
            speaker="zh_female_yingyujiaoxue_uranus_bigtts",
        )
        player = sidebar.DoubaoWebsocketTTS(settings)
        logs = []
        player.set_logger(logs.append)

        async def fake_synthesize(_payload):
            return b"RIFF....WAVEfmt "

        player._synthesize_audio = fake_synthesize
        player._play_wav_bytes = lambda _audio: True

        self.assertTrue(player._run_speak_blocking("Hello world"))
        self.assertEqual(player._last_error, "")
        self.assertTrue(any("tts played backend=doubao" in line for line in logs))

    def test_tencent_cloud_run_blocking_emits_failure_log(self):
        settings = sidebar.TencentCloudTTSSettings(
            secret_id="secret-id-1",
            secret_key="secret-key-1",
            voice_type=101001,
        )
        player = sidebar.TencentCloudSDKTTS(settings)
        logs = []
        player.set_logger(logs.append)

        def fake_synthesize(_payload):
            raise RuntimeError("boom")

        player._synthesize_audio = fake_synthesize

        self.assertFalse(player._run_speak_blocking("Hello world"))
        self.assertIn("boom", player._last_error)
        self.assertTrue(any("tts failed backend=tencent_cloud" in line for line in logs))

    def test_tencent_cloud_run_blocking_emits_success_log(self):
        settings = sidebar.TencentCloudTTSSettings(
            secret_id="secret-id-1",
            secret_key="secret-key-1",
            voice_type=101001,
        )
        player = sidebar.TencentCloudSDKTTS(settings)
        logs = []
        player.set_logger(logs.append)

        def fake_synthesize(_payload):
            return (b"RIFF....WAVEfmt ", "req-1", "session-1")

        player._synthesize_audio = fake_synthesize
        player._play_wav_bytes = lambda _audio: True

        self.assertTrue(player._run_speak_blocking("Hello world"))
        self.assertEqual(player._last_error, "")
        self.assertTrue(any("tts played backend=tencent_cloud" in line for line in logs))

    def test_is_filtered_placeholder_matches_media_placeholders(self):
        self.assertTrue(sidebar.is_filtered_placeholder("[图片]"))
        self.assertTrue(sidebar.is_filtered_placeholder("[视频]"))
        self.assertTrue(sidebar.is_filtered_placeholder("[Video]"))
        self.assertTrue(sidebar.is_filtered_placeholder("[动画表情]"))
        self.assertTrue(sidebar.is_filtered_placeholder('[语音] 2"'))
        self.assertTrue(sidebar.is_filtered_placeholder('[Voice Over] 3"'))
        self.assertTrue(sidebar.is_filtered_placeholder("[系统提示]"))
        self.assertFalse(sidebar.is_filtered_placeholder("咳"))

    def test_is_filtered_link_message_matches_explicit_http_links(self):
        self.assertTrue(sidebar.is_filtered_link_message("http://example.com"))
        self.assertTrue(sidebar.is_filtered_link_message("看看这个 https://example.com/a?b=1"))
        self.assertTrue(sidebar.is_filtered_link_message("张三: HTTPS://example.com"))
        self.assertFalse(sidebar.is_filtered_link_message("www.example.com"))
        self.assertFalse(sidebar.is_filtered_link_message("hello: world"))

    def test_is_speakable_english_text(self):
        self.assertTrue(sidebar.is_speakable_english_text("Ahem."))
        self.assertFalse(sidebar.is_speakable_english_text("咳"))
        self.assertFalse(sidebar.is_speakable_english_text("咳 (translate_failed: timeout)"))
        self.assertFalse(sidebar.is_speakable_english_text("Loading..."))

    def test_pick_preferred_tts_voice_prefers_zira_then_english(self):
        voices = [
            {"name": "Microsoft Huihui Desktop", "culture": "zh-CN"},
            {"name": "Microsoft David Desktop", "culture": "en-US"},
            {"name": "Microsoft Zira Desktop", "culture": "en-US"},
        ]
        self.assertEqual(sidebar.pick_preferred_tts_voice(voices), "Microsoft Zira Desktop")
        self.assertEqual(
            sidebar.pick_preferred_tts_voice(
                [
                    {"name": "Microsoft Huihui Desktop", "culture": "zh-CN"},
                    {"name": "Some English Voice", "culture": "en-GB"},
                ]
            ),
            "Some English Voice",
        )

    def test_windows_system_tts_create_default_is_lazy_on_windows(self):
        original_os_name = sidebar.os.name
        sidebar.os.name = "nt"
        try:
            player = sidebar.WindowsSystemTTS.create_default()
        finally:
            sidebar.os.name = original_os_name

        self.assertIsNotNone(player)
        self.assertEqual(player.voice_name, "")

    def test_exit_startup_error_prints_and_raises(self):
        original_dialog = sidebar.maybe_show_frozen_error_dialog
        calls = []

        try:
            sidebar.maybe_show_frozen_error_dialog = calls.append
            with self.assertRaises(SystemExit) as cm, mock.patch(
                "sys.stderr",
                new_callable=io.StringIO,
            ) as stderr:
                sidebar.exit_startup_error("invalid config: missing deeplx url", exit_code=3)
        finally:
            sidebar.maybe_show_frozen_error_dialog = original_dialog

        self.assertEqual(cm.exception.code, 3)
        self.assertEqual(calls, ["invalid config: missing deeplx url"])
        self.assertIn(
            "[sidebar] invalid config: missing deeplx url",
            stderr.getvalue(),
        )

    def test_create_translator_rejects_missing_deeplx_url(self):
        with self.assertRaises(RuntimeError):
            sidebar.create_translator(
                enabled=True,
                provider="deeplx",
                deeplx_url="",
                source_lang="auto",
                target_lang="EN",
                timeout_seconds=8.0,
            )

    def test_ensure_runtime_layout_copies_default_config(self):
        with tempfile.TemporaryDirectory() as runtime_dir, tempfile.TemporaryDirectory() as bundle_dir:
            bundled_config_dir = pathlib.Path(bundle_dir) / "config"
            bundled_config_dir.mkdir(parents=True, exist_ok=True)
            bundled_config_path = bundled_config_dir / "listener.json"
            bundled_config_path.write_text('{"listen": {}}', encoding="utf-8")

            runtime_config_path = sidebar.ensure_runtime_layout(
                runtime_root=runtime_dir,
                bundled_config_path=str(bundled_config_path),
            )

            self.assertTrue(os.path.exists(runtime_config_path))
            self.assertEqual(pathlib.Path(runtime_config_path).read_text(encoding="utf-8"), '{"listen": {}}')
            self.assertTrue(os.path.isdir(pathlib.Path(runtime_dir) / "logs"))

    def test_build_worker_command_uses_python_script_in_source_mode(self):
        cmd = sidebar.build_worker_command(
            ["群1", "群2"],
            0.6,
            debug=True,
            focus_refresh=True,
            load_retry_seconds=10.0,
            frozen=False,
            python_executable="python",
            source_root=r"D:\repo\wechat-pc-auto",
            runtime_root=r"D:\runtime",
        )

        self.assertEqual(cmd[:5], ["python", "-X", "utf8", "-u", r"D:\repo\wechat-pc-auto\listener_app\group_listener_worker.py"])
        self.assertIn("--targets-json", cmd)
        self.assertIn("--debug", cmd)
        self.assertIn("--focus-refresh", cmd)

    def test_build_worker_command_uses_worker_exe_in_frozen_mode(self):
        cmd = sidebar.build_worker_command(
            ["群1"],
            0.6,
            debug=False,
            focus_refresh=False,
            load_retry_seconds=10.0,
            frozen=True,
            python_executable="python",
            source_root=r"D:\repo\wechat-pc-auto",
            runtime_root=r"D:\runtime",
        )

        self.assertEqual(cmd[0], r"D:\runtime\group_listener_worker.exe")
        self.assertNotIn("-X", cmd)
        self.assertIn("--targets-json", cmd)

    def test_deeplx_translator_retries_urlerror_then_succeeds(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"data":"hello"}'

        call_count = 0
        sleep_calls = []
        original_urlopen = sidebar.request.urlopen
        original_sleep = sidebar.time.sleep

        def fake_urlopen(req, timeout):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise error.URLError("timeout")
            return FakeResponse()

        sidebar.request.urlopen = fake_urlopen
        sidebar.time.sleep = sleep_calls.append
        try:
            translator = sidebar.DeepLXTranslator("http://127.0.0.1:1188/translate")
            result = translator.translate("你好")
        finally:
            sidebar.request.urlopen = original_urlopen
            sidebar.time.sleep = original_sleep

        self.assertEqual(result, "hello")
        self.assertEqual(call_count, 3)
        self.assertEqual(
            sleep_calls,
            [
                sidebar.DEEPLX_RETRY_BACKOFF_SECONDS,
                sidebar.DEEPLX_RETRY_BACKOFF_SECONDS * 2,
            ],
        )

    def test_append_message_with_limit(self):
        cache = []
        for idx in range(5):
            msg = sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="u",
                text_en=f"m{idx}",
                created_at="10:00:00",
                is_self=False,
            )
            sidebar.append_message_with_limit(cache, msg, limit=3)
        self.assertEqual(len(cache), 3)
        self.assertEqual([item.text_en for item in cache], ["m2", "m3", "m4"])

    def test_replace_message_in_cache_matches_message_id(self):
        cache = [
            sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="u",
                text_en="Loading...",
                created_at="10:00:00",
                is_self=False,
                message_id="msg-1",
                pending_translation=True,
            )
        ]
        replacement = sidebar.SidebarMessage(
            chat_name="g1",
            sender_name="u",
            text_en="hello",
            created_at="10:00:00",
            is_self=False,
            message_id="msg-1",
            pending_translation=False,
        )

        replaced = sidebar.replace_message_in_cache(cache, replacement)

        self.assertTrue(replaced)
        self.assertEqual(cache[0].text_en, "hello")
        self.assertFalse(cache[0].pending_translation)

    def test_append_message_active_chat_rerenders_from_cache(self):
        ui = object.__new__(sidebar.SidebarUI)
        ui.chat_messages = {"g1": []}
        ui.unread_counts = {"g1": 0}
        ui.chat_order = ["g1"]
        ui.active_chat = "g1"
        ui.message_limit = 2
        ui._ensure_chat = lambda chat_name: True
        ui._refresh_target_list = lambda: None

        render_calls = []
        insert_calls = []
        ui._render_active_chat = lambda: render_calls.append(
            [item.text_en for item in ui.chat_messages["g1"]]
        )
        ui._insert_message = lambda msg: insert_calls.append(msg.text_en)

        for idx in range(3):
            msg = sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="u",
                text_en=f"m{idx}",
                created_at="10:00:00",
                is_self=False,
            )
            sidebar.SidebarUI.append_message(ui, msg)

        self.assertEqual(render_calls[-1], ["m1", "m2"])
        self.assertEqual(insert_calls, [])

    def test_replace_message_active_chat_rerenders_without_new_unread(self):
        ui = object.__new__(sidebar.SidebarUI)
        ui.chat_messages = {
            "g1": [
                sidebar.SidebarMessage(
                    chat_name="g1",
                    sender_name="u",
                    text_en="Loading...",
                    created_at="10:00:00",
                    is_self=False,
                    message_id="msg-1",
                    pending_translation=True,
                )
            ]
        }
        ui.unread_counts = {"g1": 1}
        ui.active_chat = "g1"
        ui._ensure_chat = lambda chat_name: True
        calls = []
        ui._update_active_chat_summary = lambda: calls.append("summary")
        ui._render_active_chat = lambda: calls.append("render")

        replaced = sidebar.SidebarUI.replace_message(
            ui,
            sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="u",
                text_en="hello",
                created_at="10:00:00",
                is_self=False,
                message_id="msg-1",
                pending_translation=False,
            ),
        )

        self.assertTrue(replaced)
        self.assertEqual(ui.chat_messages["g1"][0].text_en, "hello")
        self.assertEqual(ui.unread_counts["g1"], 1)
        self.assertEqual(calls, ["render"])

    def test_build_worker_status_text(self):
        text = sidebar.build_worker_status_text(
            "waiting_wechat",
            "wechat not ready, retry in 10.0s",
            3,
        )
        self.assertEqual(text, "等待微信")
        self.assertEqual(sidebar.build_worker_status_text("running", "", 3), "")

    def test_compute_worker_restart_delay_caps(self):
        self.assertEqual(sidebar.compute_worker_restart_delay(1), 3.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(2), 6.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(3), 12.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(4), 24.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(5), 30.0)
        self.assertEqual(sidebar.compute_worker_restart_delay(9), 30.0)

    def test_truncate_target_label(self):
        self.assertEqual(sidebar.truncate_target_label("测试群123"), "测试群123")
        self.assertEqual(sidebar.truncate_target_label("测试群1234"), "测试群123...")
        self.assertEqual(sidebar.truncate_target_label("ABCDEFG"), "ABCDEF...")

    def test_toggle_target_panel_shortcut_returns_break(self):
        ui = object.__new__(sidebar.SidebarUI)
        calls = []
        ui.toggle_target_panel = lambda: calls.append("toggle")

        result = sidebar.SidebarUI.on_toggle_target_panel_shortcut(ui)

        self.assertEqual(calls, ["toggle"])
        self.assertEqual(result, "break")

    def test_toggle_auto_read_syncs_runtime_flag_from_var(self):
        class FakeVar:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        ui = object.__new__(sidebar.SidebarUI)
        ui.tts_auto_read_var = FakeVar(False)
        ui.tts_auto_read_active_chat = True

        sidebar.SidebarUI.toggle_auto_read(ui)

        self.assertFalse(ui.tts_auto_read_active_chat)

    def test_chat_switch_shortcut_wraps_and_debounces(self):
        ui = object.__new__(sidebar.SidebarUI)
        ui.chat_order = ["g1", "g2", "g3"]
        ui.active_chat = "g1"
        ui._last_chat_switch_shortcut_at = 0.0
        switched = []

        def fake_switch_chat(name):
            switched.append(name)
            ui.active_chat = name

        original_time = sidebar.time.time
        times = iter([10.0, 10.05, 10.30])
        sidebar.time.time = lambda: next(times)
        ui.switch_chat = fake_switch_chat
        try:
            sidebar.SidebarUI._handle_chat_switch_shortcut(ui, -1)
            sidebar.SidebarUI._handle_chat_switch_shortcut(ui, 1)
            sidebar.SidebarUI._handle_chat_switch_shortcut(ui, 1)
        finally:
            sidebar.time.time = original_time

        self.assertEqual(switched, ["g3", "g1"])

    def test_append_message_ignores_unknown_chat_when_targets_fixed(self):
        ui = object.__new__(sidebar.SidebarUI)
        ui.allowed_chat_names = {"g1"}
        ui.chat_messages = {"g1": []}
        ui.unread_counts = {"g1": 0}
        ui.chat_order = ["g1"]
        ui.active_chat = "g1"
        ui.message_limit = 2
        ui._refresh_target_list = lambda: None
        ui._render_active_chat = lambda: (_ for _ in ()).throw(AssertionError("should not render"))

        sidebar.SidebarUI.append_message(
            ui,
            sidebar.SidebarMessage(
                chat_name="unexpected",
                sender_name="u",
                text_en="hello",
                created_at="10:00:00",
                is_self=False,
            ),
        )

        self.assertEqual(ui.chat_order, ["g1"])
        self.assertEqual(ui.chat_messages["g1"], [])

    def test_insert_message_content_uses_original_text_when_toggle_enabled(self):
        class FakeVar:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class FakeText:
            def __init__(self):
                self.calls = []

            def insert(self, *_args):
                self.calls.append(_args)

        ui = object.__new__(sidebar.SidebarUI)
        ui.show_original_var = FakeVar(True)
        ui.tts_player = object()
        ui.text = FakeText()

        sidebar.SidebarUI._insert_message_content(
            ui,
            sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="高钰",
                text_en="Ahem.",
                text_cn="咳",
                created_at="18:04:41",
                is_self=False,
                pending_translation=True,
            ),
        )

        self.assertEqual(ui.text.calls[1][1], "咳")
        self.assertEqual(ui.text.calls[1][2], "msg_left")
        self.assertEqual(ui.text.calls[2][1], "\n")
        self.assertEqual(ui.text.calls[2][2], "msg_left")

    def test_insert_message_content_marks_body_clickable_for_english_message(self):
        class FakeVar:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class FakeText:
            def __init__(self):
                self.calls = []

            def insert(self, *_args):
                self.calls.append(_args)

            def tag_configure(self, *_args, **_kwargs):
                return None

            def tag_bind(self, *_args, **_kwargs):
                return None

            def configure(self, *_args, **_kwargs):
                return None

        ui = object.__new__(sidebar.SidebarUI)
        ui.show_original_var = FakeVar(False)
        ui.tts_player = object()
        ui.text = FakeText()
        ui._tts_action_tags = {}
        ui._tts_action_index = 0
        ui._tts_body_click_press = None
        ui._tts_body_click_pending_after_id = ""
        ui._tts_body_click_pending_tag = ""

        sidebar.SidebarUI._insert_message_content(
            ui,
            sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="高钰",
                text_en="Ahem.",
                text_cn="咳",
                created_at="18:04:41",
                is_self=False,
                message_id="msg-1",
            ),
        )

        self.assertEqual(ui.text.calls[1][1], "Ahem.")
        self.assertEqual(ui.text.calls[1][2], ("msg_left", "tts_body_action_1"))
        self.assertEqual(ui.text.calls[2][1], "\n")
        self.assertEqual(ui.text.calls[2][2], "msg_left")

    def test_insert_message_content_keeps_body_clickable_when_display_includes_cn(self):
        class FakeVar:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class FakeText:
            def __init__(self):
                self.calls = []

            def insert(self, *_args):
                self.calls.append(_args)

            def tag_configure(self, *_args, **_kwargs):
                return None

            def tag_bind(self, *_args, **_kwargs):
                return None

            def configure(self, *_args, **_kwargs):
                return None

        ui = object.__new__(sidebar.SidebarUI)
        ui.show_original_var = FakeVar(False)
        ui.tts_player = object()
        ui.text = FakeText()
        ui._tts_action_tags = {}
        ui._tts_action_index = 0
        ui._tts_body_click_press = None
        ui._tts_body_click_pending_after_id = ""
        ui._tts_body_click_pending_tag = ""

        sidebar.SidebarUI._insert_message_content(
            ui,
            sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="高钰",
                text_en="Ahem.",
                text_display="Ahem.\nCN: 咳",
                text_cn="咳",
                created_at="18:04:41",
                is_self=False,
                message_id="msg-1",
            ),
        )

        self.assertEqual(ui.text.calls[1][1], "Ahem.\nCN: 咳")
        self.assertEqual(ui.text.calls[1][2], ("msg_left", "tts_body_action_1"))
        self.assertEqual(ui.text.calls[2][1], "\n")
        self.assertEqual(ui.text.calls[2][2], "msg_left")

    def test_should_render_tts_action_hides_button_for_original_mode_or_non_english(self):
        class FakeVar:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        ui = object.__new__(sidebar.SidebarUI)
        ui.show_original_var = FakeVar(False)
        ui.tts_player = object()

        self.assertTrue(
            sidebar.SidebarUI._should_render_tts_action(
                ui,
                sidebar.SidebarMessage(
                    chat_name="g1",
                    sender_name="高钰",
                    text_en="Ahem.",
                    text_cn="咳",
                    created_at="18:04:41",
                    is_self=False,
                ),
                "Ahem.",
            )
        )

        ui.show_original_var = FakeVar(True)
        self.assertFalse(
            sidebar.SidebarUI._should_render_tts_action(
                ui,
                sidebar.SidebarMessage(
                    chat_name="g1",
                    sender_name="高钰",
                    text_en="Ahem.",
                    text_cn="咳",
                    created_at="18:04:41",
                    is_self=False,
                ),
                "Ahem.",
            )
        )

        ui.show_original_var = FakeVar(False)
        self.assertFalse(
            sidebar.SidebarUI._should_render_tts_action(
                ui,
                sidebar.SidebarMessage(
                    chat_name="g1",
                    sender_name="高钰",
                    text_en="咳",
                    text_cn="咳",
                    created_at="18:04:41",
                    is_self=False,
                ),
                "咳",
            )
        )

    def test_on_tts_body_click_reads_bound_english_text(self):
        class FakePlayer:
            def __init__(self):
                self.calls = []

            def speak_async(self, text):
                self.calls.append(text)
                return True

        ui = object.__new__(sidebar.SidebarUI)
        ui.tts_player = FakePlayer()
        ui.runtime_logger = None
        ui._tts_action_tags = {"tts_body_action_1": "Ahem."}
        ui._tts_body_click_pending_after_id = ""
        ui._tts_body_click_pending_tag = ""

        result = sidebar.SidebarUI._execute_pending_tts_body_click(ui, "tts_body_action_1")

        self.assertEqual(ui.tts_player.calls, ["Ahem."])
        self.assertEqual(result, "break")

    def test_execute_pending_tts_body_click_logs_rejected_result(self):
        class FakePlayer:
            def speak_async(self, _text):
                return False

        class FakeText:
            def tag_ranges(self, *_args):
                return ()

        ui = object.__new__(sidebar.SidebarUI)
        ui.tts_player = FakePlayer()
        ui.text = FakeText()
        logs = []
        ui.runtime_logger = logs.append
        ui._tts_action_tags = {"tts_body_action_1": "Ahem."}
        ui._tts_body_click_pending_after_id = ""
        ui._tts_body_click_pending_tag = ""

        result = sidebar.SidebarUI._execute_pending_tts_body_click(ui, "tts_body_action_1")

        self.assertEqual(result, "break")
        self.assertTrue(any("tts body click rejected" in line for line in logs))

    def test_execute_pending_tts_body_click_ignores_selection(self):
        class FakePlayer:
            def __init__(self):
                self.calls = []

            def speak_async(self, text):
                self.calls.append(text)
                return True

        class FakeText:
            def tag_ranges(self, *_args):
                return ("1.0", "1.3")

        ui = object.__new__(sidebar.SidebarUI)
        ui.tts_player = FakePlayer()
        ui.text = FakeText()
        logs = []
        ui.runtime_logger = logs.append
        ui._tts_action_tags = {"tts_body_action_1": "Ahem."}
        ui._tts_body_click_pending_after_id = ""
        ui._tts_body_click_pending_tag = ""

        result = sidebar.SidebarUI._execute_pending_tts_body_click(ui, "tts_body_action_1")

        self.assertEqual(result, "break")
        self.assertEqual(ui.tts_player.calls, [])
        self.assertTrue(any("tts body click ignored reason=selection" in line for line in logs))

    def test_on_tts_body_release_schedules_click_when_move_small(self):
        class FakeEvent:
            x = 13
            y = 14

        ui = object.__new__(sidebar.SidebarUI)
        ui._tts_body_click_press = {"tag": "tts_body_action_1", "x": 10, "y": 12}
        scheduled = []
        ui._schedule_tts_body_click_play = scheduled.append
        ui._is_tts_body_tag_hit = lambda tag, event=None: tag == "tts_body_action_1"

        sidebar.SidebarUI._on_tts_body_release(ui, "tts_body_action_1", FakeEvent())

        self.assertEqual(scheduled, ["tts_body_action_1"])

    def test_on_tts_body_release_ignores_drag_selection_motion(self):
        class FakeEvent:
            x = 30
            y = 12

        ui = object.__new__(sidebar.SidebarUI)
        ui._tts_body_click_press = {"tag": "tts_body_action_1", "x": 10, "y": 12}
        scheduled = []
        ui._schedule_tts_body_click_play = scheduled.append
        ui._is_tts_body_tag_hit = lambda tag, event=None: tag == "tts_body_action_1"

        sidebar.SidebarUI._on_tts_body_release(ui, "tts_body_action_1", FakeEvent())

        self.assertEqual(scheduled, [])

    def test_on_tts_body_multi_click_cancels_pending_click(self):
        ui = object.__new__(sidebar.SidebarUI)
        ui._tts_body_click_press = {"tag": "tts_body_action_1", "x": 10, "y": 12}
        cancelled = []
        ui._cancel_pending_tts_body_click = lambda: cancelled.append(True)

        sidebar.SidebarUI._on_tts_body_multi_click(ui)

        self.assertIsNone(ui._tts_body_click_press)
        self.assertEqual(cancelled, [True])

    def test_maybe_auto_read_message_only_reads_active_chat_when_enabled(self):
        class FakeVar:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class FakePlayer:
            def __init__(self):
                self.calls = []

            def speak_async(self, text):
                self.calls.append(text)
                return True

        ui = object.__new__(sidebar.SidebarUI)
        ui.show_original_var = FakeVar(False)
        ui.tts_auto_read_var = FakeVar(True)
        ui.tts_player = FakePlayer()
        ui.tts_auto_read_active_chat = True
        ui.active_chat = "g1"

        self.assertTrue(
            sidebar.SidebarUI.maybe_auto_read_message(
                ui,
                sidebar.SidebarMessage(
                    chat_name="g1",
                    sender_name="高钰",
                    text_en="Ahem.",
                    text_cn="咳",
                    created_at="18:04:41",
                    is_self=False,
                ),
            )
        )
        self.assertEqual(ui.tts_player.calls, ["Ahem."])

        self.assertFalse(
            sidebar.SidebarUI.maybe_auto_read_message(
                ui,
                sidebar.SidebarMessage(
                    chat_name="g2",
                    sender_name="高钰",
                    text_en="You know.",
                    text_cn="你知道。",
                    created_at="18:04:42",
                    is_self=False,
                ),
            )
        )

        ui.show_original_var = FakeVar(True)
        self.assertFalse(
            sidebar.SidebarUI.maybe_auto_read_message(
                ui,
                sidebar.SidebarMessage(
                    chat_name="g1",
                    sender_name="高钰",
                    text_en="Ahem.",
                    text_cn="咳",
                    created_at="18:04:43",
                    is_self=False,
                ),
            )
        )

        ui.show_original_var = FakeVar(False)
        ui.tts_auto_read_var = FakeVar(False)
        self.assertFalse(
            sidebar.SidebarUI.maybe_auto_read_message(
                ui,
                sidebar.SidebarMessage(
                    chat_name="g1",
                    sender_name="高钰",
                    text_en="Ahem.",
                    text_cn="咳",
                    created_at="18:04:44",
                    is_self=False,
                ),
            )
        )

    def test_maybe_auto_read_message_reads_english_text_even_when_display_is_bilingual(self):
        class FakeVar:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class FakePlayer:
            def __init__(self):
                self.calls = []

            def speak_async(self, text):
                self.calls.append(text)
                return True

        ui = object.__new__(sidebar.SidebarUI)
        ui.show_original_var = FakeVar(False)
        ui.tts_player = FakePlayer()
        ui.tts_auto_read_active_chat = True
        ui.active_chat = "g1"

        self.assertTrue(
            sidebar.SidebarUI.maybe_auto_read_message(
                ui,
                sidebar.SidebarMessage(
                    chat_name="g1",
                    sender_name="高钰",
                    text_en="Ahem.",
                    text_display="Ahem.\nCN: 咳",
                    text_cn="咳",
                    created_at="18:04:41",
                    is_self=False,
                ),
            )
        )
        self.assertEqual(ui.tts_player.calls, ["Ahem."])

    def test_maybe_auto_read_message_logs_skip_reason_for_pending_translation(self):
        class FakeVar:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        ui = object.__new__(sidebar.SidebarUI)
        ui.show_original_var = FakeVar(False)
        ui.tts_auto_read_var = FakeVar(True)
        ui.tts_auto_read_active_chat = True
        ui.active_chat = "g1"
        ui.tts_player = object()
        logs = []
        ui.runtime_logger = logs.append

        result = sidebar.SidebarUI.maybe_auto_read_message(
            ui,
            sidebar.SidebarMessage(
                chat_name="g1",
                sender_name="高钰",
                text_en="Loading...",
                text_cn="咳",
                created_at="18:04:41",
                is_self=False,
                pending_translation=True,
            ),
        )

        self.assertFalse(result)
        self.assertTrue(
            any("tts auto skipped chat=g1 reason=pending_translation" in line for line in logs)
        )


if __name__ == "__main__":
    unittest.main()
