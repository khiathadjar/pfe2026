#!/usr/bin/env python3
"""
Termux/Android script: detect local IP changes and register the phone to the backend.

Usage:
  - Set `API_BASE` to your backend URL (default: http://127.0.0.1:8000)
  - Optionally set `USER_TOKEN` to a Supabase access token to associate the device with a user
  - Optionally set `DEVICE_ID` to a stable identifier; otherwise a UUID is saved in ~/.phone_device_id

Run:
  python scripts/register_phone.py
"""
import os
import time
import uuid
import socket
import json

import requests

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
DEVICE_ID_FILE = os.path.expanduser("~/.phone_device_id")
DEVICE_ID_ENV = os.getenv("DEVICE_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))


def get_device_id() -> str:
    if DEVICE_ID_ENV:
        return DEVICE_ID_ENV
    try:
        if os.path.exists(DEVICE_ID_FILE):
            return open(DEVICE_ID_FILE, "r").read().strip()
    except Exception:
        pass
    new_id = str(uuid.uuid4())
    try:
        open(DEVICE_ID_FILE, "w").write(new_id)
    except Exception:
        pass
    return new_id


def get_local_ip() -> str | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't actually send packets, just selects the outbound interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip
    except Exception:
        return None
    finally:
        try:
            s.close()
        except Exception:
            pass


def register(ip: str, device_id: str, hostname: str = None) -> dict:
    url = f"{API_BASE}/devices/register"
    headers = {"Content-Type": "application/json"}
    token = os.getenv("USER_TOKEN") or os.getenv("AUTH_TOKEN") or os.getenv("ACCESS_TOKEN")
    if token:
        if token.lower().startswith("bearer "):
            headers["Authorization"] = token
        else:
            headers["Authorization"] = f"Bearer {token}"

    payload = {
        "device_id": device_id,
        "ip": ip,
        "hostname": hostname or socket.gethostname(),
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=8)
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception:
        return {"status_code": resp.status_code, "text": resp.text}


def main():
    device_id = get_device_id()
    hostname = socket.gethostname()
    last_ip = None
    print(f"[register_phone] device_id={device_id} api={API_BASE}")
    while True:
        ip = get_local_ip()
        if ip and ip != last_ip:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] New local IP detected: {ip}")
            try:
                result = register(ip, device_id, hostname=hostname)
                print("Registered:", json.dumps(result, ensure_ascii=False))
            except Exception as e:
                print("Registration failed:", e)
            last_ip = ip
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped")
