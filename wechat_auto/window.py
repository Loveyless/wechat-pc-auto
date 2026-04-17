from __future__ import annotations

import json
import os
import subprocess
import textwrap
import time
from dataclasses import dataclass
from typing import Any, Callable

from .logger import log

WECHAT_PROCESS_CANDIDATES = ("WeChat", "Weixin", "微信")
JXA_TIMEOUT_SECONDS = 4.0
POLL_RETRY_INTERVAL_SECONDS = 0.05
POPUP_ROLE_TOKENS = ("menu", "popover", "sheet", "dialog")
POPUP_SUBROLE_TOKENS = ("dialog", "systemdialog", "floating")


class JxaAutomationError(RuntimeError):
    """JXA 调用失败。"""


class AccessibilityPermissionError(JxaAutomationError):
    """当前进程没有辅助功能权限。"""


def _is_accessibility_error(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    return (
        "-25211" in text
        or "assistive access" in text
        or "辅助访问" in text
        or "辅助功能" in text
        or "not allowed assistive access" in text
    )


def _run_jxa_json(script: str, timeout: float = JXA_TIMEOUT_SECONDS) -> Any:
    try:
        completed = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise JxaAutomationError(f"osascript timeout after {timeout:.1f}s") from exc

    stdout = str(completed.stdout or "").strip()
    stderr = str(completed.stderr or "").strip()
    if completed.returncode != 0:
        detail = stderr or stdout or f"osascript failed with exit={completed.returncode}"
        if _is_accessibility_error(detail):
            raise AccessibilityPermissionError(detail)
        raise JxaAutomationError(detail)

    if not stdout:
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise JxaAutomationError(f"invalid JXA JSON payload: {stdout[:200]}") from exc


@dataclass
class WindowCandidate:
    process_name: str
    pid: int
    title: str
    role: str
    subrole: str
    miniaturized: bool
    position: list[int] | None
    size: list[int] | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any], *, process_name: str, pid: int) -> "WindowCandidate":
        title = str(payload.get("title") or "").strip()
        role = str(payload.get("role") or "").strip()
        subrole = str(payload.get("subrole") or "").strip()
        raw_position = payload.get("position")
        raw_size = payload.get("size")
        position = [int(v) for v in raw_position] if isinstance(raw_position, list) else None
        size = [int(v) for v in raw_size] if isinstance(raw_size, list) else None
        return cls(
            process_name=process_name,
            pid=int(pid),
            title=title,
            role=role,
            subrole=subrole,
            miniaturized=bool(payload.get("miniaturized")),
            position=position,
            size=size,
        )

    @property
    def area(self) -> int:
        if not self.size or len(self.size) != 2:
            return 0
        return max(0, int(self.size[0])) * max(0, int(self.size[1]))


class MacWeChatWindow:
    """给现有 worker 保持近似 UIA 风格的窗口句柄外观。"""

    def __init__(self, manager: "WeChatWindow", candidate: WindowCandidate):
        self._manager = manager
        self._process_name = candidate.process_name
        self._pid = candidate.pid
        self._title = candidate.title

    def Exists(self, timeout: float = 0.0) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            if self._manager.current_main_window() is not None:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(POLL_RETRY_INTERVAL_SECONDS)

    def SwitchToThisWindow(self) -> bool:
        return self._manager.activate_current_window()

    def IsMinimize(self) -> bool:
        current = self._manager.current_main_window()
        return bool(current and current.miniaturized)

    def Restore(self) -> bool:
        return self._manager.restore_current_window()

    def has_popup_or_menu(self) -> bool:
        return self._manager.has_popup_or_menu()

    def run_jxa(self, script: str, timeout: float = JXA_TIMEOUT_SECONDS) -> Any:
        return self._manager.run_jxa(script, timeout=timeout)

    @property
    def process_name(self) -> str:
        return self._process_name

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def title(self) -> str:
        return self._title


