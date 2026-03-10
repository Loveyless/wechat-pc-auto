import asyncio
import json
import unittest
from urllib import request

from websockets.asyncio.client import connect

from listener_app.runtime_api import RuntimeApiServer
from listener_app.runtime_engine import ListenerRuntime


class FakeService:
    def __init__(self):
        self.runtime = ListenerRuntime(message_limit=20)
        self._config = {
            "listen": {"mode": "session", "targets": ["测试群"], "interval_seconds": 0.6},
            "translate": {"enabled": False, "provider": "passthrough"},
            "display": {"english_only": True, "tts_auto_read_active_chat": True},
            "tts": {"provider": "windows_system", "available": True},
        }

    def snapshot(self):
        return self.runtime.snapshot()

    def list_sessions(self):
        return self.runtime.list_sessions()

    def get_session_messages(self, session_id: str):
        return self.runtime.get_session_messages(session_id)

    def get_config_snapshot(self):
        return dict(self._config)

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
        self.assertEqual(config_payload["listen"]["mode"], "session")

    def test_http_active_session_control(self):
        payload = self._json_post("/api/runtime/active-session", {"session_id": "测试群"})
        self.assertEqual(payload["runtime"]["active_session_id"], "测试群")

    def test_websocket_stream_emits_runtime_events(self):
        async def run_test():
            async with connect(self.server.ws_url) as websocket:
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
