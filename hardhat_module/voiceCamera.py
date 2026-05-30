import cv2

capture = cv2.VideoCapture(1)

qrs = cv2.QRCodeDetector()

while True:
    status, img = capture.read()

    if not status:
        break

    data, bounds, straightened = qrs.detectAndDecode(img)

    if data:
        print(data)

    if bounds is not None:
        corners = bounds.astype(int)
        cv2.polylines(img, corners, True, color=(255,255,0), thickness=2)

    cv2.imshow("QR Code", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

capture.release()
cv2.destroyAllWindows()
