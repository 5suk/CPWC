import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import time

# --- 1. 설정 ---
TARGET_WINDOW_TITLE = "경관 위치 <test>"
# [높이 계산 설정]
MAX_HEIGHT_M = 1.0
# [거리 계산 설정] 새로운 기준점 적용
DISTANCE_CALIBRATION_POINTS = {
    # Y비율(0=최상단, 1=최하단): 실제 거리(m)
    0.0: 17.0,  # ROI 최상단 = 17m
    0.5: 8.0,   # ROI 절반 높이 = 8m
    1.0: 2.0    # ROI 최하단 = 2m (가까운 거리)
}

# --- 2. 창 캡처 함수 ---
def capture_window_by_title(window_title):
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd == 0: return None
    left, top, right, bot = win32gui.GetClientRect(hwnd)
    w, h = right - left, bot - top
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)
    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
    bmpstr = saveBitMap.GetBitmapBits(True)
    frame = np.frombuffer(bmpstr, dtype=np.uint8).reshape((h, w, 4))
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    return frame[...,:3].copy()

# --- 3. 높이 및 거리 측정 함수 ---
def estimate_from_color(frame):
    h, w, _ = frame.shape
    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    shrink_w, shrink_h = int(w * 0.02), int(h * 0.02)
    analysis_area = hsv_frame[shrink_h:h-shrink_h, shrink_w:w-shrink_w]
    ah, aw, _ = analysis_area.shape
    
    # [수정된 부분] ROI를 이전 버전으로 되돌림 (폭 40%, 높이 60% 지점)
    roi_top_y = int(ah * 0.6)
    roi_points = np.array([
        [int(aw * 0.3), roi_top_y],
        [int(aw * 0.7), roi_top_y],
        [aw, ah],
        [0, ah]
    ], dtype=np.int32)

    lower_blue = np.array([100, 70, 50])
    upper_blue = np.array([130, 255, 255])
    object_mask = cv2.bitwise_not(cv2.inRange(analysis_area, lower_blue, upper_blue))
    roi_mask = np.zeros(analysis_area.shape[:2], dtype="uint8")
    cv2.fillPoly(roi_mask, [roi_points], 255)
    object_in_roi_mask = cv2.bitwise_and(object_mask, roi_mask)
    
    contours, _ = cv2.findContours(object_in_roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return (0.0, 0.0), None, roi_points, (shrink_w, shrink_h)

    min_area = (aw * ah) * 0.005
    max_area = (aw * ah) * 0.30
    valid_contours = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                if aw * 0.15 < cx < aw * 0.85:
                    valid_contours.append(cnt)
    
    if not valid_contours: return (0.0, 0.0), None, roi_points, (shrink_w, shrink_h)

    largest_contour = max(valid_contours, key=cv2.contourArea)
    
    # 높이 계산
    contour_mask = np.zeros(analysis_area.shape[:2], dtype="uint8")
    cv2.drawContours(contour_mask, [largest_contour], -1, 255, -1)
    hue_channel = analysis_area[:,:,0]
    obj_hues = hue_channel[contour_mask == 255]
    if len(obj_hues) < 20: return (0.0, 0.0), None, roi_points, (shrink_w, shrink_h)
    
    peak_hue = np.median(obj_hues)
    estimated_height = MAX_HEIGHT_M * (1 - min(peak_hue, 120) / 120.0)

    # 거리 계산
    bottom_y = largest_contour[:, 0, 1].max()
    normalized_y = (bottom_y - roi_top_y) / (ah - roi_top_y) if (ah - roi_top_y) > 0 else 0
    
    y_points = sorted(list(DISTANCE_CALIBRATION_POINTS.keys()))
    dist_points = [DISTANCE_CALIBRATION_POINTS[y] for y in y_points]
    
    estimated_distance = np.interp(normalized_y, y_points, dist_points)

    return (estimated_height, estimated_distance), largest_contour, roi_points, (shrink_w, shrink_h)

# --- 메인 루프 ---
def main():
    print("색상 기반 높이/거리 자동 추정을 시작합니다. ('q' - 종료)")
    
    while True:
        frame = capture_window_by_title(TARGET_WINDOW_TITLE)
        if frame is None:
            time.sleep(1); continue

        (height, distance), contour, roi_points, offset = estimate_from_color(frame)
        
        roi_points_orig = roi_points + offset
        cv2.polylines(frame, [roi_points_orig], isClosed=True, color=(255, 0, 0), thickness=2)
        
        if contour is not None:
            contour_orig = contour + offset
            cv2.drawContours(frame, [contour_orig], -1, (0, 255, 0), 2)
            cv2.putText(frame, f"Height: {height:.3f} m", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Distance: {distance:.2f} m", (20, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Height and Distance Estimation", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()