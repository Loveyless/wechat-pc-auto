# 微信监听踩坑参考（Windows / Weixin / UIAutomation）

## 适用范围
本说明覆盖以下实现：
- `listener_app/backend_main.py`
- `listener_app/backend_runtime.py`
- `listener_app/runtime_api.py`
- `listener_app/runtime_config.py`
- `listener_app/runtime_engine.py`
- `listener_app/runtime_store.py`
- `listener_app/group_listener_worker.py`
- `listener_app/sidebar_translate_runtime.py`
- `listener_app/sidebar_runtime_support.py`
- `listener_app/sidebar_tts.py`
- `listener_app/sidebar_shared.py`
- `desktop-shell/src/**`
- `wechat_auto/window.py`
- `wechat_auto/controls.py`

目标：在不改微信客户端的前提下，稳定监听左侧会话列表的预览消息并在桌面前端展示（可接 DeepLX / OpenAI-compatible 翻译）。

当前只有一条受支持运行路径：
- `listener_app/backend_main.py` + `desktop-shell/`，默认按 `all_sessions` 方式扫描左侧可见会话列表，不再依赖 `listen.targets` 做主路径筛选。

## 架构结论
- 监听、runtime 和桌面 UI 必须分离：`group_listener_worker.py` 负责抓消息，`backend_runtime.py` 负责 supervisor / 翻译 / TTS / 健康状态，`desktop-shell/` 负责展示和交互。
- 当前主路径已经按职责拆分：
  - `runtime_config.py` 负责主路径唯一配置 schema
  - `sidebar_translate_runtime.py` 专管 translate provider、DeepLX runtime 与失败 fallback
  - `sidebar_runtime_support.py` 专管日志轮转、worker 启停支撑、运行时锁与 stdout/stderr reader
  - `sidebar_tts.py` 专管 TTS runtime、依赖探测与播放器工厂
  - `sidebar_shared.py` 收敛共享常量、路径/配置工具、文本归一化与通用校验
  - `runtime_api.py` 负责 `/healthz`、HTTP API 和 WebSocket 契约
  - `desktop-shell/` 只消费本地 `HTTP + WebSocket`，不直连 worker stdout
- UI 私有状态、provider 私有配置和 shared helper 不应再混堆；否则 shared 很快又会退化成垃圾桶。
- 当前监听主链路已收敛为 `session-only + preview-only`。
- 新主路径 worker 为单进程全会话预览扫描：一次扫描微信主窗口左侧会话列表，覆盖当前可见的群聊和私聊会话。
- 桌面壳会话列表只保留名称、时间、预览文案和未读数；不再显示每行“私聊/群聊”或“预览”标签，避免把全局 `preview-only` 语义误导成会话级实时状态。
- 新主路径桌面壳必须保持 `single-instance`：第二次启动只聚焦已有窗口，不允许额外拉起第二个壳窗口。
- 当前主路径不再维护 `chat` / `mixed` 监听模式；相关复杂度已从主链路删除。
- 当前分支不再维护任何主动操作微信的能力（发送消息、发送文件、自动回复、写输入框）。
- 新主路径运行时会显式暴露 `runtime.monitor_scope=all_sessions`、`runtime.message_fidelity=preview_only`；消息事件继续通过 `capture_level=preview|full` 区分语义，禁止把预览事件冒充完整正文。
- 默认行为必须低干扰：
  - 不抢焦点（除非 `listen.focus_refresh=true`）
  - 不置顶（除非用户手动开启“置顶”开关）
  - 当前“置顶”只改桌面壳主窗口的临时窗口状态，不回写 `listener.json`

## 关键坑位与处理

### 1) 主窗口误匹配（弹层 / 托盘窗口）
现象：
- 进程存在，但拿到的是 `mmui::XDialog` / `XPopover` / 托盘相关窗口，后续监听失败。

根因：
- Weixin 顶层窗口不止一个，按标题/类名粗匹配会命中非主窗口。

处理：
- 在 `wechat_auto/window.py` 中对窗口打分并过滤：
  - 主窗口类优先：`MainWindow` / `WeChatMainWnd*`
  - 弹层/托盘类降权：`popover` / `trayicon` / `shadow` / `toolsavebits`
  - 非主窗口直接跳过

### 2) `session` 预览不是完整消息流
现象：
- 侧边栏能看到新消息，但拿到的是左侧会话预览，不是聊天区全文。
- 长消息、连续多条消息、图片/语音/复杂卡片都会被截断或折叠。

根因：
- 当前方案读的是会话列表条目的预览文本和未读数，不是右侧聊天区消息列表。

结论：
- 当前链路适合“低干扰抓英文素材 / 翻译学习”，不适合“完整消息审计 / 零漏抓取”。

### 3) 会话预览不刷新
现象：
- `session-only` 长时间读到同一预览文本，不产出消息事件。

根因：
- 某些环境下 UIA 读取会话列表可能保持旧快照。

处理：
- 配置项 `listen.focus_refresh=true` 时，worker 只会在“连续缺目标”或“未读快照长期不变”时触发一次 `SwitchToThisWindow`。
- 默认关闭该配置，避免抢焦点；仅在出现“预览不刷新”时开启。

### 4) 抢焦点副作用
现象：
- 监听期间周期性切回微信，影响当前工作窗口。

处理：
- 默认不做轮询抢焦点。
- 仅 `listen.focus_refresh=true` 时才允许抢焦点，而且会受内部冷却与阈值约束，不再每轮执行。

### 5) 单 worker 不等于零成本
现象：
- 单 worker 比原先多 worker 干净，但如果 UIA 树异常，所有 target 会一起受影响。

根因：
- 当前 worker 为单点扫描器；状态与重连也收敛到一个进程。

处理：
- 侧边栏主进程对单 worker 做 supervisor：
  - worker 异常退出后进入 `worker_backoff`
  - 按退避梯度自动重启：`3s -> 6s -> 12s -> 24s -> 30s(cap)`
  - 重新进入 `running` 后退避次数清零
  - 运行时变更 target 时，不会先启动新 worker 再回头清旧 worker；当前实现会先请求旧 worker 退出，超时后再强杀，只有确认旧 worker 已退出后才拉起新 worker。

### 6) Worker 日志与事件混流
现象：
- `wx_auto` 普通日志不是 JSON；若按“纯 JSON 流”解析会报错。

处理：
- `sidebar_runtime_support.py` 中的 worker stdout/stderr reader 会做两类处理：
  - JSON：按事件处理（`status` / `message` / `log`）
  - 非 JSON：作为 `worker raw` 记录

### 7) DeepLX 返回 403（error code: 1010）
现象：
- 翻译调用报 `HTTP Error 403: Forbidden`，响应体常见 `error code: 1010`。

根因：
- 某些 DeepLX 网关会对 Python 默认请求特征做风控，`urllib` 默认 UA 容易被拦截。

