from __future__ import annotations

import time

if __package__:
    from .backend_runtime import BackendRuntimeService, build_arg_parser
    from .runtime_api import RuntimeApiServer
else:
    from backend_runtime import BackendRuntimeService, build_arg_parser
    from runtime_api import RuntimeApiServer


def main() -> None:
    parser = build_arg_parser()
    parser.add_argument("--host", default="127.0.0.1", help="Local bind host")
    parser.add_argument("--http-port", default=8765, type=int, help="Local HTTP port")
    parser.add_argument("--ws-port", default=8766, type=int, help="Local WebSocket port")
    args = parser.parse_args()
    service = BackendRuntimeService(config_path=args.config)
    api_server = RuntimeApiServer(
        service,
        host=args.host,
        http_port=args.http_port,
        ws_port=args.ws_port,
    )
    service.start()
    api_server.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        api_server.stop()
        service.stop()


if __name__ == "__main__":
    main()
