from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from shutil import which


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGING_MANIFEST_PATH = Path(__file__).resolve().with_name("packaging_manifest.json")
DESKTOP_SHELL_ROOT = REPO_ROOT / "desktop-shell"
SRC_TAURI_ROOT = DESKTOP_SHELL_ROOT / "src-tauri"
BINARIES_ROOT = SRC_TAURI_ROOT / "binaries"
BUILD_ROOT = SRC_TAURI_ROOT / "target" / "sidecars-pyinstaller"
SPEC_ROOT = BUILD_ROOT / "spec"
WORK_ROOT = BUILD_ROOT / "work"
DIST_ROOT = BUILD_ROOT / "dist"

BACKEND_NAME = "wechat-auto-backend"
WORKER_NAME = "group_listener_worker"

BACKEND_SOURCE = REPO_ROOT / "listener_app" / "backend_main.py"
WORKER_SOURCE = REPO_ROOT / "listener_app" / "group_listener_worker.py"
CONFIG_SOURCE = REPO_ROOT / "config"
LISTENER_CONFIG = CONFIG_SOURCE / "listener.json"
WORKER_SMOKE_ARGS = ("--help",)
BACKEND_TTS_CHECK_ARGS = (
    "--config",
    str(LISTENER_CONFIG),
    "--check-tts-deps",
)


