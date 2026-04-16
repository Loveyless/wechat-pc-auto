from __future__ import annotations

import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
from datetime import datetime
from typing import Any

if __package__:
    from .sidebar_shared import (
        EXECUTABLE_ROOT,
        LOG_ROTATE_KEEP_FILES,
        LOG_ROTATE_MAX_BYTES,
        ROOT_DIR,
        RUNTIME_LOCK_DIR,
        SOURCE_ROOT,
        WORKER_EXE_NAME,
        WORKER_FORCE_KILL_TIMEOUT_SECONDS,
        WORKER_RESTART_INITIAL_BACKOFF_SECONDS,
        WORKER_RESTART_MAX_BACKOFF_SECONDS,
        WORKER_STOP_TIMEOUT_SECONDS,
        as_int,
        is_frozen_app,
    )
else:
    from sidebar_shared import (
        EXECUTABLE_ROOT,
        LOG_ROTATE_KEEP_FILES,
        LOG_ROTATE_MAX_BYTES,
        ROOT_DIR,
        RUNTIME_LOCK_DIR,
        SOURCE_ROOT,
        WORKER_EXE_NAME,
        WORKER_FORCE_KILL_TIMEOUT_SECONDS,
        WORKER_RESTART_INITIAL_BACKOFF_SECONDS,
        WORKER_RESTART_MAX_BACKOFF_SECONDS,
        WORKER_STOP_TIMEOUT_SECONDS,
        as_int,
        is_frozen_app,
    )

_LOG_WRITE_LOCK = threading.Lock()
_TARGET_LOCK_PATHS: list[str] = []


def compute_worker_restart_delay(attempt: int) -> float:
    safe_attempt = max(1, int(attempt))
    delay = WORKER_RESTART_INITIAL_BACKOFF_SECONDS * (2 ** (safe_attempt - 1))
    return min(delay, WORKER_RESTART_MAX_BACKOFF_SECONDS)


def append_log_file(path: str, line: str):
    if not path:
        return
    try:
        with _LOG_WRITE_LOCK:
            rotate_log_file_if_needed(path)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line.rstrip() + "\n")
    except Exception:
        pass


def resolve_log_file_path(path: Any) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    resolved = raw if os.path.isabs(raw) else os.path.join(ROOT_DIR, raw)
    normalized = os.path.normpath(resolved)
    parent = os.path.dirname(normalized)
    if parent:
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception:
            pass
    return normalized


def resolve_worker_executable_path(executable_root: str = EXECUTABLE_ROOT) -> str:
    return os.path.join(executable_root, WORKER_EXE_NAME)


def build_worker_command(
    targets: list[str],
    interval: float,
    debug: bool,
    focus_refresh: bool,
    load_retry_seconds: float,
    *,
    all_sessions: bool = False,
    frozen: bool | None = None,
    python_executable: str | None = None,
    source_root: str = SOURCE_ROOT,
    executable_root: str = EXECUTABLE_ROOT,
) -> list[str]:
    use_frozen = is_frozen_app() if frozen is None else bool(frozen)
    if use_frozen:
        cmd = [
            resolve_worker_executable_path(executable_root),
            "--targets-json",
            json.dumps(targets, ensure_ascii=False),
            "--interval",
            str(interval),
            "--load-retry-seconds",
            str(load_retry_seconds),
        ]
    else:
        worker_script = os.path.join(source_root, "listener_app", "group_listener_worker.py")
        cmd = [
            python_executable or sys.executable,
            "-X",
            "utf8",
            "-u",
            worker_script,
            "--targets-json",
            json.dumps(targets, ensure_ascii=False),
            "--interval",
            str(interval),
            "--load-retry-seconds",
            str(load_retry_seconds),
        ]
    if all_sessions:
        cmd.append("--all-sessions")
    if debug:
        cmd.append("--debug")
    if focus_refresh:
        cmd.append("--focus-refresh")
    return cmd


