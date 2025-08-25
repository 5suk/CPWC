# -*- coding: utf-8 -*-
"""
두 번 연속 주행:
  [사전(Camera)]
    - 카메라 높이 추정(색 기반 최고점 + 기하 보조)
    - 임계: ≤7cm 유지 / ≥8cm 감속(20km/h) / ≥18cm 10km/h
    - RMS(pred) 로그 출력
    - 놓침 대비: dead-reckoning + sticky TTL
    - EMA: 상승 빨리 / 하강 천천히 (비대칭)

  [정밀(GT)]
    - GT: Z=길이(폭) L, Y=높이 h 사용
    - 목표 RMS(<=0.50)로 속도 계산 + 표준 캡(≥10cm→20km/h, ≥18cm→10km/h)
    - 감속이 필요할 때만 SetSpeed

공통:
  - 트리거: 방지턱까지 15 m 남았을 때(>15 → ≤15) 1회 판단
"""

import time, math
import numpy as np
import cv2
import win32com.client
from win32com.client import Dispatch, GetActiveObject
import win32gui, win32ui, win32con

# ================== UC-win attach ==================
PROGID = "UCwinRoad.F8ApplicationServicesProxy"
def attach_or_launch():
    try:    return GetActiveObject(PROGID)
    except: return Dispatch(PROGID)

# ================== 사용자 설정 ==================
SAMPLE_HZ = 10.0
DT = 1.0 / SAMPLE_HZ

# 속도 정책
UNIT = 0                    # 0=SI(m/s)
DECEL_FIXED_KMH = 20.0      # (사전) 기본 감속 목표
HARD_CAP_10_KMH = 10.0      # 18cm 이상일 때 강제 10km/h

# 트리거 & 임계
TRIGGER_DIST_M   = 14.0
HEIGHT_KEEP_CM   = 7.0      # ≤7.0cm 유지
HEIGHT_DECEL_CM  = 8.0      # ≥8.0cm 감속(20km/h)
CAMERA_HARD_CAP_CM = 18.0   # ≥18cm 10km/h

HEIGHT_MIN_M     = 0.02     # 카메라 노이즈 컷
HEIGHT_MAX_M     = 0.20     # 카메라 상한(5~20cm)
HEIGHT_ALPHA     = 0.6      # (기본 EMA 가중; 아래 비대칭 EMA에서 사용 안 함)

# 카메라 놓침 보호
MISS_HOLD_SEC = 1.0         # 높이 sticky TTL(초)

# 시나리오 인덱스
SCENARIO_INDEX = 0

# === RMS 캘리브레이션 ===
# 기준: v=30 km/h, h=0.15 m, L=3 m → RMS(target)=1.00
# raw(기준) ≈ 8.077389 → gain = 1.00 / raw
CAL_GAIN = 0.12380238

# “쾌적함” 목표 상한
COMFORT_RMS_MAX = 0.50      # ISO 2631 “쾌적함” 상한

# (사전)에서 사용할 방지턱 폭(진행방향 길이)
BUMP_WIDTH_M = 3.0

# GT(정답) 방지턱 사양 (순서대로 4개)
GT_BUMPS = [
    {"L": 3.60, "h": 0.10},   # 1번
    {"L": 3.60, "h": 0.20},   # 2번
    {"L": 3.60, "h": 0.10},   # 3번
    {"L": 3.60, "h": 0.00},   # 4번(평탄)
]

# 화면 캡처/검출
TARGET_WINDOW_TITLE = "경관 위치 <test>"
DISTANCE_CALIBRATION_POINTS = {0.0: 17.0, 0.5: 8.0, 1.0: 2.0}  # ROI y→거리 보간

# ----------------------------------------------------------------
# 카메라 캡처
# ----------------------------------------------------------------
DEBUG_PRINT = False
MAX_HEIGHT_M = HEIGHT_MAX_M

def capture_window_by_title(window_title):
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd == 0:
        return None
    left, top, right, bot = win32gui.GetClientRect(hwnd)
    w, h = right - left, bot - top
    if w == 0 or h == 0:
        return None

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

    # BGRA -> BGR
    return frame[..., :3].copy()

