# -*- coding: utf-8 -*-
import ctypes, math, time
import numpy as np
import cv2, win32gui, win32ui

# ================= 사용자 설정(빠른 모드 기본) =================
LEFT_TITLE_PART  = "left"     # 좌측 창 제목 일부
RIGHT_TITLE_PART = "right"    # 우측 창 제목 일부

BASELINE_M = 0.280            # UC-win 좌/우 Z=±0.140 m → B=0.280 m로 고정

# f(px) 결정: 1) 직접 px 2) 수직 FOV 3) 가로 FOV 4) 추정치(700)
FOCAL_LENGTH_PIXELS_OVERRIDE = None
VERTICAL_FOV_DEG   = 45.0     # 수직 FOV. 모르면 None
HORIZONTAL_FOV_DEG = None

# SGBM 파라미터(속도 우선)
MIN_DISP   = 0
NUM_DISP   = 64               # 16의 배수. 품질↑면 128로
BLOCK_SIZE = 5                # 홀수. 텍스처 부족 시 7
UNIQUENESS = 10
SPECKLE_WS = 90
SPECKLE_R  = 28
DISP12_MAXDIFF = 1

# 후처리/안정화
USE_WLS = False               # 느리면 False 권장(빠른 모드)
WLS_LAMBDA = 8000
WLS_SIGMA_COLOR = 1.5

ENABLE_VERTICAL_ALIGNMENT = False    # 흔들림 많으면 True
ALIGN_WIN_H = 80                     # 정렬용 윈도 높이(px)

TEMPORAL_EMA = True
EMA_ALPHA = 0.7                      # 0.6~0.85

# 좌측 파란 띠 제거용: 왼쪽 무효 영역 크롭
LEFT_TRIM = NUM_DISP                 # 일반적으로 numDisparities와 동일

# ROI(노면 중심 비중↑)
ROI_TOP_RATIO = 0.52
ROI_LEFT_XR   = 0.15
ROI_RIGHT_XR  = 0.85

DEPTH_MIN = 0.10
DEPTH_MAX = 100.0

SHOW_LEFT_GRAY = False
MAX_SKEW_MS = 50.0                   # 좌/우 캡처 시점 차 허용(ms)
SHOW_PROFILE = False                 # 처리시간 로그

PW_CLIENTONLY = 1

# ================= 윈도우 찾기(부분 제목) =================
def find_window_by_partial(title_part: str):
    title_part = title_part.lower()
    found = {"hwnd": 0}
    def cb(hwnd, _):
        t = win32gui.GetWindowText(hwnd)
        if t and title_part in t.lower():
            found["hwnd"] = hwnd
            return False
        return True
    win32gui.EnumWindows(cb, None)
    return found["hwnd"]

# ================= 캡처(리소스 정리 철저) =================
def capture_window(hwnd):
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0: return None
    hwndDC = mfcDC = saveDC = saveBmp = old_obj = None
    try:
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        saveBmp = win32ui.CreateBitmap()
        saveBmp.CreateCompatibleBitmap(mfcDC, width, height)
        old_obj = saveDC.SelectObject(saveBmp)
        ok = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_CLIENTONLY)
        if not ok: return None
        bmp = saveBmp.GetBitmapBits(True)
        img = np.frombuffer(bmp, dtype=np.uint8).reshape((height, width, 4))[..., :3]
        return img
    finally:
        if saveDC is not None and old_obj is not None:
            try: saveDC.SelectObject(old_obj)
            except: pass
        if saveBmp is not None:
            try: win32gui.DeleteObject(saveBmp.GetHandle())
            except: pass
        if saveDC is not None:
            try: saveDC.DeleteDC()
            except: pass
        if mfcDC is not None:
            try: mfcDC.DeleteDC()
            except: pass
        if hwndDC is not None:
            try: win32gui.ReleaseDC(hwnd, hwndDC)
            except: pass

# ================= FOV -> f(px) =================
def f_from_vfov(h_px, vfov_deg):
    r = math.radians(vfov_deg);  return (h_px/2.0)/math.tan(r/2.0)
def f_from_hfov(w_px, hfov_deg):
    r = math.radians(hfov_deg);  return (w_px/2.0)/math.tan(r/2.0)
