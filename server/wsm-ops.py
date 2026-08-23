#!/usr/bin/env python3
"""Periodic maintenance and recovery for Minecraft + Unlim."""

import json
import os
import pathlib
import shutil
import socket
import subprocess
import time
import urllib.request

HOME = pathlib.Path.home()
MC_DIR = pathlib.Path(os.environ.get("WSM_MC_DIR", HOME / "minecraft"))
STATE_DIR = HOME / ".local/state/wsm"
CONFIG_FILE = HOME / ".config/wsm/ops.json"
UNLIM = pathlib.Path(os.environ.get("WSM_UNLIM", HOME / ".local/bin/unlim"))
DEFAULTS = {
    "auto_share": True,
    "recover_minecraft": True,
    "backup_interval_hours": 24,
    "max_backups": 5,
    "disk_warning_percent": 85,
    "temperature_warning_c": 80,
    "memory_warning_percent": 90,
    "load_warning_per_cpu": 1.5,
    "battery_safe_stop_percent": 15,
    "discord_webhook": "",
}


def run(args, timeout=300):
    return subprocess.run([str(x) for x in args], cwd=MC_DIR, capture_output=True,
                          text=True, timeout=timeout)


def config():
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        CONFIG_FILE.chmod(0o600)
    try:
        supplied = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        supplied = {}
    return DEFAULTS | supplied


def docker_info():
    result = run(["docker", "inspect", "-f",
                  "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.HostConfig.RestartPolicy.Name}}",
                  "minecraft"], 20)
    return result.stdout.strip().split("|", 2) if result.returncode == 0 else ["missing", "none", "no"]


def unlim_status():
    result = run([UNLIM, "status", "--json"], 20)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"mode": "unavailable"}


def unlim_start():
    endpoint = json.loads((HOME / ".unlimited/api_endpoint").read_text(encoding="utf-8"))
    token = (HOME / ".unlimited/api_token").read_text(encoding="utf-8").strip()
    request = urllib.request.Request(
        f"http://127.0.0.1:{endpoint['port']}/api/now",
        data=json.dumps({"port_list": "25565/tcp", "public": False}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def temperatures():
    values = []
    for item in pathlib.Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            values.append(int(item.read_text().strip()) / 1000)
        except (OSError, ValueError):
            pass
    return values


def memory_percent():
    values = {}
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        values[key] = int(value.strip().split()[0])
    return round((1 - values["MemAvailable"] / values["MemTotal"]) * 100, 1)


def battery():
    for item in pathlib.Path("/sys/class/power_supply").glob("BAT*"):
        try:
            return {"percent": int((item / "capacity").read_text().strip()),
                    "status": (item / "status").read_text().strip()}
        except (OSError, ValueError):
            pass
    return None


def notify(message, cfg):
    webhook = str(cfg.get("discord_webhook", "")).strip()
    if not webhook:
        return
    payload = json.dumps({"content": f"[Minecraft Server] {message}"}).encode()
    request = urllib.request.Request(webhook, data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=20):
        pass


def notify_once(key, message, cfg, active=True):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    marker = STATE_DIR / f"alert-{key}"
    if active and not marker.exists():
        notify(message, cfg)
        marker.write_text(str(int(time.time())), encoding="utf-8")
    elif not active and marker.exists():
        marker.unlink()
        notify(f"復旧: {message}", cfg)


def main():
    cfg = config()
    events = []
    state, health, policy = docker_info()

    network_ok = False
    try:
        socket.getaddrinfo("unlim.cc", 443)
        network_ok = True
    except socket.gaierror:
        pass
    notify_once("network", "インターネット接続を確認できません。", cfg, not network_ok)

    if state == "exited" and policy != "no" and cfg.get("recover_minecraft", True):
        result = run(["docker", "start", "minecraft"], 90)
        if result.returncode == 0:
            events.append("Minecraft recovery requested")
            state = "running"
        else:
            notify_once("minecraft", "Minecraftの自動復旧に失敗しました。", cfg, True)
    minecraft_bad = policy != "no" and state not in ("running", "created")
    notify_once("minecraft", "Minecraftが停止しています。", cfg, minecraft_bad)

    if network_ok and state == "running" and cfg.get("auto_share", True):
        mode = unlim_status().get("mode", "unavailable")
        if mode == "idle":
            try:
                unlim_start()
                events.append("Unlim sharing recovery requested")
            except Exception as error:
                notify_once("unlim", f"Unlim共有の自動復旧に失敗しました: {error}", cfg, True)
        elif mode == "server":
            notify_once("unlim", "Unlim共有が停止しています。", cfg, False)

    env = os.environ | {"MAX_BACKUPS": str(cfg.get("max_backups", 5))}
    backup = subprocess.run([str(MC_DIR / "mc"), "backup-auto"], cwd=MC_DIR,
                            capture_output=True, text=True, timeout=600, env=env)
    backup_failed = backup.returncode != 0
    notify_once("backup", "自動バックアップに失敗しました。", cfg, backup_failed)
    if backup.stdout.strip():
        events.append(backup.stdout.strip())

    usage = shutil.disk_usage(MC_DIR)
    disk_percent = round((usage.used / usage.total) * 100, 1)
    notify_once("disk", f"ディスク使用率が{disk_percent}%です。", cfg,
                disk_percent >= float(cfg.get("disk_warning_percent", 85)))
    temps = temperatures()
    max_temp = max(temps, default=0)
    notify_once("temperature", f"温度が{max_temp:.1f}°Cです。", cfg,
                max_temp >= float(cfg.get("temperature_warning_c", 80)))
    mem_percent = memory_percent()
    notify_once("memory", f"メモリ使用率が{mem_percent}%です。", cfg,
                mem_percent >= float(cfg.get("memory_warning_percent", 90)))
    cpu_count = os.cpu_count() or 1
    load_per_cpu = round(os.getloadavg()[0] / cpu_count, 2)
    notify_once("load", f"CPU負荷が高い状態です ({load_per_cpu}/core)。", cfg,
                load_per_cpu >= float(cfg.get("load_warning_per_cpu", 1.5)))
    battery_info = battery()
    if battery_info and battery_info["status"] == "Discharging":
        low = battery_info["percent"] <= int(cfg.get("battery_safe_stop_percent", 15))
        notify_once("battery", f"バッテリー残量が{battery_info['percent']}%です。", cfg, low)
        if low and state == "running":
            run(["docker", "exec", "minecraft", "rcon-cli", "save-all", "flush"], 30)
            run(["docker", "stop", "-t", "60", "minecraft"], 75)
            events.append("Minecraft stopped because battery is low")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "timestamp": int(time.time()), "network": network_ok,
        "minecraft": {"state": state, "health": health, "restart": policy},
        "unlim": unlim_status(), "disk_percent": disk_percent,
        "max_temperature_c": max_temp, "memory_percent": mem_percent,
        "load_per_cpu": load_per_cpu, "battery": battery_info, "events": events,
    }
    (STATE_DIR / "last-check.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, ensure_ascii=False))


if __name__ == "__main__":
    main()
