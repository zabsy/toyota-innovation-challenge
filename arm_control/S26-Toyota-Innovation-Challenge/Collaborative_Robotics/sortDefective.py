# sortDefective.py
# -----------------------------------------------------------------------------
# Production-line defect sorter. Same phased, stability-locked structure as the
# original pickCVBlock.py:
#
#   PHASE 1  scanning tray   -> detect the reject tray with HoughCircles
#                               (identical method to the original plate detection)
#   PHASE 2  scanning qr     -> read a part's QR and look it up in the DB. Acts
#                               as a GATE: only unlocks when a DEFECTIVE part is
#                               confirmed in view (replaces the original value=="3"
#                               QR gate). Good/unknown parts keep the line scanning.
#   PHASE 3  scanning target -> detect the red target on the defective part
#                               (identical method to the original red-block detection)
#   PHASE 4  pick place      -> pick the red target and drop it in the tray
#
# Architecture (all on this one machine):
#   - DB/DB_server.py (Flask) is running locally on port 5050.
#   - A separate Raspberry Pi writes part statuses to that DB over the network.
#   - This script READS the DB over localhost (single source of truth).
#
# Prereqs:
#   - Run calibrateCamera.py first to generate camera_params.npz + HomographyMatrix.npy
#   - The conveyor surface is at the SAME height as the flat surface used in the
#     original file, so the existing homography is valid as-is.
#   - DB server must be running:  python DB/DB_server.py
# -----------------------------------------------------------------------------

import dobotArm
import lib.DobotDllType as dType
import numpy as np
import cv2
import time
import requests
from pyzbar import pyzbar


"""CONSTANTS"""

Z_SAFE = 40           # clearance height (mm) to avoid collisions while moving horizontally
Z_PICK = -25          # gripper height (mm) to grab a part off the surface
STABILITY_LIMIT = 60  # consecutive stable frames before locking a phase (~2s at 30fps)
QR_MISS_TOLERANCE = 10  # consecutive empty frames to forgive before resetting QR stability

# Local DB server (same machine). Unknown / not-found parts are treated as "good".
DB_BASE_URL = "http://127.0.0.1:5050"
DB_TIMEOUT  = 3       # seconds

machine_state = "scanning tray"

# --- INITIALIZATION FOR CAMERA TRANSFORMATION ---
# MAKE SURE THAT YOU HAVE RAN calibrateCamera.py FIRST TO GENERATE THE camera_params.npz FILE
api = dType.load()
cap = cv2.VideoCapture(1)
H_matrix = np.load(r"arm_control\S26-Toyota-Innovation-Challenge\Collaborative_Robotics\HomographyMatrix.npy")
data = np.load(r"arm_control\S26-Toyota-Innovation-Challenge\Collaborative_Robotics\camera_params.npz")
camera_matrix = data["camera_matrix"]
dist_coeffs   = data["dist_coeffs"]

# Compute undistort maps once
ret, frame = cap.read()
h, w = frame.shape[:2]
new_K, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (w, h), 1)
map1, map2 = cv2.initUndistortRectifyMap(camera_matrix, dist_coeffs, None, new_K, (w, h), cv2.CV_16SC2)


def pixel_to_robot(u, v, H):
    """Map a camera pixel (u, v) to robot-frame (x, y) using the homography."""
    p = np.array([u, v, 1])
    xy = H @ p
    xy /= xy[2]
    return xy[0], xy[1]


# ---------------------------------------------------------
# DATABASE LOOKUP (localhost)
# Returns the status string ("good" / "defective"), or None if the part is not
# in the DB or the server can't be reached. None is treated as "good" upstream.
# Results are cached per-QR so we don't hammer the server every frame.
# ---------------------------------------------------------
_status_cache = {}

def get_status(qr_code):
    if qr_code in _status_cache:
        return _status_cache[qr_code]
    try:
        resp = requests.get(f"{DB_BASE_URL}/part/{qr_code}", timeout=DB_TIMEOUT)
        status = resp.json().get("status") if resp.status_code == 200 else None
    except requests.exceptions.RequestException as e:
        print(f"[DB] lookup failed for {qr_code}: {e}")
        status = None
    _status_cache[qr_code] = status
    return status


