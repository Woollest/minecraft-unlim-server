import { useCallback, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";

type Status = { minecraft:{state:string;health:string;restart:string}; players:string; tps:string; unlim:Record<string,unknown>; backup:{name:string|null;size:number;timestamp:number|null}; disk:{free:number;total:number} };
const fmt=(n=0)=>{const u=["B","KB","MB","GB","TB"];let i=0;while(n>=1024&&i<4){n/=1024;i++}return `${n.toFixed(i>1?1:0)} ${u[i]}`};
const clean=(s="")=>s.replace(/§./g,"").replace(/\u001b\[[0-9;]*m/g,"");

function App(){
  const [status,setStatus]=useState<Status|null>(null),[busy,setBusy]=useState<string|null>(null),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const [drawer,setDrawer]=useState<{title:string;content:string}|null>(null);
  const refresh=useCallback(async(quiet=false)=>{if(!quiet)setBusy("status");try{setStatus(await invoke("run_action",{action:"status"}));setError("")}catch(e){setError(String(e))}finally{if(!quiet)setBusy(null)}},[]);
  useEffect(()=>{refresh();const id=setInterval(()=>refresh(true),15000);return()=>clearInterval(id)},[refresh]);
  const act=async(action:string)=>{setBusy(action);setError("");setNotice("");try{const r=await invoke<Record<string,unknown>>("run_action",{action});if(action==="logs")setDrawer({title:"最新ログ",content:String(r.logs??"")});if(action==="players")setDrawer({title:"参加者",content:String(r.players??"")});if(action==="unlim-share")setDrawer({title:"Unlim 招待情報",content:JSON.stringify(r.share??{},null,2)});setNotice(String(r.message??"完了しました。"));await refresh(true)}catch(e){setError(String(e))}finally{setBusy(null)}};
  const running=status?.minecraft.state==="running",healthy=running&&status?.minecraft.health==="healthy",mode=String(status?.unlim?.mode??"unknown"),live=mode==="server";
  const count=useMemo(()=>status?.players.match(/There are (\d+) of/)?.[1]??"0",[status]);
  const used=status?Math.round((1-status.disk.free/status.disk.total)*100):0;
  return <div className="app-shell">
    <header><div><p className="eyebrow">WOOLLEST SMP</p><h1>Server Manager</h1><p className="subtitle">ノートPC上のMinecraftとUnlimを安全に管理</p></div><button className="refresh" onClick={()=>refresh()} disabled={!!busy}>↻ 更新</button></header>
    {(error||notice)&&<div className={`toast ${error?"error":"success"}`}>{error||notice}</div>}
    <section className="hero-grid">
      <article className="status-card primary"><div className="status-title"><span className={`dot ${healthy?"online":"offline"}`}/>Minecraft</div><strong>{healthy?"稼働中":running?"起動処理中":"停止中"}</strong><small>{status?`${status.minecraft.state} · health ${status.minecraft.health}`:"接続確認中…"}</small></article>
      <article className="status-card"><div className="status-title"><span className={`dot ${live?"online":"standby"}`}/>Unlim</div><strong>{live?"共有中":mode==="idle"?"待機中":mode}</strong><small>Java版 25565/TCP</small></article>
      <article className="status-card"><div className="status-title"><span className="icon">♟</span>参加者</div><strong>{count} <em>/ 20</em></strong><small>{running?"現在オンライン":"サーバー停止中"}</small></article>
      <article className="status-card"><div className="status-title"><span className="icon">◷</span>最新バックアップ</div><strong>{status?.backup.timestamp?new Date(status.backup.timestamp*1000).toLocaleDateString("ja-JP"):"なし"}</strong><small>{status?.backup.name??"まだ作成されていません"}</small></article>
    </section>
    <section className="panel"><div className="panel-head"><div><h2>サーバー操作</h2><p>保存処理を含む安全な操作だけを実行します</p></div></div><div className="action-grid">
      <button className="action start" disabled={!!busy||running} onClick={()=>act("start")}><span>▶</span><b>起動</b><small>Minecraftを開始</small></button>
      <button className="action stop" disabled={!!busy||!running} onClick={()=>act("stop")}><span>■</span><b>停止</b><small>保存して終了</small></button>
      <button className="action" disabled={!!busy||!running} onClick={()=>act("restart")}><span>↻</span><b>再起動</b><small>保存後に再起動</small></button>
      <button className="action" disabled={!!busy||!running} onClick={()=>act("backup")}><span>◇</span><b>バックアップ</b><small>新しい世代を作成</small></button>
    </div></section>
    <section className="lower-grid">
      <article className="panel unlim-panel"><div className="panel-head"><div><h2>Unlim接続</h2><p>参加者向けP2P接続</p></div><span className={`pill ${live?"live":""}`}>{mode}</span></div><div className="inline-actions"><button disabled={!!busy||!running||live} onClick={()=>act("unlim-start")}>共有を開始</button><button disabled={!!busy||!live} onClick={()=>act("unlim-share")}>招待情報</button><button className="danger-text" disabled={!!busy||!live} onClick={()=>act("unlim-stop")}>共有を停止</button></div></article>
      <article className="panel metrics"><div className="panel-head"><div><h2>状態</h2><p>15秒ごとに自動更新</p></div></div><dl><div><dt>TPS</dt><dd>{clean(status?.tps).match(/20\.0|\d+\.\d+/)?.[0]??"—"}</dd></div><div><dt>ディスク</dt><dd>{used}%</dd></div><div><dt>空き容量</dt><dd>{fmt(status?.disk.free)}</dd></div><div><dt>自動起動</dt><dd>{status?.minecraft.restart==="no"?"OFF":"ON"}</dd></div></dl></article>
    </section>
    <footer><button onClick={()=>act("players")} disabled={!!busy}>参加者を確認</button><button onClick={()=>act("logs")} disabled={!!busy}>ログを表示</button><span>{busy?"処理中…":"wls-server.local に接続"}</span></footer>
    {drawer&&<div className="modal-backdrop" onClick={()=>setDrawer(null)}><div className="modal" onClick={e=>e.stopPropagation()}><div className="modal-head"><h2>{drawer.title}</h2><button onClick={()=>setDrawer(null)}>×</button></div><pre>{drawer.content}</pre><div className="modal-actions"><button onClick={()=>navigator.clipboard.writeText(drawer.content)}>コピー</button><button onClick={()=>setDrawer(null)}>閉じる</button></div></div></div>}
  </div>
}
export default App;
