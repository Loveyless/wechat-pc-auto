use std::{ffi::OsStr, os::windows::ffi::OsStrExt, ptr::null_mut};

use windows_sys::Win32::{
    Foundation::{
        CloseHandle, GetLastError, FILETIME, HANDLE, STILL_ACTIVE, WAIT_ABANDONED, WAIT_FAILED,
        WAIT_OBJECT_0, WAIT_TIMEOUT,
    },
    System::Threading::{
        CreateMutexW, GetExitCodeProcess, GetProcessTimes, OpenProcess, ReleaseMutex,
        WaitForSingleObject, PROCESS_QUERY_LIMITED_INFORMATION,
    },
};

pub struct BackendBootstrapLock {
    handle: HANDLE,
}

impl Drop for BackendBootstrapLock {
    fn drop(&mut self) {
        unsafe {
            let _ = ReleaseMutex(self.handle);
            let _ = CloseHandle(self.handle);
        }
    }
}

pub fn acquire_bootstrap_lock(
    mutex_name: &str,
    timeout_ms: u32,
) -> Result<BackendBootstrapLock, String> {
    let wide_name = to_wide(mutex_name);
    let handle = unsafe { CreateMutexW(null_mut(), 0, wide_name.as_ptr()) };
    if handle.is_null() {
        return Err(format!("CreateMutexW failed: {}", unsafe {
            GetLastError()
        }));
    }

    let wait_status = unsafe { WaitForSingleObject(handle, timeout_ms) };
    match wait_status {
        WAIT_OBJECT_0 | WAIT_ABANDONED => Ok(BackendBootstrapLock { handle }),
        WAIT_TIMEOUT => {
            unsafe {
                let _ = CloseHandle(handle);
            }
            Err(format!(
                "wait backend bootstrap lock timeout after {timeout_ms}ms"
            ))
        }
        WAIT_FAILED => {
            let error_code = unsafe { GetLastError() };
            unsafe {
                let _ = CloseHandle(handle);
            }
            Err(format!("WaitForSingleObject failed: {error_code}"))
        }
        other => {
            unsafe {
                let _ = CloseHandle(handle);
            }
            Err(format!("unexpected mutex wait status: {other}"))
        }
    }
}

pub fn process_is_alive(pid: u32) -> bool {
    let Some(handle) = open_process_for_query(pid) else {
        return false;
    };
    let mut exit_code = 0;
    let ok = unsafe { GetExitCodeProcess(handle, &mut exit_code) } != 0;
    unsafe {
        let _ = CloseHandle(handle);
    }
    ok && exit_code == STILL_ACTIVE as u32
}

pub fn process_start_token(pid: u32) -> Option<String> {
    let Some(handle) = open_process_for_query(pid) else {
        return None;
    };
    let mut creation = FILETIME {
        dwLowDateTime: 0,
        dwHighDateTime: 0,
    };
    let mut exit = FILETIME {
        dwLowDateTime: 0,
        dwHighDateTime: 0,
    };
    let mut kernel = FILETIME {
        dwLowDateTime: 0,
        dwHighDateTime: 0,
    };
    let mut user = FILETIME {
        dwLowDateTime: 0,
        dwHighDateTime: 0,
    };
    let ok =
        unsafe { GetProcessTimes(handle, &mut creation, &mut exit, &mut kernel, &mut user) } != 0;
    unsafe {
        let _ = CloseHandle(handle);
    }
    if !ok {
        return None;
    }
    Some(format!(
        "{:08x}{:08x}",
        creation.dwHighDateTime, creation.dwLowDateTime
    ))
}

fn open_process_for_query(pid: u32) -> Option<HANDLE> {
    if pid == 0 {
        return None;
    }
    let handle = unsafe { OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid) };
    if handle.is_null() {
        return None;
    }
    Some(handle)
}

fn to_wide(value: &str) -> Vec<u16> {
    OsStr::new(value).encode_wide().chain(Some(0)).collect()
}
