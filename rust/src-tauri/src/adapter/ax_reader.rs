use anyhow::{Context, Result};
use core_foundation::array::CFArray;
use core_foundation::base::{CFType, TCFType};
use core_foundation::string::CFString;
use regex::Regex;
use std::collections::HashSet;
use std::sync::LazyLock;

pub const WECHAT_BUNDLE_ID: &str = "com.tencent.xinWeChat";
const WECHAT_PROCESS_NAMES: &[&str] = &["WeChat", "微信", "Weixin"];

extern "C" {
    fn proc_listallpids(buffer: *mut std::ffi::c_void, buffersize: i32) -> i32;
    fn proc_name(pid: i32, buffer: *mut std::ffi::c_void, buffersize: u32) -> i32;
    fn CGWindowListCopyWindowInfo(
        option: u32,
        relative_to_window: u32,
    ) -> core_foundation_sys::array::CFArrayRef;
}

const CG_WINDOW_LIST_ON_SCREEN_ONLY: u32 = 1 << 0;
const CG_WINDOW_LIST_EXCLUDE_DESKTOP: u32 = 1 << 4;
const CG_NULL_WINDOW_ID: u32 = 0;
const MIN_MAIN_WINDOW_SIZE: f64 = 200.0;

static TIME_HINT_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^(?:昨天|今天|星期[一二三四五六日天])?\s*\d{1,2}:\d{2}$").unwrap()
});
static SESSION_UNREAD_PREFIX_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\[\d+条\]\s*").unwrap());
static SESSION_UNREAD_COUNT_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\[(\d+)条\]\s*").unwrap());
static SESSION_NEWMSG_SUFFIX_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\s*\d+[+]?\s*条新消息$").unwrap());
static SENDER_PREFIX_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*([^:：]{1,40})[:：]\s*(.+?)\s*$").unwrap());

static NOISE_TEXTS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    ["微信", "搜索", "通讯录", "我", "聊天", "联系人", "设置"]
        .into_iter()
        .collect()
});

unsafe fn cg_dict_get_f64(
    dict: core_foundation_sys::dictionary::CFDictionaryRef,
    key: &str,
) -> Option<f64> {
    let cf_key = CFString::new(key);
    let ptr = core_foundation_sys::dictionary::CFDictionaryGetValue(
        dict,
        cf_key.as_concrete_TypeRef() as *const std::ffi::c_void,
    );
    if ptr.is_null() {
        return None;
    }
    let mut value: f64 = 0.0;
    let ok = core_foundation_sys::number::CFNumberGetValue(
        ptr as core_foundation_sys::number::CFNumberRef,
        core_foundation_sys::number::kCFNumberFloat64Type,
        &mut value as *mut f64 as *mut std::ffi::c_void,
    );
    if ok {
        Some(value)
    } else {
        None
    }
}

unsafe fn cg_dict_get_i32(
    dict: core_foundation_sys::dictionary::CFDictionaryRef,
    key: &str,
) -> Option<i32> {
    let cf_key = CFString::new(key);
    let ptr = core_foundation_sys::dictionary::CFDictionaryGetValue(
        dict,
        cf_key.as_concrete_TypeRef() as *const std::ffi::c_void,
    );
    if ptr.is_null() {
        return None;
    }
    let mut value: i32 = 0;
    let ok = core_foundation_sys::number::CFNumberGetValue(
        ptr as core_foundation_sys::number::CFNumberRef,
        core_foundation_sys::number::kCFNumberSInt32Type,
        &mut value as *mut i32 as *mut std::ffi::c_void,
    );
    if ok {
        Some(value)
    } else {
        None
    }
}

fn get_wechat_pid_from_process_list() -> Option<i32> {
    unsafe {
        let pid_count = proc_listallpids(std::ptr::null_mut(), 0);
        if pid_count <= 0 {
            return None;
        }

        let mut pids = vec![0i32; pid_count as usize + 32];
        let copied = proc_listallpids(
            pids.as_mut_ptr() as *mut std::ffi::c_void,
            (pids.len() * std::mem::size_of::<i32>()) as i32,
        );
        if copied <= 0 {
            return None;
        }

        let mut buf = vec![0u8; 1024];
        for pid in pids.into_iter().take(copied as usize) {
            if pid <= 0 {
                continue;
            }
            let len = proc_name(
                pid,
                buf.as_mut_ptr() as *mut std::ffi::c_void,
                buf.len() as u32,
            );
            if len <= 0 {
                continue;
            }
            let name = String::from_utf8_lossy(&buf[..len as usize])
                .trim()
                .to_string();
            if WECHAT_PROCESS_NAMES.contains(&name.as_str()) {
                return Some(pid);
            }
        }
    }

    None
}

