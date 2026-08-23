use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{env, fs, io::Write, path::PathBuf, process::{Command, Stdio}, sync::Mutex};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
static SSH_LOCK: Mutex<()> = Mutex::new(());

const ACTIONS: &[&str] = &["status", "start", "stop", "restart", "auto-on", "auto-off", "backup", "backups", "restore-latest", "monitor", "update", "logs", "players", "unlim-start", "unlim-stop", "unlim-share"];

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct ConnectionConfig { host: String, fallback_host: String, user: String, agent_path: String }

impl Default for ConnectionConfig {
    fn default() -> Self { Self { host: "wls-server.local".into(), fallback_host: "192.168.1.75".into(), user: "woollest".into(), agent_path: "/home/woollest/minecraft/wsm-agent".into() } }
}

fn config_path() -> PathBuf {
    PathBuf::from(env::var("APPDATA").unwrap_or_else(|_| ".".into())).join("Woollest Server Manager").join("connection.json")
}

fn read_config() -> ConnectionConfig {
    fs::read(config_path()).ok().and_then(|data| serde_json::from_slice(&data).ok()).unwrap_or_default()
}

fn valid_simple(value: &str) -> bool { !value.is_empty() && value.len() <= 255 && value.chars().all(|c| c.is_ascii_alphanumeric() || ".-_:/".contains(c)) }

#[tauri::command]
fn get_connection() -> ConnectionConfig { read_config() }

#[tauri::command]
fn save_connection(config: ConnectionConfig) -> Result<(), String> {
    if !valid_simple(&config.host) || (!config.fallback_host.is_empty() && !valid_simple(&config.fallback_host)) || !valid_simple(&config.user) || !valid_simple(&config.agent_path) || !config.agent_path.starts_with('/') {
        return Err("接続設定に使用できない文字が含まれています。".into());
    }
    let path = config_path();
    fs::create_dir_all(path.parent().ok_or("設定フォルダを作成できません。")?).map_err(|e| e.to_string())?;
    fs::write(path, serde_json::to_vec_pretty(&config).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}

fn call_host(config: &ConnectionConfig, host: &str, action: &str, input: &str) -> Result<Value, String> {
    let mut command = Command::new("ssh");
    command.args(["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", &format!("{}@{host}", config.user), &config.agent_path, action]);

    // Windows creates a visible console for command-line child processes by
    // default. Status polling runs every 15 seconds, so always start SSH
    // without a console window to avoid stealing focus from the current app.
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);

    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = command.spawn().map_err(|error| format!("SSHを起動できません: {error}"))?;
    if !input.is_empty() {
        child.stdin.as_mut().ok_or("SSHの標準入力を開けません。")?.write_all(input.as_bytes()).map_err(|e| e.to_string())?;
    }
    drop(child.stdin.take());
    let output = child.wait_with_output().map_err(|error| format!("SSHの応答を待機できません: {error}"))?;
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
    let _guard = SSH_LOCK.lock().map_err(|_| "SSH操作の排他制御に失敗しました。")?;
    let config = read_config();
    match call_host(&config, &config.host, &action, "") {
        Ok(value) => Ok(value),
        Err(primary) if !config.fallback_host.is_empty() => call_host(&config, &config.fallback_host, &action, "").map_err(|fallback| format!("接続できませんでした。\n{primary}\n{fallback}")),
        Err(primary) => Err(format!("接続できませんでした。\n{primary}")),
    }
}

#[tauri::command]
fn save_discord_webhook(webhook: String) -> Result<Value, String> {
    if webhook.len() > 512 || (!webhook.is_empty() && !webhook.starts_with("https://discord.com/api/webhooks/")) {
        return Err("Discord Webhook URLを確認してください。".into());
    }
    let _guard = SSH_LOCK.lock().map_err(|_| "SSH操作の排他制御に失敗しました。")?;
    let config = read_config();
    match call_host(&config, &config.host, "discord-set", &webhook) {
        Ok(value) => Ok(value),
        Err(primary) if !config.fallback_host.is_empty() => call_host(&config, &config.fallback_host, "discord-set", &webhook).map_err(|fallback| format!("接続できませんでした。\n{primary}\n{fallback}")),
        Err(primary) => Err(primary),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![run_action, get_connection, save_connection, save_discord_webhook])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
