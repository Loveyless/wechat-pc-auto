import ctypes
import os
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from typing import Any, Callable

if __package__:
    from .sidebar_shared import (
        is_speakable_english_text,
        summarize_tts_text,
    )
else:
    from sidebar_shared import (
        is_speakable_english_text,
        summarize_tts_text,
    )

PREFERRED_UI_FONTS = ("Cascadia Code", "JetBrains Mono", "黑体")
DEFAULT_SIDEBAR_HEIGHT = 550
DEFAULT_META_FONT_SIZE = 10
MESSAGE_FONT_EXTRA_PX = 2
DEFAULT_TARGET_PANEL_WIDTH = 150
TARGET_LABEL_MAX_CHARS = 6
META_TEXT_COLOR = "#555555"
TTS_BODY_CLICK_MOVE_TOLERANCE_PX = 4
CHAT_SWITCH_SHORTCUT_DEBOUNCE_SECONDS = 0.15


def get_system_double_click_time_ms(default: int = 500) -> int:
    if os.name != "nt":
        return default
    try:
        value = int(ctypes.windll.user32.GetDoubleClickTime())
    except Exception:
        return default
    return max(200, min(1000, value))


TTS_BODY_CLICK_PLAY_DELAY_MS = get_system_double_click_time_ms()


def truncate_target_label(name: str, max_chars: int = TARGET_LABEL_MAX_CHARS) -> str:
    text = str(name or "").strip()
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def build_sidebar_window_title(chat_name: str) -> str:
    name = str(chat_name or "").strip()
    if name:
        return name
    return "未选择会话"


def pick_ui_font_family(root: tk.Tk) -> str:
    try:
        available = {name.lower(): name for name in tkfont.families(root)}
    except Exception:
        available = {}

    for font_name in PREFERRED_UI_FONTS:
        chosen = available.get(font_name.lower())
        if chosen:
            return chosen

    return str(tkfont.nametofont("TkDefaultFont").cget("family"))

@dataclass
class SidebarMessage:
    chat_name: str
    sender_name: str
    text_en: str
    created_at: str
    is_self: bool
    text_display: str = ""
    text_cn: str = ""
    message_id: str = ""
    pending_translation: bool = False


def append_message_with_limit(cache: list[SidebarMessage], msg: SidebarMessage, limit: int):
    cache.append(msg)
    if limit <= 0:
        cache.clear()
        return
    overflow = len(cache) - limit
    if overflow > 0:
        del cache[:overflow]


def replace_message_in_cache(cache: list[SidebarMessage], msg: SidebarMessage) -> bool:
    message_id = str(msg.message_id or "").strip()
    if not message_id:
        return False
    for idx, existing in enumerate(cache):
        if str(existing.message_id or "").strip() == message_id:
            cache[idx] = msg
            return True
    return False