class WeChatWindow:
    def __init__(
        self,
        *,
        script_runner: Callable[[str, float], Any] | None = None,
    ):
        self.window: MacWeChatWindow | None = None
        self._script_runner = script_runner or _run_jxa_json
        self._last_state = "idle"
        self._last_detail = ""
        self._last_process_name = ""
        self._last_pid = 0

    def run_jxa(self, script: str, *, timeout: float = JXA_TIMEOUT_SECONDS) -> Any:
        return self._script_runner(script, timeout)

    def _set_status(self, state: str, detail: str) -> None:
        self._last_state = str(state or "").strip() or "unknown"
        self._last_detail = str(detail or "").strip()

    def get_last_state(self) -> str:
        return self._last_state

    def get_last_detail(self) -> str:
        return self._last_detail

    def _build_process_query_script(self) -> str:
        process_names = ", ".join(json.dumps(name) for name in WECHAT_PROCESS_CANDIDATES)
        return textwrap.dedent(
            f"""
            const systemEvents = Application("System Events");
            const candidates = [{process_names}];
            function readProcessEntry(proc) {{
              try {{
                const pid = Number(proc.unixId());
                const procName = String(proc.name() || "");
                if (!procName || !pid) {{
                  return null;
                }}
                return {{ name: procName, pid: pid }};
              }} catch (error) {{
                return null;
              }}
            }}
            function readProcessByName(name) {{
              try {{
                const proc = systemEvents.processes.byName(name);
                return readProcessEntry(proc);
              }} catch (error) {{
                return null;
              }}
            }}
            let found = null;
            for (const name of candidates) {{
              const current = readProcessByName(name);
              if (current) {{
                found = current;
                break;
              }}
            }}
            if (!found) {{
              try {{
                const processes = systemEvents.processes();
                for (const proc of processes) {{
                  const current = readProcessEntry(proc);
                  if (current && candidates.includes(current.name)) {{
                    found = current;
                    break;
                  }}
                }}
              }} catch (error) {{
                // ignore and let Python-side fallback continue.
              }}
            }}
            JSON.stringify(found);
            """
        ).strip()

    def _build_window_query_script(self, process_name: str, pid: int) -> str:
        quoted_name = json.dumps(process_name)
        return textwrap.dedent(
            f"""
            const systemEvents = Application("System Events");
            const targetPid = {int(pid)};
            function findProcessByPid() {{
              try {{
                const processes = systemEvents.processes();
                for (const proc of processes) {{
                  try {{
                    if (Number(proc.unixId()) === targetPid) {{
                      return proc;
                    }}
                  }} catch (error) {{
                    // ignore and keep scanning sibling processes.
                  }}
                }}
              }} catch (error) {{
                // ignore and let byName fallback continue.
              }}
              return null;
            }}
            let proc = findProcessByPid();
            if (!proc) {{
              proc = systemEvents.processes.byName({quoted_name});
            }}
            const windows = proc.windows();
            const items = windows.map(window => {{
              let position = null;
              let size = null;
              try {{
                position = window.position();
              }} catch (error) {{
                position = null;
              }}
              try {{
                size = window.size();
              }} catch (error) {{
                size = null;
              }}
              return {{
                title: String(window.name() || ""),
                role: String(window.role() || ""),
                subrole: String(window.subrole() || ""),
                miniaturized: Boolean(window.miniaturized()),
                position: position,
                size: size,
              }};
            }});
            JSON.stringify(items);
            """
        ).strip()

    def _build_ax_window_query_script(self, pid: int) -> str:
        return textwrap.dedent(
            f"""
            ObjC.import("Cocoa");
            ObjC.bindFunction("AXUIElementCreateApplication", ["id", ["unsigned int"]]);
            ObjC.bindFunction("AXUIElementCopyAttributeValue", ["int", ["id", "id", "id*"]]);

            function rawAttr(element, name) {{
              const value = Ref();
              const err = $.AXUIElementCopyAttributeValue(element, $(name), value);
              if (Number(err) !== 0 || !value[0]) {{
                return null;
              }}
              return value[0];
            }}

            function jsAttr(element, name) {{
              const value = rawAttr(element, name);
              if (!value) {{
                return null;
              }}
              try {{
                return value.js;
              }} catch (error) {{
                return null;
              }}
            }}

            function stringAttr(element, name) {{
              const value = jsAttr(element, name);
              if (value === null || value === undefined) {{
                return "";
              }}
              return String(value);
            }}

            function boolAttr(element, name) {{
              const value = jsAttr(element, name);
              return Boolean(value);
            }}

            function arrayAttr(element, name) {{
              const value = jsAttr(element, name);
              return Array.isArray(value) ? value : [];
            }}

            function pushCandidate(items, seen, window) {{
              if (!window) {{
                return;
              }}
              const title = stringAttr(window, "AXTitle");
              const role = stringAttr(window, "AXRole");
              const subrole = stringAttr(window, "AXSubrole");
              const miniaturized = boolAttr(window, "AXMinimized");
              const signature = [title, role, subrole, miniaturized ? "1" : "0"].join("|");
              if (seen[signature]) {{
                return;
              }}
              seen[signature] = true;
              items.push({{
                title: title,
                role: role,
                subrole: subrole,
                miniaturized: miniaturized,
                position: null,
                size: null,
              }});
            }}

            const app = $.AXUIElementCreateApplication({int(pid)});
            const items = [];
            const seen = Object.create(null);
            for (const window of arrayAttr(app, "AXWindows")) {{
              pushCandidate(items, seen, window);
            }}
            pushCandidate(items, seen, rawAttr(app, "AXMainWindow"));
            pushCandidate(items, seen, rawAttr(app, "AXFocusedWindow"));
            JSON.stringify(items);
            """
        ).strip()

    def _build_popup_query_script(self, pid: int) -> str:
        return textwrap.dedent(
            f"""
            ObjC.import("Cocoa");
            ObjC.bindFunction("AXUIElementCreateApplication", ["id", ["unsigned int"]]);
            ObjC.bindFunction("AXUIElementCopyAttributeValue", ["int", ["id", "id", "id*"]]);

            function attr(element, name) {{
              const value = Ref();
              const err = $.AXUIElementCopyAttributeValue(element, $(name), value);
              if (Number(err) !== 0 || !value[0]) {{
                return null;
              }}
              try {{
                return value[0].js;
              }} catch (error) {{
                return null;
              }}
            }}

            function stringAttr(element, name) {{
              const value = attr(element, name);
              if (value === null || value === undefined) {{
                return "";
              }}
              return String(value);
            }}

            function arrayAttr(element, name) {{
              const value = attr(element, name);
              return Array.isArray(value) ? value : [];
            }}

            function isPopupNode(element) {{
              const role = stringAttr(element, "AXRole").toLowerCase();
              const subrole = stringAttr(element, "AXSubrole").toLowerCase();
              const title = stringAttr(element, "AXTitle").toLowerCase();
              return (
                role === "axmenu" ||
                role.includes("menu") ||
                role.includes("popover") ||
                role.includes("sheet") ||
                role.includes("dialog") ||
                subrole.includes("dialog") ||
                subrole.includes("systemdialog") ||
                subrole.includes("floating") ||
                title.includes("popup") ||
                title.includes("菜单") ||
                title.includes("弹窗")
              );
            }}

            function shouldSkipSubtree(element) {{
              const role = stringAttr(element, "AXRole").toLowerCase();
              return role === "axmenubar" || role === "axmenubaritem";
            }}

            function hasPopup(nodes, depth) {{
              if (!Array.isArray(nodes) || depth > 4) {{
                return false;
              }}
              for (const node of nodes) {{
                if (!node) {{
                  continue;
                }}
                if (shouldSkipSubtree(node)) {{
                  continue;
                }}
                if (isPopupNode(node)) {{
                  return true;
                }}
                if (hasPopup(arrayAttr(node, "AXChildren"), depth + 1)) {{
                  return true;
                }}
              }}
              return false;
            }}

            const app = $.AXUIElementCreateApplication({int(pid)});
            const has_popup =
              hasPopup(arrayAttr(app, "AXWindows"), 0) ||
              hasPopup(arrayAttr(app, "AXChildren"), 0);
            JSON.stringify({{ has_popup: has_popup }});
            """
        ).strip()

    def _build_activate_script(self, process_name: str) -> str:
        quoted_name = json.dumps(process_name)
        return textwrap.dedent(
            f"""
            const app = Application({quoted_name});
            app.activate();
            JSON.stringify({{ ok: true }});
            """
        ).strip()

    def _build_restore_script(self, process_name: str, pid: int) -> str:
        quoted_name = json.dumps(process_name)
        return textwrap.dedent(
            f"""
            const systemEvents = Application("System Events");
            const targetPid = {int(pid)};
            function findProcessByPid() {{
              try {{
                const processes = systemEvents.processes();
                for (const proc of processes) {{
                  try {{
                    if (Number(proc.unixId()) === targetPid) {{
                      return proc;
                    }}
                  }} catch (error) {{
                    // ignore and keep scanning sibling processes.
                  }}
                }}
              }} catch (error) {{
                // ignore and let byName fallback continue.
              }}
              return null;
            }}
            let proc = findProcessByPid();
            if (!proc) {{
              proc = systemEvents.processes.byName({quoted_name});
            }}
            const windows = proc.windows();
            for (const window of windows) {{
              try {{
                window.miniaturized = false;
              }} catch (error) {{
                // 有些 WeChat 版本不暴露 miniaturized，可忽略并继续尝试其它窗口。
              }}
            }}
            const app = Application({quoted_name});
            app.activate();
            JSON.stringify({{ ok: true }});
            """
        ).strip()

    def _query_process_info(self) -> dict[str, Any] | None:
        payload = None
        try:
            payload = self.run_jxa(self._build_process_query_script())
        except JxaAutomationError:
            payload = None
        if not isinstance(payload, dict):
            return self._query_process_info_from_ps()
        try:
            name = str(payload.get("name") or "").strip()
            pid = int(payload.get("pid") or 0)
        except Exception:
            return self._query_process_info_from_ps()
        if not name or pid <= 0:
            return self._query_process_info_from_ps()
        return {"name": name, "pid": pid}

    def _query_process_info_from_ps(self) -> dict[str, Any] | None:
        try:
            completed = subprocess.run(
                ["/bin/ps", "-axo", "pid=,comm="],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
        except Exception:
            return None
        if completed.returncode != 0:
            return None

        candidate_set = {name.lower() for name in WECHAT_PROCESS_CANDIDATES}
        for raw_line in str(completed.stdout or "").splitlines():
            line = str(raw_line or "").strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            raw_pid, raw_command = parts
            try:
                pid = int(raw_pid)
            except ValueError:
                continue
            command = str(raw_command or "").strip()
            if not command:
                continue
            process_name = os.path.basename(command)
            process_name = process_name.strip() or command
            normalized_name = process_name.lower()
            # `ps comm` 里可能先出现 WeChat helper；这里只接受主进程可执行名，避免误连辅助进程。
            if normalized_name not in candidate_set:
                continue
            return {"name": process_name, "pid": pid}
        return None

    def _query_window_candidates(self, process_name: str, pid: int) -> list[WindowCandidate]:
        system_events_error: JxaAutomationError | None = None

        try:
            payload = self.run_jxa(self._build_window_query_script(process_name, pid))
        except JxaAutomationError as exc:
            system_events_error = exc
        else:
            if isinstance(payload, list):
                candidates = [
                    WindowCandidate.from_payload(item, process_name=process_name, pid=pid)
                    for item in payload
                    if isinstance(item, dict)
                ]
                if candidates:
                    return candidates

        try:
            ax_payload = self.run_jxa(self._build_ax_window_query_script(pid))
        except JxaAutomationError:
            if system_events_error is not None:
                raise system_events_error
            raise

        if not isinstance(ax_payload, list):
            if system_events_error is not None:
                raise system_events_error
            return []

        candidates = [
            WindowCandidate.from_payload(item, process_name=process_name, pid=pid)
            for item in ax_payload
            if isinstance(item, dict)
        ]
        if candidates:
            return candidates
        if system_events_error is not None:
            raise system_events_error
        return []

    def _query_ax_popup_state(self, pid: int) -> bool:
        payload = self.run_jxa(self._build_popup_query_script(pid))
        if not isinstance(payload, dict):
            return False
        return bool(payload.get("has_popup"))

    def _is_popup_candidate(self, candidate: WindowCandidate) -> bool:
        role = candidate.role.strip().lower()
        subrole = candidate.subrole.strip().lower()
        title = candidate.title.strip().lower()
        if any(token in role for token in POPUP_ROLE_TOKENS):
            return True
        if any(token in subrole for token in POPUP_SUBROLE_TOKENS):
            return True
        return any(token in title for token in ("菜单", "弹窗", "popup"))

    def _candidate_score(self, candidate: WindowCandidate) -> int:
        score = 0
        if not self._is_popup_candidate(candidate):
            score += 200
        title_lower = candidate.title.lower()
        if "微信" in candidate.title or "wechat" in title_lower or "weixin" in title_lower:
            score += 60
        if candidate.subrole.strip().lower() in ("", "axstandardwindow", "standard window"):
            score += 40
        if not candidate.miniaturized:
            score += 30
        score += min(candidate.area // 20000, 120)
        return score

    def _pick_main_window(self, candidates: list[WindowCandidate]) -> WindowCandidate | None:
        normal_windows = [item for item in candidates if not self._is_popup_candidate(item)]
        if not normal_windows:
            return None
        return max(normal_windows, key=self._candidate_score)

    def current_main_window(self) -> WindowCandidate | None:
        process = self._query_process_info()
        if not process:
            return None
        process_name = str(process["name"])
        pid = int(process["pid"])
        candidates = self._query_window_candidates(process_name, pid)
        return self._pick_main_window(candidates)

    def has_popup_or_menu(self) -> bool:
        process = self._query_process_info()
        if not process:
            return False
        pid = int(process["pid"])
        return self._query_ax_popup_state(pid)

    def activate_current_window(self) -> bool:
        process_name = self._last_process_name or ""
        if not process_name:
            process = self._query_process_info()
            if not process:
                return False
            process_name = str(process["name"])
        try:
            self.run_jxa(self._build_activate_script(process_name))
            return True
        except JxaAutomationError:
            return False

    def restore_current_window(self) -> bool:
        process_name = self._last_process_name or ""
        pid = int(self._last_pid or 0)
        if not process_name or pid <= 0:
            process = self._query_process_info()
            if not process:
                return False
            process_name = str(process["name"])
            pid = int(process["pid"])
        try:
            self.run_jxa(self._build_restore_script(process_name, pid))
            return True
        except JxaAutomationError:
            return False

    def load(self) -> bool:
        log("尝试定位微信进程与主窗口...")
        self.window = None

        process = self._query_process_info()
        if not process:
            self._last_process_name = ""
            self._last_pid = 0
            self._set_status("waiting_wechat", "wechat process not running")
            log("未发现 WeChat 进程，等待微信启动")
            return False

        self._last_process_name = str(process["name"])
        self._last_pid = int(process["pid"])

        try:
            candidates = self._query_window_candidates(self._last_process_name, self._last_pid)
        except AccessibilityPermissionError:
            detail = "accessibility permission required for WeChat window inspection"
            self._set_status("permission_required", detail)
            log("缺少辅助功能权限，无法读取微信窗口")
            return False
        except JxaAutomationError as exc:
            detail = f"failed to query WeChat windows: {exc}"
            self._set_status("window_query_failed", detail)
            log(f"读取微信窗口失败：{exc}")
            return False

        if not candidates:
            detail = "wechat process is running but no readable window is available"
            self._set_status("waiting_wechat", detail)
            log("微信进程存在，但当前没有可读主窗口")
            return False

        try:
            popup_blocked = self._query_ax_popup_state(self._last_pid)
        except AccessibilityPermissionError:
            detail = "accessibility permission required for WeChat window inspection"
            self._set_status("permission_required", detail)
            log("缺少辅助功能权限，无法检查微信弹窗状态")
            return False
        except JxaAutomationError as exc:
            detail = f"failed to inspect WeChat popup state: {exc}"
            self._set_status("window_query_failed", detail)
            log(f"检查微信弹窗状态失败：{exc}")
            return False

        picked = self._pick_main_window(candidates)
        if picked is None or popup_blocked:
            detail = "wechat popup/menu/dialog blocks the main window"
            self._set_status("ui_paused", detail)
            log("检测到微信弹窗或菜单遮挡主窗口，暂不进入监听")
            return False

        self.window = MacWeChatWindow(self, picked)
        self._set_status("ready", f"connected to {self._last_process_name} pid={self._last_pid}")
        log(f"已连接微信主窗口 pid={self._last_pid} title={picked.title!r}")
        return True

    def get_current_sessions(self) -> list[str]:
        """保留只读会话查询入口，具体读取逻辑在 controls.py 中实现。"""
        if not self.window or not self.window.Exists():
            log("微信窗口不存在，无法获取会话列表")
            return []

        from .controls import find_session_list, normalize_session_name

        session_list = find_session_list(self.window)
        if not session_list or not session_list.Exists(0.5):
            log("未找到会话列表控件")
            return []

        names: list[str] = []
        for item in session_list.GetChildren()[:30]:
            raw = getattr(item, "Name", "") or ""
            name = normalize_session_name(raw)
            if name and name not in names:
                names.append(name)
        log(f"获取到 {len(names)} 个会话")
        return names

    def get_window(self) -> MacWeChatWindow | None:
        return self.window
