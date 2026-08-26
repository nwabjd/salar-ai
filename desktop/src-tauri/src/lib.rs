use serde_json::{json, Value};
use std::{collections::HashMap, fs, path::PathBuf, process::Command, time::{SystemTime, UNIX_EPOCH}};
use sysinfo::{Disks, System};
use tauri::Manager;
use tauri_plugin_deep_link::DeepLinkExt;
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
async fn open_external(url: String) -> Result<Value, String> {
    let parsed = Url::parse(&url).map_err(|_| "Invalid URL".to_string())?;
    if !matches!(parsed.scheme(), "http" | "https") { return Err("Only HTTP(S) links are allowed".into()); }
    let target = parsed.as_str().to_string();
    let launch_target = target.clone();
    tauri::async_runtime::spawn_blocking(move || open::that(&launch_target).map_err(|e| e.to_string()))
        .await
        .map_err(|e| e.to_string())??;
    Ok(json!({"opened": target}))
}

fn debug_log_deeplink(source: &str, raw: &str) {
    use std::io::Write;
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(data_dir().join("deeplink.log")) {
        let _ = writeln!(f, "[{:?}] {}: {}", SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0), source, raw);
    }
}

fn deliver_auth_fragment(app: &tauri::AppHandle, raw: &str) {
    debug_log_deeplink("deliver", raw);
    let Ok(url) = Url::parse(raw) else { debug_log_deeplink("error", "unparsable url"); return };
    if url.scheme() != "salar" { return; }
    let Some(fragment) = url.fragment() else { debug_log_deeplink("error", "no fragment"); return };
    if fragment.is_empty() { debug_log_deeplink("error", "empty fragment"); return; }
    if let Some(win) = app.get_webview_window("main") {
        let safe = fragment.replace('\\', "\\\\").replace('\'', "\\'");
        let _ = win.eval(&format!("location.hash = '#{safe}'; location.reload();"));
        debug_log_deeplink("ok", "fragment injected");
    } else {
        debug_log_deeplink("error", "no main window");
    }
}

// ---------- Self-installer ----------
//
// The distributed salar-desktop.exe doubles as its own animated installer:
// on first run it shows a branded setup screen while copying itself to
// %LOCALAPPDATA%\Programs\SALAR, registering the salar:// protocol and
// creating shortcuts, then hands off to the installed copy.

fn installed_exe_path() -> Option<PathBuf> {
    dirs::data_local_dir().map(|p| p.join("Programs").join("SALAR").join("salar-desktop.exe"))
}

fn install_marker_path() -> PathBuf {
    data_dir().join(".installed")
}

#[tauri::command]
fn get_launch_mode() -> String {
    // Dev builds never enter setup mode.
    if cfg!(debug_assertions) { return "app".into(); }
    let installed = match installed_exe_path() {
        Some(path) => path,
        None => return "app".into(),
    };
    let current = match std::env::current_exe() {
        Ok(path) => path,
        Err(_) => return "app".into(),
    };
    if current == installed {
        // Running from the install location: normal app.
        "app".into()
    } else if install_marker_path().exists() {
        // A downloaded copy re-run after an existing install = update.
        "update".into()
    } else {
        "setup".into()
    }
}

#[tauri::command]
fn install_copy_files() -> Result<Value, String> {
    let current = std::env::current_exe().map_err(|e| e.to_string())?;
    let target = installed_exe_path().ok_or("Cannot resolve install directory")?;
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    if current != target {
        // A running instance locks its own executable, but renaming it is
        // always allowed — stage the swap so updates work while SALAR is open.
        if target.exists() {
            let backup = target.with_extension("exe.old");
            let _ = fs::remove_file(&backup);
            fs::rename(&target, &backup).map_err(|e| format!("Could not stage update: {e}"))?;
        }
        fs::copy(&current, &target).map_err(|e| format!("Copy failed: {e}"))?;
    }
    Ok(json!({"installed": target}))
}

#[cfg(windows)]
fn register_protocol(installed: &PathBuf) -> Result<(), String> {
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let root = hkcu.create_subkey("Software\\Classes\\salar").map_err(|e| e.to_string())?.0;
    root.set_value("URL Protocol", &"").map_err(|e| e.to_string())?;
    root.set_value("", &"URL:SALAR Protocol").map_err(|e| e.to_string())?;
    let command_key = hkcu.create_subkey("Software\\Classes\\salar\\shell\\open\\command").map_err(|e| e.to_string())?.0;
    command_key.set_value("", &format!("\"{}\" \"%1\"", installed.display())).map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(not(windows))]
fn register_protocol(_installed: &PathBuf) -> Result<(), String> {
    Err("Protocol registration is only supported on Windows".into())
}

