## 1. Backend config schema and runtime

- [ ] 1.1 Extend `listener_app/runtime_config.py` and `listener_app/sidebar_translate_runtime.py` for provider-aware translate loading, `openai_compatible` runtime support, and legacy field compatibility reads
- [ ] 1.2 Update `listener_app/runtime_config_store.py` to expose/save provider-aware translate DTOs and per-provider TTS `config_path` maps with direct-value secret handling, legacy `*_env` cleanup on save, and unchanged file-boundary persistence
- [ ] 1.3 Add or update Python regression coverage for startup loading, config save validation, legacy compatibility reads, and config API error shapes

## 2. Desktop settings contract

- [ ] 2.1 Update desktop settings types, API helpers, and hook payload building for provider-aware translate branches plus the new TTS path-map contract
- [ ] 2.2 Reshape the settings workspace so translate renders `deeplx` / `openai_compatible` / `passthrough` branches, all supported TTS providers stay editable, and secondary TTS tuning moves behind advanced sections
- [ ] 2.3 Add frontend regression tests for translate provider branching, direct-input secret editors, advanced TTS sections, and save payload generation

## 3. Docs and verification

- [ ] 3.1 Update `config/listener.json`, `config/listener.md`, and `docs/wechat-listening-pitfalls.md` for the new translate/TTS config shape and compatibility rules
- [ ] 3.2 Run targeted Python and frontend regression checks, then record any environment-limited manual verification still required
