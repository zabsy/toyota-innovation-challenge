"""
DB_client.py — runs on the RASPBERRY PI
Sends HTTP requests to the laptop's Flask server to read/write the database.

Usage:
    from DB.DB_client import update_part, get_part, sync_parts

    update_part("QR-TYT-00004", "passed")
    part = get_part("4")
    mapping = sync_parts()
"""

import requests

# ── Set this to your laptop's local IP address ───────────────────
# Find it with: ipconfig (Windows) | ifconfig or ip a (Mac/Linux)
# It will look something like 192.168.1.42
LAPTOP_IP = "172.20.10.5"
PORT = 5050
BASE_URL = f"http://{LAPTOP_IP}:{PORT}"
# ─────────────────────────────────────────────────────────────────

_last_sync_token = None


def normalize_qr_code(raw: str) -> str:
    value = raw.strip().upper()
    if value.isdigit():
        return f"QR-TYT-{int(value):05d}"
    if value.startswith("QR-TYT-"):
        suffix = value.split("-")[-1]
        if suffix.isdigit():
            return f"QR-TYT-{int(suffix):05d}"
    return value


def update_part(qr_code: str, status: str) -> bool:
    """Create or update a part entry on the laptop database."""
    try:
        response = requests.post(
            f"{BASE_URL}/part",
            json={"qr_code": normalize_qr_code(qr_code), "status": status},
            timeout=5,
        )
        if response.status_code == 200:
            print(f"[DB] Updated {qr_code} -> {status}")
            return True
        print(f"[DB] Server error: {response.json()}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"[DB] ERROR: Could not reach laptop at {BASE_URL}. Check IP and that DB_server.py is running.")
        return False
    except requests.exceptions.Timeout:
        print("[DB] ERROR: Request timed out.")
        return False


def get_part(qr_code: str) -> dict | None:
    """Fetch a single part's status from the laptop database."""
    try:
        response = requests.get(f"{BASE_URL}/part/{normalize_qr_code(qr_code)}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"[DB] ERROR fetching part: {e}")
        return None


def get_all_parts() -> dict:
    """Fetch the full database from the laptop."""
    try:
        response = requests.get(f"{BASE_URL}/parts", timeout=5)
        if response.status_code == 200:
            payload = response.json()
            return payload.get("parts", payload)
        return {}
    except Exception as e:
        print(f"[DB] ERROR fetching all parts: {e}")
        return {}


def sync_parts(force: bool = False) -> dict | None:
    """
    Poll the laptop for QR mapping changes.
    Returns the latest parts dict when changed, otherwise None.
    """
    global _last_sync_token

    params = {}
    if not force and _last_sync_token:
        params["since"] = _last_sync_token

    try:
        response = requests.get(f"{BASE_URL}/sync", params=params, timeout=5)
        if response.status_code != 200:
            return None

        payload = response.json()
        _last_sync_token = payload.get("last_updated")

        if payload.get("changed"):
            return payload.get("parts", {})
        return None
    except Exception as e:
        print(f"[DB] ERROR syncing parts: {e}")
        return None
