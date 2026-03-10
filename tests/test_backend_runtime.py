import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from listener_app.backend_runtime import BackendRuntimeService


class FakeWorkerProcess:
    def __init__(self):
        self.pid = 4321
        self.stdout = []
        self.stderr = []
        self._return_code = None

    def poll(self):
        return self._return_code

    def terminate(self):
        self._return_code = 0

    def kill(self):
        self._return_code = -9


class FakeTTSPlayer:
    def __init__(self):
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    def speak_async(self, text: str) -> bool:
        return bool(text)


class BackendRuntimeTest(unittest.TestCase):
    def _write_config(self) -> str:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "listener.json"
        payload = {
            "listen": {
                "mode": "session",
                "targets": ["测试群"],
                "interval_seconds": 0.6,
                "load_retry_seconds": 1.0,
            },
            "translate": {
                "enabled": False,
                "provider": "passthrough",
            },
            "display": {
                "english_only": True,
                "tts_auto_read_active_chat": True,
            },
            "tts": {
                "provider": "windows_system",
            },
            "logging": {
                "file": "",
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
        return str(path)

    @mock.patch("listener_app.backend_runtime.release_managed_target_locks")
    @mock.patch("listener_app.backend_runtime.set_managed_target_lock_paths")
    @mock.patch("listener_app.backend_runtime.acquire_target_lock", return_value=(True, "fake.lock"))
    @mock.patch("listener_app.backend_runtime.cleanup_stale_target_locks", return_value=0)
    @mock.patch("listener_app.backend_runtime.create_tts_player", return_value=(FakeTTSPlayer(), "tts ready"))
    @mock.patch("listener_app.backend_runtime.start_worker_process", return_value=FakeWorkerProcess())
    def test_start_and_stop_without_tk(
        self,
        _start_worker_process,
        _create_tts_player,
        _cleanup_stale_target_locks,
        _acquire_target_lock,
        _set_managed_target_lock_paths,
        _release_managed_target_locks,
    ):
        service = BackendRuntimeService(config_path=self._write_config())
        service.start()
        time.sleep(0.05)
        snapshot = service.snapshot()
        self.assertEqual(snapshot["translation"]["provider"], "passthrough")
        self.assertEqual(snapshot["tts"]["provider"], "windows_system")
        self.assertTrue(snapshot["tts"]["available"])
        service.stop()

    def test_message_event_creates_preview_message(self):
        service = BackendRuntimeService(config_path=self._write_config())
        service.settings = mock.Mock(
            session_preview_dedupe_window_seconds=20.0,
            translate_fail_behavior="show_cn_with_reason",
            translate_enabled=False,
            english_only=True,
            tts_auto_read_active_chat=False,
            tts_player=None,
        )
        service._running_targets = ["测试群"]
        service._handle_event(
            {
                "type": "message",
                "chat_name": "测试群",
                "text": "张三: hello",
                "created_at": "10:00",
            }
        )
        messages = service.get_session_messages("测试群")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["capture_level"], "preview")


if __name__ == "__main__":
    unittest.main()
