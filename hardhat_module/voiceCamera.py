import cv2
import time

capture = cv2.VideoCapture(0)
MIN_CONTOUR_AREA = 500

qrs = cv2.QRCodeDetector()

def detectQRs(imageMat):
    if imageMat is None or imageMat.size == 0:
        return -1
    if imageMat.shape[0] < 20 or imageMat.shape[1] < 20:
        return -1
    
    try:
        data, bounds, straightened = qrs.detectAndDecode(imageMat)
        cv2.imwrite("capture.png", imageMat)
        if data:
            return str(data)
        else:
            return -1
    except cv2.error:
        return -1

def getSerialNum():
    status, img = capture.read()

    initTime = time.time()

    while time.time() - initTime < 0.5:
        status, img = capture.read()

    if status:
        img = cv2.convertScaleAbs(img, alpha=0.75, beta=1.25)
        grayImg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        _, binImg = cv2.threshold(grayImg, 200, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(binImg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cv2.imwrite("output.png", img)
        cv2.imwrite("outputGray.png", grayImg)
        cv2.imwrite("outputBin.png", binImg)

        filtered = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if MIN_CONTOUR_AREA < area:
                filtered.append(contour)

        PAD = 5

        for sample in filtered:
            x, y, w, h = cv2.boundingRect(sample)

            if w < 10 or h < 10:
                continue

            x1 = max(x - PAD, 0)
            y1 = max(y - PAD, 0)
            x2 = min(x + w + PAD, img.shape[1])
            y2 = min(y + h + PAD, img.shape[0])

            roi = img[y1:y2, x1:x2]

            serial = detectQRs(roi)
            if serial != -1:
                return serial