import cv2
import time

capture = cv2.VideoCapture(1)

status, img = capture.read()

initTime = time.time()

while( time.time() - initTime < 1 ):
    status, img = capture.read()

if status:
    cv2.imwrite("capture.png", img)

capture.release()