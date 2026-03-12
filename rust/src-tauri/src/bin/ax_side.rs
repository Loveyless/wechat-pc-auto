/// ax-side: 全面 dump 气泡 AX 属性，研究 is_self 判定依据
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

unsafe fn ax_attr_type_name(el: core_foundation_sys::base::CFTypeRef, attr: &str) -> String {
    let ax = el as accessibility_sys::AXUIElementRef;
    let name = CFString::new(attr);
    let mut val: core_foundation_sys::base::CFTypeRef = std::ptr::null();
    let err =
        accessibility_sys::AXUIElementCopyAttributeValue(ax, name.as_concrete_TypeRef(), &mut val);
    if err != 0 || val.is_null() {
        return format!("(err={})", err);
    }
    let tid = core_foundation_sys::base::CFGetTypeID(val);
    let desc = core_foundation_sys::base::CFCopyTypeIDDescription(tid);
    let result = if !desc.is_null() {
        let s: CFString = TCFType::wrap_under_create_rule(desc as _);
        s.to_string()
    } else {
        format!("typeID={}", tid)
    };
    core_foundation_sys::base::CFRelease(val);
    result
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
    let ok = AXValueGetValue(val, 1, &mut pt as *mut _ as *mut _);
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
    let ok = AXValueGetValue(val, 2, &mut sz as *mut _ as *mut _);
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
            (Some(p), Some(s)) => format!(
                "pos=({:.0},{:.0}) size=({:.0}x{:.0})",
                p.x, p.y, s.width, s.height
            ),
            (Some(p), None) => format!("pos=({:.0},{:.0}) size=?", p.x, p.y),
            _ => "pos=? size=?".to_string(),
        }
    }
}