def get_f_pixels(W, H):
    if FOCAL_LENGTH_PIXELS_OVERRIDE is not None: return float(FOCAL_LENGTH_PIXELS_OVERRIDE)
    if VERTICAL_FOV_DEG   is not None: return f_from_vfov(H, VERTICAL_FOV_DEG)
    if HORIZONTAL_FOV_DEG is not None: return f_from_hfov(W, HORIZONTAL_FOV_DEG)
    return 700.0  # 추정치

# ================= ROI/형태학/깊이 =================
def get_trapezoid_mask(h, w, left_trim):
    mask = np.zeros((h, w), dtype=np.uint8)
    x0 = max(left_trim, 0)  # 왼쪽 무효영역 제외
    top_y = int(h * ROI_TOP_RATIO)
    pts = np.array([[
        (max(x0, int(w * ROI_LEFT_XR)), top_y),
        (int(w * ROI_RIGHT_XR), top_y),
        (w-1, h-1),
        (x0,  h-1)
    ]], dtype=np.int32)
    cv2.fillPoly(mask, pts, 255)
    return mask

def morph_mask(mask_u8):
    k = np.ones((3,3), np.uint8)
    m = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN,  k)
    m = cv2.morphologyEx(m,       cv2.MORPH_CLOSE, k)
    return m

def disparity_to_depth(disp_f32, f_px, B_m):
    d = disp_f32.copy();  d[d <= 0.0] = np.nan
    return (f_px * B_m) / (d + 1e-9)

def extract_depth_stats(depth_m, valid_u8):
    valid = valid_u8 > 0
    dm = depth_m.copy()
    dm[~valid] = np.nan
    dm[(dm < DEPTH_MIN) | (dm > DEPTH_MAX)] = np.nan
    vals = dm[~np.isnan(dm)]
    if vals.size == 0: return 0.0, 0.0, 0.0
    return float(np.nanmean(vals)), float(np.nanmin(vals)), float(np.nanmax(vals))

# ================= WLS 호환 래퍼 =================
def make_wls(left_matcher):
    try:
        wls = cv2.ximgproc.createDisparityWLSFilter(matcher_left=left_matcher)
    except TypeError:
        wls = cv2.ximgproc.createDisparityWLSFilter(left_matcher)
    wls.setLambda(WLS_LAMBDA)
    wls.setSigmaColor(WLS_SIGMA_COLOR)
    return wls

def apply_wls(wls, disp_l, Lg, disp_r, Rg, right_matcher):
    if hasattr(wls, "setRightMatcher") and right_matcher is not None:
        try: wls.setRightMatcher(right_matcher)
        except: pass
    try:  return wls.filter(disp_l, Lg, None, disp_r)
    except TypeError: pass
    try:  return wls.filter(disp_l, Lg, disp_r)
    except TypeError: pass
    return wls.filter(disp_l, Lg)

