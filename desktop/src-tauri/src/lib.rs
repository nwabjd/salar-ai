use serde_json::{json, Value};
use std::{collections::HashMap, fs, process::Command};
use sysinfo::System;
use url::Url;

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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![execute_device_command])
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
