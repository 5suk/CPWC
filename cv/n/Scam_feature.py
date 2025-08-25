import ctypes
import win32gui
import win32con
import win32ui
import numpy as np
import cv2

WINDOW_TITLE = "경관 위치 <top>"

def capture_window(hwnd):
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width = right - left
    height = bottom - top

    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)

    ctypes.windll.dwmapi.DwmEnableComposition(1)
    ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
    bmpstr = saveBitMap.GetBitmapBits(True)

    img = np.frombuffer(bmpstr, dtype=np.uint8).copy().reshape((height, width, 4))
    img = img[..., :3]
    win32gui.ReleaseDC(hwnd, hwndDC)
    return img

def apply_trapezoid_mask(img):
    height, width = img.shape[:2]
    mask = np.zeros_like(img)
    bottom_y = height
    top_y = int(height * 2 / 3)

    pts = np.array([[
        (int(width * 0.2), top_y),
        (int(width * 0.8), top_y),
        (width, bottom_y),
        (0, bottom_y)
    ]], dtype=np.int32)

    cv2.fillPoly(mask, pts, (255, 255, 255))
    masked = cv2.bitwise_and(img, mask)
    return masked, pts[0]

def detect_orange(img):
    roi_masked, trapezoid = apply_trapezoid_mask(img)
    hsv = cv2.cvtColor(roi_masked, cv2.COLOR_BGR2HSV)
    lower_orange = np.array([5, 100, 100])
    upper_orange = np.array([25, 255, 255])
    mask = cv2.inRange(hsv, lower_orange, upper_orange)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detected = False
    height = img.shape[0]

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 500:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h if h > 0 else 0
            if 2.5 < aspect_ratio < 6:
                detected = True
                distance_px = height - (y + h)

                # 사각형 그리기
                cv2.rectangle(roi_masked, (x, y), (x + w, y + h), (0, 140, 255), 2)
                cv2.putText(roi_masked, f"w:{w} h:{h} a:{int(area)} ar:{aspect_ratio:.1f}", 
                            (x, y - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,140,255), 1)
                cv2.putText(roi_masked, f"d:{distance_px}px", 
                            (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,140,255), 1)

    result_img = img.copy()
    cv2.polylines(result_img, [trapezoid], isClosed=True, color=(255, 0, 0), thickness=2)
    result_img = cv2.addWeighted(result_img, 0.6, roi_masked, 0.4, 0)

    cv2.putText(result_img, "Orange Detected" if detected else "No Orange",
                (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (0, 140, 255) if detected else (0, 0, 255), 2)

    return result_img, detected

# 실행 루프
if __name__ == "__main__":
    print("[INFO] Starting orange bump detection with features... (Press 'q' to quit)")
    hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
    if hwnd == 0:
        print("Window not found!")
        exit()

    while True:
        frame = capture_window(hwnd)
        result_img, detected = detect_orange(frame)
        cv2.imshow("Orange Feature Detection", result_img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
