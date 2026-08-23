use serde::Serialize;
use serde_json::Value;
use std::{env, path::PathBuf, process::{Child, Command, Stdio}, sync::Mutex};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
struct ConnectorState(Mutex<Option<Child>>);

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ConnectorStatus { installed: bool, connected: bool, detail: String, local_address: String }

fn candidate_paths() -> Vec<PathBuf> {
    let mut paths = vec![PathBuf::from("unlim.exe")];
    if let Ok(local) = env::var("LOCALAPPDATA") {
        paths.push(PathBuf::from(&local).join("Unlim").join("unlim.exe"));
        paths.push(PathBuf::from(local).join("Unlim").join("bin").join("unlim.exe"));
    }
    if let Ok(roaming) = env::var("APPDATA") {
        paths.push(PathBuf::from(roaming).join("unlim").join("bin").join("unlim.exe"));
    }
    paths
}

fn find_unlim() -> Option<PathBuf> {
    candidate_paths().into_iter().find(|path| {
        let mut cmd = Command::new(path);
        cmd.arg("--version").stdout(Stdio::null()).stderr(Stdio::null());
        #[cfg(target_os = "windows")]
        cmd.creation_flags(CREATE_NO_WINDOW);
        cmd.status().map(|status| status.success()).unwrap_or(false)
    })
}

fn run_unlim(args: &[&str]) -> Result<std::process::Output, String> {
    let exe = find_unlim().ok_or("Unlimが見つかりません。先に公式版をインストールしてください。")?;
    let mut cmd = Command::new(exe);
    cmd.args(args);
    #[cfg(target_os = "windows")]
    cmd.creation_flags(CREATE_NO_WINDOW);
    cmd.output().map_err(|error| format!("Unlimを実行できません: {error}"))
}

fn status_value() -> Option<Value> {
    let output = run_unlim(&["status", "--json"]).ok()?;
    serde_json::from_slice(&output.stdout).ok()
}

#[tauri::command]
fn connector_status() -> ConnectorStatus {
    let installed = find_unlim().is_some();
    let value = if installed { status_value() } else { None };
    let mode = value.as_ref().and_then(|v| v.get("mode")).and_then(Value::as_str).unwrap_or("idle");
    let connected = !matches!(mode, "idle" | "stopped" | "unknown");
    ConnectorStatus {
        installed,
        connected,
        detail: if !installed { "Unlimのインストールが必要です".into() } else if connected { format!("接続中 ({mode})") } else { "未接続".into() },
        local_address: "127.0.0.1:25565".into(),
    }
}

#[tauri::command]
fn connect(key: String, state: tauri::State<ConnectorState>) -> Result<(), String> {
    let key = key.trim();
    if key.len() < 8 || key.len() > 512 || !key.chars().all(|c| c.is_ascii_alphanumeric() || "-_.:/?=&".contains(c)) {
        return Err("接続キーの形式を確認してください。".into());
    }
    if connector_status().connected { return Err("すでにUnlimが接続中です。いったん切断してください。".into()); }
    let exe = find_unlim().ok_or("Unlimが見つかりません。先に公式版をインストールしてください。")?;
    let mut cmd = Command::new(exe);
    cmd.args(["--connect", key, "--no-tui"]).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
    #[cfg(target_os = "windows")]
    cmd.creation_flags(CREATE_NO_WINDOW);
    let child = cmd.spawn().map_err(|error| format!("接続を開始できません: {error}"))?;
    *state.0.lock().map_err(|_| "内部状態を取得できません。")? = Some(child);
    Ok(())
}

#[tauri::command]
fn disconnect(state: tauri::State<ConnectorState>) -> Result<(), String> {
    if find_unlim().is_some() { let _ = run_unlim(&["stop"]); let _ = run_unlim(&["quit"]); }
    if let Some(mut child) = state.0.lock().map_err(|_| "内部状態を取得できません。")?.take() {
        let _ = child.kill(); let _ = child.wait();
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default().manage(ConnectorState(Mutex::new(None)))
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![connector_status, connect, disconnect])
        .run(tauri::generate_context!()).expect("error while running tauri application");
}
