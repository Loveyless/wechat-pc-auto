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
PACKAGING_MANIFEST_PATH = REPO_ROOT / "scripts" / "packaging_manifest.json"
DESKTOP_SHELL_ROOT = REPO_ROOT / "desktop-shell"
SRC_TAURI_ROOT = DESKTOP_SHELL_ROOT / "src-tauri"
DEFAULT_HEALTH_URL = "http://127.0.0.1:8765/healthz"


def load_forbidden_bootstrap_log_patterns() -> tuple[str, ...]:
    try:
        manifest = json.loads(PACKAGING_MANIFEST_PATH.read_text(encoding="utf-8"))
        patterns = manifest["validation"]["release_smoke"]["forbidden_bootstrap_log_patterns"]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"invalid packaging manifest: {PACKAGING_MANIFEST_PATH}"
        ) from exc
    return tuple(str(item) for item in patterns)


FORBIDDEN_BOOTSTRAP_LOG_PATTERNS = load_forbidden_bootstrap_log_patterns()


def default_shell_executable_candidates() -> list[Path]:
    if os.name == "nt":
        return [SRC_TAURI_ROOT / "target" / "release" / "wechat-auto-shell.exe"]
    return [
        SRC_TAURI_ROOT
        / "target"
        / "release"
        / "bundle"
        / "macos"
        / "WeChat Auto Shell.app"
        / "Contents"
        / "MacOS"
        / "wechat-auto-shell",
        SRC_TAURI_ROOT / "target" / "release" / "wechat-auto-shell",
    ]


def default_runtime_root() -> Path:
    if os.name == "nt":
        localappdata = str(os.environ.get("LOCALAPPDATA", "")).strip()
        if localappdata:
            return Path(localappdata) / "com.wechatauto.shell"
        return Path.home() / "AppData" / "Local" / "com.wechatauto.shell"
    return Path.home() / "Library" / "Application Support" / "com.wechatauto.shell"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and smoke-test the packaged desktop shell release flow."
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip `npm run tauri -- build --bundles app` and use an existing release executable.",
    )
    parser.add_argument(
        "--shell-exe",
        default="",
        help="Path to the packaged release shell executable. Omit to auto-detect the current platform default.",
    )
    parser.add_argument(
        "--runtime-root",
        default=str(default_runtime_root()),
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


def resolve_shell_executable(shell_exe: str) -> Path:
    if str(shell_exe).strip():
        return Path(shell_exe).resolve()
    candidates = default_shell_executable_candidates()
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def fetch_backend_health(health_url: str) -> dict[str, str] | None:
    try:
        with urllib.request.urlopen(health_url, timeout=1.5) as response:
            if response.status != 200:
                return {
                    "status": "_http_error",
                    "detail": f"unexpected http status {response.status}",
                    "worker_state": "",
                }
            raw = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "status": "_invalid_payload",
            "detail": "health payload is not valid JSON",
            "worker_state": "",
        }
    if not isinstance(payload, dict):
        return {
            "status": "_invalid_payload",
            "detail": "health payload must be a JSON object",
            "worker_state": "",
        }
    status = str(payload.get("status", "")).strip()
    if not status:
        return {
            "status": "_invalid_payload",
            "detail": "health payload missing status",
            "worker_state": "",
        }
    return {
        "status": status,
        "detail": str(payload.get("detail", "")).strip(),
        "worker_state": str(payload.get("worker_state", "")).strip(),
    }


def is_backend_healthy(health_url: str) -> bool:
    payload = fetch_backend_health(health_url)
    return payload is not None and payload.get("status") == "ok"


def describe_health_payload(payload: dict[str, str]) -> str:
    parts = [f"status={payload.get('status', '').strip() or 'unknown'}"]
    detail = str(payload.get("detail", "")).strip()
    worker_state = str(payload.get("worker_state", "")).strip()
    if detail:
        parts.append(f"detail={detail}")
    if worker_state:
        parts.append(f"worker_state={worker_state}")
    return " ".join(parts)


def summarize_log_delta(log_delta: str, *, max_lines: int = 20) -> str:
    lines = [line for line in log_delta.splitlines() if line.strip()]
    if not lines:
        return "(no bootstrap log output captured)"
    return "\n".join(lines[-max_lines:])


