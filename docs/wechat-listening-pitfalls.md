# 微信监听踩坑参考（Windows / Weixin / UIAutomation）

## 适用范围
本说明覆盖以下实现：
- `listener_app/group_listener_worker.py`
- `listener_app/sidebar_translate_listener.py`
- `listener_app/sidebar_translate_runtime.py`
- `listener_app/sidebar_runtime_support.py`
- `listener_app/sidebar_ui.py`
- `listener_app/sidebar_tts.py`
- `listener_app/sidebar_shared.py`
- `wechat_auto/window.py`
- `wechat_auto/controls.py`

目标：在不改微信客户端的前提下，稳定监听指定会话的预览消息并在侧边栏展示（可接 DeepLX 翻译）。

启动时监听目标来源于配置文件：`config/listener.json` 的 `listen.targets`；运行中若用户在侧边栏显式添加/删除 target，也会回写该配置，并按“先停旧 worker、确认退出后再启动新 worker”的顺序生效。

## 架构结论
- 监听与 UI 必须分离：`group_listener_worker.py` 负责抓消息，`sidebar_translate_listener.py` 负责展示与翻译。
- 当前侧边栏主进程已经按职责拆分：
  - `sidebar_translate_listener.py` 只保留主入口编排、配置校验、翻译线程和事件分发。
  - `sidebar_translate_runtime.py` 专管 translate provider、DeepLX runtime 与失败 fallback。
  - `sidebar_runtime_support.py` 专管日志轮转、worker 启停支撑、运行时锁与 stdout/stderr reader。
  - `sidebar_ui.py` 专管 Tk UI、消息缓存、快捷键和 TTS 交互入口。
  - `sidebar_tts.py` 专管 TTS runtime、依赖探测与播放器工厂。
  - `sidebar_shared.py` 收敛共享常量、路径/配置工具、文本归一化与通用校验。
  - UI 私有常量/快捷键节流与 TTS 私有 provider/config helper 不应继续堆进 `sidebar_shared.py`；否则 shared 会再次退化成垃圾桶。
  - 拆分后也不要再假设“所有 helper 都挂在 `sidebar_translate_listener.py`”；翻译 helper 的归属是 `sidebar_translate_runtime.py`，worker/runtime helper 的归属是 `sidebar_runtime_support.py`。
- 当前监听主链路已收敛为 `session-only`。
- 当前 worker 为单进程多目标：一次扫描微信主窗口左侧会话列表，覆盖全部 `listen.targets`。
- 运行时 target 变更不走 IPC 热更新；当前实现是“UI 显式增删 -> 回写 `listener.json` -> 先停旧 worker -> 确认退出后再启动新 worker”。
- 当前主路径不再维护 `chat` / `mixed` 监听模式；相关复杂度已从主链路删除。
- 当前分支不再维护任何主动操作微信的能力（发送消息、发送文件、自动回复、写输入框）。
- 默认行为必须低干扰：
  - 不抢焦点（除非 `listen.focus_refresh=true`）
  - 不置顶（除非用户手动开启“置顶”开关）

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

### 10) 重复启动导致同 target 多实例
现象：
- 误重复执行启动命令后，同一个 target 可能被多个进程重复监听，消息重复显示。

处理：
- 为每个 target 增加运行时锁（`logs/.runtime/target_*.lock`）。
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
- `listen.interval_seconds<0.2` 或 `translate.timeout_seconds<=0` 时，worker/翻译线程会在运行期报错。
- `display.width` 过小会导致窗口布局异常。
- `translate.enabled=true` 但未配置 `translate.deeplx_url` / `DEEPLX_URL` 时，旧逻辑会静默降级成原文透传，用户误以为翻译正常。

处理：
- 侧边栏主进程启动时对关键配置做 fail-fast 校验，不合法直接退出并打印错误：
  - `listen.interval_seconds >= 0.2`
  - `listen.load_retry_seconds > 0`
  - `translate.timeout_seconds > 0`
  - `display.width >= 280`
  - `translate.enabled=true and provider=deeplx` 时必须存在 `translate.deeplx_url` 或 `DEEPLX_URL`

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
  - 主程序 `wechat_sidebar.exe`
  - 同目录 worker `group_listener_worker.exe`
- 主程序在 frozen 环境下不再拉 `.py` 文件，而是直接拉同目录的 `group_listener_worker.exe`。
- 打包态默认配置、日志、`.env.local`、运行时锁都按主程序目录解析，不再写回源码目录。

### 20) 打包态目标名乱码，左侧多出脏会话项
现象：
- 源码运行时目标名正常，打包后侧边栏左侧会出现 `����` 之类乱码项。
- 配置里的目标群明明在监听列表里，但实际消息跑进了一个乱码新项里。

