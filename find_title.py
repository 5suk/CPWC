import win32gui, win32con, win32ui
import cv2
import numpy as np
import time

def enum_windows():
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            print(win32gui.GetWindowText(hwnd))

    win32gui.EnumWindows(callback, None)

enum_windows()