处理：
- 在 `listener_app/sidebar_translate_runtime.py` 的 `DeepLXTranslator` 请求头中显式设置：
  - `User-Agent`（浏览器风格）
  - `Accept`
  - `Content-Type: application/json; charset=utf-8`
  - `Origin` / `Referer`
- 对网络层 `URLError` 做有限重试，避免短时握手抖动直接把一次翻译打成失败。
- 保留错误响应体片段，便于定位风控 / 配额问题。

### 8) 中文乱码（侧边栏显示 `�`）
现象：
- 侧边栏日志或消息中出现中文乱码（`�` 或错码文本）。

根因：
- worker 子进程 stdout 使用系统编码（常见 GBK），父进程按 UTF-8 解码，导致错码。

处理：
- worker 启动时强制 UTF-8：
  - 命令行增加 `-X utf8`
  - 环境变量增加 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`

### 9) 重复消息与预览抖动
现象：
- 同一预览文本可能因为 UIA 抖动短时间重复触发。
- 相同文案在后续再次出现时可能需要允许重新展示。

处理：
- worker 只做短防抖（默认 `0.8s`），用于抑制同轮询重复，不做永久去重。
- 侧边栏按 `session_preview_dedupe_window_seconds` 做时间窗去重。
- 去重缓存使用 TTL + 上限清理，避免长期运行时内存无界增长。

调参影响：
- 优先关注 `listen.session_preview_dedupe_window_seconds`
  - 过小：预览抖动更容易重复显示
  - 过大：短时间同文案重复发送更容易被吞

### 10) 重复启动导致监听实例重叠
现象：
- 误重复执行启动命令后，后端主路径若并行启动多份，会造成重复事件或锁冲突。

处理：
- 主路径继续为兼容性 target 元数据维护运行时锁（`logs/.runtime/target_*.lock`）。
- 启动阶段会先扫描 `logs/.runtime`，仅清理 `pid/start_token` 已失效或格式异常的陈旧锁。
- 仍存活的锁必须保留，禁止“启动即全删锁”，否则会破坏单实例约束并造成重复监听。

### 11) PID 复用造成运行时锁误判
现象：
- 仅依赖 `pid` 判断锁活性时，极端情况下可能把“新进程复用旧 pid”误判为同一实例。

处理：
- 运行时锁同时记录 `pid` 与进程启动时间 token（Windows `GetProcessTimes`）。
- 清理陈旧锁前先校验 `pid+token` 一致性，减少误判概率。
- Windows 上锁活性判断不再依赖 `os.kill(pid, 0)`，避免部分 Python/Win32 组合下对无效 PID 抛出异常导致启动即崩。

### 12) 翻译网络抖动卡 UI
现象：
- DeepLX 延迟或超时时，侧边栏滚动和交互明显卡顿。

根因：
- 若在 UI 线程直接做翻译请求，主线程会被网络 I/O 阻塞。

处理：
- 翻译改为后台单线程队列，UI 线程只负责去重与渲染。
- 翻译失败通过事件回流记录日志，不阻塞后续消息处理。

### 13) 翻译队列无限增长
现象：
- 翻译服务慢于消息流入时，若队列无上限，内存会持续增长。

处理：
- 翻译队列改为有界（默认上限 `300`）。
- 队列满时丢弃最旧待翻译任务并输出 `translate queue overflow` 日志，优先保持系统可用。

### 14) 程序先启动，但微信还没启动
现象：
- 先运行侧边栏程序时，若微信尚未启动或未登录，旧逻辑会直接退出，必须手动重启程序。

处理：
- worker 启动阶段改为等待微信就绪，不直接退出。
- 使用 `listen.load_retry_seconds` 控制重试间隔。
- 侧边栏状态栏显示 `waiting_wechat` / `connecting`，不再只有一次性失败文本。

### 15) 监听中途微信被关闭，恢复不了
现象：
- 监听过程中关闭微信后，若不做重连，只会报 `window_lost`。

处理：
- worker 发现窗口丢失后进入 `window_lost -> reconnecting -> running` 状态流。
- 微信重新打开后，重新定位主窗口并恢复所有 target 的 `session` 基线，不要求手动重启侧边栏。

### 16) 长时间运行日志膨胀
现象：
- 持续运行时日志文件增长过快，排障时难以定位近期信息。

处理：
- 启用按大小轮转：单文件约 `10MB` 自动切分，保留最近 `5` 个历史文件。

### 17) 配置脏值导致运行中崩溃
现象：
- `listen.interval_seconds<0.2`、`translate.providers.<provider>.timeout_seconds<=0` 或 provider 缺必填字段时，worker/翻译线程会在运行期报错。
- `translate.enabled=true` 但 active provider 缺少必填字段时，旧逻辑可能静默降级成原文透传，用户误以为翻译正常。

处理：
- 主路径后端启动时对关键配置做 fail-fast 校验，不合法直接退出并打印错误：
  - `listen.interval_seconds >= 0.2`
  - `listen.load_retry_seconds > 0`
  - `translate.providers.deeplx.timeout_seconds > 0` / `translate.providers.openai_compatible.timeout_seconds > 0`
  - `translate.enabled=true and provider=deeplx` 时必须存在 `translate.providers.deeplx.deeplx_url` 或 `translate.providers.deeplx.deeplx_url_env`
  - `translate.providers.deeplx.deeplx_url_env` 只允许 `DEEPLX_URL`
  - `translate.enabled=true and provider=openai_compatible` 时必须存在 `translate.providers.openai_compatible.base_url`、`model`、`api_key`

### 18) 监听体感慢，不一定是 UIA 本身
现象：
- 微信里已经出现新消息，但侧边栏要过一会儿才更新。

根因：
- `listen.interval_seconds` 配太大。
- 若轮询实现是“做完一轮再额外 sleep 一轮”，实际周期会变成“扫描耗时 + 配置间隔”，比配置值更钝。
- UI 线程若过慢地消费 worker 队列，也会再叠加几十到几百毫秒。
- 即使采样很快，DeepLX 网络往返仍然会影响“最终翻译文本出现”的时机。

处理：
- 当前 worker 以“每轮开始时刻”为周期基准，`listen.interval_seconds` 表示目标采样周期，不再额外叠加整轮 `sleep`。
- 默认 `listen.interval_seconds` 调整为 `0.6s`，侧边栏主线程队列消费间隔收紧到 `80ms`。
- 启用 DeepLX 时，侧边栏先展示 `Loading...` 占位，翻译完成后再原位替换，降低“网络没回来就整条空白”的体感延迟。
- 想更灵敏时，优先把 `listen.interval_seconds` 调到 `0.5 ~ 0.8` 区间；最低不要低于 `0.2`，继续下压会线性增加 UIA 扫描频率和 CPU 占用。
- 如果体感仍慢，先区分是“采样慢”还是“翻译慢”；当前实现仍是翻译完成后再渲染最终文本，提频不能消掉 DeepLX 往返延迟。

### 19) 打包后 worker 拉不起来
现象：
- 源码里本地运行正常，但打包成 exe 后主程序一启动就报 worker 启动失败。

根因：
- 开发态可以直接 `python listener_app/group_listener_worker.py`。
- 打包态不能再假设用户机器上有一套可用的 `python + .py` 子进程模型。

处理：
- 打包产物必须包含两个 exe：
  - 主程序 `wechat-auto-shell.exe`
  - 同目录 worker `group_listener_worker.exe`
- 主程序在 frozen 环境下不再拉 `.py` 文件，而是直接拉同目录的 `group_listener_worker.exe`。
- 打包态默认配置、日志、`.env.local`、运行时锁都按主程序目录解析，不再写回源码目录。

### 20) 打包态会话名乱码，左侧多出脏会话项
现象：
- 源码运行时会话名正常，打包后侧边栏左侧会出现 `����` 之类乱码项。
- 实际预览消息会被归到乱码会话项里，看起来像“凭空多了一条脏会话”。

根因：
- `group_listener_worker.exe` 是独立子进程。
- 如果打包 worker 的 stdout/stderr 仍按系统本地编码写出，而主程序固定按 UTF-8 读管道，就会把事件里的 `chat_name`、debug 日志、`wx_auto` 日志全部解码坏。

处理：
- worker 启动时强制把 stdout/stderr 重配置为 UTF-8，保证 JSON 行事件在源码态和打包态都维持同一编码契约。
- 当前桌面壳会按 backend 推过来的 `session_snapshot` / `message` 事件建立会话列表；主路径看的是实际可见会话，不是 `listen.targets` 白名单。
- 如果 `chat_name` 在子进程输出时就被解码坏，前端拿到的就是脏会话名；这类问题该查编码链路，不该回头怀疑“是不是没配目标群”。

### 21) 语音/视频/动画表情占位污染翻译结果
现象：
- DeepLX 会把语音、视频、动画表情这类方括号占位文本翻成 `[Voice Over] 3"`、`[animated emoticon]`、`[Video]` 之类噪音。
- 这类结果没有学习价值，还会占翻译队列和 UI 空间。

