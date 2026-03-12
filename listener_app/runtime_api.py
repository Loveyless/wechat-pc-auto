from __future__ import annotations

import asyncio
import json
import queue
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlparse

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8765
DEFAULT_WS_PORT = 8766


class RuntimeApiServer:
    def __init__(
        self,
        service: Any,
        *,
        host: str = DEFAULT_HTTP_HOST,
        http_port: int = DEFAULT_HTTP_PORT,
        ws_port: int = DEFAULT_WS_PORT,
    ):
        self.service = service
        self.host = str(host or DEFAULT_HTTP_HOST)
        self.http_port = int(http_port)
        self.ws_port = int(ws_port)
        self._http_server: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._ws_thread: threading.Thread | None = None
        self._ws_loop: asyncio.AbstractEventLoop | None = None
        self._ws_stop_event: asyncio.Event | None = None
        self._ws_ready = threading.Event()

    @property
    def http_base_url(self) -> str:
        return f"http://{self.host}:{self.http_port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.ws_port}/events"

    def start(self) -> None:
        if self._http_server is None:
            handler = self._build_handler_class()
            self._http_server = ThreadingHTTPServer((self.host, self.http_port), handler)
            self.http_port = int(self._http_server.server_address[1])
            self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
            self._http_thread.start()

        if self._ws_thread is None:
            self._ws_thread = threading.Thread(target=self._run_ws_server, daemon=True)
            self._ws_thread.start()
            self._ws_ready.wait(timeout=5)

    def stop(self) -> None:
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
            self._http_server = None
        if self._http_thread and self._http_thread.is_alive():
            self._http_thread.join(timeout=2)
        self._http_thread = None

        if self._ws_loop is not None and self._ws_stop_event is not None:
            self._ws_loop.call_soon_threadsafe(self._ws_stop_event.set)
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=2)
        self._ws_thread = None
        self._ws_loop = None
        self._ws_stop_event = None
        self._ws_ready.clear()

    def _build_handler_class(self):
        service = self.service
        api_server = self

        class RuntimeRequestHandler(BaseHTTPRequestHandler):
            def _send_cors_headers(self) -> None:
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

            def _read_json_body(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                if not raw:
                    return {}
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be JSON object")
                return payload

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self) -> None:
                self.send_response(HTTPStatus.NO_CONTENT)
                self._send_cors_headers()
                self.end_headers()

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                path = parsed.path
                if path == "/healthz":
                    payload_getter = getattr(service, "get_health_snapshot", None)
                    if callable(payload_getter):
                        payload = payload_getter()
                    else:
                        payload = {
                            "status": "startup_failed",
                            "detail": "health snapshot unavailable",
                            "worker_state": "unknown",
                        }
                    self._send_json(HTTPStatus.OK, payload)
                    return
                if path == "/api/runtime":
                    self._send_json(HTTPStatus.OK, service.snapshot())
                    return
                if path == "/api/sessions":
                    self._send_json(HTTPStatus.OK, {"items": service.list_sessions()})
                    return
                if path == "/api/config":
                    self._send_json(HTTPStatus.OK, service.get_config_snapshot())
                    return
                if path.startswith("/api/sessions/") and path.endswith("/messages"):
                    session_path = path[len("/api/sessions/") : -len("/messages")].strip("/")
                    session_id = unquote(session_path)
                    self._send_json(
                        HTTPStatus.OK,
                        {"items": service.get_session_messages(session_id)},
                    )
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                path = parsed.path
                if path != "/api/runtime/active-session":
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                    return
                try:
                    payload = self._read_json_body()
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                session_id = str(payload.get("session_id", "")).strip()
                service.set_active_session(session_id)
                self._send_json(
                    HTTPStatus.OK,
                    {"runtime": service.snapshot().get("runtime", {})},
                )

            def log_message(self, format: str, *args: Any) -> None:
                logger = getattr(service, "_log_line", None)
                if callable(logger):
                    logger(f"http: {format % args}")

        return RuntimeRequestHandler

    def _run_ws_server(self) -> None:
        asyncio.run(self._serve_ws())

    async def _serve_ws(self) -> None:
        self._ws_loop = asyncio.get_running_loop()
        self._ws_stop_event = asyncio.Event()
        async with serve(self._handle_ws, self.host, self.ws_port) as server:
            sockets = getattr(server, "sockets", None) or []
            if sockets:
                self.ws_port = int(sockets[0].getsockname()[1])
            self._ws_ready.set()
            await self._ws_stop_event.wait()

    async def _handle_ws(self, websocket) -> None:
        if websocket.request.path != "/events":
            await websocket.close(code=1008, reason="unsupported path")
            return

        subscriber = self.service.runtime.subscribe()
        loop = asyncio.get_running_loop()
        try:
            while True:
                try:
                    event = await loop.run_in_executor(None, subscriber.get, True, 0.25)
                except queue.Empty:
                    if websocket.state.name.lower() != "open":
                        return
                    continue
                await websocket.send(json.dumps(event.to_dict(), ensure_ascii=False))
        except ConnectionClosed:
            return
        finally:
            self.service.runtime.unsubscribe(subscriber)
