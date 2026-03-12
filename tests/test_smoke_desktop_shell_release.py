import unittest
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


if __name__ == "__main__":
    unittest.main()
