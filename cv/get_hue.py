import cv2
import numpy as np
import win32gui, win32ui, win32con
import time

def capture_window_by_title(window_title):
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd == 0: return None
    left, top, right, bot = win32gui.GetClientRect(hwnd)
    w, h = right - left, bot - top
    if w < 2 or h < 2: return None
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
    saveDC.DeleteDC(); mfcDC.DeleteDC(); win32gui.ReleaseDC(hwnd, hwndDC)
    return frame[..., :3].copy()

if __name__ == "__main__":
    HEIGHT_WINDOW_TITLE = "경관 위치 <test>"
    print("Hue 진단을 시작합니다. 종료하려면 'q' 키를 누르세요.")

    # ==========================================================
    # ### 진단용 설정값 (이 값들을 조절하세요) ###
    # ==========================================================
    ROI_SETTINGS = {
        'top_y': 0.6, 
        'bottom_y': 0.98,
        'top_w': 0.25, 
        'bottom_w': 0.95
    }
    HUE_SETTINGS = {
        'lower': 0, 
        'upper': 95 
    }
    # ==========================================================

    while True:
        frame = capture_window_by_title(HEIGHT_WINDOW_TITLE)
        if frame is None:
            print(f"'{HEIGHT_WINDOW_TITLE}' 창을 찾을 수 없습니다. 1초 후 재시도합니다.")
            time.sleep(1)
            continue
            
        h, w, _ = frame.shape

        # --- ROI 생성 ---
        top_y = int(h * ROI_SETTINGS['top_y'])
        bottom_y = int(h * ROI_SETTINGS['bottom_y'])
        top_x_start = int(w/2 - (w * ROI_SETTINGS['top_w'] / 2))
        top_x_end = int(w/2 + (w * ROI_SETTINGS['top_w'] / 2))
        bottom_x_start = int(w/2 - (w * ROI_SETTINGS['bottom_w'] / 2))
        bottom_x_end = int(w/2 + (w * ROI_SETTINGS['bottom_w'] / 2))

        roi_points = np.array([
            (top_x_start, top_y), (top_x_end, top_y),
            (bottom_x_end, bottom_y), (bottom_x_start, bottom_y)
        ], dtype=np.int32)
        
        roi_mask = np.zeros_like(frame[:, :, 0])
        cv2.fillPoly(roi_mask, [roi_points], 255)

        # --- Hue 필터링 및 분석 ---
        hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h_channel = hsv_img[:,:,0]
        
        hue_mask = cv2.inRange(h_channel, HUE_SETTINGS['lower'], HUE_SETTINGS['upper'])
        
        hue_roi_mask = cv2.bitwise_and(hue_mask, roi_mask)

        # 터미널에 감지된 Hue 값들의 통계 출력
        hue_values_detected = h_channel[np.nonzero(hue_roi_mask)]
        if len(hue_values_detected) > 100: # 최소 100픽셀 이상 감지 시
            min_h = np.min(hue_values_detected)
            max_h = np.max(hue_values_detected)
            avg_h = np.mean(hue_values_detected)
            print(f"감지된 Hue 범위: Min={min_h}, Max={max_h}, Avg={avg_h:.2f}")
        else:
            print("감지된 Hue 없음")

        # --- 시각화 ---
        cv2.polylines(frame, [roi_points], isClosed=True, color=(0, 255, 0), thickness=2)
        
        contours, _ = cv2.findContours(hue_roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            cv2.drawContours(frame, contours, -1, (255, 255, 255), 2)

        cv2.imshow("Real-time Hue Diagnostic", frame)
        cv2.imshow("Hue Filter Result (흰색: 감지 영역)", hue_roi_mask)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
        time.sleep(0.1)

    cv2.destroyAllWindows()
    print("분석을 종료합니다.")