处理：
- 在主进程进入翻译前，先过滤明显的媒体占位文本（图片、视频、动画表情、语音等）。
- 当前额外启用了一条激进兜底：凡是整条消息被 ASCII 方括号完整包住（`[ ... ]`），一律按占位文本过滤，不再送翻译。
- 桌面壳顶部功能区提供“原文”开关，默认关闭；打开后才在消息阅读区展开原始预览。
- 当消息 `pendingTranslation=true` 且“原文”关闭时，消息正文区只显示等待中的转圈占位，不展示中文原文；翻译完成后再替换成译文。
- 当消息 `pendingTranslation=true` 且“原文”打开时，可以直接展示中文；这时不再额外显示 loading 占位。
- 这类“原文”开关属于前端显示状态，不回写运行配置。
- `Right` / `Ctrl+Right` 都会复用同一个“原文”开关状态，而不是额外维护一套快捷键私有状态；否则复选框状态和实际显示很容易跑偏。

### 21.1) 带 `http://` / `https://` 的链接消息不该进翻译链路
现象：
- 群里带链接的消息通常是转发、推广、报名或资料入口，DeepLX 翻出来价值低，还会把 URL 连同正文一起塞进侧边栏。

处理：
- 主进程在进入翻译前会额外检查正文里是否包含显式 `http://` 或 `https://`。
- 命中后整条消息直接过滤：不显示、不翻译、不进 TTS。
- 当前只拦显式协议链接，不拦 `www.example.com` 这类裸域名，避免误伤普通文本。

### 22) 系统 TTS 只应读英文，不该读中文/失败文本
现象：
- 如果直接把右侧当前显示文本喂给 TTS，原文模式下会把中文读出来，翻译失败时还可能把 `translate_failed` 一起读掉。

处理：
- 当前手动朗读入口只在“原文关闭 + 正文可判定为英文 + 非 Loading/失败文本”时启用。
- 当前正文支持“轻点朗读”：按下后小位移松开会播放；若形成拖拽选区，或触发双击/三击选词，则不会播放。
- 正文点击范围只覆盖正文字符，不包括时间、发送人和空白区。
- TTS provider 现在走独立配置：`listener.json` 只负责选择 `tts.provider`，provider 私有参数拆到独立 JSON（例如 `config/doubao_tts.json`、`config/tencent_tts.json`）。
- 仓库跟踪的默认 provider 现在回到 `windows_system`；目标不是“偏爱系统语音”，而是保证 fresh install 无密钥也能先进入桌面壳和设置页。
- 仓库跟踪的 provider JSON 只应保留安全默认值；豆包 `appid/access_token`、腾讯云 `secret_id/secret_key` 这类真实凭证应留在 `.env.local` 或 Tauri 运行时目录，不应写回仓库文件。
- `tts.provider=windows_system` 时，仍走 Windows 系统 `System.Speech`，默认优先选 `Microsoft Zira Desktop`，不存在时再回退到其他英文 voice。
- `tts.provider=doubao` 时，走豆包单向流式 WebSocket；当前播放链路要求 provider 配置里的 `audio_format=wav`，否则启动阶段直接报错。
- `tts.provider=tencent_cloud` 时，走腾讯云基础语音合成 `TextToVoice`（官方 Python SDK）；当前播放链路同样只允许 `codec=wav`，不会顺手放开 `mp3/pcm`。
- 腾讯云默认音色当前固定成 `WeJames`，也就是 `VoiceType=501008`；`501008` 不是 `sample_rate`，采样率仍只接受 `8000 / 16000 / 24000`。
- 豆包配置当前额外支持 `sample_rate` / `speech_rate` / `loudness_rate` / `use_cache`。
- 腾讯云配置当前额外支持 `voice_type` / `sample_rate` / `speed` / `volume` / `primary_language` / `segment_rate` / `emotion_*` / `request_timeout_seconds`。
- 豆包链路默认值收敛为 `sample_rate=32000`、`speech_rate=-15`、`loudness_rate=0`、`use_cache=false`。
- `sample_rate` 不再只做“>=8000”这种宽松校验，而是限制在官方支持值集合内；`speech_rate` / `loudness_rate` 也按官方范围 fail-fast 校验，避免把脏值拖到运行时才炸。
- 腾讯云这条链路同样做 fail-fast 校验：`voice_type>0`、`sample_rate ∈ {8000,16000,24000}`、`speed ∈ [-2,6]`、`volume ∈ [-10,10]`、`primary_language ∈ {1,2}`、`segment_rate ∈ {0,1,2}`，避免把脏值拖到请求时才报业务错。
- `use_cache` 只做成显式开关，默认不启用；聊天短句重复率有限，而且缓存会干扰不同语速/音量参数的对比。
- 这条链路允许引入云 TTS，但必须把 provider 私有参数与监听主配置解耦，避免把不同供应商字段继续堆进 `listener.json`。

