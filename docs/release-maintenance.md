# Release 维护手册

适用分支：`spike/tauri-react-refactor-mac`

这份文档只讲当前 `Apple Silicon macOS` 维护线怎么发版，以及它和 Windows 老分支怎么分工。  
如果你现在要维护的是 `spike/tauri-react-refactor`，不要照着这份文档打 tag；先切到对应分支，再看那条分支里的同名文档。

## 分支分工

| release 线 | 分支 | 平台 | tag 规则 | workflow | 默认公开资产 |
| --- | --- | --- | --- | --- | --- |
| 当前分支 | `spike/tauri-react-refactor-mac` | Apple Silicon macOS | `mac-v0.x.y` / `mac-v0.x.y-rc.n` | `.github/workflows/macos-release-on-tag.yml` | `.app` 压缩包、`SHA256SUMS.txt` |
| 兼容分支 | `spike/tauri-react-refactor` | Windows | `v0.x.y` / `v0.x.y-rc.n` | `.github/workflows/windows-release-on-tag.yml` | `msi`、`setup.exe`、`SHA256SUMS.txt` |

维护约束：

- 当前分支不要推 `v*` tag；那会落到 Windows 老分支的 release 语义里。
- Windows 老分支也不要推 `mac-v*` tag；mac release 线只在当前分支维护。
- GitHub Releases 仍只有一个总入口：[GitHub Releases](https://github.com/Loveyless/wechat-pc-auto/releases)。
- GitHub 页面同一时刻只会有一个 `Latest`；当前仓库接受“双 release 页面并存”的展示方式，不再强求 win/mac 资产挂同一个 release。

## 当前分支的版本规则

版本入口仍是：

- `pyproject.toml`
- `desktop-shell/package.json`
- `desktop-shell/package-lock.json`
- `desktop-shell/src-tauri/Cargo.toml`
- `desktop-shell/src-tauri/Cargo.lock`
- `desktop-shell/src-tauri/tauri.conf.json`

推荐先用脚本同步版本，再决定 tag：

```bash
python3 scripts/sync_desktop_shell_release_version.py --channel stable --base-version 0.1.0 --tag-prefix mac-v
python3 scripts/sync_desktop_shell_release_version.py --channel rc --base-version 0.1.0 --rc-number 1 --tag-prefix mac-v
```

当前分支的版本语义：

- stable：
  - Python：`0.1.0`
  - Desktop bundle：`0.1.0`
  - 推荐 tag：`mac-v0.1.0`
- rc：
  - Python：`0.1.0rc1`
  - Desktop bundle：`0.1.0-1`
  - 推荐 tag：`mac-v0.1.0-rc.1`

注意：

- GitHub Release 标题和公开资产名里的 `<version>` 取自真实 desktop bundle 版本，不直接按 tag 去前缀计算。
- RC 时最容易踩坑：tag 看起来是 `mac-v0.1.0-rc.1`，但公开资产版本仍是 `0.1.0-1`。

## 当前分支发版步骤

1. 先同步远端，确认你在 `spike/tauri-react-refactor-mac` 且工作区干净。
2. 用版本同步脚本更新版本入口。
3. 把版本改动先提交到分支；不要先打 tag。
4. 跑完整发布闸口：

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

5. 只有上面全部通过，才允许打 annotated tag，例如：

```bash
git tag -a mac-v0.1.0 -m "macOS release 0.1.0"
git tag -a mac-v0.1.0-rc.1 -m "macOS rc 0.1.0-rc.1"
```

6. 先 push 分支，再 push tag：

```bash
git push origin spike/tauri-react-refactor-mac
git push origin mac-v0.1.0
```

7. 到 GitHub Release 页面确认：
  - workflow runner 是 `macos-14`
  - release 标题是 `WeChat Auto Shell macOS Apple Silicon <version>`
  - 资产只有 `wechat-auto-shell-<version>-macos-apple-silicon.zip` 和 `SHA256SUMS.txt`
  - tag 包含 `-rc.` 时才会标成 prerelease

## `DMG` 的边界

- `DMG` 继续只作为可选 GUI 专项验收产物。
- 默认自动化不对 `DMG` 背书；它不属于当前 GitHub Release 自动发布资产。
- 如果你要单独验 `DMG`，再在可交互 Finder 会话里执行：

```bash
cd desktop-shell
npm run tauri build
```

## 出问题时先查什么

- 版本入口没改全，导致 tag、bundle version 和公开资产版本对不上。
- 误推了 `v*` tag，触发到 Windows 老分支语义。
- 只看 `.app` / `DMG` 构建成功，没跑 `python3 scripts/smoke_desktop_shell_release.py --skip-build`。
- 用旧 runtime root 验首发默认值，结果被 `~/Library/Application Support/com.wechatauto.shell` 里的历史配置污染。