def rotate_log_file_if_needed(path: str):
    try:
        if not os.path.exists(path):
            return
        if os.path.getsize(path) < LOG_ROTATE_MAX_BYTES:
            return
    except Exception:
        return

    try:
        oldest = f"{path}.{LOG_ROTATE_KEEP_FILES}"
        if os.path.exists(oldest):
            os.remove(oldest)
    except Exception:
        pass

    for idx in range(LOG_ROTATE_KEEP_FILES - 1, 0, -1):
        src = f"{path}.{idx}"
        dst = f"{path}.{idx + 1}"
        try:
            if os.path.exists(src):
                os.replace(src, dst)
        except Exception:
            pass

    try:
        os.replace(path, f"{path}.1")
    except Exception:
        pass


def _target_lock_path(target: str) -> str:
    os.makedirs(RUNTIME_LOCK_DIR, exist_ok=True)
    digest = hashlib.sha1(target.strip().lower().encode("utf-8")).hexdigest()[:12]
    return os.path.join(RUNTIME_LOCK_DIR, f"target_{digest}.lock")


def _read_lock_payload(lock_path: str) -> dict[str, Any]:
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            STILL_ACTIVE = 259

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.GetExitCodeProcess.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            kernel32.GetExitCodeProcess.restype = ctypes.c_int
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_int

            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
                False,
                int(pid),
            )
            if not handle:
                return False
            try:
                exit_code = ctypes.c_uint32()
                ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                if not ok:
                    return False
                return int(exit_code.value) == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _get_pid_start_token(pid: int) -> str:
    if pid <= 0 or os.name != "nt":
        return ""
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetProcessTimes.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        kernel32.GetProcessTimes.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        creation = FILETIME()
        exit_time = FILETIME()
        kernel_time = FILETIME()
        user_time = FILETIME()
        ok = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        kernel32.CloseHandle(handle)
        if not ok:
            return ""

        ticks = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        return str(ticks)
    except Exception:
        return ""