### 23) 自动朗读只能跟随当前选中会话，不能跟着窗口焦点走
现象：
- 用户切到别的应用时，仍希望当前选中会话的新英文消息继续自动朗读。
- 但如果切换了侧边栏左侧会话，旧会话后续消息不该继续补读，否则就会变成“后台多个群抢着说话”。

处理：
- 自动朗读的判定只看“当前选中会话”，不看操作系统焦点。
- 仅当 `display.tts_auto_read_active_chat=true`，且当前选中会话收到可朗读的英文译文时，当前会话的新消息才自动朗读。
- 自动朗读在翻译结果落地时触发，不在 `Loading...` 占位阶段触发。
- 配置项只决定启动默认值；运行中由桌面壳顶部功能区“朗读”开关接管。
- 这个“朗读”开关必须是真切换：桌面壳通过本地 API 更新 backend runtime 的 `tts.auto_read_enabled`，不能只改前端按钮样式。
- runtime 回推 `tts.updated` 时，切换动作必须带上最新 `auto_read_enabled`；桌面壳据此回写本地 TTS 状态，不能只靠按钮本地猜测结果。

### 24) TTS 出问题但日志看不见
现象：
- 豆包或系统 TTS 明明“没响”，但日志文件里只有启动配置，没有点击正文、自动朗读、合成失败、播放失败的细节。
- 用户只能猜是按钮没触发、条件被拦截、豆包鉴权失败，还是播放链路挂了。
- 还有一种更误导人的情况：日志里已经出现 `tts synthesize success`，甚至业务代码已经走到 `tts played`，但耳朵里仍然没有实际语音。

根因：
- 旧逻辑只在启动时记录 `tts configured ...`。
- 运行期失败原因只写进 TTS 对象内部 `_last_error`，UI 和日志文件都看不到。
- 正文点击与自动朗读的触发点原先也没有补充运行期日志。
- 豆包单向流式返回的 WAV 可能把 `RIFF` / `data` chunk size 写成 `0xFFFFFFFF` 占位值；这种音频有时能被宽松播放器容忍，但 `winsound` 这类 Windows 播放路径兼容性更差，表现成“合成成功但不出声”。

处理：
- TTS runtime 日志统一回流到主进程事件队列，再写入状态栏与 `logging.file`。
- 当前至少会记录这些关键节点：
  - `tts body click queued/rejected`
  - `tts auto queued/skipped/rejected`
  - `tts synthesize start/success`
  - `tts played`
  - `tts failed`
- 日志只记录 provider、endpoint host、字节数、文本预览等排障必需信息，不记录豆包密钥。
- 豆包音频进入 Windows 播放器前，必须先按实际字节数重写 `RIFF` / `data` chunk size，再交给 `winsound`；不能把流式占位头直接落盘播放。
- 这类问题的判断标准不是“豆包有没有回包”，而是“回包是不是标准 WAV”；曾复现过未修正头部时被标准库解析成异常超长时长，修正后才恢复正常播放。

### 25) 打包后自动朗读被触发了，但完全没声音
现象：
- 侧边栏里能看到 `tts auto queued` / `tts body click queued`，说明朗读入口已经触发。
- 但后面立刻跟着 `tts failed backend=doubao error=No module named 'websockets'`，或 `tts failed backend=tencent_cloud error=missing Python module 'tencentcloud...'`，完全听不到声音。

根因：
- 豆包 TTS 运行时依赖 `websockets`。
- 腾讯云 TTS 运行时依赖 `tencentcloud` SDK。
- 当前代码在真正合成时才动态导入这些模块；如果 PyInstaller 没显式收集，主程序照样能启动，但一到朗读分支才现场崩。

处理：
- 打包脚本对主程序显式加 `--collect-submodules websockets`、`--collect-submodules tencentcloud` 和 `--collect-all charset_normalizer`，并通过仓库内 PyInstaller hook 动态补齐 `charset_normalizer` 的发行版级 `__mypyc` 顶层模块；不能继续赌 PyInstaller 会自动猜中函数内动态导入和 `requests` 的字符集依赖链。
- 这些打包依赖和 smoke 脏告警规则现在统一收口到 `scripts/packaging_manifest.json`；如果以后再补动态依赖，先改清单，不要分头改两套脚本。
- 打包脚本在真正调用 PyInstaller 前，会先用源码态主程序跑一次 `--check-tts-deps`。但这一步只检查“当前默认 provider 对应的依赖链”，不是替你自动验证所有云 TTS provider 都可用。
- 主程序启动创建 TTS 时，会先做一次 provider 对应依赖探测；若缺依赖，不再伪装成 `tts configured ...`，而是直接记成 `tts unavailable ... reason=...`。
- 构建后额外执行 `wechat-auto-backend.exe --check-tts-deps` 做最小冒烟；这一步失败，或者打出 `RequestsDependencyWarning`，都说明“当前默认 provider 的朗读链路”不完整，不该继续分发。
- 如果你准备把默认 provider 改成 `doubao` 或 `tencent_cloud` 再发包，就必须额外按目标 provider 跑一遍对应依赖和配置验证，别拿 `windows_system` 的通过结果冒充云 TTS 也没问题。

### 26) 收起左侧菜单后，看不出当前正在看哪个群
现象：
- 多 target 模式下，用户会把左侧菜单收起，只保留右侧消息区。
- 旧实现的窗口标题固定写死成 `WeChat Sidebar session-only`，即使通过快捷键切群，顶部也不给当前会话名。

处理：
- 窗口标题改为始终显示“当前选中 target 的完整会话名”。
- `Up` / `Down` 在焦点不在左侧 target 列表时负责窗口级切群；如果焦点就在 `Listbox` 上，必须保留原生上下选择，否则会出现“一次按键触发两次跳群”的冲突。
- `Ctrl+Up` / `Ctrl+Down` 继续兼容旧版切换会话，标题仍会随 `active_chat` 同步更新。
- `Left` / `Ctrl+Left` / `Ctrl+B` 可以直接展开或收起左侧菜单。
- `Right` / `Ctrl+Right` 可以直接切换“原文”显示，不需要把鼠标拉回头部复选框。
- `F1` 提供快捷键速查，避免“功能做了但没人知道怎么用”。
- 删除当前 target 后，若自动切到下一个 target，标题也必须同步切过去，不能继续挂旧标题。

### 27) 桌面前端一直显示 reconnecting，但 HTTP 接口其实是活的
现象：
- `desktop-shell/` 开发页能正常拉到 `/api/runtime`、`/api/sessions`，列表也能渲染。
- 但状态徽标一直停在 `reconnecting`，控制台反复刷 `WebSocket is closed before the connection is established`。
- 网络面板会出现大量重复的 `/api/runtime`、`/api/sessions` 请求，看起来像“后端不稳”，其实未必。

