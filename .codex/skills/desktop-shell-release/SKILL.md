---
name: desktop-shell-release
description: 维护当前仓库 WeChat Auto Shell 的版本同步、tag 发布和 release 验证闭环。用户提到同步 Python/桌面壳版本、打 tag、发 rc/正式版、检查 release smoke、发布安装包或 GitHub Release 时，使用这个 skill。
---

# Desktop Shell Release

维护 WeChat Auto Shell 发版时，不要只改一个版本字段，也不要只推 tag。默认目标是：先对齐版本入口，再跑完整发布闸口，最后推送会触发 GitHub Release 的 tag。

## 先读这些文件

- `docs/wechat-listening-pitfalls.md`
- `docs/desktop-shell-build.md`
- `pyproject.toml`
- `desktop-shell/package.json`
- `desktop-shell/package-lock.json`
- `desktop-shell/src-tauri/Cargo.toml`
- `desktop-shell/src-tauri/Cargo.lock`
- `desktop-shell/src-tauri/tauri.conf.json`
- `scripts/sync_desktop_shell_release_version.py`
- `.github/workflows/windows-release-on-tag.yml`
- `.github/workflows/macos-release-on-tag.yml`
- `references/release-facts.md`

发版属于打包链和对外交付边界。别跳过坑位文档，也别跳过 workflow。

## 工作流

### 1. 先确认这次到底是什么发布动作

- 如果用户只说“打个 tag”“发个 rc”“同步版本”，先读版本入口和发布闸口，再复述目标与成功标准。
- 如果用户要正式版，默认要求版本入口统一到正式版字符串，并按正式 tag 推送。
- 如果用户要 RC，不要先假定所有生态都能接受同一个预发布版本字面值；先以仓库实际构建结果为准。

### 2. 同步版本入口，不要漏改

- 默认优先执行：
  ```bash
  python scripts/sync_desktop_shell_release_version.py --channel stable --base-version 0.1.0
  ```
  或：
  ```bash
  python scripts/sync_desktop_shell_release_version.py --channel rc --base-version 0.1.0 --rc-number 2
  ```
- 如果当前是在 Apple Silicon macOS release 线，tag 前缀要显式切到 `mac-v`：
  ```bash
  python scripts/sync_desktop_shell_release_version.py --channel stable --base-version 0.1.0 --tag-prefix mac-v
  ```
  或：
  ```bash
  python scripts/sync_desktop_shell_release_version.py --channel rc --base-version 0.1.0 --rc-number 2 --tag-prefix mac-v
  ```
- Python 包版本入口：`pyproject.toml`
- 桌面壳版本入口：
  - `desktop-shell/package.json`
  - `desktop-shell/package-lock.json`
  - `desktop-shell/src-tauri/Cargo.toml`
  - `desktop-shell/src-tauri/tauri.conf.json`
- `desktop-shell/src-tauri/Cargo.lock` 里当前仓库自己的 `wechat-auto-shell` 包版本也要保持一致；不要顺手改依赖版本。

脚本会自动生成并打印：

- Python 包版本
- 桌面壳版本
- 推荐 tag

如果用户要求“统一版本”，先用脚本或等价改动更新这些入口，再用构建结果验证。不要反过来先打 tag，再回头补版本。

### 3. 版本改动必须先落到提交

- 版本改动还没进 commit，就不要打发布 tag。
- 如果版本改动需要推到远端，先推分支，再推 tag；否则 release 会挂到旧提交上。
- tag 默认用 annotated tag，不要只打轻量 tag。

### 4. 先跑完整发布闸口，再谈可发版

Windows 老分支最少执行：

```bash
python -m build --sdist --wheel
cd desktop-shell
npm test
npm run build
npm run test:rust
cd ..
python scripts/build_desktop_shell_sidecars.py --python python
cd desktop-shell
npm run tauri -- build
cd ..
python scripts/smoke_desktop_shell_release.py --skip-build
```

Apple Silicon macOS release 线最少执行：

```bash
python3 scripts/build_desktop_shell_sidecars.py --python python3
cd desktop-shell
npm test
npm run build
npm run test:rust
npm run tauri -- build --bundles app
cd ..
python3 scripts/smoke_desktop_shell_release.py --skip-build
```

判断标准：

- Python 包能产出 sdist 和 wheel
- 前端测试、前端构建、Rust 测试全部通过
- Tauri release build 能产出 `exe`、`msi`、`setup.exe`
- release smoke 通过，说明 `/healthz`、bootstrap log 和 single-instance 没回归

### 5. 再推 tag，让 workflow 发版

- Windows 老分支：
  - `v*` tag 会触发 `.github/workflows/windows-release-on-tag.yml`
  - workflow 会发布 `wechat-auto-shell-<version>-windows-x64.msi`、`wechat-auto-shell-<version>-windows-x64-setup.exe` 和 `SHA256SUMS.txt`
  - tag 名里包含 `-` 时，GitHub Release 会被标成 prerelease
- Apple Silicon macOS release 线：
  - `mac-v*` tag 会触发 `.github/workflows/macos-release-on-tag.yml`
  - workflow 会发布 `wechat-auto-shell-<version>-macos-apple-silicon.zip` 和 `SHA256SUMS.txt`
  - prerelease 只看 tag 是否包含 `-rc.`，不能用“contains('-')”
- 两条 release 线的 GitHub Release 标题也要稳定：
  - Windows：`WeChat Auto Shell Windows <version>`
  - mac：`WeChat Auto Shell macOS Apple Silicon <version>`
- 这里的 `<version>` 以桌面壳真实 bundle 版本为准，不直接拿 tag 去前缀后的文本；RC 仍跟随仓库现有 `desktopVersion=0.1.0-<rcNumber>` 语义。

### 6. 收尾时必须明确交付状态

- 版本入口改了哪些文件
- 为什么这么改
- 本地已经跑过哪些验证
- tag 和 GitHub Release 目前是什么状态

## 常见错误

- 只改 `pyproject.toml`，不改桌面壳版本入口。结果：Python 包和安装包版本分裂。
- 只改 `package.json`，漏掉 `Cargo.toml` 或 `tauri.conf.json`。结果：构建产物版本不一致。
- 版本改完不提交，直接打 tag。结果：release 还是指向旧版本元数据。
- 不跑 `python scripts/smoke_desktop_shell_release.py --skip-build`。结果：构建成功，但启动链可能是坏的。
- 强行坚持某个预发布版本字面值，即使 `npm run tauri -- build` 已经报错。结果：版本看起来统一，实际不可发。

## 交付标准

- 版本入口和用户要求的发布类型一致
- 完整发布闸口通过，或明确说明哪一步失败、为什么失败
- 发布 tag 已推送，或明确说明为什么现在不能推
- 最终说明包含：改了什么、为什么、影响、验证结果
