use anyhow::{Context, Result};
use core_foundation::array::CFArray;
use core_foundation::base::{CFType, TCFType};
use core_foundation::string::CFString;
use std::collections::HashSet;
use std::ffi::c_void;
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::PathBuf;

const WECHAT_BUNDLE_ID: &str = "com.tencent.xinWeChat";
const DEFAULT_MAX_DEPTH: usize = 40;

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

extern "C" {
    fn AXValueGetValue(
        value: core_foundation_sys::base::CFTypeRef,
        the_type: u32,
        value_ptr: *mut c_void,
    ) -> bool;
}

fn escape_inline(raw: &str) -> String {
    raw.replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

fn get_wechat_pid() -> Result<i32> {
    let output = std::process::Command::new("osascript")
        .args([
            "-e",
            &format!(
                "tell application \"System Events\" to get unix id of (first process whose bundle identifier is \"{}\")",
                WECHAT_BUNDLE_ID
            ),
        ])
        .output()?;
    if !output.status.success() {
        anyhow::bail!("WeChat not found");
    }
    Ok(String::from_utf8_lossy(&output.stdout)
        .trim()
        .parse::<i32>()?)
}

unsafe fn copy_attr_value(
    el: core_foundation_sys::base::CFTypeRef,
    attr: &str,
) -> std::result::Result<core_foundation_sys::base::CFTypeRef, i32> {
    let ax = el as accessibility_sys::AXUIElementRef;
    let name = CFString::new(attr);
    let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
    let err =
        accessibility_sys::AXUIElementCopyAttributeValue(ax, name.as_concrete_TypeRef(), &mut val);
    if err != 0 || val.is_null() {
        return Err(err);
    }
    Ok(val)
}

unsafe fn ax_string_attr(el: core_foundation_sys::base::CFTypeRef, attr: &str) -> String {
    let Ok(val) = copy_attr_value(el, attr) else {
        return String::new();
    };
    let tid = core_foundation_sys::base::CFGetTypeID(val);
    let string_tid = core_foundation_sys::string::CFStringGetTypeID();
    let out = if tid == string_tid {
        let s = CFString::wrap_under_get_rule(val as _);
        s.to_string()
    } else {
        String::new()
    };
    core_foundation_sys::base::CFRelease(val);
    out
}

unsafe fn cf_type_name(value: core_foundation_sys::base::CFTypeRef) -> String {
    let tid = core_foundation_sys::base::CFGetTypeID(value);
    let desc = core_foundation_sys::base::CFCopyTypeIDDescription(tid);
    if desc.is_null() {
        return format!("typeID={tid}");
    }
    let s: CFString = TCFType::wrap_under_create_rule(desc as _);
    s.to_string()
}

unsafe fn cf_description(value: core_foundation_sys::base::CFTypeRef) -> String {
    let desc = core_foundation_sys::base::CFCopyDescription(value);
    if desc.is_null() {
        return "<no-description>".to_string();
    }
    let s: CFString = TCFType::wrap_under_create_rule(desc as _);
    s.to_string()
}

unsafe fn ax_attr_names(el: core_foundation_sys::base::CFTypeRef) -> Vec<String> {
    let ax = el as accessibility_sys::AXUIElementRef;
    let mut names: core_foundation_sys::base::CFTypeRef = std::ptr::null();
    let err = accessibility_sys::AXUIElementCopyAttributeNames(ax, &mut names as *mut _ as *mut _);
    if err != 0 || names.is_null() {
        return vec![];
    }
    let tid = core_foundation_sys::base::CFGetTypeID(names);
    if tid != core_foundation_sys::array::CFArrayGetTypeID() {
        core_foundation_sys::base::CFRelease(names);
        return vec![];
    }

    let arr: CFArray<CFType> = TCFType::wrap_under_create_rule(names as _);
    let mut out = Vec::new();
    for i in 0..arr.len() {
        let item = arr.get(i).unwrap();
        let ptr = item.as_CFTypeRef();
        if core_foundation_sys::base::CFGetTypeID(ptr)
            == core_foundation_sys::string::CFStringGetTypeID()
        {
            let s = CFString::wrap_under_get_rule(ptr as _);
            out.push(s.to_string());
        }
    }
    out
}

unsafe fn ax_action_names(el: core_foundation_sys::base::CFTypeRef) -> Vec<String> {
    let ax = el as accessibility_sys::AXUIElementRef;
    let mut names: core_foundation_sys::array::CFArrayRef = std::ptr::null();
    let err = accessibility_sys::AXUIElementCopyActionNames(ax, &mut names);
    if err != 0 || names.is_null() {
        return vec![];
    }

    let arr: CFArray<CFType> = TCFType::wrap_under_create_rule(names as _);
    let mut out = Vec::new();
    for i in 0..arr.len() {
        let item = arr.get(i).unwrap();
        let ptr = item.as_CFTypeRef();
        if core_foundation_sys::base::CFGetTypeID(ptr)
            == core_foundation_sys::string::CFStringGetTypeID()
        {
            let s = CFString::wrap_under_get_rule(ptr as _);
            out.push(s.to_string());
        }
    }
    out
}

unsafe fn ax_children(
    el: core_foundation_sys::base::CFTypeRef,
) -> Vec<core_foundation_sys::base::CFTypeRef> {
    let Ok(val) = copy_attr_value(el, "AXChildren") else {
        return vec![];
    };
    let mut out = Vec::new();
    if core_foundation_sys::base::CFGetTypeID(val) == core_foundation_sys::array::CFArrayGetTypeID()
    {
        let arr = CFArray::<CFType>::wrap_under_get_rule(val as _);
        for i in 0..arr.len() {
            let item = arr.get(i).unwrap();
            let ptr = item.as_CFTypeRef();
            core_foundation_sys::base::CFRetain(ptr);
            out.push(ptr);
        }
    }
    core_foundation_sys::base::CFRelease(val);
    out
}

unsafe fn ax_elements_array_attr(
    el: core_foundation_sys::base::CFTypeRef,
    attr: &str,
) -> Vec<core_foundation_sys::base::CFTypeRef> {
    let Ok(val) = copy_attr_value(el, attr) else {
        return vec![];
    };
    let mut out = Vec::new();
    if core_foundation_sys::base::CFGetTypeID(val) == core_foundation_sys::array::CFArrayGetTypeID()
    {
        let arr = CFArray::<CFType>::wrap_under_get_rule(val as _);
        for i in 0..arr.len() {
            let item = arr.get(i).unwrap();
            let ptr = item.as_CFTypeRef();
            core_foundation_sys::base::CFRetain(ptr);
            out.push(ptr);
        }
    }
    core_foundation_sys::base::CFRelease(val);
    out
}

unsafe fn decode_ax_point(value: core_foundation_sys::base::CFTypeRef) -> Option<CGPoint> {
    let mut out: CGPoint = std::mem::zeroed();
    let ok = AXValueGetValue(value, 1, &mut out as *mut _ as *mut _);
    if ok {
        Some(out)
    } else {
        None
    }
}

unsafe fn decode_ax_size(value: core_foundation_sys::base::CFTypeRef) -> Option<CGSize> {
    let mut out: CGSize = std::mem::zeroed();
    let ok = AXValueGetValue(value, 2, &mut out as *mut _ as *mut _);
    if ok {
        Some(out)
    } else {
        None
    }
}

unsafe fn attr_summary(el: core_foundation_sys::base::CFTypeRef, attr_name: &str) -> String {
    let Ok(val) = copy_attr_value(el, attr_name) else {
        return "ERR".to_string();
    };

    let tname = cf_type_name(val);
    let summary = match attr_name {
        "AXPosition" => decode_ax_point(val)
            .map(|p| format!("CGPoint(x={:.2}, y={:.2})", p.x, p.y))
            .unwrap_or_else(|| escape_inline(&cf_description(val))),
        "AXSize" => decode_ax_size(val)
            .map(|s| format!("CGSize(w={:.2}, h={:.2})", s.width, s.height))
            .unwrap_or_else(|| escape_inline(&cf_description(val))),
        _ => escape_inline(&cf_description(val)),
    };

    core_foundation_sys::base::CFRelease(val);
    format!("{tname} | {summary}")
}

unsafe fn dump_node<W: Write>(
    writer: &mut W,
    el: core_foundation_sys::base::CFTypeRef,
    depth: usize,
    max_depth: usize,
    visited: &mut HashSet<usize>,
) -> Result<()> {
    let indent = "  ".repeat(depth);
    let ptr = el as usize;
    if !visited.insert(ptr) {
        writeln!(writer, "{}[node] ptr=0x{:x} <already-visited>", indent, ptr)?;
        return Ok(());
    }

    let role = ax_string_attr(el, "AXRole");
    let subrole = ax_string_attr(el, "AXSubrole");
    let identifier = ax_string_attr(el, "AXIdentifier");
    let title = ax_string_attr(el, "AXTitle");
    let value = ax_string_attr(el, "AXValue");

    writeln!(writer, "{}[node] ptr=0x{:x} depth={}", indent, ptr, depth)?;
    writeln!(writer, "{}  role={}", indent, escape_inline(&role))?;
    writeln!(writer, "{}  subrole={}", indent, escape_inline(&subrole))?;
    writeln!(writer, "{}  id={}", indent, escape_inline(&identifier))?;
    writeln!(writer, "{}  title={}", indent, escape_inline(&title))?;
    writeln!(writer, "{}  value={}", indent, escape_inline(&value))?;

    let mut actions = ax_action_names(el);
    actions.sort();
    if actions.is_empty() {
        writeln!(writer, "{}  actions=[]", indent)?;
    } else {
        writeln!(writer, "{}  actions=[{}]", indent, actions.join(", "))?;
    }

    let mut attrs = ax_attr_names(el);
    attrs.sort();
    writeln!(writer, "{}  attrs_count={}", indent, attrs.len())?;
    for attr in attrs {
        let summary = attr_summary(el, &attr);
        writeln!(writer, "{}    {} => {}", indent, attr, summary)?;
    }

    if depth >= max_depth {
        writeln!(writer, "{}  children=<skipped:max-depth>", indent)?;
        return Ok(());
    }

    let children = ax_children(el);
    writeln!(writer, "{}  children_count={}", indent, children.len())?;
    for child in children {
        let dump_result = dump_node(writer, child, depth + 1, max_depth, visited);
        core_foundation_sys::base::CFRelease(child);
        dump_result?;
    }

    Ok(())
}

fn create_dump_path() -> Result<PathBuf> {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..");
    let log_dir = repo_root.join("logs").join("ax_dumps");
    fs::create_dir_all(&log_dir)?;
    let ts = chrono::Local::now().format("%Y%m%d_%H%M%S");
    Ok(log_dir.join(format!("wechat_ax_full_{ts}.log")))
}

fn parse_max_depth() -> usize {
    std::env::args()
        .nth(1)
        .and_then(|raw| raw.parse::<usize>().ok())
        .unwrap_or(DEFAULT_MAX_DEPTH)
}

fn main() -> Result<()> {
    let max_depth = parse_max_depth();
    let dump_path = create_dump_path()?;
    let dump_file = File::create(&dump_path)?;
    let mut writer = BufWriter::new(dump_file);

    let pid = get_wechat_pid().context("获取微信 PID 失败")?;
    writeln!(
        writer,
        "WeChat AX Full Dump\nTime: {}\nPID: {}\nMaxDepth: {}\n",
        chrono::Local::now().to_rfc3339(),
        pid,
        max_depth
    )?;

    unsafe {
        let app = accessibility_sys::AXUIElementCreateApplication(pid);
        if app.is_null() {
            anyhow::bail!("无法创建 AXUIElement");
        }

        writeln!(writer, "=== APP ELEMENT ===")?;
        let mut visited = HashSet::new();
        dump_node(&mut writer, app as _, 0, max_depth, &mut visited)?;

        let windows = ax_elements_array_attr(app as _, "AXWindows");
        writeln!(writer, "\n=== WINDOWS ({}) ===", windows.len())?;
        for (idx, win) in windows.into_iter().enumerate() {
            writeln!(writer, "\n--- WINDOW[{idx}] ---")?;
            let mut window_visited = HashSet::new();
            let dump_result = dump_node(&mut writer, win, 0, max_depth, &mut window_visited);
            core_foundation_sys::base::CFRelease(win);
            dump_result?;
        }

        core_foundation_sys::base::CFRelease(app as _);
    }

    writer.flush()?;
    println!("AX full dump written: {}", dump_path.display());
    println!("Tip: cargo run --bin ax-dump -- 80  # deeper max depth");
    Ok(())
}
