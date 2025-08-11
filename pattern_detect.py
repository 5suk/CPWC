import ctypes
import win32gui
import win32con
import win32ui
import numpy as np
import cv2

# 창 제목 (UC-win/Road의 뷰 창 이름)
WINDOW_TITLE = "경관 위치 <top>"

# ──────────────────────────────────────────────
# 창 화면 캡처 함수
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
    img = img[..., :3]  # BGRA → BGR

    win32gui.ReleaseDC(hwnd, hwndDC)
    return img

# ──────────────────────────────────────────────
# 사다리꼴 ROI 마스크 함수 (하단 1/3)
def apply_trapezoid_mask(img):
    height, width = img.shape[:2]
    mask = np.zeros_like(img)

    bottom_y = height
    top_y = int(height * 2 / 3)

    pts = np.array([[  # 사다리꼴 꼭짓점
        (int(width * 0.2), top_y),
        (int(width * 0.8), top_y),
        (width, bottom_y),
        (0, bottom_y)
    ]], dtype=np.int32)

    cv2.fillPoly(mask, pts, (255, 255, 255))
    masked = cv2.bitwise_and(img, mask)

    return masked, pts[0]  # ROI 이미지, 꼭짓점 반환

# ──────────────────────────────────────────────
# Zebra 패턴 인식 함수 (흰색 수직선 기반)
def detect_pattern(img):
    roi_masked, trapezoid = apply_trapezoid_mask(img)

    gray = cv2.cvtColor(roi_masked, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=40, maxLineGap=10)
    vertical_lines = 0

    for line in lines if lines is not None else []:
        x1, y1, x2, y2 = line[0]
        angle = np.abs(np.arctan2((y2 - y1), (x2 - x1)) * 180 / np.pi)
        if 80 <= angle <= 100:
            vertical_lines += 1
            cv2.line(roi_masked, (x1, y1), (x2, y2), (0, 255, 0), 2)

    detected = vertical_lines >= 3

    result_img = img.copy()
    cv2.polylines(result_img, [trapezoid], isClosed=True, color=(255, 0, 0), thickness=2)
    cv2.putText(result_img, "Pattern Detected" if detected else "No Pattern",
                (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (0, 255, 0) if detected else (0, 0, 255), 2)

    return result_img, detected

# ──────────────────────────────────────────────
# 실행 루프
if __name__ == "__main__":
    print("[INFO] Starting zebra pattern detection with trapezoid ROI... (Press 'q' to quit)")
    hwnd = win32gui.FindWindow(None, WINDOW_TITLE)
    if hwnd == 0:
        print("Window not found!")
        exit()

    while True:
        frame = capture_window(hwnd)
        result_img, detected = detect_pattern(frame)
        cv2.imshow("Zebra Pattern Detection", result_img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
