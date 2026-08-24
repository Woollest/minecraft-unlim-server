use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{env, fs, io::{Read, Write}, path::{Path, PathBuf}, process::{Child, Command, Stdio}, sync::Mutex, time::Duration};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const UNLIM_MAP_URL: &str = "https://api.zpw.jp/unlimmap/";
struct ConnectorState(Mutex<Option<Child>>);

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ConnectorStatus {
    installed: bool, connected: bool, detail: String, local_address: String,
    unlim_version: Option<String>, managed_unlim: bool, app_version: String,
}

#[derive(Deserialize)]
struct DownloadInfo { sha256: String, size: u64 }

#[derive(Deserialize)]
struct UnlimMap {
    version: String,
    downloads: std::collections::HashMap<String, String>,
    hashes: std::collections::HashMap<String, DownloadInfo>,
}

fn managed_dir() -> Result<PathBuf, String> {
    let base = env::var_os("APPDATA").ok_or("AppDataフォルダを取得できません。")?;
    Ok(PathBuf::from(base).join("Woollest SMP Connector").join("unlim"))
}
fn managed_unlim() -> Result<PathBuf, String> { Ok(managed_dir()?.join("unlim.exe")) }

fn candidate_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if let Ok(path) = managed_unlim() { paths.push(path); }
    paths.push(PathBuf::from("unlim.exe"));
    if let Ok(local) = env::var("LOCALAPPDATA") {
        paths.push(PathBuf::from(&local).join("Unlim").join("unlim.exe"));
        paths.push(PathBuf::from(local).join("Unlim").join("bin").join("unlim.exe"));
    }
    if let Ok(roaming) = env::var("APPDATA") { paths.push(PathBuf::from(roaming).join("unlim").join("bin").join("unlim.exe")); }
    paths
}

fn command(path: &Path) -> Command {
    let mut cmd = Command::new(path);
    #[cfg(target_os = "windows")]
    cmd.creation_flags(CREATE_NO_WINDOW);
    cmd
}
fn unlim_version(path: &Path) -> Option<String> {
    let output = command(path).arg("--version").output().ok()?;
    if !output.status.success() { return None; }
    let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
    (!text.is_empty()).then_some(text)
}
fn find_unlim() -> Option<PathBuf> { candidate_paths().into_iter().find(|path| unlim_version(path).is_some()) }
fn run_unlim(args: &[&str]) -> Result<std::process::Output, String> {
    let exe = find_unlim().ok_or("Unlimが見つかりません。自動セットアップを実行してください。")?;
    command(&exe).args(args).output().map_err(|error| format!("Unlimを実行できません: {error}"))
}
fn status_value() -> Option<Value> {
    let output = run_unlim(&["status", "--json"]).ok()?;
    serde_json::from_slice(&output.stdout).ok()
}
fn is_connected() -> bool {
    let mode = status_value().and_then(|v| v.get("mode").and_then(Value::as_str).map(str::to_owned)).unwrap_or_else(|| "idle".into());
    !matches!(mode.as_str(), "idle" | "stopped" | "unknown" | "unavailable")
}
fn platform_key() -> Result<&'static str, String> {
    match env::consts::ARCH { "x86_64" => Ok("windows_amd64"), "aarch64" => Ok("windows_arm64"), other => Err(format!("未対応のCPUです: {other}")) }
}
fn http_client() -> Result<reqwest::blocking::Client, String> {
    reqwest::blocking::Client::builder().user_agent("WoollestSMPConnector/0.2")
        .connect_timeout(Duration::from_secs(15)).timeout(Duration::from_secs(120)).build()
        .map_err(|error| format!("通信準備に失敗しました: {error}"))
}
fn install_unlim() -> Result<String, String> {
    let client = http_client()?;
    let map: UnlimMap = client.get(UNLIM_MAP_URL).send().and_then(reqwest::blocking::Response::error_for_status)
        .map_err(|error| format!("Unlimの更新情報を取得できません: {error}"))?.json()
        .map_err(|error| format!("Unlimの更新情報を解析できません: {error}"))?;
    let platform = platform_key()?;
    let url = map.downloads.get(platform).ok_or("このWindows用のUnlim配布URLがありません。")?;
    let expected = map.hashes.get(platform).ok_or("Unlimの検証情報がありません。")?;
    let directory = managed_dir()?;
    let target = managed_unlim()?;
    let version_file = directory.join("version.txt");
    if target.exists() && fs::read_to_string(&version_file).unwrap_or_default().trim() == map.version && unlim_version(&target).is_some() {
        return Ok(format!("Unlim {} は最新です。", map.version));
    }
    if is_connected() { return Ok("接続中のためUnlim更新は次回起動時に行います。".into()); }
    fs::create_dir_all(&directory).map_err(|error| format!("Unlim保存先を作成できません: {error}"))?;
    let temporary = directory.join("unlim.exe.download");
    let mut response = client.get(url).send().and_then(reqwest::blocking::Response::error_for_status)
        .map_err(|error| format!("Unlimをダウンロードできません: {error}"))?;
    let mut file = fs::File::create(&temporary).map_err(|error| format!("一時ファイルを作成できません: {error}"))?;
    let mut hasher = Sha256::new();
    let mut downloaded = 0u64;
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let count = response.read(&mut buffer).map_err(|error| format!("Unlimの受信に失敗しました: {error}"))?;
        if count == 0 { break; }
        file.write_all(&buffer[..count]).map_err(|error| format!("Unlimを保存できません: {error}"))?;
        hasher.update(&buffer[..count]); downloaded += count as u64;
        if downloaded > expected.size { let _ = fs::remove_file(&temporary); return Err("Unlimのファイルサイズが検証値を超えました。".into()); }
    }
    file.sync_all().map_err(|error| format!("Unlimの保存を確定できません: {error}"))?; drop(file);
    if downloaded != expected.size || !hex::encode(hasher.finalize()).eq_ignore_ascii_case(&expected.sha256) {
        let _ = fs::remove_file(&temporary); return Err("UnlimのSHA-256検証に失敗しました。ファイルは使用しません。".into());
    }
    let backup = directory.join("unlim.exe.previous"); let _ = fs::remove_file(&backup);
    if target.exists() { fs::rename(&target, &backup).map_err(|error| format!("旧Unlimを退避できません: {error}"))?; }
    if let Err(error) = fs::rename(&temporary, &target) {
        if backup.exists() { let _ = fs::rename(&backup, &target); }
        return Err(format!("新しいUnlimへ切り替えられません: {error}"));
    }
    if unlim_version(&target).is_none() {
        let _ = fs::remove_file(&target); if backup.exists() { let _ = fs::rename(&backup, &target); }
        return Err("更新後のUnlimを実行できないため、旧版へ戻しました。".into());
    }
    fs::write(version_file, format!("{}\n", map.version)).map_err(|error| format!("Unlimのバージョンを記録できません: {error}"))?;
    let _ = fs::remove_file(backup);
    Ok(format!("Unlim {} を安全に導入しました。", map.version))
}

