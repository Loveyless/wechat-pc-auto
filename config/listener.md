# listener.json 配置说明

这份文档只描述当前主路径：`listener_app/backend_main.py + desktop-shell/`。
Tk 回退链已经下线，不要再按旧 UI 的字段和行为理解这份配置。

## 启动与运行约束

- 源码态后端入口：`listener_app/backend_main.py`
- 后端支持参数：
  - `--config`
  - `--host`
  - `--http-port`
  - `--ws-port`
  - `--check-tts-deps`
- `desktop-shell/` 通过本地 `HTTP + WebSocket` 消费后端
  - `http://127.0.0.1:8765`
  - `ws://127.0.0.1:8766/events`
- `desktop-shell/` 的 `npm run tauri dev` / `npm run tauri build` 会先构建 PyInstaller sidecar，再由 Tauri 壳自动拉起 backend
- Tauri 壳运行时根目录固定在 `%LOCALAPPDATA%\com.wechatauto.shell`
- 仓库跟踪的默认 `listener.json` 以“首启可进入桌面壳和设置页”为目标：
  - `translate.enabled=false`
  - `tts.provider=windows_system`
  - fresh runtime root 不依赖 `.env.local` 也能启动
- 当前主路径固定为 `session-only + all_sessions + preview-only`

## 当前主路径启动方式

```bash
python listener_app/backend_main.py --config ".\config\listener.json"
cd desktop-shell
npm run dev
```

如果已经装好 Rust toolchain，也可以直接调 Tauri 壳：

```bash
cd desktop-shell
npm run tauri dev
```

没有 `cargo / rustc` 时，不要把 `npm run dev` 的 Vite 页面误判成 Tauri 壳已经验收通过。

## 当前主路径验证与壳构建

最小回归：

```bash
cd desktop-shell
npm test
npm run build
npm run test:rust
```

release 壳交付闸口：

```bash
python scripts/build_desktop_shell_sidecars.py --python python
python scripts/smoke_desktop_shell_release.py
```

更完整的测试 / 构建说明看 `docs/desktop-shell-build.md`。

## 桌面壳设置页与 `/api/config` 契约

- 桌面壳设置页只通过 `GET /api/config` 和 `PUT /api/config` 读写持久化配置；前端不允许直接改 `listener.json` 或 provider 私有 JSON。
- `GET /api/config` 返回的是安全 DTO，不是原始文件直出：
  - `translate` / `display` / `tts` 返回当前可编辑字段
  - `runtime` 返回 `config_path`、`apply_strategy`、`restart_required`、`hot_reload_supported`
  - `deeplx_url`、`api_key`、`appid`、`access_token`、`secret_id`、`secret_key` 这类 secret 只返回 `configured/source/env_key` 元数据，绝不回显原值
- `PUT /api/config` 会按现有文件边界原子写入：
  - `listener.json` 继续承载 shared 字段和 `translate.providers` / `tts.providers.<provider>.config_path`
  - `tts.providers.<provider>.config_path` 指向的 provider 私有 JSON 继续承载豆包 / 腾讯云私有字段
  - 启动加载仍兼容旧 `translate.deeplx_url(_env)`、旧顶层 `translate.timeout_seconds` 和旧 `tts.config_path`，但 GUI 新保存只写新结构
  - 未知字段必须保留，不能因为 GUI 保存被顺手删掉
- secret 更新是 write-only 语义，当前支持四种模式：
  - `keep`：保持现状
  - `direct`：写入新的直接值
  - `env`：改成环境变量名
  - `clear`：清空现有配置
- GUI 不会写 `.env.local` 真值。
  - `env` 模式只会更新配置文件中的 `*_env` 字段。
  - DeepLX 在 GUI 中固定使用 `DEEPLX_URL`，不开放自定义 env key。
  - `translate.providers.openai_compatible.api_key` 不支持 `env` 模式，也没有 `api_key_env` 兼容字段。
