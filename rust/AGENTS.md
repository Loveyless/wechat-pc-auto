# Repository Guidelines

## Project Structure & Module Organization
`src/` contains the React 19 + TypeScript frontend: page components in `src/components/`, shared UI primitives in `src/components/ui/`, Zustand stores in `src/stores/`, and Tauri IPC wrappers in `src/lib/tauri-api.ts`. `src-tauri/` contains the Rust backend: Tauri commands in `src-tauri/src/commands/`, macOS adapters in `src-tauri/src/adapter/`, and task orchestration in `src-tauri/src/task_manager.rs`. Static assets live in `public/` and `src-tauri/icons/`. Packaging helpers live in `scripts/`.

## Build, Test, and Development Commands
Use `pnpm install` to install frontend dependencies. Use `pnpm tauri dev` for the full desktop dev loop with Vite hot reload and Rust recompilation. Use `pnpm build` to type-check and build the frontend only. Use `pnpm tauri build` to produce a production app, or `pnpm package:macos` for the repo’s macOS packaging script. For adapter debugging, run commands such as `cargo run --manifest-path src-tauri/Cargo.toml --bin ax-test` or `cargo run --manifest-path src-tauri/Cargo.toml --bin ax-dump`.

## Coding Style & Naming Conventions
Follow the existing style: TypeScript uses 2-space indentation, double quotes, semicolons, `PascalCase` for components, and `camelCase` for hooks, stores, and helpers. Rust follows standard `rustfmt` style with 4-space indentation, `snake_case` for functions/modules, and focused modules by feature. Keep Tauri invoke wrappers centralized in `src/lib/tauri-api.ts`; do not scatter raw `invoke()` calls across components.

## Testing Guidelines
This repository does not currently ship a dedicated automated test suite or coverage gate. At minimum, verify changes with `pnpm build` and the relevant manual smoke path in `pnpm tauri dev`. Backend or AX integration changes should be exercised with the matching Rust debug binary under `src-tauri/src/bin/`. If you add automated tests, prefer Rust tests under `src-tauri/tests/` or colocated unit tests, and keep filenames descriptive, such as `sidebar_window_tests.rs`.

## Commit & Pull Request Guidelines
Match the recent Conventional Commit style seen in history: `feat(macos): ...`, `docs(listening): ...`, `refactor(applescript): ...`, `release: v0.1.1`. Keep scopes specific to the subsystem you changed. PRs should include a short problem/solution summary, affected paths, local verification steps, and screenshots or recordings for UI/sidebar changes. Call out macOS-specific prerequisites, especially Accessibility permission requirements or WeChat client assumptions.

## Security & Configuration Tips
This app is macOS-specific and depends on WeChat plus Accessibility access. Never commit local machine paths, app data from `~/Library/Application Support/com.wang.wechat-pc-auto/`, or secrets embedded in config files. Treat AppleScript and AX changes as high-risk and document any new permission or automation behavior in the PR.
