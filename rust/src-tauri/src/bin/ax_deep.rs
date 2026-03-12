use anyhow::Result;
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
    if depth > 10 {
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

unsafe fn dump_tree(el: core_foundation_sys::base::CFTypeRef, depth: usize, max_depth: usize) {
    if depth > max_depth {
        return;
    }
    let indent = "  ".repeat(depth);
    let role = ax_attr(el, "AXRole").unwrap_or_default();
    let subrole = ax_attr(el, "AXSubrole").unwrap_or_default();
    let title = ax_attr(el, "AXTitle").unwrap_or_default();
    let value = ax_attr(el, "AXValue").unwrap_or_default();
    let identifier = ax_attr(el, "AXIdentifier").unwrap_or_default();
    let desc = ax_attr(el, "AXDescription").unwrap_or_default();

    let mut info = format!("{}{}", indent, role);
    if !subrole.is_empty() {
        info.push_str(&format!(" ({})", subrole));
    }
    if !identifier.is_empty() {
        info.push_str(&format!(" id=\"{}\"", identifier));
    }
    if !title.is_empty() {
        let t: String = title.chars().take(40).collect();
        info.push_str(&format!(" title=\"{}\"", t));
    }
    if !value.is_empty() {
        let v: String = value.chars().take(60).collect();
        info.push_str(&format!(" value=\"{}\"", v));
    }
    if !desc.is_empty() {
        let d: String = desc.chars().take(40).collect();
        info.push_str(&format!(" desc=\"{}\"", d));
    }
    println!("{}", info);

    let children = ax_children(el);
    for c in &children {
        dump_tree(*c, depth + 1, max_depth);
        core_foundation_sys::base::CFRelease(*c);
    }
}

fn main() -> Result<()> {
    let pid = get_wechat_pid()?;
    println!("WeChat PID: {}\n", pid);

    unsafe {
        let app = accessibility_sys::AXUIElementCreateApplication(pid);
        if app.is_null() {
            anyhow::bail!("无法创建 AXUIElement");
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

        let win = windows.get(0).unwrap();

        // Find the main split view
        println!("=== 查找 main_window_main_splitter_view ===");
        if let Some(splitter) = find_by_id(win.as_CFTypeRef(), "main_window_main_splitter_view", 0)
        {
            let children = ax_children(splitter);
            println!("main_splitter children: {}\n", children.len());

            // First child = session list area, second child = chat area
            if children.len() >= 2 {
                // Look at the sub splitter (chat area)
                println!("=== 右侧区域 (child[1]) 深度 6 ===");
                dump_tree(children[1], 0, 6);
            }

            if !children.is_empty() {
                println!("\n=== 左侧会话列表 (child[0]) 深度 4 ===");
                dump_tree(children[0], 0, 4);
            }

            for c in &children {
                core_foundation_sys::base::CFRelease(*c);
            }
            core_foundation_sys::base::CFRelease(splitter);
        } else {
            println!("main_window_main_splitter_view not found, dumping full tree depth 5");
            dump_tree(win.as_CFTypeRef(), 0, 5);
        }

        core_foundation_sys::base::CFRelease(app as _);
    }
    Ok(())
}
