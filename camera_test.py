import win32gui, win32con, win32ui
import cv2
import numpy as np
import time

# 윈도우 핸들 가져오기
top_view = win32gui.FindWindow(None, "경관 위치 <top>")
left_view = win32gui.FindWindow(None, "경관 위치 <left>")
right_view = win32gui.FindWindow(None, "경관 위치 <right>")

# 윈도우 캡처 함수
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
    saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)

    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    
    img = np.frombuffer(bmpstr, dtype='uint8')
    img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
    
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

# 과속방지턱 패턴 인식 함수
def pattern_detection(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_white = np.array([0, 0, 200])
    upper_white = np.array([180, 50, 255])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)

    kernel = np.ones((5, 5), np.uint8)
    mask_clean = cv2.morphologyEx(mask_white, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000:
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, 'Pattern Detected', (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return frame, len(contours)

# 스테레오 시차맵 생성 함수
def compute_disparity(left_img, right_img):
    # 그레이스케일 변환
    left_gray = cv2.cvtColor(left_img, cv2.COLOR_BGR2GRAY)
    right_gray = cv2.cvtColor(right_img, cv2.COLOR_BGR2GRAY)

    # StereoBM 생성
    stereo = cv2.StereoBM_create(numDisparities=16*3, blockSize=15)
    disparity = stereo.compute(left_gray, right_gray)

    # 시각화를 위한 정규화
    disp_normalized = cv2.normalize(disparity, None, 0, 255, cv2.NORM_MINMAX)
    disp_normalized = np.uint8(disp_normalized)

    return disp_normalized

# Main Loop
while True:
    top_img = capture_window(top_view)
    left_img = capture_window(left_view)
    right_img = capture_window(right_view)

    # Top View 패턴 인식
    top_result, pattern_count = pattern_detection(top_img)
    cv2.imshow("Top Pattern Detection", top_result)

    # 스테레오 시차맵 생성 (좌/우)
    disparity_map = compute_disparity(left_img, right_img)
    cv2.imshow("Stereo Disparity", disparity_map)

    # 개별 뷰도 그대로 출력
    cv2.imshow("LEFT", top_img)
    cv2.imshow("LEFT", left_img)
    cv2.imshow("RIGHT", right_img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
