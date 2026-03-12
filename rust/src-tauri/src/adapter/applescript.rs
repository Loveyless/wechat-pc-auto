use anyhow::{Context, Result};
use core_foundation::base::TCFType;
use core_foundation::string::CFString;
use std::process::Command;

use super::ax_reader::WECHAT_BUNDLE_ID;

extern "C" {
    fn CGWindowListCopyWindowInfo(
        option: u32,
        relative_to_window: u32,
    ) -> core_foundation_sys::array::CFArrayRef;
}

const CG_WINDOW_LIST_ON_SCREEN_ONLY: u32 = 1 << 0;
const CG_WINDOW_LIST_EXCLUDE_DESKTOP: u32 = 1 << 4;
const CG_NULL_WINDOW_ID: u32 = 0;
const WECHAT_PROCESS_NAMES: &[&str] = &["WeChat", "微信", "Weixin"];
const MIN_MAIN_WINDOW_SIZE: f64 = 200.0;

pub fn run_osascript(script: &str) -> Result<String> {
    let output = Command::new("osascript")
        .args(["-e", script])
        .output()
        .context("failed to run osascript")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        anyhow::bail!("osascript failed: {}", stderr);
    }

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

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

fn find_main_wechat_window_cg() -> Option<(f64, f64, f64, f64)> {
    unsafe {
        let options = CG_WINDOW_LIST_ON_SCREEN_ONLY | CG_WINDOW_LIST_EXCLUDE_DESKTOP;
        let window_list = CGWindowListCopyWindowInfo(options, CG_NULL_WINDOW_ID);
        if window_list.is_null() {
            return None;
        }

        let count = core_foundation_sys::array::CFArrayGetCount(window_list);
        let owner_key = CFString::new("kCGWindowOwnerName");
        let layer_key = CFString::new("kCGWindowLayer");
        let bounds_key = CFString::new("kCGWindowBounds");
        let mut best: Option<(f64, f64, f64, f64, f64)> = None;

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
            let layer_ptr = core_foundation_sys::dictionary::CFDictionaryGetValue(
                dict,
                layer_key.as_concrete_TypeRef() as *const std::ffi::c_void,
            );
            if !layer_ptr.is_null() {
                let mut layer: i32 = 0;
                core_foundation_sys::number::CFNumberGetValue(
                    layer_ptr as core_foundation_sys::number::CFNumberRef,
                    core_foundation_sys::number::kCFNumberSInt32Type,
                    &mut layer as *mut i32 as *mut std::ffi::c_void,
                );
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
            let (x, y, w, h) = match (
                cg_dict_get_f64(bounds_dict, "X"),
                cg_dict_get_f64(bounds_dict, "Y"),
                cg_dict_get_f64(bounds_dict, "Width"),
                cg_dict_get_f64(bounds_dict, "Height"),
            ) {
                (Some(x), Some(y), Some(w), Some(h)) => (x, y, w, h),
                _ => continue,
            };
            if w < MIN_MAIN_WINDOW_SIZE || h < MIN_MAIN_WINDOW_SIZE {
                continue;
            }
            let area = w * h;
            if best.as_ref().map_or(true, |b| area > b.4) {
                best = Some((x, y, w, h, area));
            }
        }

        core_foundation_sys::base::CFRelease(window_list as _);
        best.map(|(x, y, w, h, _)| (x, y, w, h))
    }
}

pub fn query_wechat_window() -> Result<Option<(f64, f64, f64, f64)>> {
    let script = format!(
        r#"tell application "System Events"
            set wProc to first process whose bundle identifier is "{bid}"
            if not (visible of wProc) then return "hidden"
            return "visible"
        end tell"#,
        bid = WECHAT_BUNDLE_ID
    );
    let output = run_osascript(&script)?;
    if output.trim() == "hidden" {
        return Ok(None);
    }
    Ok(find_main_wechat_window_cg())
}

pub fn is_wechat_frontmost() -> bool {
    let script = r#"tell application "System Events" to get bundle identifier of first process whose frontmost is true"#;
    match run_osascript(script) {
        Ok(bid) => bid.trim() == WECHAT_BUNDLE_ID,
        Err(_) => false,
    }
}

pub fn get_wechat_window_frame() -> Result<(f64, f64, f64, f64)> {
    find_main_wechat_window_cg().context("未找到微信主窗口（可能未打开或已最小化）")
}