根因：
- `group_listener_worker.exe` 是独立子进程。
- 如果打包 worker 的 stdout/stderr 仍按系统本地编码写出，而主程序固定按 UTF-8 读管道，就会把事件里的 `chat_name`、debug 日志、`wx_auto` 日志全部解码坏。

处理：
- worker 启动时强制把 stdout/stderr 重配置为 UTF-8，保证 JSON 行事件在源码态和打包态都维持同一编码契约。
- 侧边栏 UI 在 `session-only` 分支只接受“当前运行 target 集”；它来自启动配置，外加用户在窗口中显式添加/删除并回写配置后的结果。未知 `chat_name` 一律丢弃，不再把脏事件扩展成新的左侧会话项。

### 21) 语音/视频/动画表情占位污染翻译结果
现象：
- DeepLX 会把语音、视频、动画表情这类方括号占位文本翻成 `[Voice Over] 3"`、`[animated emoticon]`、`[Video]` 之类噪音。
- 这类结果没有学习价值，还会占翻译队列和 UI 空间。

处理：
- 在主进程进入翻译前，先过滤明显的媒体占位文本（图片、视频、动画表情、语音等）。
- 当前额外启用了一条激进兜底：凡是整条消息被 ASCII 方括号完整包住（`[ ... ]`），一律按占位文本过滤，不再送翻译。
- 侧边栏头部增加“原文”开关，便于在不改配置的情况下切换查看消息原文，继续补充新的占位样本。
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
- 当前默认 provider 已切到 `tencent_cloud`；这会让启动默认依赖腾讯云凭证和 `config/tencent_tts.json`，不再像旧版那样天然只依赖本机系统语音。
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
- 仅当 `display.tts_auto_read_active_chat=true`、原文关闭、翻译结果可判定为英文时，当前选中会话的新消息才自动朗读。
- 自动朗读在翻译结果落地时触发，不在 `Loading...` 占位阶段触发。
- 配置项只决定启动默认值；运行中由侧边栏头部“朗读”开关接管。

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
- 打包脚本对主程序显式加 `--collect-submodules websockets` 和 `--collect-submodules tencentcloud`，不能继续赌 PyInstaller 会自动猜中函数内动态导入。
- 打包脚本在真正调用 PyInstaller 前，会先用源码态主程序跑一次 `--check-tts-deps`。当前默认 `tts.provider=tencent_cloud`，缺 `tencentcloud` SDK 时必须在这里直接失败，不能等 PyInstaller 白跑完才补刀。
- 主程序启动创建 TTS 时，会先做一次 provider 对应依赖探测；若缺依赖，不再伪装成 `tts configured ...`，而是直接记成 `tts unavailable ... reason=...`。
- 构建后额外执行 `wechat_sidebar.exe --check-tts-deps` 做最小冒烟；这一步失败，说明产物里的 TTS 朗读链路根本不完整，不该继续分发。

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

## 推荐运行命令

### 低干扰稳定方案（推荐）
```bash
python listener_app/sidebar_translate_listener.py ^
  --config ".\config\listener.json"
```

### 接入 DeepLX
在 `config/listener.json` 设置 `translate.enabled=true` 且配置 `translate.deeplx_url`。

### 仅在必要时开启强刷新（会抢焦点）
在 `config/listener.json` 设置 `listen.focus_refresh=true`。

## 排障最小步骤
1. 先看侧边栏状态是否为 `session-only ... running`。
2. 再看 `logging.file` 指向的日志文件是否有 `status: running session-only targets=...`（相对路径按项目根目录解析）。
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
- 启动阶段必须对 `listen.interval_seconds`、`listen.load_retry_seconds`、`translate.timeout_seconds`、`display.width` 做 fail-fast 校验。
- 运行时锁活性判断必须包含 `pid` 与进程启动时间 token，禁止仅靠 `pid` 判断。
- 翻译任务队列必须有上限并具备溢出日志，禁止无界增长。
- TTS 运行期必须输出可定位日志，至少覆盖触发、跳过/拒绝、合成开始、播放成功、失败原因，禁止把错误只留在对象内部状态。
- 左侧消息（非自己消息）UI 头部展示格式为“`[时间] 发送人`”，正文只展示消息内容，不再重复 `发送人:` 前缀。
- 消息正文字号比时间/昵称行大 `2px`；时间与昵称保持基础字号不变。
- 时间与昵称颜色使用更深的灰色，避免在浅底主题下过淡难读。
- 窗口标题必须显示当前选中 target 的完整会话名，不能再固定写死成产品文案。
- 侧边栏窗口初始高度为 `550px`；若屏幕高度不足，自动收缩到可显示范围内。
- UI 字体优先顺序：`Cascadia Code` -> `JetBrains Mono` -> `黑体`；都不可用时回退系统默认字体。
- 默认行为必须是低干扰：
  - 不抢焦点（除非 `listen.focus_refresh=true`）
  - 不置顶（除非用户手动开启“置顶”开关）
