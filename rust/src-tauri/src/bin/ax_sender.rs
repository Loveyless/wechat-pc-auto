//! ax-sender: 探测微信群聊消息 AX 树中的发送者名字。
//!
//! 结论：WeChat macOS 的 AX 树不暴露独立的发送者名字元素。
//! 所有 chat_bubble_item_view 都是扁平 AXStaticText，AXTitle 仅含消息正文。
//! 发送者名字由 Qt 渲染引擎直接绘制在画布上，不创建 Accessibility 节点。
//!
//! 运行：cargo run --bin ax-sender

use anyhow::{Context, Result};
use core_foundation::array::CFArray;
use core_foundation::base::{CFType, TCFType};
use core_foundation::string::CFString;

const WECHAT_BUNDLE_ID: &str = "com.tencent.xinWeChat";

fn get_wechat_pid() -> Result<i32> {
    let output = std::process::Command::new("osascript")
        .args(["-e", &format!(
            "tell application \"System Events\" to get unix id of (first process whose bundle identifier is \"{}\")",
            WECHAT_BUNDLE_ID
        )])
        .output()?;
    if !output.status.success() {
        anyhow::bail!("WeChat not found");
    }
    Ok(String::from_utf8_lossy(&output.stdout)
        .trim()
        .parse::<i32>()?)
}

unsafe fn ax_attr(el: core_foundation_sys::base::CFTypeRef, attr: &str) -> Option<String> {
    let ax = el as accessibility_sys::AXUIElementRef;
    let name = CFString::new(attr);
    let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
    let err =
        accessibility_sys::AXUIElementCopyAttributeValue(ax, name.as_concrete_TypeRef(), &mut val);
    if err != 0 || val.is_null() {
        return None;
    }
    let tid = core_foundation_sys::base::CFGetTypeID(val);
    if tid == core_foundation_sys::string::CFStringGetTypeID() {
        let s: CFString = TCFType::wrap_under_create_rule(val as _);
        Some(s.to_string())
    } else {
        core_foundation_sys::base::CFRelease(val);
        None
    }
}

unsafe fn ax_children(
    el: core_foundation_sys::base::CFTypeRef,
) -> Vec<core_foundation_sys::base::CFTypeRef> {
    let ax = el as accessibility_sys::AXUIElementRef;
    let name = CFString::new("AXChildren");
    let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
    let err =
        accessibility_sys::AXUIElementCopyAttributeValue(ax, name.as_concrete_TypeRef(), &mut val);
    if err != 0 || val.is_null() {
        return vec![];
    }
    let tid = core_foundation_sys::base::CFGetTypeID(val);
    if tid != core_foundation_sys::array::CFArrayGetTypeID() {
        core_foundation_sys::base::CFRelease(val);
        return vec![];
    }
    let arr: CFArray<CFType> = TCFType::wrap_under_create_rule(val as _);
    let mut out = Vec::new();
    for i in 0..arr.len() {
        let c = arr.get(i).unwrap();
        let p = c.as_CFTypeRef();
        core_foundation_sys::base::CFRetain(p);
        out.push(p);
    }
    out
}

unsafe fn find_by_id(
    el: core_foundation_sys::base::CFTypeRef,
    target_id: &str,
    depth: usize,
) -> Option<core_foundation_sys::base::CFTypeRef> {
    if depth > 12 {
        return None;
    }
    if let Some(id) = ax_attr(el, "AXIdentifier") {
        if id == target_id {
            core_foundation_sys::base::CFRetain(el);
            return Some(el);
        }
    }
    let children = ax_children(el);
    for c in &children {
        if let Some(found) = find_by_id(*c, target_id, depth + 1) {
            for c2 in &children {
                core_foundation_sys::base::CFRelease(*c2);
            }
            return Some(found);
        }
    }
    for c in &children {
        core_foundation_sys::base::CFRelease(*c);
    }
    None
}

