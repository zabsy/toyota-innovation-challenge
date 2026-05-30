"""
db_client.py — runs on the RASPBERRY PI
Sends HTTP requests to the laptop's Flask server to read/write the database.
Import this into your jarvisAssistant.py on the Raspi.
 
Usage:
    from db_client import update_part, get_part
 
    update_part("QR-TYT-00005", "defect")
    part = get_part("QR-TYT-00005")
    print(part["status"])  # "defect"
"""
 
import requests
 
# ── Set this to your laptop's local IP address ───────────────────
# Find it with: ipconfig (Windows) | ifconfig or ip a (Mac/Linux)
# It will look something like 192.168.1.42
LAPTOP_IP   = "10.36.183.59"
PORT        = 5050
BASE_URL    = f"http://{10.36.183.59}:{PORT}"
# ─────────────────────────────────────────────────────────────────
 
 
def update_part(qr_code: str, status: str) -> bool:
    """
    Create or update a part entry on the laptop database.
    status must be: "passed", "defect", "critical", or "pending"
    Returns True on success, False on failure.
    """
    try:
        response = requests.post(
            f"{BASE_URL}/part",
            json={"qr_code": qr_code, "status": status},
            timeout=5
        )
        if response.status_code == 200:
            print(f"[DB] Updated {qr_code} → {status}")
            return True
        else:
            print(f"[DB] Server error: {response.json()}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"[DB] ERROR: Could not reach laptop at {BASE_URL}. Check IP and that server.py is running.")
        return False
    except requests.exceptions.Timeout:
        print(f"[DB] ERROR: Request timed out.")
        return False
 
 
def get_part(qr_code: str) -> dict | None:
    """
    Fetch a single part's status from the laptop database.
    Returns {"qr_code": ..., "status": ...} or None if not found.
    """
    try:
        response = requests.get(f"{BASE_URL}/part/{qr_code}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"[DB] ERROR fetching part: {e}")
        return None
 
 
def get_all_parts() -> dict:
    """
    Fetch the full database from the laptop.
    Returns a dict of {qr_code: {status}} or empty dict on failure.
    """
    try:
        response = requests.get(f"{BASE_URL}/parts", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        print(f"[DB] ERROR fetching all parts: {e}")
        return {}
 