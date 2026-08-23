#!/usr/bin/env python3
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

HOME = pathlib.Path.home()
MC_DIR = HOME / "minecraft"
UNLIM = HOME / ".local/bin/unlim"
ANSI = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def run(args, timeout=90, check=False):
    result = subprocess.run(
        [str(x) for x in args],
        cwd=MC_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = ANSI.sub("", result.stdout + result.stderr).replace(">....", "").strip()
    if check and result.returncode:
        raise RuntimeError(output or f"command failed: {result.returncode}")
    return result.returncode, output


def docker_state():
    code, output = run([
        "docker", "inspect", "-f",
        "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.HostConfig.RestartPolicy.Name}}",
        "minecraft",
    ])
    if code:
        return "missing", "none", "none"
    return tuple(output.split("|", 2))


def rcon(command):
    return run(["docker", "exec", "minecraft", "rcon-cli", command], timeout=20)[1]


def unlim_json(command):
    code, output = run([UNLIM, *command, "--json"], timeout=20)
    if code:
        return {"mode": "unavailable", "error": output}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"mode": "unknown", "raw": output}


def unlim_post(path, body):
    endpoint = json.loads((HOME / ".unlimited/api_endpoint").read_text(encoding="utf-8"))
    token = (HOME / ".unlimited/api_token").read_text(encoding="utf-8").strip()
    url = f"http://127.0.0.1:{endpoint['port']}{path}"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(error.read().decode("utf-8", errors="replace")) from error


def status():
    state, health, restart = docker_state()
    players = rcon("list") if state == "running" else "Server stopped"
    tps = rcon("tps") if state == "running" else ""
    backups = sorted((MC_DIR / "backups").glob("minecraft-*.tar.gz"), key=lambda p: p.stat().st_mtime)
    latest = backups[-1] if backups else None
    disk = os.statvfs(MC_DIR)
    return {
        "minecraft": {"state": state, "health": health, "restart": restart},
        "players": players,
        "tps": tps,
        "unlim": unlim_json(["status"]),
        "backup": {
            "name": latest.name if latest else None,
            "size": latest.stat().st_size if latest else 0,
            "timestamp": int(latest.stat().st_mtime) if latest else None,
        },
        "disk": {
            "free": disk.f_bavail * disk.f_frsize,
            "total": disk.f_blocks * disk.f_frsize,
        },
        "automation": automation_status(),
    }


def automation_status():
    path = HOME / ".local/state/wsm/last-check.json"
    if not path.exists():
        return {"available": False}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        value["available"] = True
        value["age_seconds"] = max(0, int(time.time()) - int(value.get("timestamp", 0)))
        return value
    except (OSError, ValueError, json.JSONDecodeError):
        return {"available": False, "error": "監視結果を読み取れません。"}


def backup_list():
    items = []
    for path in sorted((MC_DIR / "backups").glob("minecraft-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True):
        items.append({"name": path.name, "size": path.stat().st_size,
                      "timestamp": int(path.stat().st_mtime)})
    return items


def discord_configured():
    path = HOME / ".config/wsm/ops.json"
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("discord_webhook"))
    except (OSError, json.JSONDecodeError):
        return False


def set_discord_webhook():
    value = sys.stdin.read(600).strip()
    if value and not re.fullmatch(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/[A-Za-z0-9._/-]+", value):
        raise RuntimeError("Discord Webhook URLの形式が正しくありません。")
    path = HOME / ".config/wsm/ops.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data["discord_webhook"] = value
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return {"message": "Discord通知を有効にしました。" if value else "Discord通知を無効にしました。"}


def restore_latest():
    backups = backup_list()
    if not backups:
        raise RuntimeError("復元できるバックアップがありません。")
    was_running = docker_state()[0] == "running"
    target = MC_DIR / "backups" / backups[0]["name"]
    if was_running:
        listing = rcon("list")
        match = re.search(r"There are (\d+) of", listing)
        if not match or int(match.group(1)) != 0:
            raise RuntimeError("参加者がいるため復元できません。")
        code, output = run(["make", "backup"], timeout=600)
        if code:
            raise RuntimeError(output or "復元前バックアップに失敗しました。")
        # The newly-created safety backup is newest; restore the backup that
        # was selected before it was created.
        rcon("save-all flush")
        run(["docker", "stop", "-t", "60", "minecraft"], timeout=75, check=True)
    stamp = str(int(time.time()))
    rollback = MC_DIR / f"data.before-restore-{stamp}"
    with tarfile.open(target, "r:gz") as archive:
        members = archive.getmembers()
        if not members or any(not (m.name == "data" or m.name.startswith("data/")) or m.name.startswith("/") or ".." in pathlib.PurePosixPath(m.name).parts for m in members):
            raise RuntimeError("バックアップの内容が安全ではありません。")
        temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="restore-", dir=MC_DIR))
        try:
            archive.extractall(temp_dir, filter="data")
            if not (temp_dir / "data").is_dir():
                raise RuntimeError("バックアップ内にdataフォルダがありません。")
            shutil.move(MC_DIR / "data", rollback)
            try:
                shutil.move(temp_dir / "data", MC_DIR / "data")
            except Exception:
                if not (MC_DIR / "data").exists() and rollback.exists():
                    shutil.move(rollback, MC_DIR / "data")
                raise
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    if was_running:
        run(["docker", "start", "minecraft"], timeout=90, check=True)
        for _ in range(90):
            if docker_state()[1] == "healthy":
                return {"message": f"{target.name} を復元しました。復元前データ: {rollback.name}"}
            time.sleep(2)
        raise RuntimeError(f"復元後のhealthy確認に失敗しました。復元前データ: {rollback.name}")
    return {"message": f"{target.name} を復元しました。Minecraftは停止したままです。"}


