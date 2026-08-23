#!/usr/bin/env python3
import json
import os
import pathlib
import re
import subprocess
import sys
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
    }


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
    elif action == "backup":
        if docker_state()[0] != "running":
            raise RuntimeError("バックアップにはMinecraftの起動が必要です。")
        run(["make", "backup"], timeout=300, check=True)
        result = {"message": "バックアップを作成しました。"}
    elif action == "logs":
        result = {"logs": run(["docker", "logs", "--tail", "200", "minecraft"], timeout=30)[1]}
    elif action == "players":
        result = {"players": rcon("list") if docker_state()[0] == "running" else "Server stopped"}
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