fn get_wechat_pid_from_cg_window_list() -> Option<i32> {
    unsafe {
        let options = CG_WINDOW_LIST_ON_SCREEN_ONLY | CG_WINDOW_LIST_EXCLUDE_DESKTOP;
        let window_list = CGWindowListCopyWindowInfo(options, CG_NULL_WINDOW_ID);
        if window_list.is_null() {
            return None;
        }

        let count = core_foundation_sys::array::CFArrayGetCount(window_list);
        let owner_key = CFString::new("kCGWindowOwnerName");
        let bounds_key = CFString::new("kCGWindowBounds");

        let mut best: Option<(i32, f64)> = None;

        for i in 0..count {
            let dict = core_foundation_sys::array::CFArrayGetValueAtIndex(window_list, i)
                as core_foundation_sys::dictionary::CFDictionaryRef;

            let name_ptr = core_foundation_sys::dictionary::CFDictionaryGetValue(
                dict,
                owner_key.as_concrete_TypeRef() as *const std::ffi::c_void,
            );
            if name_ptr.is_null() {
                continue;
            }
            let name_cf =
                CFString::wrap_under_get_rule(name_ptr as core_foundation_sys::string::CFStringRef);
            let name = name_cf.to_string();
            if !WECHAT_PROCESS_NAMES.contains(&name.as_str()) {
                continue;
            }

            if let Some(layer) = cg_dict_get_i32(dict, "kCGWindowLayer") {
                if layer != 0 {
                    continue;
                }
            }

            let bounds_ptr = core_foundation_sys::dictionary::CFDictionaryGetValue(
                dict,
                bounds_key.as_concrete_TypeRef() as *const std::ffi::c_void,
            );
            if bounds_ptr.is_null() {
                continue;
            }
            let bounds_dict = bounds_ptr as core_foundation_sys::dictionary::CFDictionaryRef;
            let (w, h) = match (
                cg_dict_get_f64(bounds_dict, "Width"),
                cg_dict_get_f64(bounds_dict, "Height"),
            ) {
                (Some(w), Some(h)) => (w, h),
                _ => continue,
            };
            if w < MIN_MAIN_WINDOW_SIZE || h < MIN_MAIN_WINDOW_SIZE {
                continue;
            }

            let Some(pid) = cg_dict_get_i32(dict, "kCGWindowOwnerPID") else {
                continue;
            };
            let area = w * h;
            if best
                .as_ref()
                .map_or(true, |(_, best_area)| area > *best_area)
            {
                best = Some((pid, area));
            }
        }

        core_foundation_sys::base::CFRelease(window_list as _);
        best.map(|(pid, _)| pid)
    }
}

