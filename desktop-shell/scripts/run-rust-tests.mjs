import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const desktopShellRoot = resolve(scriptDir, "..");
const tauriRoot = resolve(desktopShellRoot, "src-tauri");
const testConfigPath = resolve(tauriRoot, "tauri.test.conf.json");

const testConfig = JSON.parse(await readFile(testConfigPath, "utf8"));
const cargoExecutable = process.platform === "win32" ? "cargo.exe" : "cargo";
const child = spawn(cargoExecutable, ["test"], {
  cwd: tauriRoot,
  env: {
    ...process.env,
    TAURI_CONFIG: JSON.stringify(testConfig),
  },
  stdio: "inherit",
});

child.on("error", (error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
