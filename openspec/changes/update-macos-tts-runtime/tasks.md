## 1. Backend TTS runtime and config compatibility

- [x] 1.1 Update `listener_app/sidebar_tts.py` so the supported built-in system provider becomes `macos_system`, legacy `windows_system` resolves through a defined compatibility path, and system/cloud playback use mac-compatible commands instead of Windows-only audio APIs
- [x] 1.2 Update `listener_app/runtime_config.py`, `listener_app/runtime_config_store.py`, and `listener_app/runtime_api.py` so the authoritative TTS provider enum, defaults, config snapshots, and save behavior expose `macos_system` while preserving existing file-boundary persistence and legacy-read compatibility
- [x] 1.3 Add or update Python regression coverage for provider normalization, config snapshot/save behavior, API payloads, dependency checks, and runtime auto-read behavior under the mac-only provider set

## 2. Desktop settings contract

- [x] 2.1 Update `desktop-shell/src/lib/settings-types.ts` and related settings data plumbing so the editable TTS provider enum and draft model use `macos_system` plus the existing cloud providers
- [ ] 2.2 Update `desktop-shell/src/components/shell/settings-workspace.tsx` so the TTS provider selector and provider-specific branches reflect the mac-only provider set, including the built-in macOS system guidance branch and unchanged cloud-provider forms
- [ ] 2.3 Add frontend regression coverage for the updated TTS provider selector, macOS system-provider branch, and preserved cloud-provider branches

## 3. Docs and verification

- [ ] 3.1 Update `config/listener.json`, `config/listener.md`, and `docs/wechat-listening-pitfalls.md` so shipped defaults, provider guidance, and migration notes match the mac-only TTS runtime
- [ ] 3.2 Run the targeted Python and frontend checks from the plan, record any environment-limited manual verification, and keep the resulting notes aligned with the CSV issue state