class SidebarUI:
    def __init__(
        self,
        width: int,
        side: str,
        targets: list[str],
        message_limit: int,
        tts_player: Any | None = None,
        tts_auto_read_active_chat: bool = True,
    ):
        self.root = tk.Tk()
        self.root.title(build_sidebar_window_title(""))
        self.ui_font_family = pick_ui_font_family(self.root)
        self.root.option_add("*Font", (self.ui_font_family, DEFAULT_META_FONT_SIZE))
        self.topmost_var = tk.BooleanVar(value=False)
        self.show_original_var = tk.BooleanVar(value=False)
        self.tts_auto_read_var = tk.BooleanVar(value=bool(tts_auto_read_active_chat))
        self.root.attributes("-topmost", self.topmost_var.get())
        self.status_var = tk.StringVar(value="starting...")
        self.target_panel_visible = False
        self.target_panel_toggle_text = tk.StringVar(value="菜单")
        self.message_limit = max(1, int(message_limit))
        self.tts_player = tts_player
        self.tts_auto_read_active_chat = bool(self.tts_auto_read_var.get())
        self.runtime_logger: Callable[[str], None] | None = None
        self.allowed_chat_names = {str(item or "").strip() for item in targets if str(item or "").strip()}
        self.chat_order: list[str] = []
        self.chat_messages: dict[str, list[SidebarMessage]] = {}
        self.unread_counts: dict[str, int] = {}
        self.active_chat = ""
        self._on_add_target_request: Callable[[str], None] | None = None
        self._on_remove_target_request: Callable[[str], None] | None = None
        self._context_menu_target = ""
        self._tts_action_tags: dict[str, str] = {}
        self._tts_action_index = 0
        self._tts_body_click_press: dict[str, Any] | None = None
        self._tts_body_click_pending_after_id = ""
        self._tts_body_click_pending_tag = ""
        self._last_chat_switch_shortcut_at = 0.0

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        height = min(DEFAULT_SIDEBAR_HEIGHT, max(320, screen_h - 80))
        if side == "right":
            x = screen_w - width - 16
        else:
            x = 16
        max_x = max(0, screen_w - width - 8)
        x = min(max(0, x), max_x)
        y = 24
        max_y = max(24, screen_h - height - 24)
        if y > max_y:
            y = max_y
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        controls = ttk.Frame(self.root, padding=(8, 6, 8, 4))
        controls.pack(fill=tk.X)
        ttk.Button(
            controls,
            textvariable=self.target_panel_toggle_text,
            command=self.toggle_target_panel,
            width=6,
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.add_target_button = ttk.Button(
            controls,
            text="添加群",
            command=self._on_add_target_clicked,
            width=8,
            state=tk.DISABLED,
        )
        self.add_target_button.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Checkbutton(
            controls,
            text="原文",
            variable=self.show_original_var,
            command=self.on_show_original_toggled,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Checkbutton(
            controls,
            text="朗读",
            variable=self.tts_auto_read_var,
            command=self.toggle_auto_read,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Checkbutton(
            controls,
            text="置顶",
            variable=self.topmost_var,
            command=self.toggle_topmost,
        ).pack(side=tk.LEFT)
        ttk.Label(controls, textvariable=self.status_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        content = ttk.Frame(self.root)
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.left_panel = ttk.Frame(content, width=DEFAULT_TARGET_PANEL_WIDTH)
        self.left_panel.pack_propagate(False)
        self.target_list = tk.Listbox(
            self.left_panel,
            exportselection=False,
            activestyle="none",
            font=(self.ui_font_family, DEFAULT_META_FONT_SIZE),
        )
        self.target_list.pack(fill=tk.BOTH, expand=True)
        self.target_list.bind("<<ListboxSelect>>", self._on_target_selected)
        self.target_list.bind("<Button-3>", self._on_target_context_menu)
        self.target_context_menu = tk.Menu(self.root, tearoff=0)
        self.target_context_menu.add_command(
            label="删除监听目标",
            command=self._on_remove_target_menu,
        )

        self.text = scrolledtext.ScrolledText(
            content,
            wrap=tk.WORD,
            font=(self.ui_font_family, DEFAULT_META_FONT_SIZE),
            state=tk.DISABLED,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        message_font_size = DEFAULT_META_FONT_SIZE + MESSAGE_FONT_EXTRA_PX
        self.text.tag_configure(
            "msg_left",
            justify=tk.LEFT,
            lmargin1=8,
            lmargin2=8,
            rmargin=40,
            font=(self.ui_font_family, message_font_size),
        )
        self.text.tag_configure(
            "msg_right",
            justify=tk.RIGHT,
            lmargin1=40,
            lmargin2=40,
            rmargin=8,
            font=(self.ui_font_family, message_font_size),
        )
        self.text.tag_configure(
            "msg_left_pending",
            justify=tk.LEFT,
            lmargin1=8,
            lmargin2=8,
            rmargin=40,
            font=(self.ui_font_family, message_font_size),
            foreground=META_TEXT_COLOR,
        )
        self.text.tag_configure(
            "msg_right_pending",
            justify=tk.RIGHT,
            lmargin1=40,
            lmargin2=40,
            rmargin=8,
            font=(self.ui_font_family, message_font_size),
            foreground=META_TEXT_COLOR,
        )
        self.text.tag_configure("meta_left", justify=tk.LEFT, foreground=META_TEXT_COLOR)
        self.text.tag_configure("meta_right", justify=tk.RIGHT, foreground=META_TEXT_COLOR)

        for target in targets:
            self._ensure_chat(target)
        if self.chat_order:
            self.switch_chat(self.chat_order[0])
        self.root.bind("<F1>", self.on_show_shortcuts_help)
        self.root.bind("<Left>", self.on_toggle_target_panel_shortcut)
        self.root.bind("<Right>", self.on_toggle_show_original_shortcut)
        self.root.bind("<Up>", self.on_switch_prev_chat_arrow)
        self.root.bind("<Down>", self.on_switch_next_chat_arrow)
        self.root.bind("<Control-Left>", self.on_toggle_target_panel_shortcut)
        self._set_target_panel_visible(True)
        self.root.bind("<Control-b>", self.on_toggle_target_panel_shortcut)
        self.root.bind("<Control-B>", self.on_toggle_target_panel_shortcut)
        self.root.bind("<Control-Right>", self.on_toggle_show_original_shortcut)
        self.root.bind("<Control-Up>", self.on_switch_prev_chat_shortcut)
        self.root.bind("<Control-Down>", self.on_switch_next_chat_shortcut)

    def set_status(self, text: str):
        self.status_var.set(text)

    def set_target_editor_handlers(
        self,
        on_add_target: Callable[[str], None] | None,
        on_remove_target: Callable[[str], None] | None,
    ):
        self._on_add_target_request = on_add_target
        self._on_remove_target_request = on_remove_target
        self.add_target_button.configure(state=tk.NORMAL if on_add_target else tk.DISABLED)

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())

    def toggle_auto_read(self):
        self.tts_auto_read_active_chat = self._is_auto_read_enabled()

    def on_show_original_toggled(self):
        self._render_active_chat()

    def toggle_show_original(self):
        self.show_original_var.set(not self.show_original_var.get())
        self.on_show_original_toggled()

    def toggle_target_panel(self):
        self._set_target_panel_visible(not self.target_panel_visible)

    def on_show_shortcuts_help(self, _event=None):
        help_lines = [
            "F1: 打开快捷键速查",
            "Up / Down: 切换会话（焦点在左侧会话列表时保留列表原生上下选择）",
            "Left: 展开 / 收起左侧菜单",
            "Right: 切换原文显示",
            "Ctrl+Up / Ctrl+Down: 兼容旧版切换会话",
            "Ctrl+Left / Ctrl+B: 兼容旧版展开 / 收起左侧菜单",
            "Ctrl+Right: 兼容旧版切换原文显示",
        ]
        messagebox.showinfo("快捷键速查", "\n".join(help_lines), parent=self.root)
        return "break"

    def on_toggle_target_panel_shortcut(self, _event=None):
        self.toggle_target_panel()
        return "break"

    def on_toggle_show_original_shortcut(self, _event=None):
        self.toggle_show_original()
        return "break"

    def on_switch_prev_chat_arrow(self, _event=None):
        if self._should_skip_window_arrow_chat_switch():
            return None
        self._handle_chat_switch_shortcut(-1)
        return "break"

    def on_switch_next_chat_arrow(self, _event=None):
        if self._should_skip_window_arrow_chat_switch():
            return None
        self._handle_chat_switch_shortcut(1)
        return "break"

    def on_switch_prev_chat_shortcut(self, _event=None):
        self._handle_chat_switch_shortcut(-1)
        return "break"

    def on_switch_next_chat_shortcut(self, _event=None):
        self._handle_chat_switch_shortcut(1)
        return "break"

    def _handle_chat_switch_shortcut(self, delta: int):
        if not self.chat_order:
            return
        now_ts = time.time()
        if (
            self._last_chat_switch_shortcut_at
            and now_ts - self._last_chat_switch_shortcut_at < CHAT_SWITCH_SHORTCUT_DEBOUNCE_SECONDS
        ):
            return
        self._last_chat_switch_shortcut_at = now_ts
        if self.active_chat not in self.chat_order:
            self.switch_chat(self.chat_order[0])
            return
        current_index = self.chat_order.index(self.active_chat)
        next_index = (current_index + int(delta)) % len(self.chat_order)
        self.switch_chat(self.chat_order[next_index])

    def _should_skip_window_arrow_chat_switch(self) -> bool:
        focused_widget = self.root.focus_get()
        return bool(
            self.target_panel_visible
            and focused_widget is self.target_list
        )

    def _set_target_panel_visible(self, visible: bool):
        if visible:
            self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), before=self.text)
            self.target_panel_toggle_text.set("收起")
            self.target_panel_visible = True
            return
        self.left_panel.pack_forget()
        self.target_panel_toggle_text.set("菜单")
        self.target_panel_visible = False

    def _update_window_title(self):
        self.root.title(build_sidebar_window_title(self.active_chat))

    def _ensure_chat(self, chat_name: str):
        name = str(chat_name or "").strip()
        if not name:
            return False
        allowed_chat_names = getattr(self, "allowed_chat_names", set())
        if allowed_chat_names and name not in allowed_chat_names:
            return False
        if name not in self.chat_messages:
            self.chat_messages[name] = []
            self.unread_counts[name] = 0
            self.chat_order.append(name)
            self._refresh_target_list()
        return True

    def add_target(self, chat_name: str) -> bool:
        name = str(chat_name or "").strip()
        if not name:
            return False
        self.allowed_chat_names.add(name)
        created = self._ensure_chat(name)
        if not self.active_chat:
            self.switch_chat(name)
        else:
            self._refresh_target_list()
        return created

    def remove_target(self, chat_name: str) -> str:
        name = str(chat_name or "").strip()
        if not name:
            return self.active_chat
        self.allowed_chat_names.discard(name)
        self.chat_messages.pop(name, None)
        self.unread_counts.pop(name, None)
        if name in self.chat_order:
            self.chat_order.remove(name)
        if self.active_chat == name:
            self.active_chat = self.chat_order[0] if self.chat_order else ""
        self._update_window_title()
        self._refresh_target_list()
        self._render_active_chat()
        return self.active_chat

    def _format_chat_label(self, chat_name: str) -> str:
        display_name = truncate_target_label(chat_name)
        unread = self.unread_counts.get(chat_name, 0)
        if unread > 0:
            return f"{display_name} ({unread})"
        return display_name

    def _refresh_target_list(self):
        self.target_list.delete(0, tk.END)
        for chat_name in self.chat_order:
            self.target_list.insert(tk.END, self._format_chat_label(chat_name))
        if self.active_chat in self.chat_order:
            idx = self.chat_order.index(self.active_chat)
            self.target_list.selection_clear(0, tk.END)
            self.target_list.selection_set(idx)
            self.target_list.activate(idx)

    def _on_target_selected(self, _event=None):
        selection = self.target_list.curselection()
        if not selection:
            return
        idx = int(selection[0])
        if idx < 0 or idx >= len(self.chat_order):
            return
        self.switch_chat(self.chat_order[idx])

    def _on_target_context_menu(self, event):
        if not self.chat_order or not self._on_remove_target_request:
            return "break"
        idx = self.target_list.nearest(event.y)
        if idx < 0 or idx >= len(self.chat_order):
            return "break"
        bbox = self.target_list.bbox(idx)
        if not bbox:
            return "break"
        _, item_y, _, item_height = bbox
        if event.y < item_y or event.y > item_y + item_height:
            return "break"
        self.target_list.selection_clear(0, tk.END)
        self.target_list.selection_set(idx)
        self.target_list.activate(idx)
        self._context_menu_target = self.chat_order[idx]
        try:
            self.target_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.target_context_menu.grab_release()
        return "break"

    def _on_add_target_clicked(self):
        handler = self._on_add_target_request
        if not handler:
            return
        raw_name = simpledialog.askstring(
            "添加监听目标",
            "输入微信左侧会话名（必须完全一致）",
            parent=self.root,
        )
        if raw_name is None:
            return
        target_name = str(raw_name or "").strip()
        if not target_name:
            messagebox.showerror("添加失败", "会话名不能为空", parent=self.root)
            return
        try:
            handler(target_name)
        except Exception as e:
            messagebox.showerror("添加失败", str(e), parent=self.root)

    def _on_remove_target_menu(self):
        target_name = str(self._context_menu_target or "").strip()
        handler = self._on_remove_target_request
        if not target_name or not handler:
            return
        confirmed = messagebox.askyesno(
            "删除监听目标",
            f"删除后会写回配置并重启 worker。\n\n确认删除：{target_name}",
            parent=self.root,
        )
        if not confirmed:
            return
        try:
            handler(target_name)
        except Exception as e:
            messagebox.showerror("删除失败", str(e), parent=self.root)

    def switch_chat(self, chat_name: str):
        name = str(chat_name or "").strip()
        if not name:
            return
        if not self._ensure_chat(name):
            return
        self.active_chat = name
        self.unread_counts[name] = 0
        self._update_window_title()
        self._refresh_target_list()
        self._render_active_chat()

    def _insert_message_content(self, msg: SidebarMessage):
        meta_tag = "meta_right" if msg.is_self else "meta_left"
        display_text = msg.text_cn if self.show_original_var.get() and msg.text_cn else (msg.text_display or msg.text_en)
        if msg.pending_translation and not self.show_original_var.get():
            msg_tag = "msg_right_pending" if msg.is_self else "msg_left_pending"
        else:
            msg_tag = "msg_right" if msg.is_self else "msg_left"
        clickable = self._should_render_tts_action(msg, msg.text_en)
        header = f"[{msg.created_at}]"
        if msg.sender_name:
            header += f" {msg.sender_name}"
        self.text.insert(tk.END, header + "\n", meta_tag)
        if clickable:
            body_action_tag = self._register_tts_body_action_tag(msg)
            self.text.insert(tk.END, display_text, (msg_tag, body_action_tag))
        else:
            self.text.insert(tk.END, display_text, msg_tag)
        self.text.insert(tk.END, "\n", msg_tag)

    def _render_active_chat(self):
        self._cancel_pending_tts_body_click()
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self._tts_action_tags = {}
        self._tts_action_index = 0
        self._tts_body_click_press = None
        for msg in self.chat_messages.get(self.active_chat, []):
            self._insert_message_content(msg)
        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)

    def append_message(self, msg: SidebarMessage):
        if not self._ensure_chat(msg.chat_name):
            return
        cache = self.chat_messages[msg.chat_name]
        append_message_with_limit(cache, msg, self.message_limit)
        if msg.chat_name != self.active_chat:
            self.unread_counts[msg.chat_name] = self.unread_counts.get(msg.chat_name, 0) + 1
            self._refresh_target_list()
            return
        self._render_active_chat()

    def replace_message(self, msg: SidebarMessage) -> bool:
        if not self._ensure_chat(msg.chat_name):
            return False
        cache = self.chat_messages[msg.chat_name]
        replaced = replace_message_in_cache(cache, msg)
        if not replaced:
            return False
        if msg.chat_name == self.active_chat:
            self._render_active_chat()
        return True

    def append_log(self, line: str):
        self.status_var.set(str(line or ""))

    def set_runtime_logger(self, logger: Callable[[str], None] | None):
        self.runtime_logger = logger

    def _emit_runtime_log(self, line: str):
        logger = getattr(self, "runtime_logger", None)
        if not logger:
            return
        try:
            logger(str(line or ""))
        except Exception:
            pass

    def _get_tts_action_block_reason(self, msg: SidebarMessage, display_text: str) -> str:
        if self.show_original_var.get():
            return "original_mode"
        if msg.pending_translation:
            return "pending_translation"
        if not getattr(self, "tts_player", None):
            return "no_player"
        if not is_speakable_english_text(display_text):
            return "non_english_or_invalid"
        return ""

    def _should_render_tts_action(self, msg: SidebarMessage, display_text: str) -> bool:
        return not self._get_tts_action_block_reason(msg, display_text)

    def _play_bound_tts_text(
        self,
        tag_name: str,
        *,
        trigger_name: str,
    ):
        text = self._tts_action_tags.get(str(tag_name or ""))
        if not text:
            self._emit_runtime_log(f"tts {trigger_name} ignored reason=missing_bound_text")
            return "break"
        tts_player = getattr(self, "tts_player", None)
        if not tts_player:
            self._emit_runtime_log(f"tts {trigger_name} ignored reason=no_player")
            return "break"
        result = tts_player.speak_async(text)
        preview = summarize_tts_text(text)
        action = "queued" if result else "rejected"
        self._emit_runtime_log(f"tts {trigger_name} {action} preview={preview}")
        return "break"

    def _register_tts_body_action_tag(self, msg: SidebarMessage) -> str:
        self._tts_action_index += 1
        tag_name = f"tts_body_action_{self._tts_action_index}"
        self._tts_action_tags[tag_name] = str(msg.text_en or "")
        self.text.tag_bind(tag_name, "<ButtonPress-1>", lambda event, tag=tag_name: self._on_tts_body_press(tag, event))
        self.text.tag_bind(tag_name, "<ButtonRelease-1>", lambda event, tag=tag_name: self._on_tts_body_release(tag, event))
        self.text.tag_bind(tag_name, "<Double-Button-1>", self._on_tts_body_multi_click)
        self.text.tag_bind(tag_name, "<Triple-Button-1>", self._on_tts_body_multi_click)
        return tag_name

    def _is_tts_body_tag_hit(self, tag_name: str, event=None) -> bool:
        if event is None:
            return True
        text_widget = getattr(self, "text", None)
        if text_widget is None:
            return False
        try:
            index = text_widget.index(f"@{event.x},{event.y}")
            return tag_name in text_widget.tag_names(index)
        except Exception:
            return False

    def _has_text_selection(self) -> bool:
        text_widget = getattr(self, "text", None)
        if text_widget is None:
            return False
        try:
            return bool(text_widget.tag_ranges(tk.SEL))
        except Exception:
            return False

    def _cancel_pending_tts_body_click(self):
        after_id = str(getattr(self, "_tts_body_click_pending_after_id", "") or "")
        root = getattr(self, "root", None)
        if after_id and root is not None:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
        self._tts_body_click_pending_after_id = ""
        self._tts_body_click_pending_tag = ""

    def _schedule_tts_body_click_play(self, tag_name: str):
        self._cancel_pending_tts_body_click()
        root = getattr(self, "root", None)
        if root is None:
            self._execute_pending_tts_body_click(tag_name)
            return

        self._tts_body_click_pending_tag = str(tag_name or "")

        def _callback(tag=tag_name):
            self._execute_pending_tts_body_click(tag)

        self._tts_body_click_pending_after_id = str(
            root.after(TTS_BODY_CLICK_PLAY_DELAY_MS, _callback)
        )

    def _execute_pending_tts_body_click(self, tag_name: str):
        pending_tag = str(getattr(self, "_tts_body_click_pending_tag", "") or "")
        self._tts_body_click_pending_after_id = ""
        self._tts_body_click_pending_tag = ""
        if pending_tag and pending_tag != str(tag_name or ""):
            return "break"
        if self._has_text_selection():
            self._emit_runtime_log("tts body click ignored reason=selection")
            return "break"
        return self._play_bound_tts_text(
            tag_name,
            trigger_name="body click",
        )

    def _on_tts_body_press(self, tag_name: str, event=None):
        self._cancel_pending_tts_body_click()
        if not self._is_tts_body_tag_hit(tag_name, event):
            self._tts_body_click_press = None
            return
        self._tts_body_click_press = {
            "tag": str(tag_name or ""),
            "x": int(getattr(event, "x", 0)),
            "y": int(getattr(event, "y", 0)),
        }

    def _on_tts_body_release(self, tag_name: str, event=None):
        press = getattr(self, "_tts_body_click_press", None)
        self._tts_body_click_press = None
        if not isinstance(press, dict):
            return
        expected_tag = str(press.get("tag", "") or "")
        if expected_tag != str(tag_name or ""):
            return
        if not self._is_tts_body_tag_hit(tag_name, event):
            return
        dx = int(getattr(event, "x", 0)) - int(press.get("x", 0))
        dy = int(getattr(event, "y", 0)) - int(press.get("y", 0))
        if dx * dx + dy * dy > TTS_BODY_CLICK_MOVE_TOLERANCE_PX * TTS_BODY_CLICK_MOVE_TOLERANCE_PX:
            return
        self._schedule_tts_body_click_play(tag_name)

    def _on_tts_body_multi_click(self, _event=None):
        self._tts_body_click_press = None
        self._cancel_pending_tts_body_click()
        return

    def maybe_auto_read_message(self, msg: SidebarMessage) -> bool:
        if not self._is_auto_read_enabled():
            return False
        if str(msg.chat_name or "") != str(getattr(self, "active_chat", "")):
            return False
        reason = self._get_tts_action_block_reason(msg, msg.text_en)
        if reason:
            self._emit_runtime_log(
                f"tts auto skipped chat={msg.chat_name} reason={reason} preview={summarize_tts_text(msg.text_en)}"
            )
            return False
        tts_player = getattr(self, "tts_player", None)
        if not tts_player:
            return False
        result = bool(tts_player.speak_async(msg.text_en))
        action = "queued" if result else "rejected"
        self._emit_runtime_log(
            f"tts auto {action} chat={msg.chat_name} preview={summarize_tts_text(msg.text_en)}"
        )
        return result

    def _is_auto_read_enabled(self) -> bool:
        auto_read_var = getattr(self, "tts_auto_read_var", None)
        if auto_read_var is not None:
            try:
                return bool(auto_read_var.get())
            except Exception:
                pass
        return bool(getattr(self, "tts_auto_read_active_chat", True))
