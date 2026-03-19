import json
import tempfile
import unittest
from pathlib import Path

from scripts import sync_desktop_shell_release_version as sync


class SyncDesktopShellReleaseVersionTest(unittest.TestCase):
    def testDeriveReleaseVersionsForStable(self):
        versions = sync.DeriveReleaseVersions("stable", "0.1.0", None)
        self.assertEqual(versions.pythonVersion, "0.1.0")
        self.assertEqual(versions.desktopVersion, "0.1.0")
        self.assertEqual(versions.recommendedTag, "v0.1.0")

    def testDeriveReleaseVersionsForRc(self):
        versions = sync.DeriveReleaseVersions("rc", "0.1.0", 2)
        self.assertEqual(versions.pythonVersion, "0.1.0rc2")
        self.assertEqual(versions.desktopVersion, "0.1.0-2")
        self.assertEqual(versions.recommendedTag, "v0.1.0-rc.2")

    def testDeriveReleaseVersionsRejectsInvalidBaseVersion(self):
        with self.assertRaises(RuntimeError) as excCtx:
            sync.DeriveReleaseVersions("stable", "0.1.0rc2", None)
        self.assertIn("MAJOR.MINOR.PATCH", str(excCtx.exception))

    def testDeriveReleaseVersionsRejectsOutOfRangeRcNumber(self):
        with self.assertRaises(RuntimeError) as excCtx:
            sync.DeriveReleaseVersions("rc", "0.1.0", 65536)
        self.assertIn("65535", str(excCtx.exception))

    def testSyncVersionsUpdatesWorkspaceEntriesOnly(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            repoRoot = Path(tmpDir)
            (repoRoot / "desktop-shell" / "src-tauri").mkdir(parents=True)
            (repoRoot / "desktop-shell").mkdir(exist_ok=True)

            (repoRoot / "pyproject.toml").write_text(
                '[project]\nname = "wechat-pc-auto"\nversion = "1.1.2"\n',
                encoding="utf-8",
                newline="\n",
            )
            (repoRoot / "desktop-shell" / "package.json").write_text(
                json.dumps({"name": "wechat-auto-shell", "version": "1.1.2"}, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (repoRoot / "desktop-shell" / "package-lock.json").write_text(
                json.dumps(
                    {
                        "name": "wechat-auto-shell",
                        "version": "1.1.2",
                        "packages": {
                            "": {"name": "wechat-auto-shell", "version": "1.1.2"},
                            "node_modules/x": {"version": "9.9.9"},
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (repoRoot / "desktop-shell" / "src-tauri" / "Cargo.toml").write_text(
                '[package]\nname = "wechat-auto-shell"\nversion = "1.1.2"\n',
                encoding="utf-8",
                newline="\n",
            )
            (repoRoot / "desktop-shell" / "src-tauri" / "tauri.conf.json").write_text(
                json.dumps({"productName": "WeChat Auto Shell", "version": "1.1.2"}, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (repoRoot / "desktop-shell" / "src-tauri" / "Cargo.lock").write_text(
                '\n'.join(
                    [
                        '[[package]]',
                        'name = "other-package"',
                        'version = "0.1.0"',
                        '',
                        '[[package]]',
                        'name = "wechat-auto-shell"',
                        'version = "1.1.2"',
                        'dependencies = [',
                        ' "serde",',
                        ']',
                        '',
                        '[[package]]',
                        'name = "another-package"',
                        'version = "0.1.0"',
                        '',
                    ]
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            updatedFiles = sync.SyncVersions(
                repoRoot,
                sync.ReleaseVersions(
                    baseVersion="0.1.0",
                    channel="rc",
                    pythonVersion="0.1.0rc2",
                    desktopVersion="0.1.0-2",
                    recommendedTag="v0.1.0-rc.2",
                ),
            )

            self.assertEqual(len(updatedFiles), 6)
            self.assertIn('version = "0.1.0rc2"', (repoRoot / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertEqual(
                json.loads((repoRoot / "desktop-shell" / "package.json").read_text(encoding="utf-8"))["version"],
                "0.1.0-2",
            )
            packageLock = json.loads(
                (repoRoot / "desktop-shell" / "package-lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual(packageLock["version"], "0.1.0-2")
            self.assertEqual(packageLock["packages"][""]["version"], "0.1.0-2")
            self.assertEqual(packageLock["packages"]["node_modules/x"]["version"], "9.9.9")
            self.assertIn(
                'version = "0.1.0-2"',
                (repoRoot / "desktop-shell" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                json.loads(
                    (repoRoot / "desktop-shell" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
                )["version"],
                "0.1.0-2",
            )
            cargoLockText = (repoRoot / "desktop-shell" / "src-tauri" / "Cargo.lock").read_text(
                encoding="utf-8"
            )
            self.assertIn('name = "wechat-auto-shell"\nversion = "0.1.0-2"', cargoLockText)
            self.assertIn('name = "other-package"\nversion = "0.1.0"', cargoLockText)


if __name__ == "__main__":
    unittest.main()