根因：
- 前端连接逻辑如果把“拉快照”和“建 WebSocket”放在同一个 `useEffect` 里，又让 effect 依赖会在运行时频繁变化，就会反复清理旧连接。
- React 开发态 `StrictMode` 会额外执行一次 mount/unmount 检查；如果没有做连接代次隔离，旧一轮异步请求回来的结果还能继续创建或关闭 socket，形成竞态。
- 结果就是：真正的后端 WS 服务明明可用，前端却自己把还在 `CONNECTING` 的 socket 提前关掉。

处理：
- `desktop-shell/src/hooks/use-desktop-shell.ts` 的连接生命周期必须收敛成“单活跃代次”：
  - 每次重连先递增连接代次，再关闭旧 socket、清掉旧 timer。
  - 快照请求返回后，只有当前代次仍然有效，才允许继续创建 WebSocket。
  - `open` / `error` / `close` 回调也必须校验代次；过期回调只能忽略，不能再改状态或补重连。
- 不要用“删掉 `StrictMode`”掩盖问题；这只能把竞态藏起来，不能证明连接管理是对的。
- 判断是否修好，至少看三点：
  - managed backend 冷启动时先看到 `starting`，而不是误报 `reconnecting`
  - 页面状态最终从 `starting` 变成稳定 `ready`
  - 控制台不再持续刷 `closed before the connection is established`
  - `/events` 能被前端稳定订阅，而不是退回高频 HTTP 轮询

### 27.1) `/healthz` 判活不能再靠裸字符串包含
现象：
- backend 明明已经返回健康 JSON，但桌面壳还在等 ready。
- 最典型的坏实现是拿 `{"status":"ok"}` 当固定字符串去匹配，结果被空格或编码细节打脸。

根因：
- `listener_app/runtime_api.py` 返回的是 JSON，不是约定好的固定字节串。
- 只做裸字符串包含，等于把健康协议写成了“碰巧长这样”。

处理：
- `desktop-shell/src-tauri/src/backend_health.rs` 必须按“HTTP 200 + JSON `status == ok`”判活。
- 这个协议是桌面壳 bootstrap 的硬契约，不允许再退回字符串猜测。

### 27.2) 桌面壳信息层级如果还是一坨卡片，状态再全也会被用废
现象：
- 后端状态、会话导航、消息阅读都能渲染，但如果页面还是“同权重卡片墙”，用户会继续把 `starting` / `degraded` / `preview_only` 看漏。
- 没有会话或没有消息时，如果页面只剩空白容器，用户会误判成前端挂了。

处理：
- 当前桌面壳首页必须稳定分成三层：
  - `Runtime Overview`
  - `Session Navigation`
  - `Message Reading`
- 当前连接态除了 overview 徽标，还会在非 `ready` 时额外显示页面级 connection banner；`startup_failed`、`degraded`、`reconnecting` 不能再共用一套模糊提示。
- 当前会话导航行必须同时暴露这些信息，而且主次分明：
  - 选中态
  - 会话名
  - 会话类型
  - `preview_only` cue（非错误态）
  - 最近更新时间
  - 未读数
- 当前消息卡必须把 `display/translated` 作为第一阅读层；原始预览只留在次级区块；`captureLevel=preview` 和 `pendingTranslation=true` 继续显示，但只能作为次级状态提示。
- `pendingTranslation=true` 时，正文区是否进入 loading 态取决于“原文”开关：关闭时必须 loading，打开时允许直接展示中文原文。
- 当前桌面壳必须显式区分 `no sessions` 和 `no messages` 两种空态，且这两种空态的优先级低于 `startup_failed` / `degraded` / `reconnecting` 这类异常态。

### 28) `npm run tauri build` 现在已经能做一体化桌面壳；密钥仍然外置，但 fresh install 不该被密钥卡死
现象：
- `desktop-shell` 现在已经能产出 `wechat-auto-shell.exe`、`msi`、`nsis`，而且双击壳会自动拉起 backend sidecar。
- 运行时配置、日志、锁会落到 `%LOCALAPPDATA%\com.wechatauto.shell`，不再写回源码目录。
- fresh runtime root 使用仓库跟踪的默认 bundle 配置时，即使没有 `.env.local`，也应该能先进入桌面壳和设置页。
- 但已有 runtime root 若残留旧配置，或者你把 DeepLX / 云 TTS 打开后又没补 URL / 凭据，壳启动阶段仍会 fail-fast。

根因：
- `desktop-shell/package.json` 的 `pretauri` 会先构建 PyInstaller sidecar。
- `desktop-shell/src-tauri/src/main.rs` 现在会托管 `wechat-auto-backend.exe`，并给 sidecar 注入 `WECHAT_AUTO_RUNTIME_ROOT`。
- `listener_app/sidebar_shared.py` 会按运行时根目录解析配置/日志，并在 Tauri 壳下按“运行时目录优先、可执行目录兜底”读取 `.env.local`。
- `listener_app/sidebar_shared.py` 复制 bundle 配置时只补不存在的文件，不覆盖已有 runtime 配置。
- 一体化不等于“顺手把你的密钥一起烘焙进 installer”；这条边界必须保留。

处理：
- `tauri.conf.json` 继续显式维护 Windows `.ico`，否则 bundle 还是会直接失败。
- 仓库跟踪的默认 `config/listener.json` 必须保持这两个首启安全值：
  - `translate.enabled=false`
  - `tts.provider=windows_system`
- 需要 DeepLX 或云 TTS 时，再通过设置页或运行时配置补下面这些条件：
  - `translate.enabled=true and provider=deeplx` 时，显式提供 `translate.providers.deeplx.deeplx_url` 或 `translate.providers.deeplx.deeplx_url_env`
  - `translate.enabled=true and provider=openai_compatible` 时，补 `translate.providers.openai_compatible.base_url/model/api_key`
  - `tts.provider=doubao` 或 `tts.provider=tencent_cloud` 时，补对应 `tts.providers.<provider>.config_path`、provider 私有配置和密钥
- 验 fresh install 时，必须隔离一个干净 runtime root；已有 `%LOCALAPPDATA%\com.wechatauto.shell\config\listener.json` 不会被 installer 覆盖
- 真正的最小验证不是“exe 打开了”，而是：
  - `http://127.0.0.1:8765/healthz` 返回 `{"status":"ok"}`
  - `%LOCALAPPDATA%\com.wechatauto.shell\logs\desktop-shell-bootstrap.log` 出现 `spawned backend sidecar pid=...`

### 28.0) fast regression 的 Rust 单测不该依赖 sidecar 二进制
现象：
- 干净 CI 上直接跑 `cd desktop-shell/src-tauri && cargo test`，会在编译期报 `resource path binaries\\wechat-auto-backend-<target>.exe doesn't exist`。
- 本地偶尔过，只是因为 `desktop-shell/src-tauri/binaries/` 残留了上次打包产物，不是测试链真的对。

