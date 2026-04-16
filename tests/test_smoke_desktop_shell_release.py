import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import mock

from scripts import smoke_desktop_shell_release as smoke


class SmokeDesktopShellReleaseTest(unittest.TestCase):
    def test_describe_health_payload_includes_detail_and_worker_state(self):
        description = smoke.describe_health_payload(
            {
                "status": "degraded",
                "detail": "worker crashed",
                "worker_state": "worker_backoff",
            }
        )
        self.assertEqual(
            description,
            "status=degraded detail=worker crashed worker_state=worker_backoff",
        )

    def test_wait_for_backend_ready_fails_fast_on_startup_failed(self):
        with mock.patch.object(
            smoke,
            "fetch_backend_health",
            return_value={
                "status": "startup_failed",
                "detail": "missing deeplx url",
                "worker_state": "startup_failed",
            },
        ), mock.patch.object(
            smoke,
            "time",
        ) as time_mock:
            time_mock.time.side_effect = [0.0, 0.0]
            time_mock.sleep.return_value = None
            with self.assertRaises(RuntimeError) as exc_ctx:
                smoke.wait_for_backend_ready(
                    "http://127.0.0.1:8765/healthz",
                    45.0,
                    log_path=Path("unused.log"),
                    start_offset=0,
                )
        self.assertIn("startup_failed", str(exc_ctx.exception))
        self.assertIn("missing deeplx url", str(exc_ctx.exception))

    def test_ensure_clean_start_rejects_any_reachable_health_endpoint(self):
        with mock.patch.object(
            smoke,
            "fetch_backend_health",
            return_value={
                "status": "starting",
                "detail": "initializing backend runtime",
                "worker_state": "idle",
            },
        ):
            with self.assertRaises(RuntimeError) as exc_ctx:
                smoke.ensure_clean_start("http://127.0.0.1:8765/healthz")
        self.assertIn("status=starting", str(exc_ctx.exception))

    def test_fetch_backend_health_marks_invalid_json_as_invalid_payload(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"not-json"

        with mock.patch.object(smoke.urllib.request, "urlopen", return_value=FakeResponse()):
            payload = smoke.fetch_backend_health("http://127.0.0.1:8765/healthz")
        self.assertEqual(payload["status"], "_invalid_payload")
        self.assertEqual(payload["detail"], "health payload is not valid JSON")

    def test_default_runtime_root_uses_macos_app_support(self):
        with mock.patch.object(smoke.os, "name", "posix"), mock.patch.object(
            smoke.Path, "home", return_value=Path("/Users/test")
        ):
            runtime_root = smoke.default_runtime_root()
        self.assertEqual(
            runtime_root,
            Path("/Users/test/Library/Application Support/com.wechatauto.shell"),
        )

    def test_resolve_shell_executable_uses_existing_candidate(self):
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing-shell"
            existing = Path(temp_dir) / "wechat-auto-shell"
            existing.write_text("", encoding="utf-8")
            with mock.patch.object(
                smoke,
                "default_shell_executable_candidates",
                return_value=[missing, existing],
            ):
                resolved = smoke.resolve_shell_executable("")
        self.assertEqual(resolved, existing.resolve())

    def test_force_kill_process_tree_uses_graceful_shutdown_on_posix(self):
        class FakeProcess:
            def __init__(self) -> None:
                self.pid = 123
                self.terminate_called = False
                self.kill_called = False

            def poll(self):
                return None

            def terminate(self):
                self.terminate_called = True

            def wait(self, timeout=None):
                return 0

            def kill(self):
                self.kill_called = True

        process = FakeProcess()
        with mock.patch.object(smoke.os, "name", "posix"):
            smoke.force_kill_process_tree(process)
        self.assertTrue(process.terminate_called)
        self.assertFalse(process.kill_called)

    def test_wait_for_backend_shutdown_succeeds_when_health_disappears(self):
        with mock.patch.object(
            smoke,
            "fetch_backend_health",
            side_effect=[
                {
                    "status": "ok",
                    "detail": "",
                    "worker_state": "running",
                },
                None,
            ],
        ), mock.patch.object(
            smoke,
            "time",
        ) as time_mock:
            time_mock.time.side_effect = [0.0, 0.0, 0.1]
            time_mock.sleep.return_value = None
            smoke.wait_for_backend_shutdown("http://127.0.0.1:8765/healthz", 2.0)


if __name__ == "__main__":
    unittest.main()