def wait_for_backend_ready(
    health_url: str,
    timeout: float,
    *,
    log_path: Path,
    start_offset: int,
) -> None:
    deadline = time.time() + timeout
    last_health: dict[str, str] | None = None
    while time.time() < deadline:
        health = fetch_backend_health(health_url)
        if health is not None:
            if health.get("status") == "ok":
                return
            last_health = health
            if health.get("status") != "starting":
                raise RuntimeError(
                    f"backend reported non-ready health before timeout: {describe_health_payload(health)}"
                )
        time.sleep(0.5)
    log_delta = read_log_delta(log_path, start_offset)
    fail_on_forbidden_log_patterns(log_delta)
    if last_health is not None:
        raise RuntimeError(
            f"backend never became healthy within {timeout:.1f}s: {health_url}\n"
            f"last health: {describe_health_payload(last_health)}\n"
            f"bootstrap log tail:\n{summarize_log_delta(log_delta)}"
        )
    raise RuntimeError(
        f"backend never became healthy within {timeout:.1f}s: {health_url}\n"
        f"bootstrap log tail:\n{summarize_log_delta(log_delta)}"
    )


def ensure_backend_stays_healthy(health_url: str, *, step: str) -> None:
    health = fetch_backend_health(health_url)
    if health is None:
        raise RuntimeError(f"{step}: health endpoint unavailable")
    if health.get("status") != "ok":
        raise RuntimeError(f"{step}: {describe_health_payload(health)}")


def summarize_non_clean_start(health_url: str) -> str:
    health = fetch_backend_health(health_url)
    if health is None:
        return "health endpoint unavailable"
    return describe_health_payload(health)


def bootstrap_log_path(runtime_root: Path) -> Path:
    return runtime_root / "logs" / "desktop-shell-bootstrap.log"


def read_log_delta(log_path: Path, start_offset: int) -> str:
    if not log_path.exists():
        return ""
    with log_path.open("rb") as handle:
        handle.seek(start_offset)
        return handle.read().decode("utf-8", errors="replace")


def fail_on_forbidden_log_patterns(log_delta: str) -> None:
    for pattern in FORBIDDEN_BOOTSTRAP_LOG_PATTERNS:
        if pattern in log_delta:
            raise RuntimeError(f"bootstrap log contains forbidden text: {pattern}")


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
    if os.name == "nt":
        subprocess.run(
            [resolve_tool_path("taskkill"), "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return

    try:
        process.terminate()
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    try:
        process.kill()
        process.wait(timeout=5)
    except Exception:
        pass


def ensure_clean_start(health_url: str) -> None:
    if fetch_backend_health(health_url) is not None:
        raise RuntimeError(
            "health endpoint is already reachable before smoke test; "
            f"stop the existing shell/backend first ({summarize_non_clean_start(health_url)})"
        )


def wait_for_backend_shutdown(health_url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fetch_backend_health(health_url) is None:
            return
        time.sleep(0.5)
    raise RuntimeError(f"backend health endpoint still reachable after shell cleanup: {health_url}")


def maybe_build_release(skip_build: bool) -> None:
    if skip_build:
        return
    run_command(
        [resolve_tool_path("npm"), "run", "tauri", "--", "build", "--bundles", "app"],
        cwd=DESKTOP_SHELL_ROOT,
        step="Tauri release app bundle build",
    )


def assert_log_contains(log_delta: str, needle: str, *, timeout: float, log_path: Path, start_offset: int) -> str:
    deadline = time.time() + timeout
    current = log_delta
    while time.time() < deadline:
        fail_on_forbidden_log_patterns(current)
        if needle in current:
            return current
        time.sleep(0.5)
        current = read_log_delta(log_path, start_offset)
    fail_on_forbidden_log_patterns(current)
    raise RuntimeError(f"missing bootstrap log line: {needle}")


def main() -> None:
    args = parse_args()
    runtime_root = Path(args.runtime_root).resolve()
    log_path = bootstrap_log_path(runtime_root)
    log_offset = log_path.stat().st_size if log_path.exists() else 0

    ensure_clean_start(args.health_url)
    maybe_build_release(args.skip_build)
    shell_exe = resolve_shell_executable(args.shell_exe)
    if not shell_exe.exists():
        raise RuntimeError(f"missing shell executable: {shell_exe}")

    first_shell = launch_process(shell_exe)
    second_shell: subprocess.Popen[bytes] | None = None
    try:
        wait_for_backend_ready(
            args.health_url,
            args.ready_timeout,
            log_path=log_path,
            start_offset=log_offset,
        )
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
        ensure_backend_stays_healthy(
            args.health_url,
            step="backend lost readiness after second launch",
        )
        log_delta = read_log_delta(log_path, log_offset)
        fail_on_forbidden_log_patterns(log_delta)

        force_kill_process_tree(first_shell)
        wait_for_backend_shutdown(args.health_url, timeout=args.ready_timeout)

        print(f"Release smoke passed: {shell_exe}")
        print(f"Verified health endpoint: {args.health_url}")
        print(f"Verified bootstrap log: {log_path}")
    finally:
        if second_shell is not None:
            force_kill_process_tree(second_shell)
        force_kill_process_tree(first_shell)


if __name__ == "__main__":
    main()
