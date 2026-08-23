import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import "./App.css";

type Status = { installed: boolean; connected: boolean; detail: string; localAddress: string };
const emptyStatus: Status = { installed: false, connected: false, detail: "確認中…", localAddress: "127.0.0.1:25565" };

function App() {
  const [status, setStatus] = useState<Status>(emptyStatus);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function refresh() { try { setStatus(await invoke<Status>("connector_status")); } catch (error) { setMessage(String(error)); } }
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 2500); return () => window.clearInterval(timer); }, []);
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
    <section className="hero"><div className="step">1</div><div className="content"><h2>招待キーを入力</h2><p>管理者から届いたUnlimのキーを貼り付けてください。</p><div className="keyrow"><input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="招待キー" disabled={status.connected || busy} /><button className="primary" onClick={connect} disabled={!status.installed || !key.trim() || status.connected || busy}>接続する</button></div>{!status.installed && <div className="install">Unlimがまだありません。<button className="link" onClick={() => openUrl("https://wiki.unlim.cc/getting-started")}>公式ページから導入</button></div>}</div></section>
    <section className="hero"><div className="step">2</div><div className="content"><h2>Minecraftから参加</h2><p>Java版の「マルチプレイ」で、次のサーバーアドレスを追加します。</p><div className="address"><code>{status.localAddress}</code><button onClick={copyAddress}>コピー</button></div></div></section>
    <footer><div>{footerMessage}</div>{status.connected && <button className="danger" onClick={disconnect} disabled={busy}>切断する</button>}<button className="credit" onClick={() => openUrl("https://unlim.cc/")}>Powered by Unlim ↗</button></footer>
  </main>;
}
export default App;
