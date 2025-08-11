import ctypes
import win32gui
import win32ui
import numpy as np
import cv2

# 창 이름
LEFT_WINDOW = "경관 위치 <left>"
RIGHT_WINDOW = "경관 위치 <right>"

# 스테레오 파라미터
BASELINE = 0.3  # meters
FOCAL_LENGTH_PIXELS = 700  # px 단위 focal length (예상값)

# ─────────────────────────────
def capture_window(hwnd):
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width, height = right - left, bottom - top

    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)

    ctypes.windll.dwmapi.DwmEnableComposition(1)
    ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

    bmpstr = saveBitMap.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((height, width, 4))[:, :, :3]  # BGRA → BGR
    win32gui.ReleaseDC(hwnd, hwndDC)
    return img

# ─────────────────────────────
def get_trapezoid_mask(shape):
    height, width = shape
    mask = np.zeros((height, width), dtype=np.uint8)
    top_y = int(height * 0.3)
    pts = np.array([[
        (int(width * 0.2), top_y),
        (int(width * 0.8), top_y),
        (width, height),
        (0, height)
    ]], dtype=np.int32)
    cv2.fillPoly(mask, pts, 255)
    return mask

# ─────────────────────────────
def calculate_depth(disparity):
    disparity[disparity <= 0.0] = 0.1
    return (FOCAL_LENGTH_PIXELS * BASELINE) / disparity

# ─────────────────────────────
if __name__ == "__main__":
    print("[INFO] Stereo depth estimation with ROI + SGBM + WLS + Filter")

    hwnd_left = win32gui.FindWindow(None, LEFT_WINDOW)
    hwnd_right = win32gui.FindWindow(None, RIGHT_WINDOW)
    if hwnd_left == 0 or hwnd_right == 0:
        print("❌ One or both windows not found!")
        exit()

    # StereoSGBM 설정
    min_disp = 0
    num_disp = 64
    block_size = 5
    sgbm = cv2.StereoSGBM_create(
        minDisparity=min_disp,
        numDisparities=num_disp,
        blockSize=block_size,
        P1=8 * 3 * block_size ** 2,
        P2=32 * 3 * block_size ** 2,
        disp12MaxDiff=1,
        uniquenessRatio=10,
        speckleWindowSize=100,
        speckleRange=32
    )

    right_matcher = cv2.ximgproc.createRightMatcher(sgbm)
    wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_left=sgbm)
    wls_filter.setLambda(8000)
    wls_filter.setSigmaColor(1.5)

    while True:
        left_img = capture_window(hwnd_left)
        right_img = capture_window(hwnd_right)

        left_gray = cv2.cvtColor(cv2.resize(left_img, (640, 480)), cv2.COLOR_BGR2GRAY)
        right_gray = cv2.cvtColor(cv2.resize(right_img, (640, 480)), cv2.COLOR_BGR2GRAY)

        # Disparity 계산
        disp_left = sgbm.compute(left_gray, right_gray).astype(np.float32) / 16.0
        disp_right = right_matcher.compute(right_gray, left_gray).astype(np.float32) / 16.0

        # WLS 필터 적용
        disp_filtered = wls_filter.filter(disp_left, left_gray, None, disp_right)

        # ROI 마스크 생성
        mask = get_trapezoid_mask(left_gray.shape)
        disp_roi = cv2.bitwise_and(disp_filtered, disp_filtered, mask=mask)

        # Thresholding & Morphological Filtering
        _, disp_thresh = cv2.threshold(disp_roi, 1.0, 255, cv2.THRESH_TOZERO)
        disp_thresh = np.uint8(cv2.normalize(disp_thresh, None, 0, 255, cv2.NORM_MINMAX))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        disp_morph = cv2.morphologyEx(disp_thresh, cv2.MORPH_CLOSE, kernel)

        # Depth 계산
        depth_map = calculate_depth(disp_roi)
        roi_depth = depth_map[mask == 255]
        mean_depth = np.mean(roi_depth)
        min_depth = np.min(roi_depth)
        max_depth = np.max(roi_depth)

        # 시각화
        disp_vis = cv2.applyColorMap(disp_morph, cv2.COLORMAP_JET)
        cv2.putText(disp_vis, f"Mean: {mean_depth:.2f}m", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        cv2.putText(disp_vis, f"Min: {min_depth:.2f}m", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        cv2.putText(disp_vis, f"Max: {max_depth:.2f}m", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

        # 결과 표시
        cv2.imshow("Left View", left_gray)
        cv2.imshow("Disparity (WLS + Filtered)", disp_vis)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