根因：
- `desktop-shell/src-tauri/build.rs` 会执行 `tauri_build::build()`，它会读取 `desktop-shell/src-tauri/tauri.conf.json` 的 `bundle.externalBin`。
- `desktop-shell/src-tauri/src/main.rs` 的 `tauri::generate_context!()` 仍要求真实 Tauri 配置存在，所以测试态不能粗暴跳过整份配置。
- `desktop-shell/package.json` 的 `pretauri` 只会在 `npm run tauri ...` 前构建 sidecar；裸 `cargo test` 根本不会走这条链。

处理：
- Rust 单测统一走 `cd desktop-shell && npm run test:rust`。
- 这条命令会把 `desktop-shell/src-tauri/tauri.test.conf.json` 通过 `TAURI_CONFIG` 合并进测试态配置，只清空 `bundle.externalBin`，不改 `frontendDist`。
- 所以 fast regression 仍然必须先跑 `npm run build` 产出 `desktop-shell/dist`，但不需要先打 sidecar。
- sidecar 打包正确性继续由 `python scripts/build_desktop_shell_sidecars.py` 和 `python scripts/smoke_desktop_shell_release.py` 兜底；别把 Rust 单测误当成打包 smoke。

### 28.05) packaging smoke 报 `backend stderr:` 不一定是 backend 真坏了，可能只是日志流分错了
现象：
- `python scripts/smoke_desktop_shell_release.py` 已经等到 `/healthz` ready，但还是因为 bootstrap log 里出现 `backend stderr:` 直接失败。
- 常见表现是 log 里只有 `owner watchdog enabled/lost/recovered/exiting` 这类生命周期提示，没有 traceback，也没有 `startup failed`。

根因：
- `scripts/smoke_desktop_shell_release.py` 会把 `backend stderr:` 视为 release 脏信号，见 `scripts/packaging_manifest.json` 的 forbidden patterns。
- `desktop-shell/src-tauri/src/backend/bootstrap.rs` 会把 sidecar stderr 原样写进 `%LOCALAPPDATA%\\com.wechatauto.shell\\logs\\desktop-shell-bootstrap.log`。
- `listener_app/backend_main.py` 里的 owner watchdog 属于正常生命周期信息，不该走 stderr；真错误才应该走 stderr。

处理：
- owner watchdog 的 `enabled/lost/recovered/exiting` 统一走 stdout。
- `startup failed`、依赖检查失败、非法 owner pid 这类异常继续走 stderr，不要为了过 smoke 把真错误静音。
- 遇到 `backend stderr:` 时，先看具体文案；如果只是正常生命周期提示，修日志分流，不要去放宽 smoke 规则。

### 28.06) tag 发布不能绕过 Windows release smoke
现象：
- 有些仓库会在打 tag 后直接上传 installer / setup.exe，看起来很省事，但一旦构建链和真实启动链脱节，就会把“能编译”误当成“能交付”。
- 这种错最坏的地方不是 CI 红了，而是包已经发出去了，用户才替你做 smoke。

根因：
- `npm run tauri -- build` 只能证明 Tauri/sidecar 构建成功，不能证明 release 壳真的能拉起 backend、通过 `/healthz`、守住 single-instance、也不能证明 bootstrap log 干净。
- tag 发布如果不复用 `python scripts/smoke_desktop_shell_release.py`，就等于又发明了一条和现有发布闸口不一致的发版链。

处理：
- `windows-release-on-tag` 必须先执行完整 Windows 发布闸口，再发布产物：
  - sidecar build
  - frontend test/build
  - `npm run test:rust`
  - `npm run tauri -- build`
  - `python scripts/smoke_desktop_shell_release.py --skip-build`
- 只有 smoke 通过后，才允许把 `msi`、`nsis setup.exe` 和 `SHA256SUMS.txt` 挂到 GitHub Release。
- raw `wechat-auto-shell.exe`、`wechat-auto-backend.exe`、`group_listener_worker.exe` 继续留在本地 build 输出和 workflow artifact，别再把内部 sidecar 当最终用户下载面。
- 分支 / PR 上继续跑 `windows-fast-regression` 和 `windows-packaging-smoke`；`v*` tag 则交给 `windows-release-on-tag`，不要让同一个 tag 触发多套重复 Windows 重活。

### 28.07) Windows 包没图标，通常不是 Tauri 坏了，是你把图标链路只接了一半
现象：
- `wechat-auto-shell.exe`、`msi` 或 `nsis setup.exe` 带着默认空白图标，看起来像没做完的内部包。
- 更隐蔽的一种情况是：主程序图标换了，但 `nsis` 安装器还是默认图标。

根因：
- `desktop-shell/src-tauri/tauri.conf.json` 的 `bundle.icon` 只覆盖可执行文件和 WiX 产物，不能自动把 NSIS installer icon 补上。
- `bundle.windows.nsis.installerIcon` 不显式配置时，Tauri 生成的 `installer.nsi` 会把 `INSTALLERICON` 留空。
- 仓库里如果只留一个占位 `icon.ico`，那打包链当然也只会把占位符带进产物。

处理：
- 图标设计源统一放在 `desktop-shell/src-tauri/icons/icon.svg`。
- Windows 打包输入统一放在 `desktop-shell/src-tauri/icons/icon.ico`，不要再塞一个 70 字节占位文件自欺欺人。
- `desktop-shell/src-tauri/tauri.conf.json` 里同时维护：
  - `bundle.icon`
  - `bundle.windows.nsis.installerIcon`
- 需要重生图标时，执行 `python scripts/generate_desktop_shell_icon.py`，然后至少重跑一次 `cd desktop-shell && npm run tauri -- build`，确认生成出来的 `installer.nsi` 不再是空 `INSTALLERICON`。

### 28.1) 把源码态配置和安装版配置混成一套
现象：
- 安装路径明明不在仓库里，但重装后翻译和 TTS 还是“自动就能用”。
- 你以为安装版会吃项目里的 `config/listener.json`，结果实际行为和仓库文件对不上。

根因：
- Tauri 壳启动 sidecar 时，会把 `runtime_root/config/listener.json` 作为真实配置路径传给 backend。
- 当前这个 `runtime_root` 是 `%LOCALAPPDATA%\com.wechatauto.shell`，不是仓库目录。
- `listener_app/sidebar_shared.py` 还会优先读取 `%LOCALAPPDATA%\com.wechatauto.shell\.env.local`。
- 安装包首次只会补齐缺失的 `config/*.json`；已有 runtime 配置不会被覆盖。

