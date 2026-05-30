"""
DB_server.py — runs on the LAPTOP
Receives HTTP requests from the Raspberry Pi and mobile UI, reads/writes parts_db.json.

Start with:
    pip install -r requirements.txt
    python DB/DB_server.py

Mobile UI:  http://<LAPTOP_LOCAL_IP>:5050
Pi client:  http://<LAPTOP_LOCAL_IP>:5050/parts
"""

from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json

ROOT = Path(__file__).resolve().parent.parent

app = Flask(__name__, static_folder=str(ROOT / "ui"), static_url_path="")
CORS(app)

DB_PATH = ROOT / "parts_db.json"
UI_PATH = ROOT / "ui"

VALID_STATUSES = {"passed", "defect", "critical", "pending"}
STATUS_LABELS = {
    "passed": "Good",
    "defect": "Defective",
    "critical": "Critical Defect",
    "pending": "Pending Inspection",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_db() -> dict:
    return {
        "parts": {
            "QR-TYT-00001": {"status": "passed"},
            "QR-TYT-00002": {"status": "defect"},
            "QR-TYT-00003": {"status": "critical"},
            "QR-TYT-00004": {"status": "pending"},
        },
        "last_updated": utc_now(),
    }


def load_db() -> dict:
    if not DB_PATH.exists():
        db = default_db()
        save_db(db)
        return db
    with open(DB_PATH, "r") as f:
        db = json.load(f)
    if "parts" not in db:
        db["parts"] = {}
    if "last_updated" not in db:
        db["last_updated"] = utc_now()
    return db


def save_db(db: dict) -> None:
    db["last_updated"] = utc_now()
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


def normalize_qr_code(raw: str) -> str:
    value = raw.strip().upper()
    if value.isdigit():
        return f"QR-TYT-{int(value):05d}"
    if value.startswith("QR-TYT-"):
        suffix = value.split("-")[-1]
        if suffix.isdigit():
            return f"QR-TYT-{int(suffix):05d}"
    return value


def part_payload(qr_code: str, status: str) -> dict:
    return {
        "qr_code": qr_code,
        "status": status,
        "label": STATUS_LABELS.get(status, status.title()),
        "is_good": status == "passed",
        "is_bad": status in {"defect", "critical"},
    }


@app.route("/")
def serve_ui():
    return send_from_directory(UI_PATH, "index.html")


@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(UI_PATH / "assets", filename)


@app.route("/health", methods=["GET"])
def health():
    db = load_db()
    return jsonify({"ok": True, "last_updated": db.get("last_updated"), "part_count": len(db["parts"])}), 200


@app.route("/part/<qr_code>", methods=["GET"])
def get_part(qr_code):
    db = load_db()
    normalized = normalize_qr_code(qr_code)
    part = db["parts"].get(normalized)
    if not part:
        return jsonify({"error": "Part not found"}), 404
    return jsonify(part_payload(normalized, part["status"])), 200


@app.route("/part", methods=["POST"])
def upsert_part():
    data = request.get_json(silent=True) or {}

    qr_code = normalize_qr_code(data.get("qr_code", ""))
    status = data.get("status", "").strip().lower()

    if not qr_code:
        return jsonify({"error": "Missing qr_code"}), 400
    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of {sorted(VALID_STATUSES)}"}), 400

    db = load_db()
    db["parts"][qr_code] = {"status": status}
    save_db(db)

    print(f"[DB] {qr_code} -> {status}")
    return jsonify({**part_payload(qr_code, status), "last_updated": db["last_updated"]}), 200


@app.route("/parts", methods=["GET"])
def get_all_parts():
    db = load_db()
    parts = {
        qr_code: part_payload(qr_code, part["status"])
        for qr_code, part in db["parts"].items()
    }
    return jsonify({"parts": parts, "last_updated": db["last_updated"]}), 200


@app.route("/sync", methods=["GET"])
def sync_parts():
    """Lightweight endpoint for Raspberry Pi polling."""
    db = load_db()
    since = request.args.get("since")
    last_updated = db.get("last_updated")
    changed = since != last_updated if since else True
    return jsonify(
        {
            "changed": changed,
            "last_updated": last_updated,
            "parts": db["parts"] if changed else {},
        }
    ), 200


if __name__ == "__main__":
    load_db()
    print("Toyota QR Control UI: http://0.0.0.0:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)