#[tauri::command]
fn install_register_protocol() -> Result<Value, String> {
    let target = installed_exe_path().ok_or("Install directory unresolved")?;
    if !target.exists() { return Err("Installed executable not found".into()); }
    register_protocol(&target)?;
    Ok(json!({"protocol": "salar://", "target": target}))
}

#[tauri::command]
fn install_create_shortcuts() -> Result<Value, String> {
    let target = installed_exe_path().ok_or("Install directory unresolved")?;
    let working_dir = target.parent().unwrap_or(&target).display().to_string();
    let mut created = Vec::new();
    let desktop = std::env::var("USERPROFILE").ok().map(|p| PathBuf::from(p).join("Desktop").join("SALAR.lnk"));
    let start_menu = std::env::var("APPDATA").ok().map(|p| PathBuf::from(p).join("Microsoft").join("Windows").join("Start Menu").join("Programs").join("SALAR.lnk"));
    for lnk in [desktop, start_menu].into_iter().flatten() {
        let script = format!(
            "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('{}'); $s.TargetPath = '{}'; $s.WorkingDirectory = '{}'; $s.Save()",
            lnk.display(),
            target.display(),
            working_dir.replace('\'', "''")
        );
        let output = Command::new("powershell")
            .args(["-NoProfile", "-NonInteractive", "-Command", &script])
            .output()
            .map_err(|e| e.to_string())?;
        if !output.status.success() {
            return Err(format!("Shortcut failed at {}: {}", lnk.display(), String::from_utf8_lossy(&output.stderr)));
        }
        created.push(lnk);
    }
    Ok(json!({"created": created}))
}

#[tauri::command]
fn install_finish() -> Result<Value, String> {
    let target = installed_exe_path().ok_or("Install directory unresolved")?;
    if !target.exists() { return Err("Installed executable not found".into()); }
    fs::write(install_marker_path(), b"1").map_err(|e| e.to_string())?;
    Command::new(&target).spawn().map_err(|e| e.to_string())?;
    std::process::exit(0);
}

