import ctypes
import win32gui
import win32ui
import numpy as np
import cv2

# 창 이름
LEFT_WINDOW = "경관 위치 <left>"
RIGHT_WINDOW = "경관 위치 <right>"

# 스테레오 설정
BASELINE = 0.3  # meters
FOCAL_LENGTH_PIXELS = 700  # 추정값 (px)

# ──────────────────────────────
# 창 캡처 함수
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
    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((height, width, 4))[..., :3]
    win32gui.ReleaseDC(hwnd, hwndDC)
    return img

# ──────────────────────────────
# 사다리꼴 ROI 생성 함수
def get_trapezoid_mask(shape):
    height, width = shape
    mask = np.zeros((height, width), dtype=np.uint8)
    top_y = int(height * 0.4)
    pts = np.array([[
        (int(width * 0.15), top_y),
        (int(width * 0.85), top_y),
        (width, height),
        (0, height)
    ]], dtype=np.int32)
    cv2.fillPoly(mask, pts, 255)
    return mask

# ──────────────────────────────
# 깊이 계산 함수
def calculate_depth(disparity):
    disparity[disparity <= 0] = 0.1
    return (FOCAL_LENGTH_PIXELS * BASELINE) / disparity

# ──────────────────────────────
# 형태학적 필터 적용
def apply_morph_filter(img):
    kernel = np.ones((3, 3), np.uint8)
    img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
    return img

# ──────────────────────────────
# ROI 내 Feature 정량 추출
def extract_feature_region(depth_map, mask):
    masked_depth = cv2.bitwise_and(depth_map, depth_map, mask=mask)
    masked_depth = np.where((masked_depth > 0.1) & (masked_depth < 100.0), masked_depth, 0)
    roi_depth = masked_depth[masked_depth > 0]
    if roi_depth.size == 0:
        return 0, 0, 0
    return np.mean(roi_depth), np.min(roi_depth), np.max(roi_depth)

# ──────────────────────────────
# 메인 루프
def main():
    hwnd_left = win32gui.FindWindow(None, LEFT_WINDOW)
    hwnd_right = win32gui.FindWindow(None, RIGHT_WINDOW)
    if hwnd_left == 0 or hwnd_right == 0:
        print("One or both windows not found.")
        return

    print("[INFO] Stereo Depth Estimation Started")

    # StereoSGBM + WLS
    min_disp = 0
    num_disp = 64
    block_size = 6
    sgbm = cv2.StereoSGBM_create(
        minDisparity=min_disp,
        numDisparities=num_disp,
        blockSize=block_size,
        P1=8 * 3 * block_size ** 2,
        P2=32 * 3 * block_size ** 2,
        disp12MaxDiff=1,
        uniquenessRatio=12,
        speckleWindowSize=90,
        speckleRange=28
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

        disp_left = sgbm.compute(left_gray, right_gray).astype(np.float32) / 16.0
        disp_right = right_matcher.compute(right_gray, left_gray).astype(np.float32) / 16.0
        filtered_disp = wls_filter.filter(disp_left, left_gray, None, disp_right)

        mask = get_trapezoid_mask(left_gray.shape)
        filtered_disp = apply_morph_filter(filtered_disp)
        filtered_disp = cv2.bitwise_and(filtered_disp, filtered_disp, mask=mask)

        depth = calculate_depth(filtered_disp)
        mean_depth, min_depth, max_depth = extract_feature_region(depth, mask)

        disp_vis = cv2.normalize(filtered_disp, None, 0, 255, cv2.NORM_MINMAX)
        disp_vis = np.uint8(disp_vis)
        disp_color = cv2.applyColorMap(disp_vis, cv2.COLORMAP_JET)
        cv2.putText(disp_color, f"Mean: {mean_depth:.2f}m", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        cv2.putText(disp_color, f"Min: {min_depth:.2f}m", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        cv2.putText(disp_color, f"Max: {max_depth:.2f}m", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

        cv2.imshow("Left View", left_gray)
        cv2.imshow("Disparity (WLS)", disp_color)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
