# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

微信 PC macOS 自动化工具的 Rust 原生版。基于 **Tauri 2 + React 19 + Rust** 构建，通过 macOS Accessibility API 与 AppleScript 直接驱动微信，无 Python 依赖。

## 常用命令

```bash
# 安装前端依赖
pnpm install

# 开发模式（前端热更新 + Rust 编译）
pnpm tauri dev

# 构建生产版本（DMG + .app）
pnpm tauri build

# 调试 CLI 工具（在 src-tauri/ 目录下运行）
cargo run --bin ax-test     # AX API 功能测试
cargo run --bin ax-dump     # 导出微信 AX 控件树
cargo run --bin ax-deep     # 深层控件树导出
cargo run --bin ax-msg      # 消息读取测试
cargo run --bin ax-sender   # 发送功能测试
```

注意：cargo 命令需要在 `src-tauri/` 目录下运行，或使用 `--manifest-path src-tauri/Cargo.toml`。

## 架构

### 整体分层

- **前端** (`src/`)：React 19 + TypeScript + Vite 7 + Tailwind CSS v4 + shadcn/ui
- **后端** (`src-tauri/src/`)：Rust + Tauri 2 + tokio 异步运行时
- **通信**：Tauri IPC（invoke / listen），前端通过 `src/lib/tauri-api.ts` 统一封装

### Rust 后端核心模块

- `lib.rs` — Tauri 应用初始化、托盘菜单、状态管理（managed state）
- `task_manager.rs` — 核心调度：消息监听循环、差集算法（锚点法 + 尾部追加 + Bag Diff）、翻译、自动回复、入库
- `adapter/mod.rs` — MacOSAdapter 门面，统一暴露 AX 读取和 AppleScript 操作
- `adapter/ax_reader.rs` — Accessibility API 消息读取（读会话名、消息列表、会话快照）
- `adapter/applescript.rs` — AppleScript 操作（激活微信、搜索会话、复制粘贴发送）
- `events.rs` — EventStore 事件广播到前端
- `db.rs` — rusqlite SQLite 消息持久化，SHA256 去重
- `translator.rs` — DeepLX HTTP 翻译客户端
- `sidebar_window.rs` — 浮窗窗口生命周期（位置跟踪、微信最小化自动隐藏）
- `config.rs` — 配置文件读写（listener.json）
- `commands/` — 26 个 Tauri invoke 命令，按功能分文件（send/listen/sidebar/config/db/sessions/preflight/tray）

### 前端结构

- `App.tsx` — 根组件，路由分发（`?view=sidebar` 走 SidebarView，否则走 MainApp）
- `stores/` — Zustand 状态管理（eventStore / sidebarStore / formStore / preflightStore / toastStore）
- `lib/tauri-api.ts` — 所有 Tauri invoke 调用的统一封装层
- `lib/types.ts` — 前后端共享的 TypeScript 类型定义
- `components/` — 业务页面（SettingsPage / MessageHistory / SendCenter / SidebarView / PreflightBar / EventStream / ServiceLogs）
- `components/ui/` — shadcn/ui 基础组件

### 关键数据流

1. **消息监听**：TaskManager 异步循环 → AX API 读取 → 差集算法识别新消息 → EventStore 广播 + SQLite 入库 + 可选翻译
2. **浮窗（Sidebar）**：独立 WebviewWindow（`?view=sidebar`，always_on_top） → 每 500ms 查询微信窗口位置并跟随
3. **发送**：前端 invoke → commands/send.rs → MacOSAdapter → AppleScript（剪贴板 + 粘贴发送）

## 数据存储

- 消息数据库：`~/Library/Application Support/com.wang.wechat-pc-auto/messages.db`
- 配置文件：`~/Library/Application Support/com.wang.wechat-pc-auto/config/listener.json`

## macOS 特殊要求

- 需要辅助功能权限（系统设置 → 隐私与安全 → 辅助功能）
- macOS 专用依赖：`accessibility-sys`、`core-foundation`、`core-foundation-sys`
- 构建使用 `macos-private-api` feature（Tauri 配置中 `macOSPrivateApi: true`）

## 前端 Path Alias

`@` 映射到 `./src`（在 vite.config.ts 中配置），如 `import { foo } from "@/lib/utils"`。
