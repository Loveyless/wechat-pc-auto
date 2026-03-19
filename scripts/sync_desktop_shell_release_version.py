from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
PACKAGE_JSON_PATH = REPO_ROOT / "desktop-shell" / "package.json"
PACKAGE_LOCK_PATH = REPO_ROOT / "desktop-shell" / "package-lock.json"
CARGO_TOML_PATH = REPO_ROOT / "desktop-shell" / "src-tauri" / "Cargo.toml"
TAURI_CONF_PATH = REPO_ROOT / "desktop-shell" / "src-tauri" / "tauri.conf.json"
CARGO_LOCK_PATH = REPO_ROOT / "desktop-shell" / "src-tauri" / "Cargo.lock"

BASE_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
PROJECT_VERSION_PATTERN = re.compile(
    r'(^\[project\]\s+name = "wechat-pc-auto"\s+version = ")([^"]+)(")',
    re.MULTILINE,
)
PACKAGE_VERSION_PATTERN = re.compile(
    r'(^\[package\]\s+name = "wechat-auto-shell"\s+version = ")([^"]+)(")',
    re.MULTILINE,
)
CARGO_LOCK_VERSION_PATTERN = re.compile(
    r'(\[\[package\]\]\s+name = "wechat-auto-shell"\s+version = ")([^"]+)(")',
    re.MULTILINE,
)


@dataclass(frozen=True)
class ReleaseVersions:
    baseVersion: str
    channel: str
    pythonVersion: str
    desktopVersion: str
    recommendedTag: str


def ParseArgs() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync WeChat Auto Shell release versions across Python and desktop-shell entry files."
    )
    parser.add_argument(
        "--channel",
        choices=("stable", "rc"),
        required=True,
        help="Release channel. stable keeps a shared version; rc derives Python/Desktop variants.",
    )
    parser.add_argument(
        "--base-version",
        required=True,
        help="Base version in MAJOR.MINOR.PATCH form, for example 0.1.0.",
    )
    parser.add_argument(
        "--rc-number",
        type=int,
        help="Required when --channel rc. Must be between 1 and 65535.",
    )
    return parser.parse_args()


def DeriveReleaseVersions(channel: str, baseVersion: str, rcNumber: int | None) -> ReleaseVersions:
    if not BASE_VERSION_PATTERN.fullmatch(baseVersion):
        raise RuntimeError(
            "base version must use MAJOR.MINOR.PATCH form, for example 0.1.0"
        )
    if channel == "stable":
        if rcNumber is not None:
            raise RuntimeError("stable release does not accept --rc-number")
        return ReleaseVersions(
            baseVersion=baseVersion,
            channel=channel,
            pythonVersion=baseVersion,
            desktopVersion=baseVersion,
            recommendedTag=f"v{baseVersion}",
        )
    if rcNumber is None:
        raise RuntimeError("rc release requires --rc-number")
    if rcNumber < 1 or rcNumber > 65535:
        raise RuntimeError("rc number must be between 1 and 65535")
    return ReleaseVersions(
        baseVersion=baseVersion,
        channel=channel,
        pythonVersion=f"{baseVersion}rc{rcNumber}",
        desktopVersion=f"{baseVersion}-{rcNumber}",
        recommendedTag=f"v{baseVersion}-rc.{rcNumber}",
    )


def ReplaceSingle(
    text: str,
    pattern: re.Pattern[str],
    replacementBuilder: Callable[[re.Match[str]], str],
    *,
    label: str,
) -> str:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {label} entry, found {len(matches)}")
    match = matches[0]
    return (
        text[: match.start()]
        + replacementBuilder(match)
        + text[match.end() :]
    )


def UpdatePyproject(text: str, pythonVersion: str) -> str:
    return ReplaceSingle(
        text,
        PROJECT_VERSION_PATTERN,
        lambda match: f"{match.group(1)}{pythonVersion}{match.group(3)}",
        label="pyproject version",
    )


def UpdateCargoToml(text: str, desktopVersion: str) -> str:
    return ReplaceSingle(
        text,
        PACKAGE_VERSION_PATTERN,
        lambda match: f"{match.group(1)}{desktopVersion}{match.group(3)}",
        label="Cargo.toml package version",
    )


def UpdateCargoLock(text: str, desktopVersion: str) -> str:
    return ReplaceSingle(
        text,
        CARGO_LOCK_VERSION_PATTERN,
        lambda match: f"{match.group(1)}{desktopVersion}{match.group(3)}",
        label="Cargo.lock workspace package version",
    )


def UpdateJsonFile(path: Path, updater: Callable[[dict[str, Any]], None]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    updater(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def SyncVersions(repoRoot: Path, versions: ReleaseVersions) -> list[Path]:
    pyprojectPath = repoRoot / PYPROJECT_PATH.relative_to(REPO_ROOT)
    packageJsonPath = repoRoot / PACKAGE_JSON_PATH.relative_to(REPO_ROOT)
    packageLockPath = repoRoot / PACKAGE_LOCK_PATH.relative_to(REPO_ROOT)
    cargoTomlPath = repoRoot / CARGO_TOML_PATH.relative_to(REPO_ROOT)
    tauriConfPath = repoRoot / TAURI_CONF_PATH.relative_to(REPO_ROOT)
    cargoLockPath = repoRoot / CARGO_LOCK_PATH.relative_to(REPO_ROOT)

    pyprojectPath.write_text(
        UpdatePyproject(pyprojectPath.read_text(encoding="utf-8"), versions.pythonVersion),
        encoding="utf-8",
        newline="\n",
    )
    packageJsonPathPayload = json.loads(packageJsonPath.read_text(encoding="utf-8"))
    packageJsonPathPayload["version"] = versions.desktopVersion
    packageJsonPath.write_text(
        json.dumps(packageJsonPathPayload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    UpdateJsonFile(
        packageLockPath,
        lambda payload: (
            payload.__setitem__("version", versions.desktopVersion),
            payload.setdefault("packages", {}).setdefault("", {}).__setitem__(
                "version", versions.desktopVersion
            ),
        ),
    )
    cargoTomlPath.write_text(
        UpdateCargoToml(cargoTomlPath.read_text(encoding="utf-8"), versions.desktopVersion),
        encoding="utf-8",
        newline="\n",
    )
    UpdateJsonFile(
        tauriConfPath,
        lambda payload: payload.__setitem__("version", versions.desktopVersion),
    )
    cargoLockPath.write_text(
        UpdateCargoLock(cargoLockPath.read_text(encoding="utf-8"), versions.desktopVersion),
        encoding="utf-8",
        newline="\n",
    )
    return [
        pyprojectPath,
        packageJsonPath,
        packageLockPath,
        cargoTomlPath,
        tauriConfPath,
        cargoLockPath,
    ]


def Main() -> None:
    args = ParseArgs()
    versions = DeriveReleaseVersions(args.channel, args.base_version, args.rc_number)
    updatedFiles = SyncVersions(REPO_ROOT, versions)
    print(f"python_version={versions.pythonVersion}")
    print(f"desktop_version={versions.desktopVersion}")
    print(f"recommended_tag={versions.recommendedTag}")
    for path in updatedFiles:
        print(f"updated {path}")


if __name__ == "__main__":
    Main()
