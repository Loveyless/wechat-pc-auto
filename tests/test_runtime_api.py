import asyncio
import json
import unittest
from urllib import error, request

from websockets.asyncio.client import connect

from listener_app.runtime_api import RuntimeApiServer
from listener_app.runtime_engine import ListenerRuntime
from listener_app.runtime_config_store import ConfigValidationError


class FakeService:
    def __init__(self):
        self.runtime = ListenerRuntime(message_limit=20)
        self._health = {"status": "starting", "detail": "booting", "worker_state": "idle"}
        self._config = {
            "translate": {
                "enabled": False,
                "provider": "passthrough",
                "available_providers": ["deeplx", "openai_compatible", "passthrough"],
                "source_lang": "auto",
                "target_lang": "EN",
                "providers": {
                    "deeplx": {
                        "timeout_seconds": 8.0,
                        "deeplx_url": {
                            "configured": False,
                            "source": "env",
                            "env_key": "DEEPLX_URL",
                        },
                    },
                    "openai_compatible": {
                        "base_url": "",
                        "model": "",
                        "timeout_seconds": 8.0,
                        "api_key": {"configured": False, "source": "unset"},
                    },
                    "passthrough": {},
                },
            },
            "display": {"english_only": True, "tts_auto_read_active_chat": True},
            "tts": {
                "provider": "windows_system",
                "available_providers": ["windows_system", "doubao", "tencent_cloud"],
                "providers": {
                    "windows_system": {},
                    "doubao": {"config_path": "config/doubao_tts.json"},
                    "tencent_cloud": {"config_path": "config/tencent_tts.json"},
                },
            },
            "runtime": {
                "config_path": "D:/mock/config/listener.json",
                "apply_strategy": "restart_required",
                "restart_required": True,
                "hot_reload_supported": False,
            },
        }
        self._saved_payload = None
        self._save_error: Exception | None = None

    def snapshot(self):
        return self.runtime.snapshot()

    def list_sessions(self):
        return self.runtime.list_sessions()

    def get_session_messages(self, session_id: str):
        return self.runtime.get_session_messages(session_id)

    def get_config_snapshot(self):
        return dict(self._config)

    def save_config_snapshot(self, payload: dict):
        if self._save_error is not None:
            raise self._save_error
        self._saved_payload = dict(payload)
        return dict(self._config)

    def get_health_snapshot(self):
        return dict(self._health)

    def set_active_session(self, session_id: str):
        self.runtime.set_active_session(session_id)

    def _log_line(self, _line: str):
        return None


class RuntimeApiServerTest(unittest.TestCase):
    def setUp(self):
        self.service = FakeService()
        self.server = RuntimeApiServer(self.service, host="127.0.0.1", http_port=0, ws_port=0)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def _json_get(self, path: str) -> dict:
        with request.urlopen(f"{self.server.http_base_url}{path}", timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def _json_post(self, path: str, payload: dict) -> dict:
        raw = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.server.http_base_url}{path}",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def _json_put(self, path: str, payload: dict) -> tuple[int, dict]:
        raw = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.server.http_base_url}{path}",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            with request.urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_http_runtime_endpoint_exposes_cors_headers(self):
        with request.urlopen(f"{self.server.http_base_url}/api/runtime", timeout=3) as response:
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

    def test_http_snapshot_sessions_and_config_endpoints(self):
        self.service.runtime.record_preview_message(
            session_name="测试群",
            text="hello",
            created_at="10:00",
        )
        runtime_payload = self._json_get("/api/runtime")
        sessions_payload = self._json_get("/api/sessions")
        messages_payload = self._json_get("/api/sessions/%E6%B5%8B%E8%AF%95%E7%BE%A4/messages")
        config_payload = self._json_get("/api/config")

        self.assertIn("runtime", runtime_payload)
        self.assertEqual(len(sessions_payload["items"]), 1)
        self.assertEqual(len(messages_payload["items"]), 1)
        self.assertEqual(config_payload["translate"]["provider"], "passthrough")
        self.assertIn("openai_compatible", config_payload["translate"]["providers"])
        self.assertEqual(
            config_payload["tts"]["providers"]["tencent_cloud"]["config_path"],
            "config/tencent_tts.json",
        )

    def test_http_health_endpoint_uses_service_snapshot(self):
        self.service._health = {
            "status": "startup_failed",
            "detail": "missing config",
            "worker_state": "startup_failed",
        }
        health_payload = self._json_get("/healthz")
        self.assertEqual(health_payload["status"], "startup_failed")
        self.assertEqual(health_payload["detail"], "missing config")

    def test_http_health_endpoint_fails_closed_when_service_has_no_health_snapshot(self):
        class MissingHealthService:
            def __init__(self):
                self.runtime = ListenerRuntime(message_limit=20)

            def snapshot(self):
                return self.runtime.snapshot()

            def list_sessions(self):
                return []

            def get_session_messages(self, _session_id: str):
                return []

            def get_config_snapshot(self):
                return {}

            def set_active_session(self, session_id: str):
                self.runtime.set_active_session(session_id)

            def _log_line(self, _line: str):
                return None

        server = RuntimeApiServer(MissingHealthService(), host="127.0.0.1", http_port=0, ws_port=0)
        server.start()
        try:
            with request.urlopen(f"{server.http_base_url}/healthz", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.stop()

        self.assertEqual(payload["status"], "startup_failed")
        self.assertEqual(payload["detail"], "health snapshot unavailable")

    def test_http_active_session_control(self):
        payload = self._json_post("/api/runtime/active-session", {"session_id": "测试群"})
        self.assertEqual(payload["runtime"]["active_session_id"], "测试群")

    def test_http_put_config_returns_saved_snapshot(self):
        status, payload = self._json_put(
            "/api/config",
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
                "secret_updates": {
                    "translate": {
                        "openai_compatible": {
                            "api_key": {
                                "mode": "direct",
                                "value": "token",
                            }
                        }
                    }
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["config"]["runtime"]["config_path"], "D:/mock/config/listener.json")
        self.assertEqual(
            self.service._saved_payload["translate"]["providers"]["openai_compatible"]["model"],
            "gpt-4o-mini",
        )

    def test_http_put_config_returns_field_errors(self):
        self.service._save_error = ConfigValidationError(
            "config validation failed",
            field_errors={"tts.provider": "invalid provider"},
        )
        status, payload = self._json_put("/api/config", {"tts": {"provider": "bad"}})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "validation_failed")
        self.assertEqual(payload["field_errors"]["tts.provider"], "invalid provider")

    def test_websocket_stream_emits_runtime_events(self):
        async def run_test():
            async with connect(self.server.ws_url) as websocket:
                await asyncio.sleep(0.1)
                self.service.runtime.record_preview_message(
                    session_name="测试群",
                    text="hello",
                    created_at="10:00",
                )
                raw = await asyncio.wait_for(websocket.recv(), timeout=2)
                payload = json.loads(raw)
                self.assertEqual(payload["event"], "message.created")

        asyncio.run(run_test())

    def test_websocket_stream_emits_tts_and_error_events(self):
        async def run_test():
            async with connect(self.server.ws_url) as websocket:
                await asyncio.sleep(0.1)
                self.service.runtime.publish_tts_event(
                    action="autoplay",
                    session_id="测试群",
                    message_id="m1",
                    accepted=True,
                )
                first = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
                self.assertEqual(first["event"], "tts.updated")

                self.service.runtime.publish_error(
                    source="translate",
                    message="fallback",
                    detail="timeout",
                )
                second = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
                self.assertEqual(second["event"], "error.reported")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
