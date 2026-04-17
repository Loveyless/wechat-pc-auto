from __future__ import annotations

import json
import re
import textwrap
from typing import Any, Optional

_UNREAD_RE = re.compile(r"\[\d+条\]|\d+条新消息|未读")
_TIME_ONLY_RE = re.compile(r"^(?:昨天|今天|星期[一二三四五六日天])?\s*\d{1,2}:\d{2}$")
_CONTROL_CACHE: dict[tuple[int, str], Any] = {}
_WINDOW_CACHE_KEYS: list[int] = []
_CONTROL_CACHE_MAX_WINDOWS = 16
_AX_QUERY_TIMEOUT_SECONDS = 4.0


class MacSessionItem:
    def __init__(self, name: str):
        self.Name = str(name or "")


class MacSessionList:
    def __init__(self, items: list[MacSessionItem], *, found: bool):
        self._items = list(items)
        self._found = bool(found)

    def Exists(self, timeout: float = 0.2) -> bool:
        return self._found

    def GetChildren(self) -> list[MacSessionItem]:
        return list(self._items)


def normalize_session_name(raw_name: str) -> str:
    """提取会话项第一行作为会话名称。"""
    if not raw_name:
        return ""
    lines = [line.strip() for line in raw_name.splitlines() if line.strip()]
    if not lines:
        return ""
    name = lines[0]
    name = re.sub(r"\s*\d+[+]?\s*条新消息$", "", name)
    return name.strip()


def is_unread_session(raw_name: str) -> bool:
    if not raw_name:
        return False
    return bool(_UNREAD_RE.search(raw_name))


def is_meaningful_message_text(text: str) -> bool:
    if not text:
        return False
    s = text.strip()
    if not s:
        return False
    if _TIME_ONLY_RE.match(s):
        return False
    return True


def _iter_controls(root, control_type: str, max_nodes: int = 800):
    stack = [(root, 0)]
    visited = 0
    while stack and visited < max_nodes:
        node, depth = stack.pop()
        visited += 1
        try:
            if getattr(node, "ControlTypeName", "") == control_type:
                yield node
            if depth >= 8:
                continue
            children = node.GetChildren()
            for child in reversed(children):
                stack.append((child, depth + 1))
        except Exception:
            continue


def _exists(ctrl, timeout: float = 0.2) -> bool:
    try:
        return bool(ctrl and ctrl.Exists(timeout))
    except Exception:
        return False


def _window_cache_key(window) -> int:
    for attr in ("NativeWindowHandle", "pid"):
        try:
            value = int(getattr(window, attr))
            if value:
                return value
        except Exception:
            continue
    return id(window)


def _remember_window_key(window_key: int):
    if window_key in _WINDOW_CACHE_KEYS:
        _WINDOW_CACHE_KEYS.remove(window_key)
    _WINDOW_CACHE_KEYS.append(window_key)
    overflow = len(_WINDOW_CACHE_KEYS) - _CONTROL_CACHE_MAX_WINDOWS
    while overflow > 0:
        expired_key = _WINDOW_CACHE_KEYS.pop(0)
        stale_keys = [key for key in _CONTROL_CACHE if key[0] == expired_key]
        for stale_key in stale_keys:
            _CONTROL_CACHE.pop(stale_key, None)
        overflow -= 1


def _get_cached_control(window, control_name: str) -> Any:
    window_key = _window_cache_key(window)
    cached = _CONTROL_CACHE.get((window_key, control_name))
    if _exists(cached):
        _remember_window_key(window_key)
        return cached
    _CONTROL_CACHE.pop((window_key, control_name), None)
    return None


def _cache_control(window, control_name: str, ctrl) -> Any:
    if not _exists(ctrl):
        return None
    window_key = _window_cache_key(window)
    _CONTROL_CACHE[(window_key, control_name)] = ctrl
    _remember_window_key(window_key)
    return ctrl


