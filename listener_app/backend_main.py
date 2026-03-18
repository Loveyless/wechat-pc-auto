from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

if __package__:
    from .backend_runtime import BackendRuntimeService, build_arg_parser
    from .runtime_api import RuntimeApiServer
    from .sidebar_shared import load_json_config
    from .sidebar_runtime_support import is_process_identity_alive
    from .sidebar_tts import check_tts_dependency_packaging
else:
    from backend_runtime import BackendRuntimeService, build_arg_parser
    from runtime_api import RuntimeApiServer
    from sidebar_shared import load_json_config
    from sidebar_runtime_support import is_process_identity_alive
    from sidebar_tts import check_tts_dependency_packaging

STARTUP_FAILURE_GRACE_SECONDS = 5.0
OWNER_PID_ENV = "WECHAT_AUTO_OWNER_PID"
OWNER_START_TOKEN_ENV = "WECHAT_AUTO_OWNER_START_TOKEN"
OWNER_WATCHDOG_POLL_SECONDS = 3.0
OWNER_WATCHDOG_GRACE_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class OwnerProcessIdentity:
    pid: int
    start_token: str


def load_owner_process_identity() -> OwnerProcessIdentity | None:
    raw_pid = str(os.getenv(OWNER_PID_ENV, "")).strip()
    if not raw_pid:
        return None
    try:
        pid = int(raw_pid)
    except ValueError:
        print(
            f"[backend] ignore invalid owner pid from env {OWNER_PID_ENV}={raw_pid!r}",
            file=sys.stderr,
            flush=True,
        )
        return None
    if pid <= 0:
        return None
    return OwnerProcessIdentity(
        pid=pid,
        start_token=str(os.getenv(OWNER_START_TOKEN_ENV, "")).strip(),
    )


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
    owner_identity = load_owner_process_identity()
    api_server.start()
    startup_failed_exit_code = 0
    startup_failure_deadline = 0.0
    owner_missing_deadline = 0.0
    next_owner_probe_at = 0.0
    if owner_identity is not None:
        print(
            "[backend] owner watchdog enabled "
            f"pid={owner_identity.pid} "
            f"probe={OWNER_WATCHDOG_POLL_SECONDS:.1f}s "
            f"grace={OWNER_WATCHDOG_GRACE_SECONDS:.1f}s",
            file=sys.stderr,
            flush=True,
        )
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
            now_ts = time.time()
            if startup_failed_exit_code and now_ts >= startup_failure_deadline:
                raise SystemExit(startup_failed_exit_code)
            if owner_identity is None or now_ts < next_owner_probe_at:
                continue
            next_owner_probe_at = now_ts + OWNER_WATCHDOG_POLL_SECONDS
            if is_process_identity_alive(owner_identity.pid, owner_identity.start_token):
                if owner_missing_deadline:
                    print(
                        f"[backend] owner watchdog recovered pid={owner_identity.pid}",
                        file=sys.stderr,
                        flush=True,
                    )
                owner_missing_deadline = 0.0
                continue
            if owner_missing_deadline == 0.0:
                owner_missing_deadline = now_ts + OWNER_WATCHDOG_GRACE_SECONDS
                print(
                    "[backend] owner watchdog lost owner "
                    f"pid={owner_identity.pid}, "
                    f"grace={OWNER_WATCHDOG_GRACE_SECONDS:.1f}s",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            if now_ts >= owner_missing_deadline:
                print(
                    f"[backend] owner watchdog exiting because owner pid={owner_identity.pid} is gone",
                    file=sys.stderr,
                    flush=True,
                )
                raise SystemExit(0)
    except KeyboardInterrupt:
        pass
    finally:
        api_server.stop()
        service.stop()


if __name__ == "__main__":
    main()
