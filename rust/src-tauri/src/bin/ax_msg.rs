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

unsafe fn dump_element(el: core_foundation_sys::base::CFTypeRef, indent: &str) {
    let role = ax_attr(el, "AXRole").unwrap_or_default();
    let title = ax_attr(el, "AXTitle").unwrap_or_default();
    let value = ax_attr(el, "AXValue").unwrap_or_default();
    let identifier = ax_attr(el, "AXIdentifier").unwrap_or_default();
    let geo = pos_size_str(el);

    let mut line = format!("{}{}", indent, role);
    if !identifier.is_empty() {
        line.push_str(&format!(" id=\"{}\"", identifier));
    }
    line.push_str(&format!(" {}", geo));
    if !title.is_empty() {
        let t: String = escape_title(&title).chars().take(80).collect();
        line.push_str(&format!(" title=\"{}\"", t));
    }
    if !value.is_empty() {
        let v: String = escape_title(&value).chars().take(80).collect();
        line.push_str(&format!(" value=\"{}\"", v));
    }
    println!("{}", line);
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
        let midpoint_x = match (list_pos, list_size) {
            (Some(p), Some(s)) => p.x + s.width * 0.4,
            _ => 0.0,
        };
        println!(
            "=== chat_message_list {} midpoint_x={:.0} ===\n",
            list_geo, midpoint_x
        );

        let children = ax_children(list);
        let total = children.len();

        // First: show a summary of ALL children types
        println!("Total children: {}", total);
        let mut bubble_count = 0;
        let mut other_types: Vec<(usize, String, String)> = Vec::new();
        for idx in 0..total {
            let child = children[idx];
            let raw_id = ax_attr(child, "AXIdentifier").unwrap_or_default();
            if raw_id == "chat_bubble_item_view" {
                bubble_count += 1;
            } else {
                let raw_role = ax_attr(child, "AXRole").unwrap_or_default();
                other_types.push((idx, raw_role, raw_id));
            }
        }
        println!(
            "  Bubbles: {}, Other elements: {}",
            bubble_count,
            other_types.len()
        );
        for (idx, role, id) in &other_types {
            let geo = pos_size_str(children[*idx]);
            let title = ax_attr(children[*idx], "AXTitle").unwrap_or_default();
            let t_short: String = escape_title(&title).chars().take(40).collect();
            println!(
                "  [{:>2}] {} id=\"{}\" {} title=\"{}\"",
                idx, role, id, geo, t_short
            );
        }
        println!();

        // Second: dump last few bubbles with ALL attributes
        let bubble_indices: Vec<usize> = (0..total)
            .filter(|&i| {
                ax_attr(children[i], "AXIdentifier").as_deref() == Some("chat_bubble_item_view")
            })
            .collect();
        let bstart = if bubble_indices.len() > 6 {
            bubble_indices.len() - 6
        } else {
            0
        };

        println!(
            "=== Last {} bubbles (detailed) ===\n",
            bubble_indices.len() - bstart
        );

        for &bi in &bubble_indices[bstart..] {
            let bubble = children[bi];
            let raw_title = ax_attr(bubble, "AXTitle").unwrap_or_default();
            let geo = pos_size_str(bubble);

            println!("--- Bubble [{}] {} ---", bi, geo);
            println!("  AXTitle(raw): \"{}\"", escape_title(&raw_title));

            let attr_names = ax_all_attr_names(bubble);
            let mut with_val = Vec::new();
            let mut non_string = Vec::new();
            for attr_name in &attr_names {
                if attr_name == "AXTitle"
                    || attr_name == "AXPosition"
                    || attr_name == "AXSize"
                    || attr_name == "AXFrame"
                    || attr_name == "AXChildren"
                    || attr_name == "AXParent"
                    || attr_name == "AXWindow"
                {
                    continue;
                }
                if let Some(val) = ax_attr(bubble, attr_name) {
                    if !val.is_empty() {
                        let v: String = escape_title(&val).chars().take(100).collect();
                        with_val.push(format!("{}=\"{}\"", attr_name, v));
                    }
                } else {
                    let tname = ax_attr_type_name(bubble, attr_name);
                    non_string.push(format!("{}({})", attr_name, tname));
                }
            }
            if !with_val.is_empty() {
                println!("  Str: {}", with_val.join(", "));
            }
            if !non_string.is_empty() {
                println!("  Non-str: {}", non_string.join(", "));
            }

            let direct_children = ax_children(bubble);
            println!("  Children: {}", direct_children.len());
            for dc in &direct_children {
                print!("    ");
                dump_element(*dc, "");
                core_foundation_sys::base::CFRelease(*dc);
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