def clear_control_cache(window=None):
    if window is None:
        _CONTROL_CACHE.clear()
        _WINDOW_CACHE_KEYS.clear()
        return

    window_key = _window_cache_key(window)
    stale_keys = [key for key in _CONTROL_CACHE if key[0] == window_key]
    for stale_key in stale_keys:
        _CONTROL_CACHE.pop(stale_key, None)
    try:
        _WINDOW_CACHE_KEYS.remove(window_key)
    except ValueError:
        pass


def _has_mac_ax_runner(window) -> bool:
    return callable(getattr(window, "run_jxa", None)) and hasattr(window, "pid")


def _build_raw_session_name(chat_name: str, raw_value: str) -> str:
    normalized_chat_name = str(chat_name or "").strip()
    normalized_raw_value = str(raw_value or "").strip()
    if not normalized_chat_name:
        return normalized_raw_value
    if not normalized_raw_value:
        return normalized_chat_name
    first_line = normalize_session_name(normalized_raw_value)
    if first_line == normalized_chat_name:
        return normalized_raw_value
    return f"{normalized_chat_name}\n{normalized_raw_value}"


def _build_session_list_query_script(pid: int) -> str:
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

        function attr(element, name) {{
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

        function isPopupWindow(window) {{
          const role = stringAttr(window, "AXRole").toLowerCase();
          const subrole = stringAttr(window, "AXSubrole").toLowerCase();
          return (
            role.includes("menu") ||
            role.includes("popover") ||
            role.includes("sheet") ||
            role.includes("dialog") ||
            subrole.includes("dialog") ||
            subrole.includes("floating")
          );
        }}

        function findElementByIdentifier(root, identifier, depth) {{
          if (!root || depth > 10) {{
            return null;
          }}
          if (stringAttr(root, "AXIdentifier") === identifier) {{
            return root;
          }}
          const children = arrayAttr(root, "AXChildren");
          for (const child of children) {{
            const found = findElementByIdentifier(child, identifier, depth + 1);
            if (found) {{
              return found;
            }}
          }}
          return null;
        }}

        function collectSessionItems(listElement) {{
          const items = [];
          const children = arrayAttr(listElement, "AXChildren");
          for (const child of children) {{
            const identifier = stringAttr(child, "AXIdentifier");
            if (!identifier || !identifier.startsWith("session_item_")) {{
              continue;
            }}
            const chatName = identifier.replace(/^session_item_/, "").trim();
            const rawValue = stringAttr(child, "AXTitle") || stringAttr(child, "AXValue") || chatName;
            items.push({{
              identifier: identifier,
              chat_name: chatName,
              raw_value: rawValue,
            }});
          }}
          return items;
        }}

        function collectCandidateWindows(app) {{
          const windows = [];
          const seen = Object.create(null);
          function pushWindow(window) {{
            if (!window) {{
              return;
            }}
            const signature = [
              stringAttr(window, "AXTitle"),
              stringAttr(window, "AXRole"),
              stringAttr(window, "AXSubrole"),
            ].join("|");
            if (seen[signature]) {{
              return;
            }}
            seen[signature] = true;
            windows.push(window);
          }}
          for (const window of arrayAttr(app, "AXWindows")) {{
            pushWindow(window);
          }}
          pushWindow(rawAttr(app, "AXMainWindow"));
          pushWindow(rawAttr(app, "AXFocusedWindow"));
          return windows;
        }}

        const app = $.AXUIElementCreateApplication({int(pid)});
        const windows = collectCandidateWindows(app);
        let sessionItems = [];
        let foundSessionList = false;

        for (const window of windows) {{
          if (isPopupWindow(window)) {{
            continue;
          }}
          const sessionList = findElementByIdentifier(window, "session_list", 0);
          if (!sessionList) {{
            continue;
          }}
          sessionItems = collectSessionItems(sessionList);
          foundSessionList = true;
          break;
        }}

        JSON.stringify({{
          found: foundSessionList,
          items: sessionItems,
        }});
        """
    ).strip()


def _query_mac_session_items(window) -> MacSessionList | None:
    try:
        payload = window.run_jxa(
            _build_session_list_query_script(int(window.pid)),
            timeout=_AX_QUERY_TIMEOUT_SECONDS,
        )
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    raw_items = payload.get("items")
    found = bool(payload.get("found"))
    if not isinstance(raw_items, list):
        return MacSessionList([], found=found)

    items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        raw_name = _build_raw_session_name(item.get("chat_name", ""), item.get("raw_value", ""))
        items.append(MacSessionItem(raw_name))
    return MacSessionList(items, found=found)


def _find_session_list_with_legacy_controls(window):
    candidates = [
        window.ListControl(AutomationId="session_list"),
        window.ListControl(Name="会话"),
        window.ListControl(AutomationId="search_list"),
    ]
    for ctrl in candidates:
        cached_ctrl = _cache_control(window, "session_list", ctrl)
        if cached_ctrl:
            return cached_ctrl

    best = None
    best_score = -1
    for ctrl in _iter_controls(window, "ListControl"):
        try:
            score = 0
            aid = (getattr(ctrl, "AutomationId", "") or "").lower()
            cls = getattr(ctrl, "ClassName", "") or ""
            name = getattr(ctrl, "Name", "") or ""
            children = ctrl.GetChildren()

            if "session" in aid:
                score += 120
            if "search_list" in aid:
                score += 90
            if name == "会话":
                score += 60
            if "XTableView" in cls:
                score += 20
            score += min(len(children), 50)
            if children and "ChatSession" in (getattr(children[0], "ClassName", "") or ""):
                score += 100

            if score > best_score:
                best_score = score
                best = ctrl
        except Exception:
            continue
    return _cache_control(window, "session_list", best)


def find_session_list(window) -> Optional[Any]:
    if _has_mac_ax_runner(window):
        # mac AX 结果是点时快照，不是可持续刷新的 live control，不能跨轮询复用。
        return _query_mac_session_items(window)

    cached = _get_cached_control(window, "session_list")
    if cached:
        return cached

    return _find_session_list_with_legacy_controls(window)


def find_message_list(window) -> Optional[Any]:
    cached = _get_cached_control(window, "message_list")
    if cached:
        return cached

    if _has_mac_ax_runner(window):
        return None

    candidates = [
        window.ListControl(AutomationId="chat_message_list"),
        window.ListControl(Name="消息"),
    ]
    for ctrl in candidates:
        cached_ctrl = _cache_control(window, "message_list", ctrl)
        if cached_ctrl:
            return cached_ctrl

    best = None
    best_score = -1
    for ctrl in _iter_controls(window, "ListControl"):
        try:
            score = 0
            aid = (getattr(ctrl, "AutomationId", "") or "").lower()
            cls = getattr(ctrl, "ClassName", "") or ""
            name = getattr(ctrl, "Name", "") or ""
            children = ctrl.GetChildren()

            if "message" in aid:
                score += 120
            if name == "消息":
                score += 80
            if "RecyclerListView" in cls:
                score += 40
            if children and "Chat" in (getattr(children[0], "ClassName", "") or ""):
                score += 80
            score += min(len(children), 50)

            if score > best_score:
                best_score = score
                best = ctrl
        except Exception:
            continue
    return _cache_control(window, "message_list", best)


def find_search_box(window) -> Optional[Any]:
    cached = _get_cached_control(window, "search_box")
    if cached:
        return cached

    if _has_mac_ax_runner(window):
        return None

    direct = [
        window.EditControl(Name="搜索"),
        window.EditControl(ClassName="mmui::XValidatorTextEdit"),
    ]
    for ctrl in direct:
        cached_ctrl = _cache_control(window, "search_box", ctrl)
        if cached_ctrl:
            return cached_ctrl

    best = None
    best_score = -1
    for ctrl in _iter_controls(window, "EditControl"):
        try:
            score = 0
            name = getattr(ctrl, "Name", "") or ""
            cls = getattr(ctrl, "ClassName", "") or ""
            aid = (getattr(ctrl, "AutomationId", "") or "").lower()

            if "搜索" in name:
                score += 120
            if "validator" in cls.lower():
                score += 70
            if "chat_input" in aid or "chatinput" in cls.lower():
                score -= 100

            if score > best_score:
                best_score = score
                best = ctrl
        except Exception:
            continue
    return _cache_control(window, "search_box", best)