# ================= 수직 정렬(작은 dy 보정) =================
def align_vertical_via_phasecorr(Lg, Rg, win_h=80):
    h, w = Lg.shape[:2]
    h0 = max(0, int(h * (ROI_TOP_RATIO - 0.1)))
    h1 = min(h, h0 + win_h)
    if h1 - h0 < 20: return Rg
    a = Lg[h0:h1, :]; b = Rg[h0:h1, :]
    a32 = np.float32(a) - np.mean(a)
    b32 = np.float32(b) - np.mean(b)
    (dx, dy), _ = cv2.phaseCorrelate(b32, a32)  # b->a
    dy = int(round(dy))
    if dy == 0: return Rg
    M = np.float32([[1,0,0],[0,1,dy]])
    return cv2.warpAffine(Rg, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

# ================= 메인 =================
def main():
    hwnd_left  = find_window_by_partial(LEFT_TITLE_PART)
    hwnd_right = find_window_by_partial(RIGHT_TITLE_PART)
    if hwnd_left == 0 or hwnd_right == 0:
        print("Left/Right 창을 찾지 못했습니다."); return

    L0 = capture_window(hwnd_left)
    R0 = capture_window(hwnd_right)
    if L0 is None or R0 is None:
        print("초기 캡처 실패."); return
    H, W = L0.shape[:2]
    if R0.shape[:2] != (H, W):
        print("좌/우 창 해상도가 다릅니다."); return

    f_px = get_f_pixels(W, H)
    print(f"[INFO] Stereo | f(px)={f_px:.2f}, B={BASELINE_M:.3f} m, size={W}x{H}")

    roi_mask_full = get_trapezoid_mask(H, W, LEFT_TRIM)

    sgbm = cv2.StereoSGBM_create(
        minDisparity=MIN_DISP,
        numDisparities=NUM_DISP,
        blockSize=BLOCK_SIZE,
        P1=8 * 3 * (BLOCK_SIZE**2),
        P2=32 * 3 * (BLOCK_SIZE**2),
        disp12MaxDiff=DISP12_MAXDIFF,
        uniquenessRatio=UNIQUENESS,
        speckleWindowSize=SPECKLE_WS,
        speckleRange=SPECKLE_R,
        preFilterCap=31,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
    )
    right_matcher = cv2.ximgproc.createRightMatcher(sgbm)
    wls = make_wls(sgbm) if USE_WLS else None

    prev_filtered = None

    while True:
        t0 = time.perf_counter()
        L = capture_window(hwnd_left)
        t1 = time.perf_counter()
        R = capture_window(hwnd_right)
        t2 = time.perf_counter()

        if L is None or R is None:
            if cv2.waitKey(1) & 0xFF == ord('q'): break
            continue

        # 좌/우 캡처 시점 차가 크면 스킵(끊김 완화)
        skew_ms = (t2 - t1) * 1000.0
        if skew_ms > MAX_SKEW_MS:
            continue

        if L.shape[:2] != (H, W) or R.shape[:2] != (H, W):
            H, W = L.shape[:2]
            f_px = get_f_pixels(W, H)
            roi_mask_full = get_trapezoid_mask(H, W, LEFT_TRIM)
            print(f"[INFO] Resize → f(px)={f_px:.2f}, size={W}x{H}")

        Lg = cv2.cvtColor(L, cv2.COLOR_BGR2GRAY)
        Rg = cv2.cvtColor(R, cv2.COLOR_BGR2GRAY)

        if ENABLE_VERTICAL_ALIGNMENT:
            Rg = align_vertical_via_phasecorr(Lg, Rg, win_h=ALIGN_WIN_H)

        t3 = time.perf_counter()
        disp_l = sgbm.compute(Lg, Rg).astype(np.float32) / 16.0
        if USE_WLS:
            disp_r = right_matcher.compute(Rg, Lg).astype(np.float32) / 16.0
            filtered = apply_wls(wls, disp_l, Lg, disp_r, Rg, right_matcher)
        else:
            filtered = disp_l
        t4 = time.perf_counter()

        # 좌측 무효 영역 크롭(파란 띠 제거)
        filtered = filtered[:, LEFT_TRIM:]
        roi_mask  = roi_mask_full[:, LEFT_TRIM:]

        # 시차 EMA 스무딩
        if TEMPORAL_EMA and prev_filtered is not None:
            filtered = EMA_ALPHA * filtered + (1.0 - EMA_ALPHA) * prev_filtered
        prev_filtered = filtered.copy()

        valid = (filtered > 0.0).astype(np.uint8) * 255
        valid = morph_mask(valid)
        valid = cv2.bitwise_and(valid, roi_mask)

        depth = disparity_to_depth(filtered, f_px, BASELINE_M)
        mean_d, min_d, max_d = extract_depth_stats(depth, valid)

        # 시각화
        disp_vis = cv2.normalize(filtered, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        disp_color = cv2.applyColorMap(disp_vis, cv2.COLORMAP_JET)
        edges = cv2.Canny(roi_mask, 50, 150)
        disp_color[edges > 0] = (255, 255, 255)

        cv2.putText(disp_color, f"f(px): {f_px:.1f}  B: {BASELINE_M:.3f} m",
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        cv2.putText(disp_color, f"Mean: {mean_d:.2f} m  Min: {min_d:.2f} m  Max: {max_d:.2f} m",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        if SHOW_LEFT_GRAY:
            cv2.imshow("Left View (gray)", Lg)
        cv2.imshow("Disparity (WLS)" if USE_WLS else "Disparity", disp_color)

        if SHOW_PROFILE:
            total_ms = (time.perf_counter() - t0) * 1000.0
            sgbm_ms  = (t4 - t3) * 1000.0
            print(f"skew:{skew_ms:5.1f} ms  sgbm+post:{sgbm_ms:5.1f} ms  total:{total_ms:5.1f} ms")

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