- 当前主路径没有 config hot reload。
  - 源码态或外部 backend 连接：只能 `save-only`，保存后必须手动重启 backend
  - Tauri 托管且当前壳拥有 backend sidecar ownership：才允许 `保存并应用`
  - `保存并应用` 本质上仍然是“先落盘，再重启当前壳自己拉起的 backend”，不是运行态热更新

## 源码态与 Tauri 壳别混

- 源码态启动：
  - `python listener_app/backend_main.py --config ".\\config\\listener.json"`
  - 当前 backend 直接吃仓库里的 `config/listener.json`
  - `.env.local` 默认也在仓库根目录
- Tauri 壳 / 安装版启动：
  - `npm run tauri dev`
  - `wechat-auto-shell.exe`
  - installer 安装后的应用
  - 当前 backend 吃 `%LOCALAPPDATA%\\com.wechatauto.shell\\config\\listener.json`
  - `.env.local` 优先读 `%LOCALAPPDATA%\\com.wechatauto.shell\\.env.local`

这两套配置目录不会自动同步。
桌面壳设置页保存时，只会写当前 backend 的 `runtime.config_path` 指向的那套配置，不会顺手把另一套也改掉。
安装目录也不是配置目录；Tauri 壳真正长期落盘的位置还是 `%LOCALAPPDATA%\\com.wechatauto.shell`。

## 完整配置示例

```json
{
  "listen": {
    "interval_seconds": 0.6,
    "load_retry_seconds": 10.0,
    "session_preview_dedupe_window_seconds": 20.0,
    "focus_refresh": false,
    "worker_debug": false
  },
  "translate": {
    "enabled": false,
    "provider": "deeplx",
    "source_lang": "auto",
    "target_lang": "EN",
    "providers": {
      "deeplx": {
        "deeplx_url_env": "DEEPLX_URL",
        "timeout_seconds": 8.0
      },
      "openai_compatible": {
        "base_url": "",
        "model": "",
        "api_key": "",
        "timeout_seconds": 8.0
      },
      "passthrough": {}
    }
  },
  "display": {
    "english_only": true,
    "tts_auto_read_active_chat": true,
    "on_translate_fail": "show_cn_with_reason"
  },
  "tts": {
    "provider": "windows_system",
    "providers": {
      "doubao": {
        "config_path": "config/doubao_tts.json"
      },
      "tencent_cloud": {
        "config_path": "config/tencent_tts.json"
      }
    }
  },
  "logging": {
    "file": "logs/sidebar_listener.log"
  }
}
```

## 字段说明

### `listen`

- `interval_seconds`：worker 轮询间隔（秒），默认 `0.6`
  - 必须 `>= 0.2`
  - 越小越实时，但 UIA 扫描频率和 CPU 占用也越高
- `load_retry_seconds`：微信未启动、未登录或断开后的重试间隔（秒），默认 `10.0`
  - 必须 `> 0`
- `session_preview_dedupe_window_seconds`：`session_preview` 时间窗去重，默认 `20.0`
  - 过小：更容易被预览抖动打出重复消息
  - 过大：短时间相同文案更容易被吞
- `focus_refresh`：是否允许 worker 在必要时切回微信刷新 UIA
  - 默认 `false`
  - 设成 `true` 仍然可能打断当前工作窗口，不要默认开
- `worker_debug`：是否输出 worker 调试日志

### `translate`

- `enabled`：是否启用翻译
  - `true`：调用翻译 provider
  - `false`：原文透传
  - 仓库默认值是 `false`，目的是让首次打包运行不因缺 provider 私有字段直接 fail-fast
- `provider`：当前支持 `deeplx` / `openai_compatible` / `passthrough`
- `source_lang`：源语言，通常填 `auto`
- `target_lang`：目标语言，例如 `EN`
- `providers.deeplx`
  - `deeplx_url`：DeepLX 接口地址的直接值
  - `deeplx_url_env`：DeepLX URL 对应的环境变量名
    - 只允许写成 `DEEPLX_URL`
    - 仓库默认值固定为 `DEEPLX_URL`
    - 清空这个字段就等于显式关闭 env 模式，不会再偷偷 fallback
  - `timeout_seconds`：DeepLX 请求超时（秒），必须 `> 0`
  - 当 `translate.enabled=true` 且 `provider=deeplx` 时，若 `deeplx_url` 和 `deeplx_url_env` 都为空，启动阶段会 fail-fast
