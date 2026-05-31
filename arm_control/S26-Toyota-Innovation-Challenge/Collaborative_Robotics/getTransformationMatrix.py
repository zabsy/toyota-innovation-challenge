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

RETREAT_POS = (150, -120, 80)

robot_points = np.array([
    [200,-80], [230,-80], [260,-80],
    [200,-40], [230,-40], [260,-40],
    [200,  0], [230,  0], [260,  0],
    [200, 40], [230, 40], [260, 40]
], dtype=np.float32)


def detect_red_center(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    lower1 = np.array([0,  120, 70])
    upper1 = np.array([10, 255, 255])
    lower2 = np.array([170, 120, 70])
    upper2 = np.array([180, 255, 255])

    mask = cv2.inRange(hsv, lower1, upper1) + cv2.inRange(hsv, lower2, upper2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    c = max(contours, key=cv2.contourArea)

    if cv2.contourArea(c) < 50:
        return None

    M = cv2.moments(c)
    if M["m00"] == 0:
        return None

    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    return cx, cy


def collect_calibration():
    pixel_points = []

    for idx, pt in enumerate(robot_points):
        x, y = pt

        print(f"\n----------------------------------")
        print(f"Point {idx+1}/{len(robot_points)}: Moving robot to ({x:.0f}, {y:.0f})")

        # ============================================================
        # CHANGED: Two-step move — lift to safe height first, then
        # move XY, then descend. Prevents dragging across the surface
        # when transitioning between calibration points.
        # ============================================================
        dobotArm.move_to_xyz(api, x, y, 80)
        time.sleep(0.4)
        dobotArm.move_to_xyz(api, x, y, -24)

        print("Robot is at the point. Press SPACE when you have noted the tip position.")

        # ============================================================
        # CHANGED: Robot now waits at the point until SPACE is pressed,
        # so you can clearly see where the tip is before it moves away.
        # Previously it moved away immediately with no wait.
        # ============================================================
        while True:
            ret, frame = cam.read()
            frame = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
            display = frame.copy()
            cv2.putText(display, f"Point {idx+1}/{len(robot_points)}: Note tip position, press SPACE",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
            cv2.imshow("Calibration", display)
            if cv2.waitKey(1) & 0xFF == 32:
                break

        # Move robot away so camera can see the surface clearly
        print("Moving robot away...")
        dobotArm.move_to_xyz(api, *RETREAT_POS)

        print("Place RED sticker where the tip was.")
        print("Press SPACE to save the point, or R to redo.")

        detected = None
        while True:
            ret, frame = cam.read()
            frame = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
            display = frame.copy()

            center = detect_red_center(frame)

            if center:
                u, v = center
                cv2.circle(display, (u, v), 6,  (0, 255, 0), -1)
                cv2.circle(display, (u, v), 14, (0, 255, 0),  2)
                cv2.putText(display, f"Detected  pixel=({u},{v})  robot=({x:.0f},{y:.0f})",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                detected = center
            else:
                cv2.putText(display, "No red sticker detected — place sticker now",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

            cv2.putText(display, "SPACE = save    R = redo this point",
                        (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.imshow("Calibration", display)

            key = cv2.waitKey(1) & 0xFF

            # ============================================================
            # CHANGED: Added R key to redo the current point. Robot moves
            # back to the point so you can re-note the position, then moves
            # away again for a fresh sticker placement.
            # ============================================================
            if key == ord('r'):
                print("  Redo — robot returning to point...")
                detected = None
                dobotArm.move_to_xyz(api, x, y, 80)
                time.sleep(0.4)
                dobotArm.move_to_xyz(api, x, y, -24)
                print("  Note tip position, press SPACE to move away again.")
                while True:
                    ret, frame2 = cam.read()
                    frame2 = cv2.remap(frame2, map1, map2, cv2.INTER_LINEAR)
                    disp2 = frame2.copy()
                    cv2.putText(disp2, "REDO: note tip position, press SPACE",
                                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                    cv2.imshow("Calibration", disp2)
                    if cv2.waitKey(1) & 0xFF == 32:
                        break
                dobotArm.move_to_xyz(api, *RETREAT_POS)
                print("  Place sticker again and press SPACE to save.")

            if key == 32 and detected is not None:
                print(f"  Saved: pixel {detected} → robot ({x:.0f}, {y:.0f})")
                pixel_points.append(detected)
                # ============================================================
                # CHANGED: Prompt to remove sticker before next point so it
                # doesn't get picked up as a false detection on the next frame.
                # ============================================================
                print("  Remove the sticker, then press SPACE for next point.")
                while True:
                    ret, frame = cam.read()
                    frame = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
                    display = frame.copy()
                    cv2.putText(display, "Remove sticker, press SPACE for next point",
                                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                    cv2.imshow("Calibration", display)
                    if cv2.waitKey(1) & 0xFF == 32:
                        break
                break

    return np.array(pixel_points, dtype=np.float32)


def compute_homography(pixel_points):
    H, status = cv2.findHomography(pixel_points, robot_points)

    inliers = int(status.sum()) if status is not None else 0
    total   = len(pixel_points)

    print(f"\nHomography Matrix ({inliers}/{total} inliers):")
    print(H)

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
        print("WARNING: mean error > 2mm. Consider recalibrating.")
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
