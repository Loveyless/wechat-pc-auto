from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from shutil import which


REPO_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_SHELL_ROOT = REPO_ROOT / "desktop-shell"
SRC_TAURI_ROOT = DESKTOP_SHELL_ROOT / "src-tauri"
DEFAULT_SHELL_EXE = SRC_TAURI_ROOT / "target" / "release" / "wechat-auto-shell.exe"
DEFAULT_RUNTIME_ROOT = Path(os.environ["LOCALAPPDATA"]) / "com.wechatauto.shell"
DEFAULT_HEALTH_URL = "http://127.0.0.1:8765/healthz"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and smoke-test the Tauri desktop shell release flow."
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip `npm run tauri build` and use an existing release executable.",
    )
    parser.add_argument(
        "--shell-exe",
        default=str(DEFAULT_SHELL_EXE),
        help="Path to wechat-auto-shell.exe",
    )
    parser.add_argument(
        "--runtime-root",
        default=str(DEFAULT_RUNTIME_ROOT),
        help="Expected runtime root used by the shell.",
    )
    parser.add_argument(
        "--health-url",
        default=DEFAULT_HEALTH_URL,
        help="Backend health endpoint exposed by the shell-managed sidecar.",
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=45.0,
        help="Seconds to wait for /healthz and relaunch logs.",
    )
    parser.add_argument(
        "--relaunch-grace",
        type=float,
        default=10.0,
        help="Seconds to wait for the second launch to hand control back to the first instance.",
    )
    return parser.parse_args()


def run_command(args: list[str], *, cwd: Path, step: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
        raise RuntimeError(f"{step} failed with exit code {result.returncode}")
    return result


def resolve_tool_path(tool: str) -> str:
    candidates = [tool]
    if os.name == "nt" and "." not in Path(tool).name:
        candidates.extend([f"{tool}.cmd", f"{tool}.exe", f"{tool}.bat"])
    for candidate in candidates:
        resolved = which(candidate)
        if resolved:
            return resolved
    raise RuntimeError(f"required tool not found on PATH: {tool}")


def is_backend_healthy(health_url: str) -> bool:
    try:
        with urllib.request.urlopen(health_url, timeout=1.5) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False
    return payload.get("status") == "ok"


def wait_for_backend_ready(health_url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_backend_healthy(health_url):
            return
        time.sleep(0.5)
    raise RuntimeError(f"backend never became healthy within {timeout:.1f}s: {health_url}")


def bootstrap_log_path(runtime_root: Path) -> Path:
    return runtime_root / "logs" / "desktop-shell-bootstrap.log"


def read_log_delta(log_path: Path, start_offset: int) -> str:
    if not log_path.exists():
        return ""
    with log_path.open("rb") as handle:
        handle.seek(start_offset)
        return handle.read().decode("utf-8", errors="replace")


def launch_process(executable: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [str(executable)],
        cwd=str(executable.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def force_kill_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    subprocess.run(
        [resolve_tool_path("taskkill"), "/PID", str(process.pid), "/T", "/F"],
        capture_output=True,
        check=False,
    )
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def ensure_clean_start(health_url: str) -> None:
    if is_backend_healthy(health_url):
        raise RuntimeError(
            "health endpoint is already up before smoke test; stop the existing shell/backend first"
        )


def maybe_build_release(skip_build: bool) -> None:
    if skip_build:
        return
    run_command(
        [resolve_tool_path("npm"), "run", "tauri", "--", "build"],
        cwd=DESKTOP_SHELL_ROOT,
        step="Tauri release build",
    )


def assert_log_contains(log_delta: str, needle: str, *, timeout: float, log_path: Path, start_offset: int) -> str:
    deadline = time.time() + timeout
    current = log_delta
    while time.time() < deadline:
        if needle in current:
            return current
        time.sleep(0.5)
        current = read_log_delta(log_path, start_offset)
    raise RuntimeError(f"missing bootstrap log line: {needle}")


def main() -> None:
    args = parse_args()
    shell_exe = Path(args.shell_exe).resolve()
    runtime_root = Path(args.runtime_root).resolve()
    log_path = bootstrap_log_path(runtime_root)
    log_offset = log_path.stat().st_size if log_path.exists() else 0

    ensure_clean_start(args.health_url)
    maybe_build_release(args.skip_build)
    if not shell_exe.exists():
        raise RuntimeError(f"missing shell executable: {shell_exe}")

    first_shell = launch_process(shell_exe)
    second_shell: subprocess.Popen[bytes] | None = None
    try:
        wait_for_backend_ready(args.health_url, args.ready_timeout)
        log_delta = read_log_delta(log_path, log_offset)
        log_delta = assert_log_contains(
            log_delta,
            "spawning backend sidecar",
            timeout=args.ready_timeout,
            log_path=log_path,
            start_offset=log_offset,
        )

        second_shell = launch_process(shell_exe)
        second_shell.wait(timeout=args.relaunch_grace)
        log_delta = assert_log_contains(
            log_delta,
            "single-instance relaunch detected, focus existing window",
            timeout=args.ready_timeout,
            log_path=log_path,
            start_offset=log_offset,
        )

        if log_delta.count("spawning backend sidecar") != 1:
            raise RuntimeError("expected exactly one backend sidecar spawn during smoke test")
        if not is_backend_healthy(args.health_url):
            raise RuntimeError("backend lost readiness after second launch")

        print(f"Release smoke passed: {shell_exe}")
        print(f"Verified health endpoint: {args.health_url}")
        print(f"Verified bootstrap log: {log_path}")
    finally:
        if second_shell is not None:
            force_kill_process_tree(second_shell)
        force_kill_process_tree(first_shell)


if __name__ == "__main__":
    main()