def main():
    action = sys.argv[1] if len(sys.argv) == 2 else "status"
    if action == "status":
        result = status()
    elif action == "start":
        run(["docker", "start", "minecraft"], check=True)
        result = {"message": "Minecraftを起動しました。"}
    elif action == "stop":
        if docker_state()[0] == "running":
            rcon("say サーバーを停止します。")
            rcon("save-all flush")
            run(["docker", "stop", "-t", "60", "minecraft"], timeout=75, check=True)
        result = {"message": "Minecraftを停止しました。"}
    elif action == "restart":
        if docker_state()[0] == "running":
            rcon("say サーバーを再起動します。")
            rcon("save-all flush")
        run(["docker", "restart", "-t", "60", "minecraft"], timeout=90, check=True)
        result = {"message": "Minecraftを再起動しました。"}
    elif action == "auto-on":
        run(["docker", "update", "--restart", "unless-stopped", "minecraft"], check=True)
        result = {"message": "Minecraftの異常停止・PC再起動後の自動復旧を有効にしました。"}
    elif action == "auto-off":
        run(["docker", "update", "--restart", "no", "minecraft"], check=True)
        result = {"message": "Minecraftの自動起動を無効にしました。"}
    elif action == "backup":
        if docker_state()[0] != "running":
            raise RuntimeError("バックアップにはMinecraftの起動が必要です。")
        run(["make", "backup"], timeout=300, check=True)
        result = {"message": "バックアップを作成しました。"}
    elif action == "logs":
        result = {"logs": run(["docker", "logs", "--tail", "200", "minecraft"], timeout=30)[1]}
    elif action == "players":
        result = {"players": rcon("list") if docker_state()[0] == "running" else "Server stopped"}
    elif action == "monitor":
        result = {"automation": automation_status(), "status": status()}
    elif action == "backups":
        result = {"backups": backup_list()}
    elif action == "update":
        if docker_state()[0] != "running":
            raise RuntimeError("安全な更新にはMinecraftの起動が必要です。")
        code, output = run(["make", "update"], timeout=900)
        if code:
            raise RuntimeError(output or "更新に失敗しました。")
        result = {"message": output or "安全な更新が完了しました。"}
    elif action == "restore-latest":
        result = restore_latest()
    elif action == "discord-status":
        result = {"configured": discord_configured()}
    elif action == "discord-set":
        result = set_discord_webhook()
    elif action == "unlim-start":
        if docker_state()[0] != "running":
            raise RuntimeError("先にMinecraftを起動してください。")
        current = unlim_json(["status"])
        if current.get("mode") not in ("idle", "starting", "server"):
            raise RuntimeError(f"Unlim is busy: {current.get('mode')}")
        if current.get("mode") == "idle":
            unlim_post("/api/now", {"port_list": "25565/tcp", "public": False})
        result = {"message": "Unlimの共有開始を要求しました。"}
    elif action == "unlim-stop":
        run([UNLIM, "stop"], timeout=20)
        result = {"message": "Unlimの共有を停止しました。"}
    elif action == "unlim-share":
        result = {"share": unlim_json(["share"])}
    else:
        raise RuntimeError("許可されていない操作です。")
    print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
