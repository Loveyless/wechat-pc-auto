import unittest
from io import StringIO
from unittest import mock

from listener_app import backend_main


class BackendMainTest(unittest.TestCase):
    def test_main_keeps_api_alive_long_enough_to_report_startup_failed(self):
        order = []
        stdout = StringIO()
        stderr = StringIO()

        class FakeService:
            def __init__(self, config_path):
                self.config_path = config_path
                self.marked_error = ""
                self.stopped = False

            def start(self):
                order.append("service.start")
                raise RuntimeError("boom")

            def mark_startup_failed(self, detail):
                order.append("service.mark_startup_failed")
                self.marked_error = detail

            def stop(self):
                order.append("service.stop")
                self.stopped = True

        class FakeApiServer:
            def __init__(self, service, **_kwargs):
                self.service = service

            def start(self):
                order.append("api.start")

            def stop(self):
                order.append("api.stop")

        with mock.patch.object(backend_main, "BackendRuntimeService", FakeService), mock.patch.object(
            backend_main,
            "RuntimeApiServer",
            FakeApiServer,
        ), mock.patch.object(
            backend_main,
            "STARTUP_FAILURE_GRACE_SECONDS",
            0.0,
        ), mock.patch(
            "sys.argv",
            ["backend_main.py", "--config", "config/listener.json"],
        ), mock.patch.dict(
            "os.environ",
            {
                backend_main.OWNER_PID_ENV: "",
                backend_main.OWNER_START_TOKEN_ENV: "",
            },
            clear=False,
        ), mock.patch(
            "sys.stdout",
            stdout,
        ), mock.patch(
            "sys.stderr",
            stderr,
        ):
            with self.assertRaises(SystemExit) as exc_ctx:
                backend_main.main()

        self.assertEqual(exc_ctx.exception.code, 2)
        self.assertEqual(
            order,
            [
                "api.start",
                "service.start",
                "service.mark_startup_failed",
                "api.stop",
                "service.stop",
            ],
        )
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("[backend] startup failed: boom", stderr.getvalue())

    def test_main_exits_when_owner_watchdog_times_out(self):
        order = []
        stdout = StringIO()
        stderr = StringIO()

        class FakeService:
            def __init__(self, config_path):
                self.config_path = config_path

            def start(self):
                order.append("service.start")

            def stop(self):
                order.append("service.stop")

        class FakeApiServer:
            def __init__(self, service, **_kwargs):
                self.service = service

            def start(self):
                order.append("api.start")

            def stop(self):
                order.append("api.stop")

        with mock.patch.object(backend_main, "BackendRuntimeService", FakeService), mock.patch.object(
            backend_main,
            "RuntimeApiServer",
            FakeApiServer,
        ), mock.patch.object(
            backend_main,
            "OWNER_WATCHDOG_POLL_SECONDS",
            0.0,
        ), mock.patch.object(
            backend_main,
            "OWNER_WATCHDOG_GRACE_SECONDS",
            0.5,
        ), mock.patch.object(
            backend_main,
            "is_process_identity_alive",
            return_value=False,
        ), mock.patch.object(
            backend_main.time,
            "sleep",
            return_value=None,
        ), mock.patch.object(
            backend_main.time,
            "time",
            side_effect=[0.0, 1.0],
        ), mock.patch.dict(
            "os.environ",
            {
                backend_main.OWNER_PID_ENV: "4321",
                backend_main.OWNER_START_TOKEN_ENV: "owner-token",
            },
            clear=False,
        ), mock.patch(
            "sys.stdout",
            stdout,
        ), mock.patch(
            "sys.stderr",
            stderr,
        ), mock.patch(
            "sys.argv",
            ["backend_main.py", "--config", "config/listener.json"],
        ):
            with self.assertRaises(SystemExit) as exc_ctx:
                backend_main.main()

        self.assertEqual(exc_ctx.exception.code, 0)
        self.assertEqual(
            order,
            [
                "api.start",
                "service.start",
                "api.stop",
                "service.stop",
            ],
        )
        stdout_text = stdout.getvalue()
        self.assertIn("[backend] owner watchdog enabled pid=4321 probe=0.0s grace=0.5s", stdout_text)
        self.assertIn("[backend] owner watchdog lost owner pid=4321, grace=0.5s", stdout_text)
        self.assertIn(
            "[backend] owner watchdog exiting because owner pid=4321 is gone",
            stdout_text,
        )
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
