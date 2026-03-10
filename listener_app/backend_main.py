from __future__ import annotations

import time

if __package__:
    from .backend_runtime import BackendRuntimeService, build_arg_parser
else:
    from backend_runtime import BackendRuntimeService, build_arg_parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    service = BackendRuntimeService(config_path=args.config)
    service.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()