- `providers.openai_compatible`
  - `base_url`：OpenAI-compatible Chat Completions 入口基地址
  - `model`：请求模型名
  - `api_key`：直接值密钥
    - 当前配置契约不支持 `api_key_env`
    - 桌面壳 GUI 只支持 direct/clear，不会把这个字段改成 env 模式
  - `timeout_seconds`：请求超时（秒），必须 `> 0`
  - 当 `translate.enabled=true` 且 `provider=openai_compatible` 时，`base_url`、`model`、`api_key` 三个字段都必须存在
- `providers.passthrough`
  - 当前固定为空对象；只保留 shared 语言方向字段，不发起外部翻译请求
- 启动加载兼容旧结构：
  - 旧 `translate.deeplx_url`
  - 旧 `translate.deeplx_url_env`
  - 旧顶层 `translate.timeout_seconds`
  - 兼容只用于读；新保存结果只写 `translate.providers.*`

`.env.local` 读取顺序：

- 源码态默认读仓库根目录 `.env.local`
- Tauri 壳优先读 `%LOCALAPPDATA%\com.wechatauto.shell\.env.local`
- 若运行时目录没有，再回退到 `wechat-auto-shell.exe` 同目录 `.env.local`

当前默认打包配置不要求首启必须带 `.env.local`。
但只要你把 `translate.enabled=true` 且 `provider=deeplx`，DeepLX URL 仍然必须通过 `translate.providers.deeplx.deeplx_url` 或 `DEEPLX_URL` 提供。

### `display`

- `english_only`：是否只显示翻译后的文本
- `tts_auto_read_active_chat`：是否自动朗读当前选中会话的新英文消息
  - 这是持久化默认值
  - 桌面壳顶部“朗读开/关”是 runtime-only toggle，通过 `/api/runtime/tts-auto-read` 更新当前运行态，不会反写这个字段
- `on_translate_fail`：翻译失败回退策略
  - `show_cn_with_reason`
  - `show_cn`
  - `show_reason`

主路径只消费上面这三个字段。
如果你的 `listener.json` 里还残留 `display.width`、`display.side` 之类旧 UI 字段，当前主路径会容忍它们出现在原始 JSON 中，但不会再把它们当成受支持契约。

### `tts`

- `provider`：TTS 后端
  - `windows_system`
  - `doubao`
  - `tencent_cloud`
  - 仓库默认值是 `windows_system`，目的是让 fresh install 不依赖云凭据也能首启进入设置页
- `providers.doubao.config_path` / `providers.tencent_cloud.config_path`：provider 私有配置文件路径
  - 相对路径优先按 `listener.json` 所在目录解析
  - 找不到时再按项目根目录解析
  - 推荐把 provider 私有参数拆到独立 JSON，不要把不同供应商字段继续堆回 `listener.json`
  - `windows_system` 没有 provider 私有路径
- 启动加载兼容旧结构：
  - 若当前激活 provider 缺失 `tts.providers.<provider>.config_path`，会回退读取旧 `tts.config_path`
  - GUI 新保存只写 `tts.providers.<provider>.config_path`
  - 未激活 provider 的路径配置会继续保留，不会因为切换 provider 被清掉

### `logging`

- `file`：运行日志输出文件路径
  - 相对路径按当前运行根目录解析
  - 源码态根目录是仓库根目录
  - Tauri 壳根目录是 `%LOCALAPPDATA%\com.wechatauto.shell`

## `config/doubao_tts.json` 示例

```json
{
  "provider": "doubao",
  "endpoint": "wss://openspeech.bytedance.com/api/v3/tts/unidirectional/stream",
  "appid_env": "VOLCENGINE_TTS_APPID",
  "access_token_env": "VOLCENGINE_TTS_ACCESS_TOKEN",
  "resource_id": "seed-tts-2.0",
  "speaker": "en_female_dacey_uranus_bigtts",
  "audio_format": "wav",
  "sample_rate": 32000,
  "speech_rate": -15,
  "loudness_rate": 0,
  "use_cache": false,
  "uid": "wechat-pc-auto",
  "connect_timeout_seconds": 10.0
}
```

