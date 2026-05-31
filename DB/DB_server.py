"""
server.py — runs on the LAPTOP
Receives HTTP requests from the Raspberry Pi and reads/writes parts_db.json.
The database file lives at DB/parts_db.json, right next to this server
(created automatically on the first write — see DB_PATH below).
 
Start with:
    pip install flask
    python server.py
 
The Raspi sends requests to http://<LAPTOP_LOCAL_IP>:5050
Find your laptop's local IP with: ipconfig (Windows) or ifconfig / ip a (Mac/Linux)
"""
 
from flask import Flask, request, jsonify
import json
from pathlib import Path
 
# Serve the dashboard (ui/) from this same server so the frontend and the API
# share one origin — the UI fetches /parts, /part, etc. from window.location.origin.
UI_DIR = Path(__file__).parent.parent / "ui"
app = Flask(__name__, static_folder=str(UI_DIR), static_url_path="")
DB_PATH = Path(__file__).parent / "parts_db.json"


# ── GET / ────────────────────────────────────────────────────────
# Serves the dashboard UI (ui/index.html). Static assets (app.js,
# styles.css, assets/…) are served automatically from UI_DIR.
@app.route("/")
def index():
    return app.send_static_file("index.html")
 
VALID_STATUSES = {"good", "defective"}
 
 
def load_db() -> dict:
    if not DB_PATH.exists():
        return {"parts": {}}
    with open(DB_PATH, "r") as f:
        return json.load(f)
 
 
def save_db(db: dict) -> None:
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)
 
 
# ── GET /part/<qr_code> ──────────────────────────────────────────
# Returns the status of a single part.
# Example: GET http://laptop-ip:5050/part/QR-TYT-00001
@app.route("/part/<qr_code>", methods=["GET"])
def get_part(qr_code):
    db = load_db()
    part = db["parts"].get(qr_code)
    if not part:
        return jsonify({"error": "Part not found"}), 404
    return jsonify({"qr_code": qr_code, "status": part["status"]}), 200
 
 
# ── POST /part ───────────────────────────────────────────────────
# Creates or updates a part entry.
# Body: { "qr_code": "QR-TYT-00005", "status": "defective" }
@app.route("/part", methods=["POST"])
def upsert_part():
    data = request.get_json()
 
    qr_code = data.get("qr_code", "").strip()
    status  = data.get("status", "").strip()
 
    if not qr_code:
        return jsonify({"error": "Missing qr_code"}), 400
    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of {VALID_STATUSES}"}), 400
 
    db = load_db()
    db["parts"][qr_code] = {"status": status}
    save_db(db)
 
    print(f"[DB] {qr_code} -> {status}")
    return jsonify({"qr_code": qr_code, "status": status}), 200
 
 
# ── DELETE /part/<qr_code> ───────────────────────────────────────
# Deletes a part entry.
# Example: DELETE http://laptop-ip:5050/part/QR-TYT-00005
@app.route("/part/<qr_code>", methods=["DELETE"])
def delete_part(qr_code):
    db = load_db()
    if qr_code not in db["parts"]:
        return jsonify({"error": "Part not found"}), 404

    del db["parts"][qr_code]
    save_db(db)

    print(f"[DB] Deleted {qr_code}")
    return jsonify({"deleted": qr_code}), 200


# ── GET /parts ───────────────────────────────────────────────────
# Returns the full database.
@app.route("/parts", methods=["GET"])
def get_all_parts():
    db = load_db()
    return jsonify(db["parts"]), 200
 
 
if __name__ == "__main__":
    # host="0.0.0.0" makes it reachable on your local network, not just localhost
    app.run(host="0.0.0.0", port=5050, debug=True)
 