fn escape_title(raw: &str) -> String {
    raw.replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

unsafe fn ax_all_attr_names(el: core_foundation_sys::base::CFTypeRef) -> Vec<String> {
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
    let mut result = Vec::new();
    for i in 0..arr.len() {
        let item = arr.get(i).unwrap();
        let ptr = item.as_CFTypeRef();
        let str_tid = core_foundation_sys::string::CFStringGetTypeID();
        if core_foundation_sys::base::CFGetTypeID(ptr) == str_tid {
            let s: &CFString = std::mem::transmute(&item);
            result.push(s.to_string());
        }
    }
    result
}

unsafe fn find_by_id(
    el: core_foundation_sys::base::CFTypeRef,
    target: &str,
    depth: usize,
) -> Option<core_foundation_sys::base::CFTypeRef> {
    if depth > 12 {
        return None;
    }
    if let Some(id) = ax_attr(el, "AXIdentifier") {
        if id == target {
            core_foundation_sys::base::CFRetain(el);
            return Some(el);
        }
    }
    let children = ax_children(el);
    for c in &children {
        if let Some(found) = find_by_id(*c, target, depth + 1) {
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

/// 递归 dump 子元素树，打印关键属性
unsafe fn dump_tree(el: core_foundation_sys::base::CFTypeRef, depth: usize, max_depth: usize) {
    let indent = "    ".repeat(depth);
    let role = ax_attr(el, "AXRole").unwrap_or_default();
    let identifier = ax_attr(el, "AXIdentifier").unwrap_or_default();
    let title = ax_attr(el, "AXTitle").unwrap_or_default();
    let value = ax_attr(el, "AXValue").unwrap_or_default();
    let desc = ax_attr(el, "AXDescription").unwrap_or_default();
    let subrole = ax_attr(el, "AXSubrole").unwrap_or_default();
    let role_desc = ax_attr(el, "AXRoleDescription").unwrap_or_default();
    let help = ax_attr(el, "AXHelp").unwrap_or_default();
    let geo = pos_size_str(el);

    let mut line = format!("{}{}", indent, role);
    if !identifier.is_empty() {
        line.push_str(&format!(" id=\"{}\"", identifier));
    }
    if !subrole.is_empty() {
        line.push_str(&format!(" subrole=\"{}\"", subrole));
    }
    line.push_str(&format!(" {}", geo));
    if !title.is_empty() {
        let t: String = escape_title(&title).chars().take(60).collect();
        line.push_str(&format!(" title=\"{}\"", t));
    }
    if !value.is_empty() {
        let v: String = escape_title(&value).chars().take(60).collect();
        line.push_str(&format!(" val=\"{}\"", v));
    }
    if !desc.is_empty() {
        let d: String = escape_title(&desc).chars().take(60).collect();
        line.push_str(&format!(" desc=\"{}\"", d));
    }
    if !role_desc.is_empty() {
        line.push_str(&format!(" roleDesc=\"{}\"", role_desc));
    }
    if !help.is_empty() {
        let h: String = escape_title(&help).chars().take(60).collect();
        line.push_str(&format!(" help=\"{}\"", h));
    }
    println!("{}", line);

    if depth >= max_depth {
        return;
    }
    let children = ax_children(el);
    for c in &children {
        dump_tree(*c, depth + 1, max_depth);
        core_foundation_sys::base::CFRelease(*c);
    }
}

fn main() -> Result<()> {
    let pid = get_wechat_pid().context("WeChat not found")?;
    println!("WeChat PID: {}\n", pid);

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

        let mut list_el: Option<core_foundation_sys::base::CFTypeRef> = None;
        for i in 0..windows.len() {
            let win = windows.get(i).unwrap();
            if let Some(found) = find_by_id(win.as_CFTypeRef(), "chat_message_list", 0) {
                list_el = Some(found);
                break;
            }
        }

        let list = match list_el {
            Some(l) => l,
            None => {
                core_foundation_sys::base::CFRelease(app as _);
                anyhow::bail!("chat_message_list not found");
            }
        };

        let list_geo = pos_size_str(list);
        let list_pos = ax_pos(list);
        let list_size = ax_size(list);
        let (list_x, list_w) = match (list_pos, list_size) {
            (Some(p), Some(s)) => (p.x, s.width),
            _ => {
                core_foundation_sys::base::CFRelease(list);
                core_foundation_sys::base::CFRelease(app as _);
                anyhow::bail!("cannot get list geometry");
            }
        };
        let center_x = list_x + list_w / 2.0;

        println!(
            "=== chat_message_list {} center_x={:.0} ===\n",
            list_geo, center_x
        );

        let children = ax_children(list);
        let total = children.len();

        let bubble_indices: Vec<usize> = (0..total)
            .filter(|&i| {
                ax_attr(children[i], "AXIdentifier").as_deref() == Some("chat_bubble_item_view")
            })
            .collect();

        println!(
            "Total children: {}, Bubbles: {}\n",
            total,
            bubble_indices.len()
        );

        let skip_attrs = [
            "AXTitle",
            "AXPosition",
            "AXSize",
            "AXFrame",
            "AXChildren",
            "AXParent",
            "AXWindow",
            "AXTopLevelUIElement",
        ];
        let highlight_attrs = [
            "AXDescription",
            "AXSubrole",
            "AXValue",
            "AXRoleDescription",
            "AXHelp",
        ];

        for &bi in &bubble_indices {
            let bubble = children[bi];
            let bubble_pos = ax_pos(bubble);
            let bubble_size = ax_size(bubble);

            // 推断方向
            let direction = match (bubble_pos, bubble_size) {
                (Some(p), Some(s)) => {
                    let left_margin = p.x - list_x;
                    let right_margin = (list_x + list_w) - (p.x + s.width);
                    if s.width > list_w * 0.9 {
                        "FULL_WIDTH"
                    } else if left_margin > right_margin * 1.5 {
                        "RIGHT"
                    } else if right_margin > left_margin * 1.5 {
                        "LEFT"
                    } else {
                        "CENTER"
                    }
                }
                _ => "UNKNOWN",
            };

            let raw_title = ax_attr(bubble, "AXTitle").unwrap_or_default();
            let short_title: String = escape_title(&raw_title).chars().take(50).collect();

            println!("══════════════════════════════════════════════════════════");
            println!(
                "Bubble [{}] {} direction={}",
                bi,
                pos_size_str(bubble),
                direction
            );
            println!("  title: \"{}\"", short_title);

            // 全属性 dump
            let attr_names = ax_all_attr_names(bubble);
            println!("  ── Attributes ({}) ──", attr_names.len());
            for attr_name in &attr_names {
                if skip_attrs.contains(&attr_name.as_str()) {
                    continue;
                }
                let star = if highlight_attrs.contains(&attr_name.as_str()) {
                    " ★"
                } else {
                    ""
                };
                if let Some(v) = ax_attr(bubble, attr_name) {
                    if !v.is_empty() {
                        let vs: String = escape_title(&v).chars().take(100).collect();
                        println!("    {}{} = \"{}\"", attr_name, star, vs);
                    } else {
                        println!("    {}{} = (empty)", attr_name, star);
                    }
                } else {
                    let tname = ax_attr_type_name(bubble, attr_name);
                    println!("    {}{} = <{}>", attr_name, star, tname);
                }
            }

            // 递归子元素树（3 层）
            println!("  ── Children tree (3 levels) ──");
            let direct = ax_children(bubble);
            for dc in &direct {
                dump_tree(*dc, 2, 4);
                core_foundation_sys::base::CFRelease(*dc);
            }

            // 左右 hit-test
            if let (Some(p), Some(s)) = (bubble_pos, bubble_size) {
                let mid_y = (p.y + s.height / 2.0) as f32;
                let left_x = (list_x + 20.0) as f32;
                let right_x = (list_x + list_w - 20.0) as f32;

                print!("  ── Hit-test LEFT ({:.0},{:.0}): ", left_x, mid_y);
                let mut hit_el: accessibility_sys::AXUIElementRef = std::ptr::null_mut();
                let hit_err = accessibility_sys::AXUIElementCopyElementAtPosition(
                    app,
                    left_x,
                    mid_y,
                    &mut hit_el,
                );
                if hit_err == 0 && !hit_el.is_null() {
                    let role = ax_attr(hit_el as _, "AXRole").unwrap_or_default();
                    let id = ax_attr(hit_el as _, "AXIdentifier").unwrap_or_default();
                    let t = ax_attr(hit_el as _, "AXTitle").unwrap_or_default();
                    let ts: String = escape_title(&t).chars().take(30).collect();
                    println!("{} id=\"{}\" title=\"{}\"", role, id, ts);
                    core_foundation_sys::base::CFRelease(hit_el as _);
                } else {
                    println!("(nothing, err={})", hit_err);
                }

                print!("  ── Hit-test RIGHT ({:.0},{:.0}): ", right_x, mid_y);
                let mut hit_el2: accessibility_sys::AXUIElementRef = std::ptr::null_mut();
                let hit_err2 = accessibility_sys::AXUIElementCopyElementAtPosition(
                    app,
                    right_x,
                    mid_y,
                    &mut hit_el2,
                );
                if hit_err2 == 0 && !hit_el2.is_null() {
                    let role = ax_attr(hit_el2 as _, "AXRole").unwrap_or_default();
                    let id = ax_attr(hit_el2 as _, "AXIdentifier").unwrap_or_default();
                    let t = ax_attr(hit_el2 as _, "AXTitle").unwrap_or_default();
                    let ts: String = escape_title(&t).chars().take(30).collect();
                    println!("{} id=\"{}\" title=\"{}\"", role, id, ts);
                    core_foundation_sys::base::CFRelease(hit_el2 as _);
                } else {
                    println!("(nothing, err={})", hit_err2);
                }
            }

            println!();
        }

        for c in &children {
            core_foundation_sys::base::CFRelease(*c);
        }
        core_foundation_sys::base::CFRelease(list);
        core_foundation_sys::base::CFRelease(app as _);
    }
    Ok(())
}
