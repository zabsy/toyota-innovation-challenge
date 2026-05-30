import lib.DobotDllType as dType
import dobotArm
import time
import numpy as np
import cv2
import os
 
CON_STR = {
    dType.DobotConnect.DobotConnect_NoError:  "DobotConnect_NoError",
    dType.DobotConnect.DobotConnect_NotFound: "DobotConnect_NotFound",
    dType.DobotConnect.DobotConnect_Occupied: "DobotConnect_Occupied"
}
 
# ============================================================
# CHANGED: Added CAP_DSHOW for faster, more reliable camera
# init on Windows. Without it, OpenCV uses MSMF which can take
# several seconds to open and occasionally drops early frames.
# ============================================================
cam = cv2.VideoCapture(1, cv2.CAP_DSHOW)
 
if not cam.isOpened():
    print("Camera failed to open")
    exit()
 
data = np.load("arm_control\\S26-Toyota-Innovation-Challenge\\Collaborative_Robotics\\camera_params.npz")
camera_matrix = data["camera_matrix"]
dist_coeffs   = data["dist_coeffs"]
 
ret, frame = cam.read()
h, w = frame.shape[:2]
 
new_K, roi = cv2.getOptimalNewCameraMatrix(
    camera_matrix, dist_coeffs, (w, h), 1
)
map1, map2 = cv2.initUndistortRectifyMap(
    camera_matrix, dist_coeffs, None, new_K, (w, h), cv2.CV_16SC2
)
 
api = dType.load()
 