fn escape(raw: &str) -> String {
    raw.replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

unsafe fn collect_all_texts(
    el: core_foundation_sys::base::CFTypeRef,
    depth: usize,
    path: &[String],
    results: &mut Vec<(String, String, Vec<String>)>,
) {
    if depth > 30 {
        return;
    }

    let role = ax_attr(el, "AXRole").unwrap_or_default();
    let identifier = ax_attr(el, "AXIdentifier").unwrap_or_default();

    let label = if identifier.is_empty() {
        role.clone()
    } else {
        format!("{}({})", role, identifier)
    };
    let mut current_path = path.to_vec();
    current_path.push(label);

    for attr in &["AXValue", "AXTitle", "AXDescription", "AXLabel"] {
        if let Some(val) = ax_attr(el, attr) {
            let clean = val.replace('\u{200b}', "").trim().to_string();
            if !clean.is_empty() {
                results.push((clean, identifier.clone(), current_path.clone()));
            }
        }
    }

    let children = ax_children(el);
    for c in &children {
        collect_all_texts(*c, depth + 1, &current_path, results);
        core_foundation_sys::base::CFRelease(*c);
    }
}

fn main() -> Result<()> {
    let search_term = std::env::args().nth(1);

    let pid = get_wechat_pid().context("WeChat not found")?;
    println!("WeChat PID: {}", pid);
    if let Some(ref term) = search_term {
        println!("搜索关键词: \"{}\"", term);
    }
    println!();

    unsafe {
        let app = accessibility_sys::AXUIElementCreateApplication(pid);
        if app.is_null() {
            anyhow::bail!("cannot create AXUIElement");
        }

        let attr = CFString::new("AXWindows");
        let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
        let err = accessibility_sys::AXUIElementCopyAttributeValue(
            app,
            attr.as_concrete_TypeRef(),
            &mut val,
        );
        if err != 0 {
            anyhow::bail!("AXError={}", err);
        }

        let windows: CFArray<CFType> = TCFType::wrap_under_create_rule(val as _);
        if windows.is_empty() {
            anyhow::bail!("no windows");
        }

        let mut all: Vec<(String, String, Vec<String>)> = Vec::new();
        for i in 0..windows.len() {
            let win = windows.get(i).unwrap();
            collect_all_texts(win.as_CFTypeRef(), 0, &[], &mut all);
        }

        println!("全窗口递归共找到 {} 个文本片段\n", all.len());

        if let Some(ref term) = search_term {
            println!("=== 包含 \"{}\" 的元素 ===\n", term);
            let mut found = 0;
            for (text, id, path) in &all {
                if text.contains(term.as_str()) {
                    found += 1;
                    let t: String = escape(text).chars().take(100).collect();
                    println!("[命中 {}] \"{}\"", found, t);
                    println!("  id=\"{}\"", id);
                    println!("  path: {}\n", path.join(" > "));
                }
            }
            if found == 0 {
                println!("未找到任何包含 \"{}\" 的 AX 元素。", term);
                println!("这证实 WeChat macOS 的 AX 树不暴露独立的发送者名字标签。");
            }
        } else {
            // Show chat_message_list children only
            for i in 0..windows.len() {
                let win = windows.get(i).unwrap();
                if let Some(list) = find_by_id(win.as_CFTypeRef(), "chat_message_list", 0) {
                    let children = ax_children(list);
                    let total = children.len();
                    let visible: Vec<usize> = (0..total)
                        .filter(|&i| {
                            ax_attr(children[i], "AXIdentifier").as_deref() != Some("virtual_cell")
                        })
                        .collect();

                    println!(
                        "chat_message_list: {} 总元素, {} 可见\n",
                        total,
                        visible.len()
                    );
                    for &vi in &visible {
                        let child = children[vi];
                        let id = ax_attr(child, "AXIdentifier").unwrap_or_default();
                        let title = ax_attr(child, "AXTitle").unwrap_or_default();
                        let t: String = escape(&title).chars().take(80).collect();
                        println!("  [{}] id=\"{}\" \"{}\"", vi, id, t);
                    }

                    for c in &children {
                        core_foundation_sys::base::CFRelease(*c);
                    }
                    core_foundation_sys::base::CFRelease(list);
                }
            }
            println!("\n提示: 传入发送者名字作为参数来精确搜索:");
            println!("  cargo run --bin ax-sender -- 前端萌新");
        }

        core_foundation_sys::base::CFRelease(app as _);
    }
    Ok(())
}
