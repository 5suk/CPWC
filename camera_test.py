import win32gui, win32con, win32ui
import cv2
import numpy as np
import time

top_view = win32gui.FindWindow(None, "경관 위치 <Drive_top>")
left_view = win32gui.FindWindow(None, "경관 위치 <Drive_left>")
right_view = win32gui.FindWindow(None, "경관 위치 <Drive_right>")

def capture_window(hwnd):
    left, top, right, bottom = win32gui.GetClientRect(hwnd) # GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)
    saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
    # win32gui.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0)

    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    
    img = np.frombuffer(bmpstr, dtype='uint8')
    img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
    
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

while True:
    top_img = capture_window(top_view)
    cv2.imshow("TOP", top_img)
    left_img = capture_window(left_view)
    cv2.imshow("LEFT", left_img)
    right_img = capture_window(right_view)
    cv2.imshow("RIGHT", right_img)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break