fn run_local_action(kind: String, payload: Value) -> Result<Value, String> {
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
            let path = if path.is_absolute() { path } else {
                let home = dirs::home_dir().ok_or("Cannot resolve home directory")?;
                home.join(path)
            };
            fs::create_dir_all(&path).map_err(|e| e.to_string())?;
            Ok(json!({"created": path}))
        }
        "write_file" => {
            let raw = payload.get("path").and_then(Value::as_str).ok_or("Missing path")?;
            let content = payload.get("content").and_then(Value::as_str).ok_or("Missing content")?;
            let path = std::path::PathBuf::from(raw);
            let path = if path.is_absolute() { path } else {
                let home = dirs::home_dir().ok_or("Cannot resolve home directory")?;
                home.join(path)
            };
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            let size = content.len();
            fs::write(&path, content).map_err(|e| e.to_string())?;
            Ok(json!({"written": path, "size": size}))
        }
        "list_files" => {
            let raw = payload.get("path").and_then(Value::as_str).ok_or("Missing path")?;
            let path = std::path::PathBuf::from(raw);
            let path = if path.is_absolute() { path } else {
                let home = dirs::home_dir().ok_or("Cannot resolve home directory")?;
                home.join(path)
            };
            if !path.is_dir() { return Err(format!("Not a directory: {}", path.display())); }
            let mut entries = Vec::new();
            for entry in fs::read_dir(&path).map_err(|e| e.to_string())?.take(100) {
                let entry = entry.map_err(|e| e.to_string())?;
                let meta = entry.metadata().map_err(|e| e.to_string())?;
                entries.push(json!({
                    "name": entry.file_name().to_string_lossy(),
                    "type": if meta.is_dir() { "dir" } else { "file" },
                    "size": meta.len(),
                }));
            }
            Ok(json!({"path": path, "entries": entries, "count": entries.len()}))
        }
        "read_file" => {
            let raw = payload.get("path").and_then(Value::as_str).ok_or("Missing path")?;
            let path = std::path::PathBuf::from(raw);
            let path = if path.is_absolute() { path } else {
                let home = dirs::home_dir().ok_or("Cannot resolve home directory")?;
                home.join(path)
            };
            let meta = fs::metadata(&path).map_err(|e| e.to_string())?;
            if meta.len() > 1_000_000 { return Err("File too large (>1MB)".into()); }
            let content = fs::read_to_string(&path).map_err(|e| e.to_string())?;
            let size = meta.len();
            let preview: String = content.chars().take(10000).collect();
            Ok(json!({"path": path, "size": size, "content": preview}))
        }
        "run_command" => {
            let raw = payload.get("command").and_then(Value::as_str).ok_or("Missing command")?;
            if raw.len() > 2000 { return Err("Command too long".into()); }
            #[cfg(target_os = "windows")]
            let mut cmd = {
                let mut c = Command::new("cmd");
                // Translate POSIX-style mkdir flags for cmd.exe
                let sanitized = if raw.to_lowercase().starts_with("mkdir -p ") { raw.replacen(" -p ", " ", 1) } else { raw.to_string() };
                c.arg("/c").arg(sanitized);
                c
            };
            #[cfg(not(target_os = "windows"))]
            let mut cmd = {
                let mut c = Command::new("sh");
                c.arg("-c").arg(raw);
                c
            };
            // Relative paths in commands must land in the user's home, not the app's install dir.
            if let Some(home) = dirs::home_dir() {
                cmd.current_dir(home);
            }
            let output = cmd.output().map_err(|e| e.to_string())?;
            Ok(json!({
                "exit_code": output.status.code(),
                "stdout": String::from_utf8_lossy(&output.stdout).chars().take(5000).collect::<String>(),
                "stderr": String::from_utf8_lossy(&output.stderr).chars().take(2000).collect::<String>(),
            }))
        }
        "set_volume" => {
            let level = payload.get("level").and_then(Value::as_u64).ok_or("Missing level (0-100)")? as u32;
            let level = level.min(100);
            #[cfg(target_os = "windows")]
            {
                // Use Windows Audio API via PowerShell to set volume
                let best_ps = format!(
                    r#"
                    $code = @'
                    using System;
                    using System.Runtime.InteropServices;
                    public class Vol {{
                        [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
                        public static void SetVol(int target) {{
                            // Mute first (vol down 50 times)
                            for(int i=0;i<50;i++){{ keybd_event(0xAE,0,0,UIntPtr.Zero); keybd_event(0xAE,0,2,UIntPtr.Zero); }}
                            // Then vol up to target
                            for(int i=0;i<target/2;i++){{ keybd_event(0xAF,0,0,UIntPtr.Zero); keybd_event(0xAF,0,2,UIntPtr.Zero); }}
                        }}
                    }}
'@
                    Add-Type -TypeDefinition $code
                    [Vol]::SetVol({})
                    "#,
                    level
                );
                Command::new("powershell")
                    .args(["-NoProfile", "-NonInteractive", "-Command", &best_ps])
                    .output()
                    .map_err(|e| e.to_string())?;
            }
            #[cfg(not(target_os = "windows"))]
            {
                // Linux/macOS: use amixer or osascript
                let _ = Command::new("sh")
                    .arg("-c")
                    .arg(format!("amixer -D pulse sset Master {}% 2>/dev/null || osascript -e 'set volume output volume {}'", level, level))
                    .output();
            }
            Ok(json!({"volume_set": level}))
        }
        "system_info" => {
            let mut system = System::new_all(); system.refresh_all();
            Ok(json!({
                "os": System::name(),
                "memory_total": system.total_memory(),
                "memory_used": system.used_memory(),
                "cpu_count": system.cpus().len(),
                "home_dir": dirs::home_dir().map(|p| p.display().to_string()).unwrap_or_default(),
                "desktop_dir": dirs::desktop_dir().map(|p| p.display().to_string()).unwrap_or_default(),
            }))
        }
        _ => Err("Command is not allowed".into()),
    }
}