### `doubao_tts.json` 字段说明

- 仓库跟踪的 `config/doubao_tts.json` 默认只保留安全默认值。
- `appid` / `access_token` 在仓库默认值里应保持空串；真实凭证优先放 `.env.local` 或 Tauri 运行时目录对应的 `.env.local`。
- `provider`：固定为 `doubao`
- `endpoint`：单向流式 WebSocket 地址
- `appid_env` / `access_token_env`：凭证环境变量名
- `appid` / `access_token`：也支持直接写死，但不推荐
- `resource_id`：豆包语音资源 ID，例如 `seed-tts-2.0`
- `speaker`：音色 ID，必须和 `resource_id` 匹配
- `audio_format`：当前必须是 `wav`
- `sample_rate`：当前只接受 `8000 / 16000 / 22050 / 24000 / 32000 / 44100 / 48000`
- `speech_rate`：允许范围 `-50 ~ 100`
- `loudness_rate`：允许范围 `-50 ~ 100`
- `use_cache`：是否启用豆包缓存，默认 `false`
- `uid`：业务侧用户标识
- `connect_timeout_seconds`：建连超时，必须 `> 0`

## `config/tencent_tts.json` 示例

```json
{
  "provider": "tencent_cloud",
  "secret_id": "",
  "secret_key": "",
  "secret_id_env": "TENCENTCLOUD_SECRET_ID",
  "secret_key_env": "TENCENTCLOUD_SECRET_KEY",
  "endpoint": "tts.tencentcloudapi.com",
  "region": "",
  "voice_type": 501008,
  "codec": "wav",
  "sample_rate": 16000,
  "speed": 0.0,
  "volume": 0.0,
  "primary_language": 2,
  "model_type": 1,
  "project_id": 0,
  "segment_rate": 0,
  "enable_subtitle": false,
  "request_timeout_seconds": 15.0
}
```

### `tencent_tts.json` 字段说明

- 仓库跟踪的 `config/tencent_tts.json` 默认只保留安全默认值。
- `secret_id` / `secret_key` 在仓库默认值里应保持空串；真实凭证优先放 `.env.local` 或 Tauri 运行时目录对应的 `.env.local`。
- `provider`：固定为 `tencent_cloud`
- `secret_id` / `secret_key`：腾讯云密钥本体；推荐留空并通过环境变量注入
- `secret_id_env` / `secret_key_env`：凭证环境变量名
- `endpoint`：默认 `tts.tencentcloudapi.com`
- `region`：可选地域；留空时不额外带 `X-TC-Region`
- `voice_type`：音色 ID，必须是正整数
- `codec`：当前必须是 `wav`
- `sample_rate`：当前只接受 `8000 / 16000 / 24000`
- `speed`：允许范围 `-2.0 ~ 6.0`
- `volume`：允许范围 `-10.0 ~ 10.0`
- `primary_language`：只接受 `1`（中文）或 `2`（英文）
- `model_type`：当前只接受 `1`
- `project_id`：必须 `>= 0`
- `segment_rate`：只接受 `0 / 1 / 2`
- `enable_subtitle`：是否开启时间戳
- `emotion_category`：情感参数，仅多情感音色可用
- `emotion_intensity`：只有 `emotion_category` 非空时才生效，允许范围 `50 ~ 200`
- `request_timeout_seconds`：SDK 请求超时，必须 `> 0`

## 当前主路径运行语义

- 主路径固定为 `session-only`，不会恢复 `chat` / `mixed`
- 主路径固定按 `all_sessions` 扫描左侧可见会话
- `runtime.monitor_scope=all_sessions`
- `runtime.message_fidelity=preview_only`
- `/healthz` 只表达 backend runtime 是否能服务桌面壳，不表达“微信 worker 是否已经抓到消息”

如果你要看更完整的运行约束、健康契约和打包排障，去读 `docs/wechat-listening-pitfalls.md`。