def _normalize_process_start_token(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    if len(token) == 16 and all(ch in "0123456789abcdef" for ch in token):
        try:
            return str(int(token, 16))
        except ValueError:
            return token
    if token.isdigit():
        return str(int(token, 10))
    return token


def is_process_identity_alive(pid: int, start_token: str = "") -> bool:
    if not _is_pid_alive(int(pid)):
        return False

    expected_token = _normalize_process_start_token(start_token)
    if not expected_token:
        return True

    current_token = _normalize_process_start_token(_get_pid_start_token(int(pid)))
    if not current_token:
        # 无法读取启动时间时退化为 PID 存活判断，避免误判活进程已经失联。
        return True
    return current_token == expected_token


def _is_lock_owner_alive(lock_payload: dict[str, Any]) -> bool:
    pid = as_int(lock_payload.get("pid"), 0)
    expected_token = str(lock_payload.get("start_token", "")).strip()
    return is_process_identity_alive(pid, expected_token)


def is_target_already_running(target: str) -> bool:
    lock_path = _target_lock_path(target)
    if not os.path.exists(lock_path):
        return False
    lock_payload = _read_lock_payload(lock_path)
    if _is_lock_owner_alive(lock_payload):
        return True
    try:
        os.remove(lock_path)
    except Exception:
        pass
    return False


def cleanup_stale_target_locks() -> int:
    if not os.path.isdir(RUNTIME_LOCK_DIR):
        return 0

    removed = 0
    try:
        entries = os.listdir(RUNTIME_LOCK_DIR)
    except Exception:
        return 0

    for name in entries:
        if not name.startswith("target_") or not name.endswith(".lock"):
            continue
        lock_path = os.path.join(RUNTIME_LOCK_DIR, name)
        if not os.path.isfile(lock_path):
            continue

        lock_payload = _read_lock_payload(lock_path)
        if _is_lock_owner_alive(lock_payload):
            continue

        try:
            os.remove(lock_path)
            removed += 1
        except Exception:
            pass
    return removed


def acquire_target_lock(target: str) -> tuple[bool, str]:
    lock_path = _target_lock_path(target)
    if os.path.exists(lock_path):
        existing = _read_lock_payload(lock_path)
        if _is_lock_owner_alive(existing):
            pid = as_int(existing.get("pid"), 0)
            return False, f"target already running pid={pid}"
        try:
            os.remove(lock_path)
        except Exception:
            pass

    start_token = _get_pid_start_token(os.getpid())
    payload = {
        "pid": os.getpid(),
        "target": target,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if start_token:
        payload["start_token"] = start_token
    try:
        with open(lock_path, "x", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except FileExistsError:
        existing = _read_lock_payload(lock_path)
        if _is_lock_owner_alive(existing):
            pid = as_int(existing.get("pid"), 0)
            return False, f"target already running pid={pid}"
        try:
            with open(lock_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            return False, f"target lock create failed: {e}"
    except Exception as e:
        return False, f"target lock create failed: {e}"
    return True, lock_path


def _release_lock_paths(lock_paths: list[str]):
    for path in lock_paths:
        if not path:
            continue
        try:
            lock_payload = _read_lock_payload(path)
            pid = as_int(lock_payload.get("pid"), 0)
            expected_token = str(lock_payload.get("start_token", "")).strip()
            current_token = _get_pid_start_token(os.getpid())
            same_process = pid == os.getpid()
            if expected_token and current_token and expected_token != current_token:
                same_process = False
            if same_process and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def set_managed_target_lock_paths(lock_paths: list[str]):
    global _TARGET_LOCK_PATHS
    _TARGET_LOCK_PATHS = [str(path or "").strip() for path in lock_paths if str(path or "").strip()]


def release_target_lock_path(lock_path: str):
    global _TARGET_LOCK_PATHS
    path = str(lock_path or "").strip()
    if not path:
        return
    _TARGET_LOCK_PATHS = [item for item in _TARGET_LOCK_PATHS if item != path]
    _release_lock_paths([path])


def release_managed_target_locks():
    global _TARGET_LOCK_PATHS
    lock_paths = list(_TARGET_LOCK_PATHS)
    _TARGET_LOCK_PATHS = []
    _release_lock_paths(lock_paths)


def resolve_taskkill_path() -> str:
    windir = str(os.environ.get("WINDIR", "")).strip()
    if windir:
        candidate = os.path.join(windir, "System32", "taskkill.exe")
        if os.path.exists(candidate):
            return candidate
    resolved = shutil.which("taskkill.exe") or shutil.which("taskkill")
    return resolved or "taskkill"


def terminate_process_tree(
    proc: subprocess.Popen | None,
    *,
    stop_timeout: float = WORKER_STOP_TIMEOUT_SECONDS,
    force_timeout: float = WORKER_FORCE_KILL_TIMEOUT_SECONDS,
) -> None:
    if proc is None or proc.poll() is not None:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                [resolve_taskkill_path(), "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
            proc.wait(timeout=max(stop_timeout + force_timeout, 0.1))
            return
        except Exception:
            pass

    try:
        proc.terminate()
        proc.wait(timeout=max(stop_timeout, 0.1))
        return
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    try:
        proc.kill()
        proc.wait(timeout=max(force_timeout, 0.1))
    except Exception:
        pass


def start_worker_process(
    targets: list[str],
    interval: float,
    debug: bool,
    focus_refresh: bool,
    load_retry_seconds: float,
    *,
    all_sessions: bool = False,
) -> subprocess.Popen:
    # 使用 UTF-8 管道，避免中文在父子进程间错码。
    cmd = build_worker_command(
        targets,
        interval,
        debug,
        focus_refresh,
        load_retry_seconds,
        all_sessions=all_sessions,
    )
    if is_frozen_app() and not os.path.exists(cmd[0]):
        raise RuntimeError(f"missing worker executable: {cmd[0]}")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.Popen(
        cmd,
        cwd=ROOT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


def stdout_reader(proc: subprocess.Popen, event_queue: "queue.Queue[dict[str, Any]]"):
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                event_queue.put(event)
            else:
                event_queue.put({"type": "log", "value": f"worker non-dict event: {line}"})
        except json.JSONDecodeError:
            event_queue.put({"type": "log", "value": f"worker raw: {line}"})


def stderr_reader(proc: subprocess.Popen, event_queue: "queue.Queue[dict[str, Any]]"):
    assert proc.stderr is not None
    for raw in proc.stderr:
        line = raw.rstrip()
        if line:
            event_queue.put({"type": "log", "value": f"worker stderr: {line}"})
