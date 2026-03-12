from __future__ import annotations

import os
import sys
import time

if __package__:
    from .backend_runtime import BackendRuntimeService, build_arg_parser
    from .runtime_api import RuntimeApiServer
    from .sidebar_shared import load_json_config
    from .sidebar_tts import check_tts_dependency_packaging
else:
    from backend_runtime import BackendRuntimeService, build_arg_parser
    from runtime_api import RuntimeApiServer
    from sidebar_shared import load_json_config
    from sidebar_tts import check_tts_dependency_packaging

STARTUP_FAILURE_GRACE_SECONDS = 5.0


def main() -> None:
    parser = build_arg_parser()
    parser.add_argument("--host", default="127.0.0.1", help="Local bind host")
    parser.add_argument("--http-port", default=8765, type=int, help="Local HTTP port")
    parser.add_argument("--ws-port", default=8766, type=int, help="Local WebSocket port")
    parser.add_argument(
        "--check-tts-deps",
        action="store_true",
        help="Validate packaged TTS Python dependencies and exit",
    )
    args = parser.parse_args()
    config_path = os.path.abspath(args.config)

    if args.check_tts_deps:
        try:
            config = load_json_config(config_path)
        except Exception as exc:
            print(f"[backend] tts dependency check failed: load config failed: {exc}", file=sys.stderr)
            raise SystemExit(2)
        tts_cfg = config.get("tts", {}) if isinstance(config.get("tts", {}), dict) else {}
        try:
            ok, detail = check_tts_dependency_packaging(tts_cfg)
        except RuntimeError as exc:
            print(f"[backend] tts dependency check failed: {exc}", file=sys.stderr)
            raise SystemExit(2)
        stream = sys.stdout if ok else sys.stderr
        print(f"[backend] {detail}", file=stream, flush=True)
        raise SystemExit(0 if ok else 2)

    service = BackendRuntimeService(config_path=config_path)
    api_server = RuntimeApiServer(
        service,
        host=args.host,
        http_port=args.http_port,
        ws_port=args.ws_port,
    )
    api_server.start()
    startup_failed_exit_code = 0
    startup_failure_deadline = 0.0
    try:
        service.start()
    except Exception as exc:
        startup_failed_exit_code = 2
        service.mark_startup_failed(str(exc))
        print(f"[backend] startup failed: {exc}", file=sys.stderr, flush=True)
        startup_failure_deadline = time.time() + STARTUP_FAILURE_GRACE_SECONDS
    try:
        while True:
            time.sleep(0.5)
            if startup_failed_exit_code and time.time() >= startup_failure_deadline:
                raise SystemExit(startup_failed_exit_code)
    except KeyboardInterrupt:
        pass
    finally:
        api_server.stop()
        service.stop()


if __name__ == "__main__":
    main()