robot_points = np.array([
    [200,-80], [230,-80], [260,-80],
    [200,-40], [230,-40], [260,-40],
    [200,  0], [230,  0], [260,  0],
    [200, 40], [230, 40], [260, 40]
], dtype=np.float32)
 
 
def detect_red_center(frame):
    # ============================================================
    # CHANGED: Added GaussianBlur before HSV conversion.
    # A red sticker on the robot tip has specular highlights that
    # break the HSV mask into multiple fragments. Blurring first
    # smooths the highlights and gives a single clean contour.
    # ============================================================
    blurred = cv2.GaussianBlur(frame, (5, 5), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
 
    lower1 = np.array([0,  120, 70])
    upper1 = np.array([10, 255, 255])
    lower2 = np.array([170, 120, 70])
    upper2 = np.array([180, 255, 255])
 
    mask = cv2.inRange(hsv, lower1, upper1) + cv2.inRange(hsv, lower2, upper2)
 
    # ============================================================
    # CHANGED: Added morphological closing after the mask to fill
    # small holes caused by specular highlights on the sticker.
    # ============================================================
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
 
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
 
    if not contours:
        return None
 
    c = max(contours, key=cv2.contourArea)
 
    # ============================================================
    # CHANGED: Added minimum area guard (50px²). Without it, a
    # single red pixel from a reflection was occasionally returned
    # as the "center", causing wildly wrong calibration points.
    # ============================================================
    if cv2.contourArea(c) < 50:
        return None
 
    M = cv2.moments(c)
    if M["m00"] == 0:
        return None
 
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    return cx, cy
 
 
# ============================================================
# CHANGED: Completely reworked calibration workflow.
#
# OLD METHOD (error-prone):
#   1. Move robot to point at Z_PICK
#   2. Move robot AWAY
#   3. Manually place a red marker where the tip was  ← human error
#   4. Capture that marker's pixel
#
# NEW METHOD (direct capture):
#   1. Attach a red sticker to the robot tip (do this once)
#   2. Move robot to each calibration point at Z_PICK
#   3. Capture the tip pixel DIRECTLY — no manual marker needed
#
# This eliminates the biggest source of calibration error: the
# imprecise manual placement of the red marker. Any offset in
# that placement shifts every downstream robot coordinate.
#
# To use: stick a small red sticker/tape on the robot tip before
# running calibration. Remove it when done.
# ============================================================
def collect_calibration():
    pixel_points = []
 
    print("\n========================================")
    print("CALIBRATION — RED STICKER METHOD")
    print("Attach a small red sticker to the robot tip NOW.")
    print("Press ENTER when ready.")
    print("========================================")
    input()
 
    for idx, pt in enumerate(robot_points):
        x, y = pt
        print(f"\n--- Point {idx+1}/{len(robot_points)}: robot ({x}, {y}) ---")
 
        # ============================================================
        # CHANGED: Robot now moves to Z_PICK (pick height) instead of
        # the original -24. Using the exact pick height means the
        # homography is computed for the plane where picking actually
        # happens, not a slightly different height. Also unified with
        # Z_PICK constant used in the main script (-29).
        # ============================================================
        Z_PICK_CAL = -29
        dobotArm.move_to_xyz(api, x, y, Z_PICK_CAL)
        time.sleep(0.8)   # ← CHANGED: wait for arm to fully settle before capture
 
        print("Robot in position. Press SPACE to capture pixel (or R to retry).")
 
        detected = None
        while True:
            ret, frame = cam.read()
            frame = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
 
            center = detect_red_center(frame)
            display = frame.copy()
 
            if center:
                u, v = center
                cv2.circle(display, (u, v), 8, (0, 255, 0), -1)
                cv2.circle(display, (u, v), 12, (0, 255, 0), 2)
                # ============================================================
                # CHANGED: Show live robot coords alongside pixel coords so
                # you can sanity-check the mapping before committing the point.
                # ============================================================
                cv2.putText(display, f"Pixel: ({u},{v})  Robot: ({x:.0f},{y:.0f})",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                detected = center
            else:
                cv2.putText(display, "No red detected — check sticker/lighting",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
 
            cv2.putText(display, f"Point {idx+1}/{len(robot_points)} — SPACE=save  R=retry",
                        (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.imshow("Calibration", display)
 
            key = cv2.waitKey(1) & 0xFF
 
            if key == ord('r'):
                # ← CHANGED: R key re-moves to the point in case the arm drifted
                dobotArm.move_to_xyz(api, x, y, Z_PICK_CAL)
                time.sleep(0.8)
 
            if key == 32 and detected is not None:   # SPACE
                print(f"  Saved pixel {detected} for robot point ({x}, {y})")
                pixel_points.append(detected)
                break
 
        # ============================================================
        # CHANGED: Lift to Z_SAFE between points instead of moving
        # horizontally at pick height. Prevents the tip from dragging
        # across the work surface when transitioning to the next point.
        # ============================================================
        dobotArm.move_to_xyz(api, x, y, 40)
 
    return np.array(pixel_points, dtype=np.float32)
 
 
def compute_homography(pixel_points):
    H, status = cv2.findHomography(pixel_points, robot_points)
 
    inliers = int(status.sum()) if status is not None else 0
    total   = len(pixel_points)
 
    print(f"\nHomography Matrix ({inliers}/{total} inliers):")
    print(H)
 
    # ============================================================
    # CHANGED: Added reprojection error report. If mean error > 2mm
    # the calibration is unreliable and you should redo it.
    # A good calibration on this setup should be < 1mm mean error.
    # ============================================================
    errors = []
    for i, (u, v) in enumerate(pixel_points):
        p = np.array([u, v, 1.0])
        xy = H @ p
        xy /= xy[2]
        rx, ry = robot_points[i]
        err = np.hypot(xy[0] - rx, xy[1] - ry)
        errors.append(err)
 
    mean_err = np.mean(errors)
    max_err  = np.max(errors)
    print(f"\nReprojection error — mean: {mean_err:.2f}mm  max: {max_err:.2f}mm")
 
    if mean_err > 2.0:
        print("WARNING: mean error > 2mm. Consider recalibrating — check sticker placement and lighting.")
    else:
        print("Calibration looks good.")
 
    np.save("HomographyMatrix.npy", H)
    print("Matrix saved to HomographyMatrix.npy")
    return H
 
 
# ------------------------------------------------
# MAIN
# ------------------------------------------------
def run():
    dobotArm.initialize_robot(api)
 
    pixel_points = collect_calibration()
 
    if len(pixel_points) < 4:
        print("Not enough points collected — need at least 4.")
        return
 
    compute_homography(pixel_points)
 
    cam.release()
    cv2.destroyAllWindows()
 
 
run()