处理：
- 源码态：看仓库根目录 `config/listener.json` 和仓库根目录 `.env.local`
- Tauri 壳 / 安装版：看 `%LOCALAPPDATA%\com.wechatauto.shell\config\listener.json` 和 `%LOCALAPPDATA%\com.wechatauto.shell\.env.local`
- 桌面壳设置页保存时，只会写当前 backend 的 `runtime.config_path` 指向的那套配置，不会替你同步另一套
- 如果要验证 installer 的“真正首启默认值”，先隔离或备份 `%LOCALAPPDATA%\com.wechatauto.shell`，别拿旧 runtime 配置污染结果

### 29) PyInstaller `onefile` 的双进程表现，别误判成重复 spawn
现象：
- 任务管理器里可能同时看到两个 `wechat-auto-backend.exe`
- `group_listener_worker.exe` 也可能同时出现两个同名进程

根因：
- 当前 sidecar 用的是 PyInstaller `onefile`
- Windows 下常见形态就是“同名父进程负责解包 + 同名子进程负责执行 payload”

处理：
- 先看父子关系，不要只看进程名个数。
- 真正要判定“是否重复 spawn”，看这两处：
  - `%LOCALAPPDATA%\com.wechatauto.shell\logs\desktop-shell-bootstrap.log`
  - `%LOCALAPPDATA%\com.wechatauto.shell\logs\.runtime\backend-sidecar.json`
- 当前 Tauri bootstrap 已经加了两层约束：
  - Windows named mutex：串行化 backend bootstrap
  - `pid + start_token` 标记：避免二次启动壳时把“还在启动的 sidecar”误判成没起，再补一份

### 29.1) 第二次启动桌面壳，只能聚焦已有窗口
现象：
- 二次双击 `wechat-auto-shell.exe` 后，如果又弹出一个新壳窗口，或者又补拉了一份 backend sidecar，这就是回归，不是“方便多开”。

根因：
- 壳窗口生命周期和 backend 复用不是一回事。
- backend 已经有 mutex + marker 约束，桌面壳自己再允许多开，只会把窗口状态和 bootstrap 日志搅乱。

处理：
- `desktop-shell/src-tauri/src/main.rs` 必须把 `tauri-plugin-single-instance` 放在第一个 plugin。
- 二次启动只做两件事：记录 `single-instance relaunch detected, focus existing window`，然后聚焦已有 `main` 窗口。
- release 验证必须实际跑 `python scripts/smoke_desktop_shell_release.py`，确认整轮里只有一次 `spawning backend sidecar`。

### 29.2) 安装版点右上角关闭后，backend / worker 不能留后台残活
现象：
- 安装版桌面壳打开后点关闭，窗口没了，但任务管理器里还能看到 `wechat-auto-backend.exe`、`group_listener_worker.exe`，或者其对应的 Python payload 继续活着。
- 再次启动 installer 版时，`/healthz` 已经先通了，表现成“像是自动续命”。

根因：
- 当前 sidecar / worker 都是 PyInstaller `onefile`，Windows 下常见是“父进程 + payload 子进程”的进程树。
- 如果退出时只杀根进程 pid，不杀整棵树，就可能只打掉 bootloader，把真正跑 runtime 的 payload 留在后台。
- `desktop-shell/src-tauri/src/main.rs` 只监听 `RunEvent::Exit` 也不够稳，用户点关闭按钮先经过的是窗口销毁和 `ExitRequested` 路径。

处理：
- `desktop-shell/src-tauri/src/main.rs` 必须至少在 `RunEvent::ExitRequested` 和 `RunEvent::Exit` 两条路径都触发 sidecar 清理，不能只赌最后一个事件。
- `desktop-shell/src-tauri/src/backend/bootstrap.rs` 里的 `ManagedBackendState.kill_owned_child()` 必须按 Windows 进程树清理 `wechat-auto-backend.exe`，不能只调 `CommandChild.kill()`。
- `listener_app/backend_runtime.py` 停 worker 时也必须走进程树清理；`group_listener_worker.exe` 同样是 `onefile`，只 `terminate()` 根 pid 不够。
- Windows 下统一按 `taskkill /PID <pid> /T /F` 处理 tree cleanup；改成单 pid kill 属于回归。
- 仅靠“壳正常退出时杀树”还不够；backend 还要有 owner watchdog：
  - sidecar 启动时由壳注入 `owner_pid + owner_start_token`
  - backend 定期向操作系统确认 owner 是否还活着，而且还是原来那一个进程
  - 当前推荐探针周期 `3s`、失联宽限 `30s`
  - watchdog 是异常退出兜底，不是拿来替代正常 close cleanup
- 验证不要只看窗口是否消失；必须在关闭后确认：
  - `http://127.0.0.1:8765/healthz` 不再可达
  - 任务管理器里不再残留 `wechat-auto-backend.exe` / `group_listener_worker.exe`
  - `%LOCALAPPDATA%\\com.wechatauto.shell\\logs\\desktop-shell-bootstrap.log` 能看到退出清理痕迹

### 30) GUI 配置保存不是热更新，也不是文件直通车
现象：
- 桌面壳设置页能读写配置后，最容易出现两种误判：
  - 误以为前端拿到的是 `listener.json` / provider JSON 原文，可以随便回显 secret
  - 误以为点了“保存”就该立刻影响当前 backend 运行态

根因：
- 当前设置页走的是 `GET /api/config` + `PUT /api/config` 安全 DTO 契约，不是原始文件直出。
- backend 当前仍在启动时加载配置；保存负责落盘，不负责热更新现有 Python runtime。

处理：
- `/api/config` 返回 secret 只允许暴露 `configured/source/env_key` 元数据；`deeplx_url`、`openai_compatible.api_key`、豆包 `appid/access_token`、腾讯云 `secret_id/secret_key` 都不允许回显原值。
- `PUT /api/config` 必须继续遵守文件边界：
  - shared 字段和 `translate.providers` / `tts.providers.<provider>.config_path` 写回 `listener.json`
  - provider 私有字段写回 `tts.providers.<provider>.config_path` 指向的独立 JSON
  - 未知字段必须保留，不能因为 GUI 保存被顺手抹掉
- secret 更新只能走 write-only 模式：`keep/direct/env/clear`；不要把“读取旧 secret 再原样发回去”这种伪方案塞回主路径。
- GUI 的 `env` 模式只会写配置里的 `*_env` 字段，不会回写 `.env.local` 真值。
- DeepLX 不再兼容隐式 env fallback；现有配置必须显式写 `translate.providers.deeplx.deeplx_url` 或 `translate.providers.deeplx.deeplx_url_env=DEEPLX_URL`，自定义 env key 不再受支持。
- `translate.providers.openai_compatible.api_key` 不支持 `env` 模式，也没有 `api_key_env` 兼容字段。
- `display.tts_auto_read_active_chat` 是持久化默认值；桌面壳顶部“朗读开/关”仍然只改当前 runtime，不会反写配置文件。

