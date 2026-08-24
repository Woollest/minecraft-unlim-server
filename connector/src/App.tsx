import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import "./App.css";

type Status = { installed: boolean; connected: boolean; detail: string; localAddress: string; unlimVersion?: string; managedUnlim: boolean; appVersion: string };
const emptyStatus: Status = { installed: false, connected: false, detail: "確認中…", localAddress: "127.0.0.1:25565", managedUnlim: false, appVersion: "…" };

function App() {
  const [status, setStatus] = useState<Status>(emptyStatus);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [update, setUpdate] = useState<Update | null>(null);
  const [updateProgress, setUpdateProgress] = useState("");
  async function refresh() { try { setStatus(await invoke<Status>("connector_status")); } catch (error) { setMessage(String(error)); } }
  async function prepareUnlim(showResult = false) {
    setBusy(true); if (showResult) setMessage("Unlimを公式配布元から確認しています…");
    try { const result = await invoke<string>("ensure_unlim"); if (showResult || !status.installed) setMessage(result); await refresh(); }
    catch (error) { setMessage(String(error)); } finally { setBusy(false); }
  }
  async function checkAppUpdate() {
    try { setUpdate(await check()); } catch (error) { setMessage(`更新確認に失敗しました: ${String(error)}`); }
  }
  useEffect(() => {
    prepareUnlim(); checkAppUpdate();
    const statusTimer = window.setInterval(refresh, 2500);
    const updateTimer = window.setInterval(() => { prepareUnlim(); checkAppUpdate(); }, 6 * 60 * 60 * 1000);
    return () => { window.clearInterval(statusTimer); window.clearInterval(updateTimer); };
  }, []);
  async function installAppUpdate() {
    if (!update) return; setBusy(true); setUpdateProgress("更新をダウンロードしています…");
    let downloaded = 0; let total = 0;
    try {
      await update.downloadAndInstall((event) => {
        if (event.event === "Started") total = event.data.contentLength ?? 0;
        if (event.event === "Progress") { downloaded += event.data.chunkLength; setUpdateProgress(total ? `更新中 ${Math.round(downloaded / total * 100)}%` : "更新中…"); }
        if (event.event === "Finished") setUpdateProgress("更新を適用しています…");
      });
      await relaunch();
    } catch (error) { setMessage(`更新に失敗しました: ${String(error)}`); setUpdateProgress(""); setBusy(false); }
  }
  async function connect() {
    setBusy(true); setMessage("接続を開始しています…");
    try { await invoke("connect", { key }); setKey(""); await new Promise((r) => setTimeout(r, 1800)); await refresh(); setMessage("接続処理を開始しました。完了まで数秒お待ちください。"); }
    catch (error) { setMessage(String(error)); } finally { setBusy(false); }
  }
  async function disconnect() {
    setBusy(true); setMessage("切断しています…");
    try { await invoke("disconnect"); await refresh(); setMessage("切断しました。"); }
    catch (error) { setMessage(String(error)); } finally { setBusy(false); }
  }
  async function copyAddress() { await navigator.clipboard.writeText(status.localAddress); setMessage("Minecraftの接続先をコピーしました。"); }
  const footerMessage = status.connected
    ? "接続中です。Minecraftから参加できます。"
    : message || "キーはこのPC内でも保存しません。";
  return <main>
    <header><div className="mark">W</div><div><p className="eyebrow">WOOLLEST SMP</p><h1>かんたん接続</h1></div><span className={`pill ${status.connected ? "online" : ""}`}>{status.detail}</span></header>
    {update && <section className="update"><div><strong>Connector {update.version} を利用できます</strong><span>{updateProgress || "安全な署名付き更新です。"}</span></div><button onClick={installAppUpdate} disabled={busy}>更新する</button></section>}
    <section className="hero"><div className="step">1</div><div className="content"><h2>招待キーを入力</h2><p>管理者から届いたUnlimのキーを貼り付けてください。</p><div className="keyrow"><input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="招待キー" disabled={status.connected || busy} /><button className="primary" onClick={connect} disabled={!status.installed || !key.trim() || status.connected || busy}>接続する</button></div>{!status.installed && <div className="install">Unlimを自動セットアップしています。<button className="link" onClick={() => prepareUnlim(true)} disabled={busy}>再試行</button></div>}</div></section>
    <section className="hero"><div className="step">2</div><div className="content"><h2>Minecraftから参加</h2><p>Java版の「マルチプレイ」で、次のサーバーアドレスを追加します。</p><div className="address"><code>{status.localAddress}</code><button onClick={copyAddress}>コピー</button></div></div></section>
    <footer><div><span>{footerMessage}</span><small>Connector {status.appVersion} ・ Unlim {status.unlimVersion ?? "準備中"}{status.managedUnlim ? "（自動管理）" : ""}</small></div>{status.installed && !status.connected && <button onClick={() => prepareUnlim(true)} disabled={busy}>Unlim更新確認</button>}{status.connected && <button className="danger" onClick={disconnect} disabled={busy}>切断する</button>}<button className="credit" onClick={() => openUrl("https://unlim.cc/")}>Powered by Unlim ↗</button></footer>
  </main>;
}
export default App;