fn run_wechat_pid_script(script: &str) -> Result<i32> {
    let output = std::process::Command::new("osascript")
        .args(["-e", script])
        .output()
        .context("failed to run osascript")?;

    if !output.status.success() {
        anyhow::bail!(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }

    let pid_str = String::from_utf8_lossy(&output.stdout).trim().to_string();
    pid_str
        .parse::<i32>()
        .context(format!("cannot parse pid: {}", pid_str))
}

fn get_wechat_pid() -> Result<i32> {
    let bundle_script = format!(
        "tell application \"System Events\" to get unix id of (first process whose bundle identifier is \"{}\")",
        WECHAT_BUNDLE_ID
    );
    let mut errors = Vec::new();
    match run_wechat_pid_script(&bundle_script) {
        Ok(pid) => return Ok(pid),
        Err(e) => errors.push(format!("bundle id: {}", e)),
    }

    for name in WECHAT_PROCESS_NAMES {
        let name_script = format!(
            "tell application \"System Events\" to get unix id of (first process whose name is \"{}\")",
            name
        );
        match run_wechat_pid_script(&name_script) {
            Ok(pid) => return Ok(pid),
            Err(e) => errors.push(format!("name {}: {}", name, e)),
        }
    }

    if let Some(pid) = get_wechat_pid_from_process_list() {
        return Ok(pid);
    }

    if let Some(pid) = get_wechat_pid_from_cg_window_list() {
        return Ok(pid);
    }

    anyhow::bail!(
        "未检测到微信进程，请先启动并登录微信: {}",
        errors.join(" | ")
    );
}

pub fn resolve_wechat_pid() -> Result<i32> {
    get_wechat_pid()
}

unsafe fn ax_element_attribute(
    element: core_foundation_sys::base::CFTypeRef,
    attr: &str,
) -> Option<String> {
    use core_foundation_sys::base::CFRelease;

    let ax_element = element as accessibility_sys::AXUIElementRef;
    let attr_name = CFString::new(attr);
    let mut value: core_foundation_sys::base::CFTypeRef = std::ptr::null();

    let err = accessibility_sys::AXUIElementCopyAttributeValue(
        ax_element,
        attr_name.as_concrete_TypeRef(),
        &mut value,
    );

    if err != 0 || value.is_null() {
        return None;
    }

    let cf_type_id = core_foundation_sys::base::CFGetTypeID(value);
    let string_type_id = core_foundation_sys::string::CFStringGetTypeID();

    let result = if cf_type_id == string_type_id {
        let cf_str: CFString = TCFType::wrap_under_create_rule(value as _);
        Some(cf_str.to_string())
    } else {
        None
    };

    if result.is_none() {
        CFRelease(value);
    }

    result
}

unsafe fn ax_element_children(
    element: core_foundation_sys::base::CFTypeRef,
) -> Vec<core_foundation_sys::base::CFTypeRef> {
    let ax_element = element as accessibility_sys::AXUIElementRef;
    let attr_name = CFString::new("AXChildren");
    let mut value: core_foundation_sys::base::CFTypeRef = std::ptr::null();

    let err = accessibility_sys::AXUIElementCopyAttributeValue(
        ax_element,
        attr_name.as_concrete_TypeRef(),
        &mut value,
    );

    if err != 0 || value.is_null() {
        return vec![];
    }

    let cf_type_id = core_foundation_sys::base::CFGetTypeID(value);
    let array_type_id = core_foundation_sys::array::CFArrayGetTypeID();

    if cf_type_id != array_type_id {
        core_foundation_sys::base::CFRelease(value);
        return vec![];
    }

    let array: CFArray<CFType> = TCFType::wrap_under_create_rule(value as _);
    let mut children = Vec::with_capacity(array.len() as usize);
    for i in 0..array.len() {
        let child = array.get(i).unwrap();
        let ptr = child.as_CFTypeRef();
        core_foundation_sys::base::CFRetain(ptr);
        children.push(ptr);
    }
    children
}

/// Recursively search for an element by AXIdentifier.
unsafe fn find_element_by_id(
    element: core_foundation_sys::base::CFTypeRef,
    target_id: &str,
    depth: usize,
) -> Option<core_foundation_sys::base::CFTypeRef> {
    if depth > 12 {
        return None;
    }
    if let Some(id) = ax_element_attribute(element, "AXIdentifier") {
        if id == target_id {
            core_foundation_sys::base::CFRetain(element);
            return Some(element);
        }
    }
    let children = ax_element_children(element);
    for child in &children {
        if let Some(found) = find_element_by_id(*child, target_id, depth + 1) {
            for c in &children {
                core_foundation_sys::base::CFRelease(*c);
            }
            return Some(found);
        }
    }
    for c in &children {
        core_foundation_sys::base::CFRelease(*c);
    }
    None
}

extern "C" {
    fn AXValueGetValue(
        value: core_foundation_sys::base::CFTypeRef,
        the_type: u32,
        value_ptr: *mut std::ffi::c_void,
    ) -> bool;
}

#[repr(C)]
#[derive(Debug, Copy, Clone)]
struct CGPoint {
    x: f64,
    y: f64,
}

#[repr(C)]
#[derive(Debug, Copy, Clone)]
struct CGSize {
    width: f64,
    height: f64,
}

const AX_VALUE_CG_POINT_TYPE: u32 = 1;
const AX_VALUE_CG_SIZE_TYPE: u32 = 2;
unsafe fn ax_element_position(element: core_foundation_sys::base::CFTypeRef) -> Option<CGPoint> {
    let ax_element = element as accessibility_sys::AXUIElementRef;
    let attr_name = CFString::new("AXPosition");
    let mut value: core_foundation_sys::base::CFTypeRef = std::ptr::null();

    let err = accessibility_sys::AXUIElementCopyAttributeValue(
        ax_element,
        attr_name.as_concrete_TypeRef(),
        &mut value,
    );

    if err != 0 || value.is_null() {
        return None;
    }

    let mut point: CGPoint = std::mem::zeroed();
    let ok = AXValueGetValue(
        value,
        AX_VALUE_CG_POINT_TYPE,
        &mut point as *mut _ as *mut std::ffi::c_void,
    );
    core_foundation_sys::base::CFRelease(value);
    if ok {
        Some(point)
    } else {
        None
    }
}

unsafe fn ax_element_size(element: core_foundation_sys::base::CFTypeRef) -> Option<CGSize> {
    let ax_element = element as accessibility_sys::AXUIElementRef;
    let attr_name = CFString::new("AXSize");
    let mut value: core_foundation_sys::base::CFTypeRef = std::ptr::null();

    let err = accessibility_sys::AXUIElementCopyAttributeValue(
        ax_element,
        attr_name.as_concrete_TypeRef(),
        &mut value,
    );

    if err != 0 || value.is_null() {
        return None;
    }

    let mut size: CGSize = std::mem::zeroed();
    let ok = AXValueGetValue(
        value,
        AX_VALUE_CG_SIZE_TYPE,
        &mut size as *mut _ as *mut std::ffi::c_void,
    );
    core_foundation_sys::base::CFRelease(value);
    if ok {
        Some(size)
    } else {
        None
    }
}

#[derive(Debug, Clone)]
pub struct ChatMessage {
    pub sender: String,
    pub content: String,
    pub is_self: bool,
}

#[derive(Debug, Clone)]
pub struct SessionItemSnapshot {
    pub chat_name: String,
    pub raw_preview: String,
    pub preview_body: String,
    pub unread_count: u32,
    pub sender_hint: Option<String>,
    pub has_sender_prefix: bool,
    /// Inferred from sender_prefix presence in session preview.
    /// true = likely group chat, false = likely private chat.
    pub is_group: bool,
}

fn clean_text(raw: &str) -> String {
    raw.replace('\u{200b}', "")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn remove_zero_width(raw: &str) -> String {
    raw.chars()
        .filter(|c| !matches!(c, '\u{200b}' | '\u{200c}' | '\u{200d}' | '\u{feff}'))
        .collect()
}

pub fn normalize_for_match(raw: &str) -> String {
    remove_zero_width(raw)
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

pub fn prefix8_key(raw: &str) -> String {
    normalize_for_match(raw).chars().take(8).collect()
}

pub fn is_same_message_prefix8(left: &str, right: &str) -> bool {
    let left_key = prefix8_key(left);
    let right_key = prefix8_key(right);
    !left_key.is_empty() && left_key == right_key
}

fn normalize_session_name_for_match(raw: &str) -> String {
    let mut name = normalize_for_match(raw);
    name = SESSION_UNREAD_PREFIX_RE.replace(&name, "").to_string();
    name = SESSION_NEWMSG_SUFFIX_RE.replace(&name, "").to_string();
    name.trim().to_string()
}

fn is_session_noise_line(line: &str) -> bool {
    let t = line.trim();
    t.is_empty() || t == "已置顶" || t == "消息免打扰" || TIME_HINT_RE.is_match(t)
}

fn parse_session_unread_count(preview_text: &str) -> u32 {
    let lines: Vec<&str> = preview_text
        .lines()
        .map(|line| line.trim())
        .filter(|line| !line.is_empty())
        .collect();
    if lines.len() <= 1 {
        return 0;
    }

    for raw_line in lines.iter().skip(1) {
        if is_session_noise_line(raw_line) {
            continue;
        }
        if let Some(caps) = SESSION_UNREAD_COUNT_RE.captures(raw_line) {
            return caps
                .get(1)
                .and_then(|m| m.as_str().parse::<u32>().ok())
                .unwrap_or(0);
        }
        break;
    }
    0
}

/// Parse a session preview text and return (sender, body) if possible.
/// Preview shape is generally:
///   line0: chat name
///   line1: "sender: body" or "body"
///   lineN: time / mute / pinned hints
pub fn parse_session_preview_line(preview_text: &str) -> (Option<String>, Option<String>) {
    let lines: Vec<&str> = preview_text
        .lines()
        .map(|line| line.trim())
        .filter(|line| !line.is_empty())
        .collect();
    if lines.len() <= 1 {
        return (None, None);
    }

    for raw_line in lines.iter().skip(1) {
        if is_session_noise_line(raw_line) {
            continue;
        }

        let candidate = SESSION_UNREAD_PREFIX_RE
            .replace(raw_line, "")
            .trim()
            .to_string();
        if candidate.is_empty() {
            continue;
        }

        // URLs contain protocol ":" and should not be treated as sender prefix.
        if candidate.contains("://") {
            return (None, Some(candidate));
        }

        if let Some(caps) = SENDER_PREFIX_RE.captures(&candidate) {
            let sender = caps
                .get(1)
                .map(|m| m.as_str().trim().to_string())
                .unwrap_or_default();
            let body = caps
                .get(2)
                .map(|m| m.as_str().trim().to_string())
                .unwrap_or_default();

            if !sender.is_empty()
                && !body.is_empty()
                && !sender.chars().all(|c| c.is_ascii_digit())
                && !matches!(sender.to_lowercase().as_str(), "http" | "https" | "ftp")
            {
                return (Some(sender), Some(body));
            }
        }

        return (None, Some(candidate));
    }

    (None, None)
}

const POPUP_ROLES: &[&str] = &["AXMenu", "AXPopover", "AXSheet", "AXDialog"];

fn get_wechat_app_element() -> Result<(accessibility_sys::AXUIElementRef, i32)> {
    let pid = get_wechat_pid()?;
    let app = unsafe { accessibility_sys::AXUIElementCreateApplication(pid) };
    if app.is_null() {
        anyhow::bail!("无法创建 AXUIElement for pid {}", pid);
    }
    Ok((app, pid))
}

/// Check if WeChat currently has a popup, context menu, sheet, or dialog visible.
/// When true, AX tree reads are unreliable and polling should be skipped.
pub fn has_popup_or_menu() -> bool {
    let Ok((app, _)) = get_wechat_app_element() else {
        return false;
    };

    unsafe {
        let windows_attr = CFString::new("AXWindows");
        let mut windows_value: core_foundation_sys::base::CFTypeRef = std::ptr::null();
        let err = accessibility_sys::AXUIElementCopyAttributeValue(
            app,
            windows_attr.as_concrete_TypeRef(),
            &mut windows_value,
        );

        if err != 0 || windows_value.is_null() {
            core_foundation_sys::base::CFRelease(app as _);
            return false;
        }

        let windows: CFArray<CFType> = TCFType::wrap_under_create_rule(windows_value as _);
        for i in 0..windows.len() {
            let win = windows.get(i).unwrap();
            let ptr = win.as_CFTypeRef();
            if let Some(role) = ax_element_attribute(ptr, "AXRole") {
                if POPUP_ROLES.contains(&role.as_str()) {
                    core_foundation_sys::base::CFRelease(app as _);
                    return true;
                }
            }
            if let Some(sub) = ax_element_attribute(ptr, "AXSubrole") {
                if sub == "AXDialog" || sub == "AXSystemDialog" || sub == "AXFloatingWindow" {
                    if ax_element_attribute(ptr, "AXTitle")
                        .map(|t| !t.contains("微信") && !t.contains("WeChat"))
                        .unwrap_or(true)
                    {
                        core_foundation_sys::base::CFRelease(app as _);
                        return true;
                    }
                }
            }
        }

        // Also check for popup children (context menus attached to the app, not as windows)
        let children = ax_element_children(app as _);
        for child in &children {
            if let Some(role) = ax_element_attribute(*child, "AXRole") {
                if role == "AXMenu" {
                    for c in &children {
                        core_foundation_sys::base::CFRelease(*c);
                    }
                    core_foundation_sys::base::CFRelease(app as _);
                    return true;
                }
            }
        }
        for c in &children {
            core_foundation_sys::base::CFRelease(*c);
        }

        core_foundation_sys::base::CFRelease(app as _);
        false
    }
}

fn get_main_window() -> Result<core_foundation_sys::base::CFTypeRef> {
    let (app, _pid) = get_wechat_app_element()?;

    unsafe {
        let windows_attr = CFString::new("AXWindows");
        let mut windows_value: core_foundation_sys::base::CFTypeRef = std::ptr::null();
        let err = accessibility_sys::AXUIElementCopyAttributeValue(
            app,
            windows_attr.as_concrete_TypeRef(),
            &mut windows_value,
        );

        if err != 0 || windows_value.is_null() {
            core_foundation_sys::base::CFRelease(app as _);
            anyhow::bail!("无法获取微信窗口列表，请检查辅助功能权限");
        }

        let windows: CFArray<CFType> = TCFType::wrap_under_create_rule(windows_value as _);
        if windows.is_empty() {
            core_foundation_sys::base::CFRelease(app as _);
            anyhow::bail!("微信没有打开的窗口");
        }

        // Collect candidate windows, filtering out popups/sheets/dialogs
        let mut candidates: Vec<core_foundation_sys::base::CFTypeRef> = Vec::new();
        for i in 0..windows.len() {
            let win = windows.get(i).unwrap();
            let ptr = win.as_CFTypeRef();

            let role = ax_element_attribute(ptr, "AXRole").unwrap_or_default();
            if POPUP_ROLES.contains(&role.as_str()) {
                continue;
            }
            let subrole = ax_element_attribute(ptr, "AXSubrole").unwrap_or_default();
            if subrole == "AXDialog" || subrole == "AXSystemDialog" {
                continue;
            }

            candidates.push(ptr);
        }

        if candidates.is_empty() {
            core_foundation_sys::base::CFRelease(app as _);
            anyhow::bail!("微信没有可用的主窗口（可能被弹窗遮挡）");
        }

        // Prefer the window that contains chat_message_list (the real main chat window)
        for &ptr in &candidates {
            if find_element_by_id(ptr, "chat_message_list", 0).is_some() {
                core_foundation_sys::base::CFRetain(ptr);
                core_foundation_sys::base::CFRelease(app as _);
                return Ok(ptr);
            }
        }

        // Fallback: first candidate with "微信"/"WeChat" in title
        for &ptr in &candidates {
            if let Some(title) = ax_element_attribute(ptr, "AXTitle") {
                if title.contains("微信") || title.contains("WeChat") {
                    core_foundation_sys::base::CFRetain(ptr);
                    core_foundation_sys::base::CFRelease(app as _);
                    return Ok(ptr);
                }
            }
        }

        // Last resort: first candidate
        let ptr = candidates[0];
        core_foundation_sys::base::CFRetain(ptr);
        core_foundation_sys::base::CFRelease(app as _);
        Ok(ptr)
    }
}

/// Read the active chat name from AXIdentifier "current_chat_name_label".
/// Fallback: window title with " - " separator.
/// Fallback: first AXStaticText in the sub splitter area.
pub fn read_active_chat_name() -> Result<String> {
    let win = get_main_window()?;

    unsafe {
        // Strategy 1: Find current_chat_name_label (most reliable for new WeChat)
        if let Some(label) = find_element_by_id(win, "current_chat_name_label", 0) {
            if let Some(value) = ax_element_attribute(label, "AXValue") {
                let name = clean_text(&value);
                core_foundation_sys::base::CFRelease(label);
                if !name.is_empty() {
                    core_foundation_sys::base::CFRelease(win);
                    return Ok(name);
                }
            }
            core_foundation_sys::base::CFRelease(label);
        }

        // Strategy 2: Find big_title_line_h_view
        if let Some(label) = find_element_by_id(win, "big_title_line_h_view", 0) {
            if let Some(value) = ax_element_attribute(label, "AXValue") {
                let name = clean_text(&value);
                core_foundation_sys::base::CFRelease(label);
                if !name.is_empty() {
                    core_foundation_sys::base::CFRelease(win);
                    return Ok(name);
                }
            }
            core_foundation_sys::base::CFRelease(label);
        }

        // Strategy 3: Window title "聊天名 - 微信" format
        if let Some(title) = ax_element_attribute(win, "AXTitle") {
            if title.contains(" - ") {
                let name = title.split(" - ").next().unwrap_or("").trim();
                if !name.is_empty() && name != "微信" && name != "WeChat" {
                    core_foundation_sys::base::CFRelease(win);
                    return Ok(name.to_string());
                }
            }
        }

        core_foundation_sys::base::CFRelease(win);
        Ok("当前会话".to_string())
    }
}

/// Read the group member count from "current_chat_count_label".
///
/// Returns `Some(count)` for group chats (e.g. "(433)" → 433),
/// `None` for private chats (element absent) or parse failure.
///
/// This is the most reliable way to distinguish group vs private chats:
/// - Group chats: `big_title_line_h_view` has 2 children:
///   `current_chat_name_label` + `current_chat_count_label` with value "(N)"
/// - Private chats: only `current_chat_name_label`, no count label
pub fn read_active_chat_member_count() -> Result<Option<u32>> {
    let win = get_main_window()?;

    unsafe {
        let result = if let Some(label) = find_element_by_id(win, "current_chat_count_label", 0) {
            let count = ax_element_attribute(label, "AXValue").and_then(|v| {
                let digits: String = v.chars().filter(|c| c.is_ascii_digit()).collect();
                digits.parse::<u32>().ok()
            });
            core_foundation_sys::base::CFRelease(label);
            count
        } else {
            None
        };

        core_foundation_sys::base::CFRelease(win);
        Ok(result)
    }
}

/// Read chat messages from the chat_message_list.
/// Returns messages from chat_bubble_item_view elements only.
pub fn read_chat_messages() -> Result<Vec<String>> {
    let win = get_main_window()?;
    let mut messages = Vec::new();

    unsafe {
        if let Some(list) = find_element_by_id(win, "chat_message_list", 0) {
            let children = ax_element_children(list);
            for child in &children {
                let id = ax_element_attribute(*child, "AXIdentifier").unwrap_or_default();
                if id == "chat_bubble_item_view" {
                    if let Some(title) = ax_element_attribute(*child, "AXTitle") {
                        let text = clean_text(&title);
                        if !text.is_empty() {
                            messages.push(text);
                        }
                    }
                }
                core_foundation_sys::base::CFRelease(*child);
            }
            core_foundation_sys::base::CFRelease(list);
        }

        core_foundation_sys::base::CFRelease(win);
    }

    Ok(messages)
}

/// Read chat messages from the active chat.
///
/// WeChat macOS AX tree exposes `chat_bubble_item_view` as flat AXStaticText
/// elements with no children. Only message content (AXTitle) is available;
/// sender names and self/other detection are not exposed by the AX tree.
pub fn read_chat_messages_rich() -> Result<Vec<ChatMessage>> {
    let win = get_main_window()?;
    let mut messages = Vec::new();

    unsafe {
        if let Some(list) = find_element_by_id(win, "chat_message_list", 0) {
            let children = ax_element_children(list);
            for child in &children {
                let id = ax_element_attribute(*child, "AXIdentifier").unwrap_or_default();
                if id == "chat_bubble_item_view" {
                    let content = ax_element_attribute(*child, "AXTitle")
                        .map(|t| clean_text(&t))
                        .unwrap_or_default();
                    if !content.is_empty() {
                        messages.push(ChatMessage {
                            sender: String::new(),
                            content,
                            is_self: false,
                        });
                    }
                }
                core_foundation_sys::base::CFRelease(*child);
            }
            core_foundation_sys::base::CFRelease(list);
        }

        core_foundation_sys::base::CFRelease(win);
    }

    Ok(messages)
}

/// Read the latest message from the active chat.
/// Reads from chat_bubble_item_view elements in chat_message_list.
pub fn read_latest_message() -> Result<String> {
    let messages = read_chat_messages()?;

    // Return the last non-noise message
    for text in messages.iter().rev() {
        if NOISE_TEXTS.contains(text.as_str()) {
            continue;
        }
        if TIME_HINT_RE.is_match(text) {
            continue;
        }
        if text.len() > 500 || text.is_empty() {
            continue;
        }
        return Ok(text.clone());
    }

    // Fallback: full tree scan (for older WeChat versions)
    let texts = get_static_texts()?;
    for text in texts.iter().rev() {
        if NOISE_TEXTS.contains(text.as_str()) {
            continue;
        }
        if TIME_HINT_RE.is_match(text) {
            continue;
        }
        if text.len() > 500 || text.is_empty() {
            continue;
        }
        return Ok(text.clone());
    }
    Ok(String::new())
}

/// Get session list from session_list AXList.
/// Extracts session names from session_item_* IDs.
pub fn get_current_sessions() -> Result<Vec<String>> {
    let win = get_main_window()?;
    let mut sessions = Vec::new();

    unsafe {
        if let Some(list) = find_element_by_id(win, "session_list", 0) {
            let children = ax_element_children(list);
            for child in &children {
                let id = ax_element_attribute(*child, "AXIdentifier").unwrap_or_default();
                if id.starts_with("session_item_") {
                    let session_name = id.strip_prefix("session_item_").unwrap_or("").to_string();
                    if !session_name.is_empty() {
                        sessions.push(session_name);
                    }
                }
                core_foundation_sys::base::CFRelease(*child);
            }
            core_foundation_sys::base::CFRelease(list);
        } else {
            // Fallback: full tree scan
            core_foundation_sys::base::CFRelease(win);
            return get_current_sessions_fallback();
        }

        core_foundation_sys::base::CFRelease(win);
    }

    Ok(sessions)
}

/// Read all session_list items and parse preview/body/unread/sender hints.
pub fn read_session_snapshots() -> Result<Vec<SessionItemSnapshot>> {
    let win = get_main_window()?;
    let mut snapshots = Vec::new();

    unsafe {
        if let Some(list) = find_element_by_id(win, "session_list", 0) {
            let children = ax_element_children(list);
            let mut seen = HashSet::new();
            for child in &children {
                let id = ax_element_attribute(*child, "AXIdentifier").unwrap_or_default();
                if !id.starts_with("session_item_") {
                    core_foundation_sys::base::CFRelease(*child);
                    continue;
                }

                let chat_name = id
                    .strip_prefix("session_item_")
                    .unwrap_or("")
                    .trim()
                    .to_string();
                if chat_name.is_empty() || !seen.insert(chat_name.clone()) {
                    core_foundation_sys::base::CFRelease(*child);
                    continue;
                }

                let raw_preview = ax_element_attribute(*child, "AXTitle")
                    .or_else(|| ax_element_attribute(*child, "AXValue"))
                    .unwrap_or_else(|| chat_name.clone());
                let (sender_hint, body_opt) = parse_session_preview_line(&raw_preview);
                let preview_body = body_opt.unwrap_or_default();
                let unread_count = parse_session_unread_count(&raw_preview);
                let has_sender_prefix = sender_hint
                    .as_deref()
                    .map(|s| !s.trim().is_empty())
                    .unwrap_or(false);

                snapshots.push(SessionItemSnapshot {
                    chat_name,
                    raw_preview,
                    preview_body,
                    unread_count,
                    is_group: has_sender_prefix,
                    sender_hint,
                    has_sender_prefix,
                });

                core_foundation_sys::base::CFRelease(*child);
            }
            core_foundation_sys::base::CFRelease(list);
        }
        core_foundation_sys::base::CFRelease(win);
    }

    Ok(snapshots)
}

/// Read full preview text of a chat item from `session_list`.
/// Tries exact `session_item_{chat_name}` match first, then falls back to line-0 name match.
pub fn read_session_preview_for_chat(chat_name: &str) -> Result<Option<String>> {
    let target_norm = normalize_session_name_for_match(chat_name);
    if target_norm.is_empty() {
        return Ok(None);
    }

    let target_id = format!("session_item_{}", chat_name.trim());
    let win = get_main_window()?;
    let mut exact: Option<String> = None;
    let mut fuzzy: Option<String> = None;

    unsafe {
        if let Some(list) = find_element_by_id(win, "session_list", 0) {
            let children = ax_element_children(list);
            for child in &children {
                let id = ax_element_attribute(*child, "AXIdentifier").unwrap_or_default();
                if !id.starts_with("session_item_") {
                    core_foundation_sys::base::CFRelease(*child);
                    continue;
                }

                let preview = ax_element_attribute(*child, "AXTitle")
                    .or_else(|| ax_element_attribute(*child, "AXValue"))
                    .unwrap_or_else(|| id.strip_prefix("session_item_").unwrap_or("").to_string());

                if id == target_id {
                    exact = Some(preview);
                    core_foundation_sys::base::CFRelease(*child);
                    continue;
                }

                if fuzzy.is_none() {
                    let first_line = preview.lines().next().unwrap_or("");
                    let first_norm = normalize_session_name_for_match(first_line);
                    if !first_norm.is_empty()
                        && (first_norm == target_norm
                            || first_norm.contains(&target_norm)
                            || target_norm.contains(&first_norm))
                    {
                        fuzzy = Some(preview);
                    }
                }

                core_foundation_sys::base::CFRelease(*child);
            }
            core_foundation_sys::base::CFRelease(list);
        }
        core_foundation_sys::base::CFRelease(win);
    }

    Ok(exact.or(fuzzy))
}

/// Fallback full-tree session scan for older WeChat versions.
fn get_current_sessions_fallback() -> Result<Vec<String>> {
    let texts = get_static_texts()?;
    let mut candidates = Vec::new();
    let mut seen = HashSet::new();

    for text in &texts {
        if NOISE_TEXTS.contains(text.as_str()) {
            continue;
        }
        if TIME_HINT_RE.is_match(text) {
            continue;
        }
        if text.len() > 40 {
            continue;
        }
        if seen.contains(text) {
            continue;
        }
        seen.insert(text.clone());
        candidates.push(text.clone());
    }

    Ok(candidates)
}

/// Full tree scan of all AXStaticText elements (fallback).
/// Get the WeChat main window position and size (in screen coordinates).
pub fn get_wechat_window_frame() -> Result<(f64, f64, f64, f64)> {
    let win = get_main_window()?;
    unsafe {
        let pos = ax_element_position(win);
        let size = ax_element_size(win);
        core_foundation_sys::base::CFRelease(win);
        match (pos, size) {
            (Some(p), Some(s)) => Ok((p.x, p.y, s.width, s.height)),
            _ => anyhow::bail!("cannot read WeChat window frame"),
        }
    }
}

pub fn get_static_texts() -> Result<Vec<String>> {
    let win = get_main_window()?;
    let mut all_texts = Vec::new();

    unsafe {
        collect_static_texts(win, &mut all_texts, 0);
        core_foundation_sys::base::CFRelease(win);
    }

    Ok(all_texts)
}

unsafe fn collect_static_texts(
    element: core_foundation_sys::base::CFTypeRef,
    results: &mut Vec<String>,
    depth: usize,
) {
    if depth > 30 {
        return;
    }
    if let Some(role) = ax_element_attribute(element, "AXRole") {
        if role == "AXStaticText" {
            for attr in &["AXValue", "AXTitle"] {
                if let Some(value) = ax_element_attribute(element, attr) {
                    let clean = clean_text(&value);
                    if !clean.is_empty() {
                        results.push(clean);
                    }
                    break;
                }
            }
        }
    }

    let children = ax_element_children(element);
    for child in &children {
        collect_static_texts(*child, results, depth + 1);
        core_foundation_sys::base::CFRelease(*child);
    }
}

#[cfg(test)]
mod tests {
    use super::{
        is_same_message_prefix8, parse_session_preview_line, parse_session_unread_count,
        prefix8_key,
    };

    #[test]
    fn parse_session_preview_with_sender_prefix() {
        let text = "ssh 前端进阶交流群3群「禁广告」\n花姐🌸: 哈哈哈哈哈哈嗝\n21:34\n消息免打扰";
        let (sender, body) = parse_session_preview_line(text);
        assert_eq!(sender.as_deref(), Some("花姐🌸"));
        assert_eq!(body.as_deref(), Some("哈哈哈哈哈哈嗝"));
    }

    #[test]
    fn parse_session_preview_without_sender_prefix() {
        let text = "某会话\n仅正文不带前缀\n今天 21:11";
        let (sender, body) = parse_session_preview_line(text);
        assert_eq!(sender, None);
        assert_eq!(body.as_deref(), Some("仅正文不带前缀"));
    }

    #[test]
    fn parse_session_preview_url_not_treated_as_sender() {
        let text = "某会话\nhttps://example.com/a:b?x=1\n21:11";
        let (sender, body) = parse_session_preview_line(text);
        assert_eq!(sender, None);
        assert_eq!(body.as_deref(), Some("https://example.com/a:b?x=1"));
    }

    #[test]
    fn parse_session_preview_skips_noise_lines() {
        let text = "某会话\n[3条] 阿强：你好呀\n今天 21:11\n已置顶\n消息免打扰";
        let (sender, body) = parse_session_preview_line(text);
        assert_eq!(sender.as_deref(), Some("阿强"));
        assert_eq!(body.as_deref(), Some("你好呀"));
    }

    #[test]
    fn parse_session_unread_count_should_parse_prefix() {
        let text = "某会话\n[12条] 阿强：你好呀\n今天 21:11\n已置顶";
        assert_eq!(parse_session_unread_count(text), 12);
    }

    #[test]
    fn parse_session_unread_count_should_ignore_non_prefix_lines() {
        let text = "某会话\n阿强：你好呀\n今天 21:11";
        assert_eq!(parse_session_unread_count(text), 0);
    }

    #[test]
    fn prefix8_match_should_work_for_same_prefix() {
        assert!(is_same_message_prefix8(
            "因为rust的代码简直不是人类读的",
            "因为rust的代码简直不是人类读的!!!"
        ));
    }

    #[test]
    fn prefix8_match_should_work_for_short_text() {
        assert!(is_same_message_prefix8("哈哈", "哈哈"));
    }

    #[test]
    fn prefix8_match_should_fail_for_empty_or_different_text() {
        assert!(!is_same_message_prefix8("", "abc"));
        assert!(!is_same_message_prefix8("前缀不同A", "前缀不同B"));
    }

    #[test]
    fn prefix8_key_should_trim_and_normalize_spaces() {
        let key = prefix8_key("  hello   world \u{200b} ");
        assert_eq!(key, "hello wo");
    }
}