def load_packaging_settings() -> tuple[Path, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    try:
        manifest = json.loads(PACKAGING_MANIFEST_PATH.read_text(encoding="utf-8"))
        pyinstaller = manifest["pyinstaller"]
        runtime_dependencies = pyinstaller["runtime_dependencies"]
        validation = manifest["validation"]
        hooks_dir = REPO_ROOT / str(pyinstaller["additional_hooks_dir"])
        collect_submodules = tuple(str(item) for item in runtime_dependencies["collect_submodules"])
        collect_all = tuple(str(item) for item in runtime_dependencies["collect_all"])
        forbidden_output_patterns = tuple(
            str(item) for item in validation["forbidden_output_patterns"]
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"invalid packaging manifest: {PACKAGING_MANIFEST_PATH}"
        ) from exc
    return hooks_dir, collect_submodules, collect_all, forbidden_output_patterns


(
    PYINSTALLER_HOOKS_DIR,
    BACKEND_COLLECT_SUBMODULES,
    BACKEND_COLLECT_ALL,
    FORBIDDEN_DEPENDENCY_WARNING_PATTERNS,
) = load_packaging_settings()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Python sidecars for the Tauri desktop shell.")
    parser.add_argument("--python", default=sys.executable, help="Python executable used for PyInstaller")
    parser.add_argument("--rustc", default="rustc", help="rustc executable used to resolve target triple")
    return parser.parse_args()


def resolve_tool_path(tool: str) -> str:
    direct = which(tool)
    if direct:
        return direct
    cargo_bin = Path.home() / ".cargo" / "bin" / (tool if tool.endswith(".exe") else f"{tool}.exe")
    if cargo_bin.exists():
        return str(cargo_bin)
    raise RuntimeError(f"required tool not found: {tool}")


def run_command(
    args: list[str],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
    step: str,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
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


def fail_on_forbidden_dependency_warnings(
    result: subprocess.CompletedProcess[str],
    *,
    step: str,
) -> None:
    combined_output = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )
    for pattern in FORBIDDEN_DEPENDENCY_WARNING_PATTERNS:
        if pattern in combined_output:
            raise RuntimeError(f"{step} emitted forbidden dependency warning: {pattern}")


def host_target_triple(rustc: str) -> str:
    result = run_command([rustc, "-vV"], step="Resolve rust target triple")
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if line.startswith("host:"):
            host = line.split(":", 1)[1].strip()
            if host:
                return host
    raise RuntimeError("failed to resolve rust host target triple")


def pyinstaller_data_arg(source: Path, target: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{source}{separator}{target}"


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def preflight_worker_dependencies(python: str) -> None:
    run_command(
        [
            python,
            str(WORKER_SOURCE),
            *WORKER_SMOKE_ARGS,
        ],
        step="Source worker dependency preflight",
    )


def preflight_backend_dependencies(python: str) -> None:
    if not LISTENER_CONFIG.exists():
        raise RuntimeError(f"missing config file: {LISTENER_CONFIG}")
    result = run_command(
        [
            python,
            str(BACKEND_SOURCE),
            *BACKEND_TTS_CHECK_ARGS,
        ],
        step="Source backend dependency preflight",
    )
    fail_on_forbidden_dependency_warnings(result, step="Source backend dependency preflight")


def build_sidecar(
    *,
    python: str,
    source: Path,
    name: str,
    extra_args: list[str],
) -> Path:
    command = [
        python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--log-level",
        "WARN",
        "--onefile",
        "--console",
        "--name",
        name,
        "--distpath",
        str(DIST_ROOT),
        "--workpath",
        str(WORK_ROOT / name),
        "--specpath",
        str(SPEC_ROOT),
        "--paths",
        str(REPO_ROOT),
        "--additional-hooks-dir",
        str(PYINSTALLER_HOOKS_DIR),
        *extra_args,
        str(source),
    ]
    run_command(command, step=f"PyInstaller build for {name}")
    executable = DIST_ROOT / f"{name}.exe"
    if not executable.exists():
        raise RuntimeError(f"missing built executable: {executable}")
    return executable


def smoke_test_worker(worker_executable: Path) -> None:
    run_command(
        [str(worker_executable), *WORKER_SMOKE_ARGS],
        step="Worker smoke test (--help)",
    )


def smoke_test_backend(backend_executable: Path) -> None:
    result = run_command(
        [
            str(backend_executable),
            *BACKEND_TTS_CHECK_ARGS,
        ],
        step="Backend packaged dependency smoke test",
    )
    fail_on_forbidden_dependency_warnings(result, step="Backend packaged dependency smoke test")


def backend_hidden_import_args() -> list[str]:
    args: list[str] = []
    for module_name in BACKEND_COLLECT_SUBMODULES:
        args.extend(["--collect-submodules", module_name])
    for module_name in BACKEND_COLLECT_ALL:
        args.extend(["--collect-all", module_name])
    return args


def install_sidecar(built_executable: Path, *, name: str, target_triple: str) -> Path:
    BINARIES_ROOT.mkdir(parents=True, exist_ok=True)
    target_path = BINARIES_ROOT / f"{name}-{target_triple}.exe"
    if target_path.exists():
        target_path.unlink()
    shutil.copy2(built_executable, target_path)
    return target_path


def main() -> None:
    args = parse_args()
    rustc = resolve_tool_path(args.rustc)
    target_triple = host_target_triple(rustc)

    ensure_clean_dir(BUILD_ROOT)
    SPEC_ROOT.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    preflight_worker_dependencies(args.python)
    preflight_backend_dependencies(args.python)

    worker_executable = build_sidecar(
        python=args.python,
        source=WORKER_SOURCE,
        name=WORKER_NAME,
        extra_args=[],
    )
    backend_executable = build_sidecar(
        python=args.python,
        source=BACKEND_SOURCE,
        name=BACKEND_NAME,
        extra_args=[
            *backend_hidden_import_args(),
            "--add-data",
            pyinstaller_data_arg(CONFIG_SOURCE, "config"),
        ],
    )

    smoke_test_worker(worker_executable)
    smoke_test_backend(backend_executable)

    installed_worker = install_sidecar(
        worker_executable,
        name=WORKER_NAME,
        target_triple=target_triple,
    )
    installed_backend = install_sidecar(
        backend_executable,
        name=BACKEND_NAME,
        target_triple=target_triple,
    )

    print(f"Built sidecar: {installed_backend}")
    print(f"Built sidecar: {installed_worker}")


if __name__ == "__main__":
    main()