fn handle_ollama_chat(payload: Value) -> Result<Value, String> {
    // Proxy a chat request to the local Ollama server, executing any tool
    // calls the model makes via the local device handlers. Runs on a blocking
    // thread so the UI never freezes during inference.
    let model = payload.get("model").and_then(Value::as_str).unwrap_or("salar-tuned").to_string();
    let mut messages: Vec<Value> = payload.get("messages").and_then(Value::as_array).cloned().unwrap_or_default();
    if messages.is_empty() { return Err("No messages provided".into()); }
    let tools = payload.get("tools").cloned().unwrap_or(Value::Null);
    // Auto-start Ollama if it isn't running.
    let ollama_up = ureq::get("http://127.0.0.1:11434/api/tags")
        .timeout(std::time::Duration::from_secs(3))
        .call()
        .is_ok();
    if !ollama_up {
        let _ = Command::new("cmd").args(["/c", "start", "/min", "ollama", "serve"]).spawn();
        let mut up = false;
        for _ in 0..20 {
            std::thread::sleep(std::time::Duration::from_millis(1000));
            if ureq::get("http://127.0.0.1:11434/api/tags").timeout(std::time::Duration::from_secs(2)).call().is_ok() { up = true; break; }
        }
        if !up { return Err("Ollama is not installed or failed to start".into()); }
    }
    let mut executed: Vec<Value> = Vec::new();
    let mut content = String::new();
    let mut last_err = String::new();
    let mut raw_snippet = String::new();
    for _round in 0..8 {
        let mut body = json!({"model": model, "messages": messages, "stream": false});
        if !tools.is_null() { body["tools"] = tools.clone(); }
        let resp = match ureq::post("http://127.0.0.1:11434/api/chat")
            .timeout(std::time::Duration::from_secs(600))
            .send_json(&body)
        {
            Ok(r) => r,
            Err(e) => { last_err = format!("Ollama unreachable (is it running?): {e}"); break; }
        };
        if resp.status() != 200 {
            let status = resp.status();
            let txt = resp.into_string().unwrap_or_default();
            let snippet: String = txt.chars().take(400).collect();
            last_err = format!("Ollama HTTP {}: {}", status, snippet);
            break;
        }
        let data: Value = match resp.into_json() { Ok(d) => d, Err(e) => { last_err = format!("Bad Ollama response: {e}"); break; } };
        if let Some(err) = data.get("error") {
            last_err = match err.as_str() {
                Some(s) => s.to_string(),
                None => serde_json::to_string(err).unwrap_or_else(|_| "Unknown Ollama error".into()),
            };
            break;
        }
        let msg = data.get("message").cloned().unwrap_or(json!({}));
        let calls = msg.get("tool_calls").and_then(Value::as_array).cloned().unwrap_or_default();
        if calls.is_empty() {
            content = msg.get("content").and_then(Value::as_str).unwrap_or("").to_string();
            if content.is_empty() {
                raw_snippet = serde_json::to_string(&data).unwrap_or_default().chars().take(800).collect();
            }
            break;
        }
        messages.push(msg);
        for call in calls {
            let fname = call.pointer("/function/name").and_then(Value::as_str).unwrap_or("").to_string();
            let fargs = call.pointer("/function/arguments").cloned().unwrap_or(json!({}));
            let result = run_local_action(fname.clone(), fargs).unwrap_or_else(|e| json!({"error": e}));
            executed.push(json!({"tool": fname, "result": result}));
            messages.push(json!({"role": "tool", "content": serde_json::to_string(&result).unwrap_or_default()}));
        }
    }
    if content.is_empty() && !last_err.is_empty() { return Err(last_err); }
    Ok(json!({"content": content, "executed": executed, "raw": raw_snippet}))
}

#[tauri::command]
async fn execute_device_command(kind: String, payload: Value) -> Result<Value, String> {
    if kind == "ollama_chat" {
        return tauri::async_runtime::spawn_blocking(move || handle_ollama_chat(payload))
            .await
            .map_err(|e| format!("Background task failed: {e}"))?;
    }
    run_local_action(kind, payload)
}

#[tauri::command]
fn live_metrics() -> Result<Value, String> {
    let mut sys = System::new_all();
    sys.refresh_all();

    let cpu_percent = sys.global_cpu_usage();
    let cpu_count = sys.cpus().len();
    let cpu_brand = sys.cpus().first().map(|c| c.brand().to_string()).unwrap_or_default();
    let mem_total = sys.total_memory();
    let mem_used = sys.used_memory();
    let mem_percent = if mem_total > 0 { (mem_used as f64 / mem_total as f64) * 100.0 } else { 0.0 };

    let disks = Disks::new_with_refreshed_list();
    let (disk_total, disk_used) = disks.list().iter().fold((0u64, 0u64), |(tot, used), d| {
        (tot + d.total_space(), used + (d.total_space() - d.available_space()))
    });
    let disk_percent = if disk_total > 0 { (disk_used as f64 / disk_total as f64) * 100.0 } else { 0.0 };

    let boot = System::boot_time();
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
        // Must be the first plugin: a second launch (e.g. the OS routing
        // salar:// here) forwards its argv to this instance and exits itself.
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            for arg in argv {
                if arg.starts_with("salar://") {
                    debug_log_deeplink("single-instance-forward", &arg);
                    deliver_auth_fragment(app, &arg);
                }
            }
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_deep_link::init())
        .setup(|app| {
            let handle = app.handle().clone();
            app.deep_link().on_open_url(move |event| {
                for u in event.urls() {
                    debug_log_deeplink("on_open_url", u.as_str());
                    deliver_auth_fragment(&handle, u.as_str());
                }
            });
            // Cold start: the OS launched SALAR itself via salar:// before the
            // webview existed. Re-check the launch URL once the window is up.
            let handle2 = app.handle().clone();
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_millis(2500));
                if let Ok(Some(urls)) = handle2.deep_link().get_current() {
                    for u in urls {
                        deliver_auth_fragment(&handle2, u.as_str());
                    }
                }
            });
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
        .invoke_handler(tauri::generate_handler![execute_device_command, save_token, load_token, clear_token, live_metrics, open_external, get_launch_mode, install_copy_files, install_register_protocol, install_create_shortcuts, install_finish])
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