### 31) “保存并应用”只能重启当前壳自己拥有的 backend
现象：
- 桌面壳已经知道后端地址后，最容易有人偷懒：无论 backend 是谁拉起的，都尝试在 GUI 里点“保存并应用”顺手重启。
- 这会直接把外部 backend、开发态 backend，甚至别的壳实例复用的 backend 一起杀掉。

根因：
- backend 自己并不知道“当前连接是不是桌面壳自己拉起的 child”；ownership 真值只存在于 Tauri bootstrap 的 child handle + marker。
- 当前主路径固定端口会复用现有 backend；不做 ownership 判断就去 kill，等于拿固定端口猜进程所有权。

处理：
- `get_backend_connection_info` 必须显式返回 `managed/ownsBackend/restartSupported`，前端只有在这三个条件和 `runtime.apply_strategy=restart_required` 同时满足时，才允许显示“保存并应用”。
- `restart_owned_backend` 只能操作当前壳实例持有 child handle 且 marker 匹配的 sidecar；复用到的 fixed-port backend 一律退回 `save-only`。
- apply 流程必须是：
  1. `PUT /api/config` 先保存配置
  2. Tauri `restart_owned_backend` 再重启 owned sidecar
  3. 桌面壳复用现有 WebSocket close/reconnect + `/healthz` 恢复链路
- “保存成功但 apply 失败”必须按真相上报：配置已经落盘，但当前重启未完成。不要把它伪装成“保存也失败”，否则 UI 状态和磁盘事实会分叉。

## 推荐运行命令

### 新主路径（推荐）
```bash
python listener_app/backend_main.py ^
  --config ".\config\listener.json"
```

然后在另一个终端启动前端开发页：

```bash
cd desktop-shell
npm run dev
```

### 可选：Tauri 壳调试

```bash
cd desktop-shell
npm run tauri dev
```

前提是本机已经装好 `cargo` / `rustc`。这条命令现在会先构建 sidecar，再由 Tauri 壳自动带起 backend。
没有 Rust toolchain 时，只能先跑 Vite 开发页验证前端契约，不要把它说成 Tauri 壳已经通过。

### 可选：Tauri 壳构建

```bash
cd desktop-shell
npm run tauri build
```

这一步现在能产出一体化 Windows 桌面壳，并把 backend sidecar 一起带上。
更具体的产物路径和验收边界看 `docs/desktop-shell-build.md`。

### 接入 DeepLX
在 `config/listener.json` 设置 `translate.enabled=true`、`translate.provider=deeplx`，并显式配置 `translate.providers.deeplx.deeplx_url` 或 `translate.providers.deeplx.deeplx_url_env`。

### 仅在必要时开启强刷新（会抢焦点）
在 `config/listener.json` 设置 `listen.focus_refresh=true`。

## 排障最小步骤
1. 先看侧边栏状态是否进入 `running` / `waiting_wechat` / `reconnecting` 之一，不要再按“有没有配置目标群”判断主链路是否存活。
2. 再看 `logging.file` 指向的日志文件是否有 `status: running all-session previews`（相对路径按项目根目录解析）。
3. 若无消息事件，临时设 `listen.worker_debug=true`，观察 `debug target=... session_preview=... unread=...` 是否变化。
4. `session_preview` 不变化时，再设 `listen.focus_refresh=true` 验证是否恢复。
5. 若怀疑 TTS 无效，直接搜 `tts ` 关键字：
   - 只有 `tts configured ...`，没有 `tts body click/tts auto`：说明根本没触发朗读入口。
   - 有 `tts body click/tts auto rejected|skipped|ignored`：看 `reason=...` 判断是原文模式、待翻译、已有选区还是非英文。
   - 有 `tts synthesize start` 但没有 `tts played`：优先看后续 `tts failed`，通常就是豆包网络/鉴权/协议或本机播放失败。
   - 有 `tts synthesize success` 但实际没声：优先怀疑返回的是流式占位 WAV 头或 Windows 播放兼容性，不要先把锅甩给豆包鉴权或系统静音。

## 契约约束（后续改动必须保持）
- `group_listener_worker.py` 输出事件必须保持 JSON 行格式（至少包含 `type` 字段）。
- `sidebar_runtime_support.py` 中的 stdout/stderr reader 必须兼容非 JSON stdout 行，不得因解析失败退出。
- 当前监听主链路必须是 `session-only`，禁止恢复 `chat` / `mixed` 分支进入主路径。
- worker 必须以“单进程多 target”方式扫描同一个微信主窗口会话列表，禁止恢复为“一目标一子进程”主架构。
- 同一 target 只允许一个活动侧边栏实例（由运行时锁保证）。
- 去重必须是“时间窗策略”，禁止恢复为全生命周期永久 `set` 去重。
- 每个 target 的消息缓存上限固定 `100` 条，禁止无限增长。
- 启动阶段必须对 `listen.interval_seconds`、`listen.load_retry_seconds`、`translate.providers.<provider>.timeout_seconds` 做 fail-fast 校验。
- 运行时锁活性判断必须包含 `pid` 与进程启动时间 token，禁止仅靠 `pid` 判断。
- 翻译任务队列必须有上限并具备溢出日志，禁止无界增长。
- TTS 运行期必须输出可定位日志，至少覆盖触发、跳过/拒绝、合成开始、播放成功、失败原因，禁止把错误只留在对象内部状态。
- 桌面壳首页结构必须保持为 `Runtime Overview + Session Navigation + Message Reading` 三层，不允许再退回同权重的卡片墙。
- `loading`、`starting`、`ready`、`startup_failed`、`degraded`、`reconnecting` 必须在桌面壳中被稳定区分；非 `ready` 状态必须有 overview 或页面级 banner 承接，禁止重新混成一类弱提示。
- `preview_only` 必须在会话导航和消息阅读中作为非错误 fidelity cue 可见；禁止把预览态冒充完整正文，也禁止把它渲染成失败态。
- `no sessions` 与 `no messages` 必须有显式空态，而且不能覆盖 `startup_failed` / `degraded` / `reconnecting` 这类更高优先级异常态。
- 左侧消息（非自己消息）UI 头部展示格式为“`[时间] 发送人`”，正文只展示消息内容，不再重复 `发送人:` 前缀。
- 消息正文字号比时间/昵称行大 `2px`；时间与昵称保持基础字号不变。
- 时间与昵称颜色使用更深的灰色，避免在浅底主题下过淡难读。
- 窗口标题必须显示当前选中 target 的完整会话名，不能再固定写死成产品文案。
- 侧边栏窗口初始高度为 `550px`；若屏幕高度不足，自动收缩到可显示范围内。
- UI 字体优先顺序：`Cascadia Code` -> `JetBrains Mono` -> `黑体`；都不可用时回退系统默认字体。
- 默认行为必须是低干扰：
  - 不抢焦点（除非 `listen.focus_refresh=true`）
  - 不置顶（除非用户手动开启“置顶”开关）
  - 当前“置顶”只作用于当前桌面壳窗口；重启后默认仍按非置顶启动
