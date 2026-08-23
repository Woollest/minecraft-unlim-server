use serde_json::Value;
use std::process::Command;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

const ACTIONS: &[&str] = &["status", "start", "stop", "restart", "backup", "logs", "players", "unlim-start", "unlim-stop", "unlim-share"];

fn call_host(host: &str, action: &str) -> Result<Value, String> {
    let mut command = Command::new("ssh");
    command.args(["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", &format!("woollest@{host}"), "/home/woollest/minecraft/wsm-agent", action]);

    // Windows creates a visible console for command-line child processes by
    // default. Status polling runs every 15 seconds, so always start SSH
    // without a console window to avoid stealing focus from the current app.
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);

    let output = command
        .output()
        .map_err(|error| format!("SSHを起動できません: {error}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_owned();
    if stdout.is_empty() {
        return Err(if stderr.is_empty() { "ノートPCから応答がありません。".into() } else { stderr });
    }
    let value: Value = serde_json::from_str(&stdout).map_err(|_| format!("応答を読み取れませんでした: {stdout}"))?;
    if !output.status.success() || value.get("ok") != Some(&Value::Bool(true)) {
        return Err(value.get("error").and_then(Value::as_str).unwrap_or("操作に失敗しました。").to_string());
    }
    Ok(value.get("data").cloned().unwrap_or(Value::Null))
}

#[tauri::command]
fn run_action(action: String) -> Result<Value, String> {
    if !ACTIONS.contains(&action.as_str()) { return Err("許可されていない操作です。".into()); }
    match call_host("wls-server.local", &action) {
        Ok(value) => Ok(value),
        Err(primary) => call_host("192.168.1.75", &action).map_err(|fallback| format!("接続できませんでした。\n{primary}\n{fallback}")),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![run_action])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