#[tauri::command]
fn ensure_unlim() -> Result<String, String> { install_unlim() }

#[tauri::command]
fn connector_status() -> ConnectorStatus {
    let executable = find_unlim(); let installed = executable.is_some();
    let value = installed.then(status_value).flatten();
    let mode = value.as_ref().and_then(|v| v.get("mode")).and_then(Value::as_str).unwrap_or("idle");
    let connected = !matches!(mode, "idle" | "stopped" | "unknown" | "unavailable");
    let managed = managed_unlim().ok();
    ConnectorStatus { installed, connected,
        detail: if !installed { "Unlimを準備中".into() } else if connected { format!("接続中 ({mode})") } else { "未接続".into() },
        local_address: "127.0.0.1:25565".into(), unlim_version: executable.as_deref().and_then(unlim_version),
        managed_unlim: executable.as_ref().zip(managed.as_ref()).is_some_and(|(a,b)| a == b), app_version: env!("CARGO_PKG_VERSION").into() }
}

#[tauri::command]
fn connect(key: String, state: tauri::State<ConnectorState>) -> Result<(), String> {
    let key = key.trim();
    if key.len() < 8 || key.len() > 512 || !key.chars().all(|c| c.is_ascii_alphanumeric() || "-_.:/?=&".contains(c)) { return Err("接続キーの形式を確認してください。".into()); }
    if is_connected() { return Err("すでにUnlimが接続中です。いったん切断してください。".into()); }
    let exe = find_unlim().ok_or("Unlimの準備が完了していません。")?;
    let child = command(&exe).args(["--connect", key, "--no-tui"]).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null())
        .spawn().map_err(|error| format!("接続を開始できません: {error}"))?;
    *state.0.lock().map_err(|_| "内部状態を取得できません。")? = Some(child); Ok(())
}

#[tauri::command]
fn disconnect(state: tauri::State<ConnectorState>) -> Result<(), String> {
    if find_unlim().is_some() { let _ = run_unlim(&["stop"]); let _ = run_unlim(&["quit"]); }
    if let Some(mut child) = state.0.lock().map_err(|_| "内部状態を取得できません。")?.take() { let _ = child.kill(); let _ = child.wait(); }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default().manage(ConnectorState(Mutex::new(None)))
        .plugin(tauri_plugin_opener::init()).plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![connector_status, ensure_unlim, connect, disconnect])
        .run(tauri::generate_context!()).expect("error while running tauri application");
}