# State machine: scanning tray -> scanning qr -> scanning target -> pick place
def next_state():
    global machine_state
    if machine_state == "scanning tray":
        machine_state = "scanning qr"
    elif machine_state == "scanning qr":
        machine_state = "scanning target"
    elif machine_state == "scanning target":
        machine_state = "pick place"
    elif machine_state == "pick place":
        machine_state = "scanning tray"
    else:
        machine_state = "scanning tray"


# ---------------------------------------------------------
# PHASE 1: DETECT the reject tray (circular plate)
# Identical detection method to the original pickCVBlock.py plate detection.
# Returns a list of (rx, ry) tray locations in ROBOT coordinates.
# ---------------------------------------------------------
def phase_detect_tray():
    print("\n[PHASE 1] Scanning for reject tray. Waiting for stability...")
    stability_counter = 0
    last_count = 0

    while True:
        ret, frame = cap.read()
        frame = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
        display_frame = frame.copy()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.medianBlur(gray, 7)
        circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, 1, 150, param1=100, param2=35, minRadius=25, maxRadius=55)

        current_list = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                cv2.circle(display_frame, (i[0], i[1]), i[2], (0, 255, 0), 2)
                rx, ry = pixel_to_robot(i[0], i[1], H_matrix)
                current_list.append((rx, ry))

        # --- AUTO-LOCK LOGIC ---
        if len(current_list) > 0 and len(current_list) == last_count:
            stability_counter += 1
        else:
            stability_counter = 0
            last_count = len(current_list)

        progress = int((stability_counter / STABILITY_LIMIT) * 100)
        cv2.putText(display_frame, f"LOCKING TRAY: {progress}%", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.imshow("Detection", display_frame)
        cv2.waitKey(1)

        if stability_counter >= STABILITY_LIMIT:
            print(f"Locked {len(current_list)} tray(s).")
            return current_list


# ---------------------------------------------------------
# PHASE 2: QR GATE (database-driven)
# Reads QR codes in view and looks each up in the DB. Acts as a trigger/gate:
# unlocks the next phase only once a DEFECTIVE part has been steadily in view.
# Good/unknown parts do NOT trip the gate (the line keeps scanning).
# Same flicker-tolerant stability logic as the original QR gate.
# ---------------------------------------------------------
def phase_qr_gate():
    print("\n[PHASE 2] Waiting for a DEFECTIVE part (QR gate)...")
    stability_counter = 0
    miss_counter = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
        display_frame = frame.copy()

        found_defective = False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for bc in pyzbar.decode(gray):
            if bc.type != "QRCODE":
                continue
            qr = bc.data.decode("utf-8")
            status = get_status(qr)
            is_defective = (status == "defective")

            pts = np.array([[p.x, p.y] for p in bc.polygon], dtype=int)
            cx, cy = int(pts[:, 0].mean()), int(pts[:, 1].mean())
            color = (0, 0, 255) if is_defective else (0, 255, 0)
            cv2.polylines(display_frame, [pts], True, color, 2)
            cv2.putText(display_frame, f"{qr}:{status}", (cx, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            if is_defective:
                found_defective = True

        # --- STABILITY LOGIC (tolerant to pyzbar flicker) ---
        if found_defective:
            miss_counter = 0
            stability_counter += 1
        else:
            miss_counter += 1
            if miss_counter > QR_MISS_TOLERANCE:
                stability_counter = 0

        progress = int((stability_counter / STABILITY_LIMIT) * 100)
        color = (0, 255, 0) if progress < 100 else (255, 255, 0)
        cv2.putText(display_frame, f"DEFECTIVE GATE: {progress}%", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.imshow("Detection", display_frame)
        cv2.waitKey(1)

        if stability_counter >= STABILITY_LIMIT:
            print("[SUCCESS] Defective part confirmed. Proceeding to target scan.")
            return True


# ---------------------------------------------------------
# PHASE 3: DETECT the red target to pick up (red block)
# Identical detection method to the original pickCVBlock.py red-block detection.
# Returns a list of (rx, ry) target locations in ROBOT coordinates.
# ---------------------------------------------------------
def phase_detect_targets():
    print("\n[PHASE 3] Scanning for red target. Waiting for stability...")
    stability_counter = 0
    last_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
        display_frame = frame.copy()

        # Red Tag Logic
        hsv = cv2.cvtColor(cv2.GaussianBlur(frame, (3, 3), 0), cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([0, 120, 70]), np.array([10, 255, 255])) + \
               cv2.inRange(hsv, np.array([170, 120, 70]), np.array([180, 255, 255]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        current_list = []
        for cnt in contours:
            if cv2.contourArea(cnt) > 100:
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                    rx, ry = pixel_to_robot(cx, cy, H_matrix)
                    current_list.append((rx, ry))
                    cv2.drawContours(display_frame, [cnt], -1, (0, 255, 0), 2)

        # --- STABILITY LOGIC ---
        if len(current_list) != 0:
            if len(current_list) == last_count:
                stability_counter += 1
            else:
                stability_counter = 0
                last_count = len(current_list)

        progress = int((stability_counter / STABILITY_LIMIT) * 100)
        color = (0, 255, 0) if progress < 100 else (255, 255, 0)
        cv2.putText(display_frame, f"LOCKING TARGETS: {progress}%", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.imshow("Detection", display_frame)
        cv2.waitKey(1)

        if stability_counter >= STABILITY_LIMIT:
            print(f"[SUCCESS] Locked {len(current_list)} target(s).")
            return current_list


# ---------------------------------------------------------
# PHASE 4: PICK/PLACE LOOP
# Picks each red target and drops it into the reject tray.
# Mirrors the original: 1 target -> 1 tray slot, paired by index.
# ---------------------------------------------------------
def refresh_feed(label=""):
    # Pump one camera frame to the window so it stays responsive during
    # blocking robot moves (OpenCV only repaints when waitKey is called).
    ret, frame = cap.read()
    if ret:
        frame = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
        if label:
            cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.imshow("Detection", frame)
    cv2.waitKey(1)


def phase_execute_batch(api, pick_list, drop_list):
    time.sleep(0.5)

    if len(pick_list) == 0 or len(drop_list) == 0:
        print("missing targets, aborting")
        return False

    # Match 1 target to 1 tray slot (uses the smaller count)
    batch_size = min(len(pick_list), len(drop_list))
    print(f"\n[PHASE 4] Diverting {batch_size} defective part(s) to the tray.")

    for i in range(batch_size):
        pick_x, pick_y = pick_list[i]
        drop_x, drop_y = drop_list[i]

        print(f"Task {i+1}: Moving {pick_x, pick_y} to tray {drop_x, drop_y}")
        status = f"DIVERT {i+1}/{batch_size}"

        # --- PICK SEQUENCE ---
        refresh_feed(status)
        dobotArm.move_to_xyz(api, pick_x, pick_y, Z_SAFE)
        refresh_feed(status)
        dobotArm.move_to_xyz(api, pick_x, pick_y, Z_PICK)
        dobotArm.close_gripper(api)
        refresh_feed(status)
        dobotArm.move_to_xyz(api, pick_x, pick_y, Z_SAFE)

        # --- PLACE SEQUENCE ---
        refresh_feed(status)
        dobotArm.move_to_xyz(api, drop_x, drop_y, Z_SAFE)
        dobotArm.open_gripper(api)
        dobotArm.stop_pump(api)
        refresh_feed(status)
        dobotArm.move_to_xyz(api, drop_x, drop_y, Z_SAFE)

    print("\nBatch Complete.")
    return True


# ---------------------------------------------------------
# MAIN EXECUTION
# Same sequential state-machine structure as the original.
# ---------------------------------------------------------
dobotArm.initialize_robot(api)
dobotArm.open_gripper(api)
dobotArm.stop_pump(api)

tray_zone = None
red_targets = None

while machine_state == "scanning tray":
    tray_zone = phase_detect_tray()
    if tray_zone is not None:
        next_state()

while machine_state == "scanning qr":
    if phase_qr_gate():
        next_state()

while machine_state == "scanning target":
    red_targets = phase_detect_targets()
    if red_targets is not None:
        next_state()

while machine_state == "pick place":
    completed = phase_execute_batch(api, red_targets, tray_zone)
    if completed:
        next_state()
    else:
        break

cap.release()
cv2.destroyAllWindows()