# ----------------------------------------------------------------
# 방지턱 높이 측정:
#  - 모든 유효 컨투어 평가
#  - 컨투어 내부 'per-pixel' 색 유사도로 높이 생성 후 상위 퍼센타일(최고점 근처) 사용
#  - 가장 높은 컨투어 선택
#  - 기하 신호는 20% 보조
# ----------------------------------------------------------------
def estimate_shape(frame):
    """
    반환: ((height_m, distance_m), best_contour, roi_points, (offset_w, offset_h))
    """
    # ===== 색 앵커/튜닝 =====
    RED_HEIGHT_M   = 0.24   # 빨강(높은 방지턱)
    GREEN_HEIGHT_M = 0.11   # 초록(낮은 방지턱)
    MID_HEIGHT_M   = 0.16   # 혼색/저채도 안전망
    H_RED_CENTERS  = [0.0, 179.0]   # 빨강은 0/179 근방
    H_GREEN_CENTER = 60.0
    H_SIGMA_DEG    = 14.0           # 10~18 권장
    W_COLOR, W_GEOM = 0.80, 0.20
    PEAK_Q = 95                     # 상위 95퍼센타일

    h, w, _ = frame.shape

    # 분석 영역 축소
    shrink_w, shrink_h = int(w * 0.02), int(h * 0.02)
    analysis_area_bgr = frame[shrink_h:h - shrink_h, shrink_w:w - shrink_w]
    ah, aw, _ = analysis_area_bgr.shape
    if ah <= 0 or aw <= 0:
        return (0.0, 0.0), None, np.array([[0,0]]), (shrink_w, shrink_h)

    # ROI(하단 사다리꼴)
    roi_top_y = int(ah * 0.6)
    roi_points = np.array([
        [int(aw * 0.30), roi_top_y],
        [int(aw * 0.70), roi_top_y],
        [aw, ah],
        [0,  ah]
    ], dtype=np.int32)
    roi_h = max(1, ah - roi_top_y)

    hsv_frame = cv2.cvtColor(analysis_area_bgr, cv2.COLOR_BGR2HSV)

    # 배경(푸른 톤) 제외
    lower_blue = np.array([100, 70, 50])
    upper_blue = np.array([130, 255, 255])
    not_blue_mask = cv2.bitwise_not(cv2.inRange(hsv_frame, lower_blue, upper_blue))

    roi_mask = np.zeros(hsv_frame.shape[:2], dtype="uint8")
    cv2.fillPoly(roi_mask, [roi_points], 255)
    object_in_roi_mask = cv2.bitwise_and(not_blue_mask, roi_mask)

    # 컨투어
    contours, _ = cv2.findContours(object_in_roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return (0.0, 0.0), None, roi_points, (shrink_w, shrink_h)

    min_area = (aw * ah) * 0.005
    max_area = (aw * ah) * 0.40
    valid_contours = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                if aw * 0.30 < cx < aw * 0.70:
                    valid_contours.append(cnt)
    if not valid_contours:
        return (0.0, 0.0), None, roi_points, (shrink_w, shrink_h)

    best_height, best_dist, best_cnt = 0.0, 0.0, None
    H, S, V = cv2.split(hsv_frame)

    for cnt in valid_contours:
        # 컨투어 마스크(침식으로 에지 제거)
        m = np.zeros(hsv_frame.shape[:2], np.uint8)
        cv2.drawContours(m, [cnt], -1, 255, -1)
        m = cv2.erode(m, np.ones((3,3), np.uint8), 1)
        idx = (m == 255)
        if idx.sum() < 20:
            continue

        # --- per-pixel 색 유사도 → per-pixel 높이 ---
        hpx = H[idx].astype(np.float32)           # 0..179
        spx = S[idx].astype(np.float32) / 255.0
        vpx = V[idx].astype(np.float32) / 255.0

        # 빨강/초록 유사도(원형 거리 가우시안)
        red_d0 = np.abs((hpx*2.0) - 0.0);   red_d0 = np.minimum(red_d0, 360.0-red_d0)
        red_d1 = np.abs((hpx*2.0) - 360.0); red_d1 = np.minimum(red_d1, 360.0-red_d1)
        red_sim = np.exp(-0.5 * (np.minimum(red_d0, red_d1)/H_SIGMA_DEG)**2)

        g_d = np.abs((hpx*2.0) - 60.0); g_d = np.minimum(g_d, 360.0-g_d)
        green_sim = np.exp(-0.5 * (g_d/H_SIGMA_DEG)**2)

        color_conf = np.clip(0.7*spx + 0.3*vpx, 0.0, 1.0)  # 픽셀별 신뢰도
        sum_sim = (red_sim + green_sim + 1e-6)
        w_red   = (red_sim   / sum_sim) * color_conf
        w_green = (green_sim / sum_sim) * color_conf
        w_mid   = 1.0 - color_conf

        height_px = w_red*RED_HEIGHT_M + w_green*GREEN_HEIGHT_M + w_mid*MID_HEIGHT_M

        # 최고점 강조: 상위 퍼센타일 사용
        color_height_peak = float(np.percentile(height_px, PEAK_Q))

        # --- 기하(보조) ---
        x, y, wc, hc = cv2.boundingRect(cnt)
        yb_norm   = float(np.clip((y + hc - roi_top_y) / roi_h, 0.0, 1.0))
        h_frac    = float(np.clip(hc / roi_h, 0.0, 1.0))
        area_frac = float(np.clip(cv2.contourArea(cnt) / float(aw*roi_h), 1e-6, 1.0))
        geom_score  = 0.55*h_frac + 0.35*yb_norm + 0.10*math.sqrt(area_frac)
        geom_score  = float(np.clip(geom_score, 0.0, 1.0))
        geom_height = float(np.interp(geom_score, [0.25, 0.75], [0.06, MAX_HEIGHT_M]))
        geom_height = float(np.clip(geom_height, 0.0, MAX_HEIGHT_M))

        # 최종 높이(색 0.8 + 기하 0.2)
        height_est = float(np.clip(W_COLOR*color_height_peak + W_GEOM*geom_height, 0.0, MAX_HEIGHT_M))

        # 거리(선택된 컨투어 하단 기준)
        y_points    = sorted(DISTANCE_CALIBRATION_POINTS.keys())
        dist_points = [DISTANCE_CALIBRATION_POINTS[y] for y in y_points]
        dist_est    = float(np.interp(yb_norm, y_points, dist_points))

        if height_est > best_height:
            best_height, best_dist, best_cnt = height_est, dist_est, cnt

    if best_cnt is None:
        return (0.0, 0.0), None, roi_points, (shrink_w, shrink_h)

    if DEBUG_PRINT:
        print(f"[dbg] pick height={best_height:.3f}m dist={best_dist:.2f}m")

    return (best_height, best_dist), best_cnt, roi_points, (shrink_w, shrink_h)

# ================== 시나리오 제어 ==================
def restart_scenario(sim, proj, idx=0):
    try:
        if hasattr(sim, "StopScenario"):
            sim.StopScenario()
            time.sleep(0.5)
    except Exception:
        pass
    sc = proj.Scenario(idx)
    sim.StartScenario(sc)
    time.sleep(1.0)

# ================== 공용 유틸 ==================
def kmh_to_mps(v): return v/3.6
def mps_to_kmh(v): return v*3.6

def unit_to_mps_factor(u: int) -> float:
    if u == 0: return 1.0
    if u == 1: return 1/3.6
    if u == 2: return 0.44704
    return 1.0

def _vec3(v):
    for names in (("X","Y","Z"), ("x","y","z")):
        if all(hasattr(v, n) for n in names):
            return float(getattr(v, names[0])), float(getattr(v, names[1])), float(getattr(v, names[2]))
    for m in ("Item","get_Item","GetAt","Get"):
        if hasattr(v, m):
            f = getattr(v, m); return float(f(0)), float(f(1)), float(f(2))
    seq = list(v); return float(seq[0]), float(seq[1]), float(seq[2])

def speed_kmh(drv):
    c = drv.CurrentCar
    if c is None: return 0.0
    try:
        sv = c.SpeedVector(UNIT)
    except TypeError:
        sv = c.SpeedVector() if callable(getattr(c,"SpeedVector",None)) else c.SpeedVector
    vx,vy,vz = _vec3(sv)
    f = unit_to_mps_factor(UNIT)
    v_mps = ((vx*f)**2 + (vy*f)**2 + (vz*f)**2) ** 0.5
    return mps_to_kmh(v_mps)

def set_speed_once_kmh(drv, v_kmh):
    c = drv.CurrentCar
    if c is None: return
    try:
        c.SetSpeed(kmh_to_mps(v_kmh), UNIT)
    except Exception:
        pass

# RMS 예측/분류
def predict_rms_raw(h_m: float, v_mps: float, L_m: float) -> float:
    if L_m <= 0 or h_m <= 0 or v_mps <= 0: return 0.0
    return (1.0/math.sqrt(2.0)) * ((math.pi * v_mps)/L_m)**2 * h_m

def predict_rms_cal(h_m: float, v_mps: float, L_m: float, gain: float = CAL_GAIN) -> float:
    return gain * predict_rms_raw(h_m, v_mps, L_m)

def classify_rms(r):
    if r < 0.315:  return "매우 쾌적함"
    elif r < 0.5:  return "쾌적함"
    elif r < 0.8:  return "약간 불쾌함"
    elif r < 1.25: return "불쾌함"
    else:          return "매우 불쾌함"

def solve_speed_for_target_rms(h_m: float, L_m: float, target_rms: float, gain: float = CAL_GAIN) -> float:
    if h_m <= 0 or L_m <= 0 or target_rms <= 0: return None
    denom = gain * (1.0/math.sqrt(2.0)) * h_m
    if denom <= 0: return None
    v_mps = (L_m / math.pi) * math.sqrt(target_rms / denom)
    return v_mps

# ================== 메인 ==================
def main():
    ucwin = attach_or_launch()
    sim = ucwin.SimulationCore
    proj = ucwin.Project

    # 시나리오 0 실행
    try:
        sc = proj.Scenario(SCENARIO_INDEX)
        sim.StartScenario(sc)
    except Exception:
        pass
    time.sleep(1.0)

    driver = sim.TrafficSimulation.Driver

    # 차량 핸들 확보
    car = None
    t0 = time.time()
    while car is None and time.time() - t0 < 15.0:
        car = driver.CurrentCar
        if car is None: time.sleep(0.2)
    if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")

    # 시작 로그
    v0 = speed_kmh(driver)
    print(f"[사전] 시작 속도 {v0:.0f} km/h, 트리거 {TRIGGER_DIST_M:.1f} m, 임계 높이 keep≤{HEIGHT_KEEP_CM:.1f}cm / slow≥{HEIGHT_DECEL_CM:.1f}cm")

    mode = "camera"           # "camera" → "gt"
    bump_idx = 0

    # 카메라/미스 방어 상태
    height_ema = None
    last_seen_dist = None
    last_seen_t = None
    h_sticky = 0.0
    h_sticky_t = 0.0
    prev_d_eff = None

    cv2.namedWindow("Bump Estimation", cv2.WINDOW_NORMAL)

    try:
        while True:
            loop_t = time.time()

            # 핸들 체크
            try:
                _ = car.Speed
            except Exception:
                car = driver.CurrentCar
                if car is None: time.sleep(DT); continue

            # 현재 속도 (가상거리 적분에 필요)
            v_kmh_now = speed_kmh(driver)
            v_mps_now = kmh_to_mps(v_kmh_now)

            # ---------- 카메라 추정 ----------
            frame = capture_window_by_title(TARGET_WINDOW_TITLE)
            est_h, est_d = 0.0, 0.0
            if frame is not None:
                (h_m, d_m), contour, roi_poly, offset = estimate_shape(frame)

                # === 비대칭 EMA: 상승 빨리 / 하강 천천히 ===
                if h_m > 0:
                    if height_ema is None:
                        height_ema = h_m
                    else:
                        ALPHA_UP = 0.20  # 값이 올라갈 때 과거 가중
                        ALPHA_DN = 0.70  # 값이 내려갈 때 과거 가중
                        if h_m > height_ema:
                            height_ema = ALPHA_UP*height_ema + (1.0-ALPHA_UP)*h_m
                        else:
                            height_ema = ALPHA_DN*height_ema + (1.0-ALPHA_DN)*h_m
                    est_h = float(np.clip(height_ema, HEIGHT_MIN_M, HEIGHT_MAX_M))
                est_d = float(d_m)

                # 시각화
                roi_poly_o = roi_poly + offset
                cv2.polylines(frame, [roi_poly_o], True, (255,0,0), 2)
                if contour is not None: cv2.drawContours(frame, [contour + offset], -1, (0,255,0), 2)
                cv2.putText(frame, f"h:{est_h*100:.1f} cm d:{est_d:.2f} m", (20,50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                cv2.imshow("Bump Estimation", frame)
                if (cv2.waitKey(1) & 0xFF) == ord('q'):
                    break

            # ---------- 카메라 놓침 방어 ----------
            if est_d > 0.0 and est_h >= HEIGHT_MIN_M:
                last_seen_dist = est_d
                last_seen_t = loop_t
                h_sticky = est_h
                h_sticky_t = loop_t

            d_hat = None
            if last_seen_dist is not None and last_seen_t is not None:
                d_hat = max(0.0, last_seen_dist - v_mps_now * (loop_t - last_seen_t))
                last_seen_dist = d_hat
                last_seen_t = loop_t

            d_eff = est_d if (est_d > 0.0) else (d_hat if d_hat is not None else 0.0)
            if (loop_t - h_sticky_t) <= MISS_HOLD_SEC:
                h_eff = max(est_h, h_sticky)
            else:
                h_eff = est_h

            bump_detected = (h_eff >= HEIGHT_MIN_M and d_eff > 0.0)

            # ---------- 경계 진입 트리거 ----------
            trigger = False
            if bump_detected:
                if prev_d_eff is not None and prev_d_eff > TRIGGER_DIST_M and d_eff <= TRIGGER_DIST_M:
                    trigger = True
                prev_d_eff = d_eff
            else:
                if last_seen_dist is not None and last_seen_dist <= 0.01:
                    height_ema = None
                    prev_d_eff = None
                    last_seen_dist = None
                    last_seen_t = None
                    h_sticky = 0.0
                    h_sticky_t = 0.0

            # ---------- 트리거 순간 1회 로그/행동 ----------
            if trigger:
                bump_idx += 1
                h_cm = h_eff * 100.0
                pred_rms_now = predict_rms_cal(h_eff, v_mps_now, BUMP_WIDTH_M)
                comfort_now  = classify_rms(pred_rms_now)
                d_txt = f"@~{d_eff:.1f}m"

                if mode == "camera":
                    if h_cm >= CAMERA_HARD_CAP_CM:
                        target = min(v_kmh_now, HARD_CAP_10_KMH)
                        set_speed_once_kmh(driver, target)
                        print(f"[사전] TRIGGER {d_txt} | h≈{h_cm:.1f}cm ≥{CAMERA_HARD_CAP_CM:.1f} ⇒ 감속 {target:.0f}km/h | RMS(pred)={pred_rms_now:.3f} ({comfort_now})")
                    elif h_cm >= HEIGHT_DECEL_CM:
                        target = min(v_kmh_now, DECEL_FIXED_KMH)
                        set_speed_once_kmh(driver, target)
                        print(f"[사전] TRIGGER {d_txt} | h≈{h_cm:.1f}cm ≥{HEIGHT_DECEL_CM:.1f} ⇒ 감속 {target:.0f}km/h | RMS(pred)={pred_rms_now:.3f} ({comfort_now})")
                    elif h_cm <= HEIGHT_KEEP_CM:
                        print(f"[사전] TRIGGER {d_txt} | h≈{h_cm:.1f}cm ≤ {HEIGHT_KEEP_CM:.1f} ⇒ 유지(명령 없음) | RMS(pred)={pred_rms_now:.3f} ({comfort_now})")
                    else:
                        print(f"[사전] TRIGGER {d_txt} | h≈{h_cm:.1f}cm (중간) ⇒ 유지(명령 없음) | RMS(pred)={pred_rms_now:.3f} ({comfort_now})")

                    # (사전) 라운드 완료 → (정밀)로 전환
                    if bump_idx >= len(GT_BUMPS):
                        print("\n[전환] (사전) 완료 → 같은 시나리오 재시작 후 (정밀)로 전환")
                        restart_scenario(sim, proj, SCENARIO_INDEX)
                        car = None
                        t0 = time.time()
                        while car is None and time.time() - t0 < 15.0:
                            car = driver.CurrentCar
                            if car is None: time.sleep(0.2)
                        if car is None: raise RuntimeError("재시작 후 차량 핸들 획득 실패")

                        mode = "gt"
                        bump_idx = 0
                        height_ema = None
                        last_seen_dist = None
                        last_seen_t = None
                        h_sticky = 0.0
                        h_sticky_t = 0.0
                        prev_d_eff = None
                        v_now = speed_kmh(driver)
                        print(f"[정밀] 시작 속도 {v_now:.0f} km/h, 목표 RMS ≤ {COMFORT_RMS_MAX:.2f}\n")

                else:  # ---------- 정밀(GT)
                    if bump_idx <= len(GT_BUMPS):
                        gt = GT_BUMPS[bump_idx-1]
                        L_gt = float(gt["L"])
                        h_gt = float(gt["h"])
                    else:
                        L_gt, h_gt = BUMP_WIDTH_M, h_eff

                    if h_gt <= 0.0:
                        print(f"[정밀] TRIGGER {d_txt} | h_gt≈0 ⇒ 유지(명령 없음)")
                    else:
                        pred_rms_now = predict_rms_cal(h_gt, v_mps_now, L_gt)
                        v_need_mps   = solve_speed_for_target_rms(h_gt, L_gt, COMFORT_RMS_MAX)
                        v_need_kmh   = mps_to_kmh(v_need_mps) if v_need_mps is not None else v_kmh_now

                        # ===== 표준 캡(≥18cm→10, ≥10cm→20, ≥8cm→20) =====
                        h_cm_gt = h_gt * 100.0
                        tag = ""
                        if h_cm_gt >= 18.0 and v_need_kmh > 10.0:
                            v_need_kmh = 10.0; tag = " | (표 캡: ≥18cm→10km/h)"
                        elif h_cm_gt >= 10.0 and v_need_kmh > 20.0:
                            v_need_kmh = 20.0; tag = " | (표 캡: ≥10cm→20km/h)"
                        elif h_cm_gt >= 8.0 and v_need_kmh > 20.0:
                            v_need_kmh = 20.0; tag = " | (표 캡: ≥8cm→20km/h)"

                        if v_need_kmh < v_kmh_now:
                            set_speed_once_kmh(driver, v_need_kmh)
                            print(f"[정밀] TRIGGER {d_txt} | L={L_gt:.2f}m h={h_cm_gt:.1f}cm | v={v_kmh_now:.1f} → {v_need_kmh:.1f}km/h | RMS(now)={pred_rms_now:.3f} → 목표 ≤{COMFORT_RMS_MAX:.2f}{tag}")
                        else:
                            print(f"[정밀] TRIGGER {d_txt} | L={L_gt:.2f}m h={h_cm_gt:.1f}cm | 현재 v={v_kmh_now:.1f}km/h가 이미 목표 충족(명령 없음){tag}")

                    if bump_idx >= len(GT_BUMPS):
                        print("\n[완료] (정밀)까지 모든 방지턱 처리 완료")
                        break

            # 루프 주기 유지
            time.sleep(max(0.0, DT - (time.time() - loop_t)))

    except KeyboardInterrupt:
        print("\n사용자 중지")
    finally:
        try: cv2.destroyAllWindows()
        except: pass

if __name__ == "__main__":
    main()
