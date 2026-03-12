/// AX Research Tool: 研究私聊/群聊区分 和 自己/他人发送
///
/// 一次运行收集所有实验数据：
/// 1. 聊天标题区域全属性（current_chat_name_label / big_title_line_h_view）
/// 2. 聊天标题栏附近的所有兄弟元素（寻找成员数等）
/// 3. 会话列表预览对比（sender_prefix 分析）
/// 4. 消息气泡几何详情
/// 5. 消息列表中非气泡子元素（时间提示、系统消息等）
use anyhow::{Context, Result};
use core_foundation::array::CFArray;
use core_foundation::base::{CFType, TCFType};
use core_foundation::string::CFString;
use std::ffi::c_void;

const WECHAT_BUNDLE_ID: &str = "com.tencent.xinWeChat";

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

unsafe fn ax_parent(
    el: core_foundation_sys::base::CFTypeRef,
) -> Option<core_foundation_sys::base::CFTypeRef> {
    let ax = el as accessibility_sys::AXUIElementRef;
    let name = CFString::new("AXParent");
    let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
    let err =
        accessibility_sys::AXUIElementCopyAttributeValue(ax, name.as_concrete_TypeRef(), &mut val);
    if err != 0 || val.is_null() {
        return None;
    }
    Some(val)
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

unsafe fn ax_pos(el: core_foundation_sys::base::CFTypeRef) -> Option<CGPoint> {
    let ax = el as accessibility_sys::AXUIElementRef;
    let name = CFString::new("AXPosition");
    let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
    let err =
        accessibility_sys::AXUIElementCopyAttributeValue(ax, name.as_concrete_TypeRef(), &mut val);
    if err != 0 || val.is_null() {
        return None;
    }
    let mut pt: CGPoint = std::mem::zeroed();
    let ok = AXValueGetValue(val, 1, &mut pt as *mut _ as *mut c_void);
    core_foundation_sys::base::CFRelease(val);
    if ok {
        Some(pt)
    } else {
        None
    }
}

unsafe fn ax_size(el: core_foundation_sys::base::CFTypeRef) -> Option<CGSize> {
    let ax = el as accessibility_sys::AXUIElementRef;
    let name = CFString::new("AXSize");
    let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
    let err =
        accessibility_sys::AXUIElementCopyAttributeValue(ax, name.as_concrete_TypeRef(), &mut val);
    if err != 0 || val.is_null() {
        return None;
    }
    let mut sz: CGSize = std::mem::zeroed();
    let ok = AXValueGetValue(val, 2, &mut sz as *mut _ as *mut c_void);
    core_foundation_sys::base::CFRelease(val);
    if ok {
        Some(sz)
    } else {
        None
    }
}

fn pos_size_str(el: core_foundation_sys::base::CFTypeRef) -> String {
    unsafe {
        let p = ax_pos(el);
        let s = ax_size(el);
        match (p, s) {
            (Some(p), Some(s)) => {
                format!(
                    "pos=({:.0},{:.0}) size=({:.0}x{:.0})",
                    p.x, p.y, s.width, s.height
                )
            }
            (Some(p), None) => format!("pos=({:.0},{:.0}) size=?", p.x, p.y),
            _ => "pos=? size=?".to_string(),
        }
    }
}

fn escape(raw: &str) -> String {
    raw.replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
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

/// Dump all attributes of an element
unsafe fn dump_all_attrs(el: core_foundation_sys::base::CFTypeRef, prefix: &str) {
    let mut attrs = ax_attr_names(el);
    attrs.sort();
    for attr in &attrs {
        match attr.as_str() {
            "AXChildren" | "AXParent" | "AXWindow" | "AXTopLevelUIElement" => continue,
            _ => {}
        }
        let ax = el as accessibility_sys::AXUIElementRef;
        let name = CFString::new(attr);
        let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
        let err = accessibility_sys::AXUIElementCopyAttributeValue(
            ax,
            name.as_concrete_TypeRef(),
            &mut val,
        );
        if err != 0 || val.is_null() {
            println!("{}  {} => (err={})", prefix, attr, err);
            continue;
        }
        let tname = cf_type_name(val);
        let desc = escape(&cf_description(val));
        let short: String = desc.chars().take(120).collect();
        println!("{}  {} => {} | {}", prefix, attr, tname, short);
        core_foundation_sys::base::CFRelease(val);
    }
}

/// Dump element with role, id, title, value (compact one-line)
unsafe fn dump_element_oneline(el: core_foundation_sys::base::CFTypeRef, prefix: &str) {
    let role = ax_attr(el, "AXRole").unwrap_or_default();
    let identifier = ax_attr(el, "AXIdentifier").unwrap_or_default();
    let title = ax_attr(el, "AXTitle").unwrap_or_default();
    let value = ax_attr(el, "AXValue").unwrap_or_default();
    let geo = pos_size_str(el);

    let mut line = format!("{}{}", prefix, role);
    if !identifier.is_empty() {
        line.push_str(&format!(" id=\"{}\"", identifier));
    }
    line.push_str(&format!(" {}", geo));
    if !title.is_empty() {
        let t: String = escape(&title).chars().take(60).collect();
        line.push_str(&format!(" title=\"{}\"", t));
    }
    if !value.is_empty() {
        let v: String = escape(&value).chars().take(60).collect();
        line.push_str(&format!(" value=\"{}\"", v));
    }
    println!("{}", line);
}

/// Dump element tree up to max_depth
unsafe fn dump_tree(el: core_foundation_sys::base::CFTypeRef, depth: usize, max_depth: usize) {
    if depth > max_depth {
        return;
    }
    let indent = "  ".repeat(depth);
    dump_element_oneline(el, &indent);
    let children = ax_children(el);
    for c in &children {
        dump_tree(*c, depth + 1, max_depth);
        core_foundation_sys::base::CFRelease(*c);
    }
}

fn main() -> Result<()> {
    let pid = get_wechat_pid().context("WeChat not found")?;
    println!("=== AX Research Tool ===");
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

        // Find the main window (containing chat_message_list)
        let mut main_win: Option<core_foundation_sys::base::CFTypeRef> = None;
        for i in 0..windows.len() {
            let win = windows.get(i).unwrap();
            if find_by_id(win.as_CFTypeRef(), "chat_message_list", 0).is_some() {
                main_win = Some(win.as_CFTypeRef());
                break;
            }
        }
        let win = match main_win {
            Some(w) => w,
            None => {
                println!("chat_message_list not found, using first window");
                windows.get(0).unwrap().as_CFTypeRef()
            }
        };

        // ========== 实验 1 & 2: 聊天标题区域分析 ==========
        println!("╔══════════════════════════════════════════════════╗");
        println!("║  实验 1 & 2: 聊天标题区域全属性分析              ║");
        println!("╚══════════════════════════════════════════════════╝\n");

        // current_chat_name_label
        if let Some(label) = find_by_id(win, "current_chat_name_label", 0) {
            println!(">>> current_chat_name_label 找到！");
            println!("    所有属性:");
            dump_all_attrs(label, "    ");

            // 看它的父节点和兄弟节点
            if let Some(parent) = ax_parent(label) {
                println!("\n    父节点:");
                dump_element_oneline(parent, "    ");
                println!("    父节点的所有子元素:");
                let siblings = ax_children(parent);
                for (i, sib) in siblings.iter().enumerate() {
                    let is_me = ax_attr(*sib, "AXIdentifier")
                        .map(|id| id == "current_chat_name_label")
                        .unwrap_or(false);
                    let marker = if is_me { " <<<" } else { "" };
                    print!("      [{}]{} ", i, marker);
                    dump_element_oneline(*sib, "");
                    core_foundation_sys::base::CFRelease(*sib);
                }
                core_foundation_sys::base::CFRelease(parent);
            }
            core_foundation_sys::base::CFRelease(label);
        } else {
            println!(">>> current_chat_name_label 未找到");
        }

        println!();

        // big_title_line_h_view
        if let Some(label) = find_by_id(win, "big_title_line_h_view", 0) {
            println!(">>> big_title_line_h_view 找到！");
            println!("    所有属性:");
            dump_all_attrs(label, "    ");

            // 看子元素
            let children = ax_children(label);
            if !children.is_empty() {
                println!("    子元素 ({}):", children.len());
                for (i, child) in children.iter().enumerate() {
                    print!("      [{}] ", i);
                    dump_element_oneline(*child, "");
                    // 也 dump 子元素的所有属性
                    dump_all_attrs(*child, "        ");
                    core_foundation_sys::base::CFRelease(*child);
                }
            }

            // 看父节点的兄弟节点（聊天标题栏区域）
            if let Some(parent) = ax_parent(label) {
                println!("\n    父节点:");
                dump_element_oneline(parent, "    ");
                let siblings = ax_children(parent);
                println!("    父节点的所有子元素 ({}):", siblings.len());
                for (i, sib) in siblings.iter().enumerate() {
                    let is_me = ax_attr(*sib, "AXIdentifier")
                        .map(|id| id == "big_title_line_h_view")
                        .unwrap_or(false);
                    let marker = if is_me { " <<<" } else { "" };
                    print!("      [{}]{} ", i, marker);
                    dump_element_oneline(*sib, "");
                    core_foundation_sys::base::CFRelease(*sib);
                }

                // 再看父父节点（更广的标题栏区域）
                if let Some(grandparent) = ax_parent(parent) {
                    println!("\n    祖父节点:");
                    dump_element_oneline(grandparent, "    ");
                    let uncle_siblings = ax_children(grandparent);
                    println!("    祖父节点的所有子元素 ({}):", uncle_siblings.len());
                    for (i, sib) in uncle_siblings.iter().enumerate() {
                        print!("      [{}] ", i);
                        dump_element_oneline(*sib, "");
                        // dump 2层深度
                        let sub_children = ax_children(*sib);
                        for (j, sub) in sub_children.iter().enumerate() {
                            print!("        [{}] ", j);
                            dump_element_oneline(*sub, "");
                            core_foundation_sys::base::CFRelease(*sub);
                        }
                        core_foundation_sys::base::CFRelease(*sib);
                    }
                    core_foundation_sys::base::CFRelease(grandparent);
                }

                core_foundation_sys::base::CFRelease(parent);
            }
            core_foundation_sys::base::CFRelease(label);
        } else {
            println!(">>> big_title_line_h_view 未找到");
        }

        // ========== 实验 3: 会话列表预览分析 ==========
        println!("\n╔══════════════════════════════════════════════════╗");
        println!("║  实验 3: 会话列表 session_list 预览分析           ║");
        println!("╚══════════════════════════════════════════════════╝\n");

        if let Some(list) = find_by_id(win, "session_list", 0) {
            let children = ax_children(list);
            println!("会话总数: {}\n", children.len());
            println!(
                "{:<4} {:<20} {:<8} {:<14} {}",
                "#", "chat_name", "prefix?", "sender_hint", "raw_preview(escaped)"
            );
            println!("{}", "-".repeat(100));

            for (i, child) in children.iter().enumerate() {
                let id = ax_attr(*child, "AXIdentifier").unwrap_or_default();
                if !id.starts_with("session_item_") {
                    core_foundation_sys::base::CFRelease(*child);
                    continue;
                }

                let chat_name = id.strip_prefix("session_item_").unwrap_or("").to_string();
                let raw_title = ax_attr(*child, "AXTitle").unwrap_or_default();
                let raw_value = ax_attr(*child, "AXValue").unwrap_or_default();
                let raw_preview = if !raw_title.is_empty() {
                    raw_title
                } else if !raw_value.is_empty() {
                    raw_value
                } else {
                    chat_name.clone()
                };

                // Parse sender prefix
                let (sender_hint, _body) = parse_preview_sender(&raw_preview);
                let has_prefix = sender_hint.is_some();
                let sender_str = sender_hint.unwrap_or_else(|| "-".to_string());
                let preview_escaped: String = escape(&raw_preview).chars().take(80).collect();

                println!(
                    "{:<4} {:<20} {:<8} {:<14} {}",
                    i,
                    truncate_str(&chat_name, 18),
                    if has_prefix { "YES" } else { "no" },
                    truncate_str(&sender_str, 12),
                    preview_escaped
                );

                // Also dump all AX attributes for the session item
                let all_attrs = ax_attr_names(*child);
                let mut extra_attrs = Vec::new();
                for attr_name in &all_attrs {
                    match attr_name.as_str() {
                        "AXTitle"
                        | "AXValue"
                        | "AXIdentifier"
                        | "AXPosition"
                        | "AXSize"
                        | "AXFrame"
                        | "AXChildren"
                        | "AXParent"
                        | "AXWindow"
                        | "AXTopLevelUIElement"
                        | "AXRole"
                        | "AXSubrole"
                        | "AXRoleDescription" => continue,
                        _ => {
                            if let Some(v) = ax_attr(*child, attr_name) {
                                if !v.is_empty() {
                                    extra_attrs.push(format!(
                                        "{}=\"{}\"",
                                        attr_name,
                                        truncate_str(&v, 30)
                                    ));
                                }
                            }
                        }
                    }
                }
                if !extra_attrs.is_empty() {
                    println!("     extra: {}", extra_attrs.join(", "));
                }

                core_foundation_sys::base::CFRelease(*child);
            }
            core_foundation_sys::base::CFRelease(list);
        } else {
            println!("session_list 未找到");
        }

        // ========== 实验 4: 消息气泡详情 ==========
        println!("\n╔══════════════════════════════════════════════════╗");
        println!("║  实验 4: 消息气泡几何 & 非气泡元素分析            ║");
        println!("╚══════════════════════════════════════════════════╝\n");

        if let Some(list) = find_by_id(win, "chat_message_list", 0) {
            let list_geo = pos_size_str(list);
            let list_pos = ax_pos(list);
            let list_size = ax_size(list);
            let midpoint_x = match (list_pos, list_size) {
                (Some(p), Some(s)) => p.x + s.width * 0.5,
                _ => 0.0,
            };
            println!(
                "chat_message_list {} midpoint_x={:.0}\n",
                list_geo, midpoint_x
            );

            let children = ax_children(list);
            let total = children.len();

            // 非气泡元素
            println!("--- 非气泡子元素 (时间提示、系统消息等) ---");
            let mut non_bubble_count = 0;
            for (idx, child) in children.iter().enumerate() {
                let raw_id = ax_attr(*child, "AXIdentifier").unwrap_or_default();
                if raw_id != "chat_bubble_item_view" {
                    let role = ax_attr(*child, "AXRole").unwrap_or_default();
                    let title = ax_attr(*child, "AXTitle").unwrap_or_default();
                    let value = ax_attr(*child, "AXValue").unwrap_or_default();
                    let geo = pos_size_str(*child);
                    println!(
                        "  [{}] {} id=\"{}\" {} title=\"{}\" value=\"{}\"",
                        idx,
                        role,
                        raw_id,
                        geo,
                        truncate_str(&escape(&title), 40),
                        truncate_str(&escape(&value), 40)
                    );
                    // dump all attrs for non-bubble elements
                    dump_all_attrs(*child, "    ");
                    non_bubble_count += 1;
                }
            }
            if non_bubble_count == 0 {
                println!("  (无)");
            }

            // 气泡元素详情
            println!("\n--- 消息气泡详情 (最后 10 条) ---");
            let bubble_indices: Vec<usize> = (0..total)
                .filter(|&i| {
                    ax_attr(children[i], "AXIdentifier").as_deref() == Some("chat_bubble_item_view")
                })
                .collect();
            let start = bubble_indices.len().saturating_sub(10);

            println!(
                "总气泡数: {}, 显示最后 {} 条\n",
                bubble_indices.len(),
                bubble_indices.len() - start
            );

            for &bi in &bubble_indices[start..] {
                let bubble = children[bi];
                let raw_title = ax_attr(bubble, "AXTitle").unwrap_or_default();
                let geo = pos_size_str(bubble);

                let content: String = escape(&raw_title).chars().take(50).collect();
                println!("  [{}] {} => \"{}\"", bi, geo, content);

                // 也输出该气泡的所有属性
                let all_attrs = ax_attr_names(bubble);
                let mut extra = Vec::new();
                for attr_name in &all_attrs {
                    match attr_name.as_str() {
                        "AXTitle"
                        | "AXPosition"
                        | "AXSize"
                        | "AXFrame"
                        | "AXChildren"
                        | "AXParent"
                        | "AXWindow"
                        | "AXTopLevelUIElement" => continue,
                        _ => {
                            if let Some(v) = ax_attr(bubble, attr_name) {
                                if !v.is_empty() {
                                    extra.push(format!(
                                        "{}=\"{}\"",
                                        attr_name,
                                        truncate_str(&v, 40)
                                    ));
                                }
                            }
                        }
                    }
                }
                if !extra.is_empty() {
                    println!("       attrs: {}", extra.join(", "));
                }

                // 子元素
                let sub_children = ax_children(bubble);
                if !sub_children.is_empty() {
                    println!("       children({}):", sub_children.len());
                    for (j, sc) in sub_children.iter().enumerate() {
                        print!("         [{}] ", j);
                        dump_element_oneline(*sc, "");
                        core_foundation_sys::base::CFRelease(*sc);
                    }
                }
            }

            // ========== 实验 1 补充: 聊天区域右上角按钮 ==========
            println!("\n--- 聊天区域右上角按钮区域 ---");
            // 从 chat_message_list 往上找按钮区域
            if let Some(parent) = ax_parent(list) {
                if let Some(grandparent) = ax_parent(parent) {
                    println!("chat_message_list 的祖父节点的子树 (depth=3):");
                    dump_tree(grandparent, 0, 3);
                    core_foundation_sys::base::CFRelease(grandparent);
                }
                core_foundation_sys::base::CFRelease(parent);
            }

            for c in &children {
                core_foundation_sys::base::CFRelease(*c);
            }
            core_foundation_sys::base::CFRelease(list);
        } else {
            println!("chat_message_list 未找到");
        }

        core_foundation_sys::base::CFRelease(app as _);
    }

    println!("\n=== 研究完成 ===");
    println!("提示: 请切换到不同的私聊/群聊后再次运行，对比差异");
    Ok(())
}

/// Simple sender prefix parser (matches ax_reader logic)
fn parse_preview_sender(raw_preview: &str) -> (Option<String>, Option<String>) {
    let lines: Vec<&str> = raw_preview
        .lines()
        .map(|line| line.trim())
        .filter(|line| !line.is_empty())
        .collect();
    if lines.len() <= 1 {
        return (None, None);
    }

    let time_re =
        regex::Regex::new(r"^(?:昨天|今天|星期[一二三四五六日天])?\s*\d{1,2}:\d{2}$").unwrap();
    let unread_prefix_re = regex::Regex::new(r"^\[\d+条\]\s*").unwrap();
    let sender_re = regex::Regex::new(r"^\s*([^:：]{1,40})[:：]\s*(.+?)\s*$").unwrap();

    for raw_line in lines.iter().skip(1) {
        let t = raw_line.trim();
        if t.is_empty() || t == "已置顶" || t == "消息免打扰" || time_re.is_match(t) {
            continue;
        }

        let candidate = unread_prefix_re.replace(raw_line, "").trim().to_string();
        if candidate.is_empty() {
            continue;
        }
        if candidate.contains("://") {
            return (None, Some(candidate));
        }
        if let Some(caps) = sender_re.captures(&candidate) {
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

fn truncate_str(s: &str, max_chars: usize) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() <= max_chars {
        s.to_string()
    } else {
        chars[..max_chars].iter().collect::<String>() + ".."
    }
}
