import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from listener_app.backend_runtime import (
    BackendRuntimeService,
    HEALTH_STATUS_DEGRADED,
    HEALTH_STATUS_OK,
    HEALTH_STATUS_STARTUP_FAILED,
)


class FakeWorkerProcess:
    def __init__(self):
        self.pid = 4321
        self.stdout = []
        self.stderr = []
        self._return_code = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = []

    def poll(self):
        return self._return_code

    def terminate(self):
        self.terminate_calls += 1
        self._return_code = 0

    def kill(self):
        self.kill_calls += 1
        self._return_code = -9

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self._return_code is None:
            self._return_code = 0
        return self._return_code


class FakeTTSPlayer:
    def __init__(self):
        self.logger = None
        self.spoken = []

    def set_logger(self, logger):
        self.logger = logger

    def speak_async(self, text: str) -> bool:
        self.spoken.append(text)
        return bool(text)


class BackendRuntimeTest(unittest.TestCase):
    def _write_config(self, *, targets: list[str] | None = None) -> str:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "listener.json"
        payload = {
            "listen": {
                "mode": "session",
                "targets": list(targets) if targets is not None else ["测试群"],
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
    @mock.patch("listener_app.backend_runtime.terminate_process_tree")
    def test_start_and_stop_without_tk(
        self,
        terminate_process_tree,
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
        terminate_process_tree.assert_called_once()

    @mock.patch("listener_app.backend_runtime.release_managed_target_locks")
    @mock.patch("listener_app.backend_runtime.set_managed_target_lock_paths")
    @mock.patch("listener_app.backend_runtime.acquire_target_lock", return_value=(True, "fake.lock"))
    @mock.patch("listener_app.backend_runtime.cleanup_stale_target_locks", return_value=0)
    @mock.patch("listener_app.backend_runtime.create_tts_player", return_value=(FakeTTSPlayer(), "tts ready"))
    @mock.patch("listener_app.backend_runtime.start_worker_process", return_value=FakeWorkerProcess())
    @mock.patch("listener_app.backend_runtime.terminate_process_tree")
    def test_start_allows_empty_targets_for_all_sessions_path(
        self,
        terminate_process_tree,
        _start_worker_process,
        _create_tts_player,
        _cleanup_stale_target_locks,
        acquire_target_lock,
        _set_managed_target_lock_paths,
        _release_managed_target_locks,
    ):
        service = BackendRuntimeService(config_path=self._write_config(targets=[]))
        service.start()
        time.sleep(0.05)
        snapshot = service.snapshot()
        self.assertEqual(snapshot["runtime"]["monitor_scope"], "all_sessions")
        acquire_target_lock.assert_not_called()
        service.stop()
        terminate_process_tree.assert_called_once()

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

    def test_active_session_keeps_tts_autoplay_semantics(self):
        service = BackendRuntimeService(config_path=self._write_config())
        player = FakeTTSPlayer()
        service.settings = mock.Mock(
            session_preview_dedupe_window_seconds=20.0,
            translate_fail_behavior="show_cn_with_reason",
            translate_enabled=False,
            english_only=True,
            tts_auto_read_active_chat=True,
            tts_player=player,
        )
        service.runtime.set_runtime_options(
            translate_enabled=False,
            translate_provider="passthrough",
            tts_auto_read_enabled=True,
            tts_provider="windows_system",
            tts_available=True,
        )
        service.set_active_session("测试群")
        q = service.runtime.subscribe()
        service._maybe_auto_tts(
            {
                "session_id": "测试群",
                "message_id": "m1",
                "text_display": "HELLO",
                "text_translated": "HELLO",
            }
        )
        event = q.get(timeout=1)
        self.assertEqual(event.event_type, "tts.updated")
        self.assertEqual(player.spoken, ["HELLO"])

    def test_health_snapshot_reports_ok_when_worker_waits_for_wechat(self):
        service = BackendRuntimeService(config_path=self._write_config())
        service.health.mark_ready()
        service.health.update_runtime("waiting_wechat", "wechat not ready")
        health = service.get_health_snapshot()
        self.assertEqual(health["status"], HEALTH_STATUS_OK)
        self.assertEqual(health["worker_state"], "waiting_wechat")

    def test_health_snapshot_degrades_on_worker_backoff(self):
        service = BackendRuntimeService(config_path=self._write_config())
        service.health.mark_ready()
        service.health.update_runtime("worker_backoff", "retry in 3.0s")
        health = service.get_health_snapshot()
        self.assertEqual(health["status"], HEALTH_STATUS_DEGRADED)

    def test_mark_startup_failed_exposes_failed_health(self):
        service = BackendRuntimeService(config_path=self._write_config())
        service.mark_startup_failed("missing deeplx url")
        health = service.get_health_snapshot()
        self.assertEqual(health["status"], HEALTH_STATUS_STARTUP_FAILED)
        self.assertEqual(health["detail"], "missing deeplx url")

    @mock.patch("listener_app.backend_runtime.release_managed_target_locks")
    @mock.patch("listener_app.backend_runtime.terminate_process_tree")
    def test_stop_uses_process_tree_cleanup_for_worker(
        self,
        terminate_process_tree,
        _release_managed_target_locks,
    ):
        worker = FakeWorkerProcess()
        service = BackendRuntimeService(config_path=self._write_config())
        service._worker = worker
        service.stop()
        terminate_process_tree.assert_called_once_with(worker)
        self.assertIsNone(service._worker)


if __name__ == "__main__":
    unittest.main()
