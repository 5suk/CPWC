import ctypes
import win32gui
import win32con
import win32ui
import numpy as np
import cv2

# 윈도우 핸들 얻기 (창 제목 기준)
hwnd = win32gui.FindWindow(None, "경관 위치 <top>")  # 창 제목을 정확히 입력할 것

if hwnd == 0:
    print("Window not found!")
    exit()

# 윈도우 클라이언트 영역 크기 구하기
left, top, right, bottom = win32gui.GetClientRect(hwnd)
width = right - left
height = bottom - top

# DC 준비
hwndDC = win32gui.GetWindowDC(hwnd)
mfcDC = win32ui.CreateDCFromHandle(hwndDC)
saveDC = mfcDC.CreateCompatibleDC()

# Bitmap 준비
saveBitMap = win32ui.CreateBitmap()
saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
saveDC.SelectObject(saveBitMap)

# DWM 기반 비활성화 방지 설정 (가려져도 캡처)
ctypes.windll.dwmapi.DwmEnableComposition(1)

# 캡처 루프
while True:
    result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)  # PW_RENDERFULLCONTENT 옵션 사용
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)

    img = np.frombuffer(bmpstr, dtype=np.uint8)
    img.shape = (height, width, 4)

    # BGRA → BGR 변환
    img = img[..., :3]

    # 화면 출력
    cv2.imshow("Captured Window", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 해제
win32gui.ReleaseDC(hwnd, hwndDC)
cv2.destroyAllWindows()
