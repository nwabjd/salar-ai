use serde_json::{json, Value};
use std::{collections::HashMap, fs, path::PathBuf, process::Command, time::{SystemTime, UNIX_EPOCH}};
use sysinfo::System;
use tauri::Manager;
use url::Url;

fn data_dir() -> PathBuf {
    let mut path = dirs::data_dir().unwrap_or_else(|| PathBuf::from("."));
    path.push("SALAR");
    let _ = fs::create_dir_all(&path);
    path
}

#[tauri::command]
fn save_token(token: String) -> Result<(), String> {
    let path = data_dir().join("session.token");
    fs::write(&path, &token).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_token() -> Result<String, String> {
    let path = data_dir().join("session.token");
    fs::read_to_string(&path).map_err(|_| "No token found".into())
}

#[tauri::command]
fn clear_token() -> Result<(), String> {
    let path = data_dir().join("session.token");
    let _ = fs::remove_file(&path);
    Ok(())
}

#[tauri::command]
fn execute_device_command(kind: String, payload: Value) -> Result<Value, String> {
    match kind.as_str() {
        "open_url" => {
            let raw = payload.get("url").and_then(Value::as_str).ok_or("Missing URL")?;
            let url = Url::parse(raw).map_err(|_| "Invalid URL")?;
            if !matches!(url.scheme(), "https" | "http") { return Err("Only HTTP(S) links are allowed".into()); }
            open::that(url.as_str()).map_err(|e| e.to_string())?;
            Ok(json!({"opened": url.as_str()}))
        }
        "open_app" => {
            let id = payload.get("app").and_then(Value::as_str).ok_or("Missing app id")?;
            let allowed: HashMap<&str, &str> = HashMap::from([
                ("chrome", "chrome.exe"), ("vscode", "code.cmd"), ("explorer", "explorer.exe"), ("notepad", "notepad.exe")
            ]);
            let executable = allowed.get(id).ok_or("Application is not in the allow-list")?;
            Command::new(executable).spawn().map_err(|e| e.to_string())?;
            Ok(json!({"opened": id}))
        }
        "reveal_path" => {
            let raw = payload.get("path").and_then(Value::as_str).ok_or("Missing path")?;
            let path = fs::canonicalize(raw).map_err(|_| "Path does not exist")?;
            open::that(&path).map_err(|e| e.to_string())?;
            Ok(json!({"revealed": path}))
        }
        "create_directory" => {
            let raw = payload.get("path").and_then(Value::as_str).ok_or("Missing path")?;
            let path = std::path::PathBuf::from(raw);
            if !path.is_absolute() { return Err("An absolute path is required".into()); }
            fs::create_dir_all(&path).map_err(|e| e.to_string())?;
            Ok(json!({"created": path}))
        }
        "system_info" => {
            let mut system = System::new_all(); system.refresh_all();
            Ok(json!({"os": System::name(), "memory_total": system.total_memory(), "memory_used": system.used_memory(), "cpu_count": system.cpus().len()}))
        }
        _ => Err("Command is not allowed".into()),
    }
}

#[tauri::command]
fn live_metrics() -> Result<Value, String> {
    let mut sys = System::new_all();
    sys.refresh_all();

    let cpu_percent = sys.global_cpu_info().cpu_usage();
    let cpu_count = sys.cpus().len();
    let cpu_brand = sys.cpus().first().map(|c| c.brand().to_string()).unwrap_or_default();
    let mem_total = sys.total_memory();
    let mem_used = sys.used_memory();
    let mem_percent = if mem_total > 0 { (mem_used as f64 / mem_total as f64) * 100.0 } else { 0.0 };

    let (disk_total, disk_used) = sys.disks().iter().fold((0u64, 0u64), |(tot, used), d| {
        (tot + d.total_space(), used + (d.total_space() - d.available_space()))
    });
    let disk_percent = if disk_total > 0 { (disk_used as f64 / disk_total as f64) * 100.0 } else { 0.0 };

    let boot = sys.boot_time();
    let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
    let uptime = now.saturating_sub(boot);

    Ok(json!({
        "cpu_percent": cpu_percent,
        "cpu_count": cpu_count,
        "cpu_brand": cpu_brand,
        "memory_total": mem_total,
        "memory_used": mem_used,
        "memory_percent": mem_percent,
        "disk_percent": disk_percent,
        "uptime_seconds": uptime,
        "os": System::name(),
    }))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.clear_all_browsing_data();
                let cleanup_js = r#"
                    (async function(){
                        try {
                            if (localStorage.getItem('_swc') === '1') return;
                            localStorage.setItem('_swc', '1');
                            if (!('serviceWorker' in navigator)) return;
                            var regs = await navigator.serviceWorker.getRegistrations();
                            if (regs.length === 0) return;
                            for (var i = 0; i < regs.length; i++) await regs[i].unregister();
                            var names = await caches.keys();
                            for (var i = 0; i < names.length; i++) await caches.delete(names[i]);
                            var base = location.href.split('?')[0];
                            location.href = base + '?_swc=' + Date.now();
                        } catch(e) { console.error('SW cleanup failed', e); }
                    })();
                "#;
                let _ = window.eval(cleanup_js);
                let win = window.clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_secs(3));
                    let win2 = win.clone();
                    let _ = win.run_on_main_thread(move || {
                        let _ = win2.eval(cleanup_js);
                    });
                });
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![execute_device_command, save_token, load_token, clear_token, live_metrics])
        .run(tauri::generate_context!())
        .expect("error while running SALAR");
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_unknown_commands() { assert!(execute_device_command("shell".into(), json!({})).is_err()); }
    #[test]
    fn rejects_non_http_urls() { assert!(execute_device_command("open_url".into(), json!({"url":"file:///secret"})).is_err()); }
}
