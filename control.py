# control.py
import time, math
import queue
import win32com.client
from win32com.client import Dispatch, GetActiveObject

# ================== UC-win/Road 연결 및 제어 함수 (원본과 동일) ==================
PROGID = "UCwinRoad.F8ApplicationServicesProxy"
def attach_or_launch():
    try:    return GetActiveObject(PROGID)
    except: return Dispatch(PROGID)

def restart_scenario(sim, proj, idx=0):
    try:
        if hasattr(sim, "StopScenario"):
            sim.StopScenario()
            time.sleep(0.5)
    except Exception: pass
    sc = proj.Scenario(idx)
    sim.StartScenario(sc)
    time.sleep(1.0)

# ================== 유틸리티 및 RMS 계산 함수 (원본과 동일) ==================
def kmh_to_mps(v): return v/3.6
def mps_to_kmh(v): return v*3.6

def _vec3(v):
    for names in (("X","Y","Z"), ("x","y","z")):
        if all(hasattr(v, n) for n in names): return float(getattr(v, names[0])), float(getattr(v, names[1])), float(getattr(v, names[2]))
    for m in ("Item","get_Item","GetAt","Get"):
        if hasattr(v, m): f = getattr(v, m); return float(f(0)), float(f(1)), float(f(2))
    seq = list(v); return float(seq[0]), float(seq[1]), float(seq[2])

def speed_kmh(drv, unit_val=0):
    c = drv.CurrentCar
    if c is None: return 0.0
    try: sv = c.SpeedVector(unit_val)
    except TypeError: sv = c.SpeedVector() if callable(getattr(c,"SpeedVector",None)) else c.SpeedVector
    vx,vy,vz = _vec3(sv)
    f = 1.0 # SI(m/s) 기준
    v_mps = ((vx*f)**2 + (vy*f)**2 + (vz*f)**2)**0.5
    return mps_to_kmh(v_mps)

def set_speed_once_kmh(drv, v_kmh, unit_val=0):
    c = drv.CurrentCar
    if c is None: return
    try: c.SetSpeed(kmh_to_mps(v_kmh), unit_val)
    except Exception: pass

def predict_rms_cal(h_m, v_mps, L_m, gain):
    if L_m <= 0 or h_m <= 0 or v_mps <= 0: return 0.0
    raw = (1.0/math.sqrt(2.0)) * ((math.pi * v_mps)/L_m)**2 * h_m
    return gain * raw

def classify_rms(r):
    if r < 0.315:   return "매우 쾌적함"
    elif r < 0.5:   return "쾌적함"
    elif r < 0.8:   return "약간 불쾌함"
    elif r < 1.25:  return "불쾌함"
    else:           return "매우 불쾌함"
    
# 메인 제어 로직 함수
def run_control_simulation(vision_queue):
    print("[Control] 제어 시뮬레이션 프로세스를 시작합니다.")
    
    # === 원본의 사용자 설정값들 ===
    DECEL_FIXED_KMH = 20.0
    HARD_CAP_10_KMH = 10.0
    HEIGHT_KEEP_CM   = 7.0
    HEIGHT_DECEL_CM  = 8.0
    CAMERA_HARD_CAP_CM = 18.0
    BUMP_WIDTH_M = 3.0
    CAL_GAIN = 0.12380238
    SAMPLE_HZ = 10.0
    DT = 1.0 / SAMPLE_HZ

    # UC-win/Road 연결
    try:
        ucwin = attach_or_launch()
        sim = ucwin.SimulationCore
        proj = ucwin.Project
        driver = sim.TrafficSimulation.Driver
        
        # 시나리오 시작 및 차량 핸들 확보
        restart_scenario(sim, proj, 0)
        car = None
        t0 = time.time()
        while car is None and time.time() - t0 < 15.0:
            car = driver.CurrentCar
            if car is None: time.sleep(0.2)
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        print(f"[Control] UC-win/Road 연결 및 차량 핸들 확보 완료.")
    except Exception as e:
        print(f"[Control] UC-win/Road 연결 실패: {e}")
        return

    triggered_bump_types = set() # 이미 처리한 방지턱 타입을 기록

    while True:
        loop_t = time.time()
        v_kmh_now = speed_kmh(driver)
        
        # [핵심 수정] Vision 프로세스로부터 데이터 수신
        try:
            data = vision_queue.get_nowait()
            bump_type = data['type']

            # 이전에 처리하지 않은 새로운 타입의 방지턱일 때만 로직 실행
            if bump_type not in triggered_bump_types:
                triggered_bump_types.add(bump_type)
                h_eff_m = data['height_m']
                h_cm = h_eff_m * 100.0
                pred_rms = predict_rms_cal(h_eff_m, kmh_to_mps(v_kmh_now), BUMP_WIDTH_M, CAL_GAIN)
                comfort = classify_rms(pred_rms)

                print(f"\n[Control] Vision 신호 수신: 타입={bump_type}, 높이={h_cm:.1f}cm")

                target_speed = v_kmh_now
                action_taken = False
                
                # 원본의 '사전(Camera)' 모드 판단 로직 적용
                if h_cm >= CAMERA_HARD_CAP_CM:
                    target_speed = min(v_kmh_now, HARD_CAP_10_KMH)
                    print(f"[Control] 판단: 높이 ≥{CAMERA_HARD_CAP_CM:.1f}cm ⇒ 감속 {target_speed:.0f}km/h | RMS(예측)={pred_rms:.3f} ({comfort})")
                    action_taken = True
                elif h_cm >= HEIGHT_DECEL_CM:
                    target_speed = min(v_kmh_now, DECEL_FIXED_KMH)
                    print(f"[Control] 판단: 높이 ≥{HEIGHT_DECEL_CM:.1f}cm ⇒ 감속 {target_speed:.0f}km/h | RMS(예측)={pred_rms:.3f} ({comfort})")
                    action_taken = True
                elif h_cm <= HEIGHT_KEEP_CM:
                    print(f"[Control] 판단: 높이 ≤{HEIGHT_KEEP_CM:.1f}cm ⇒ 속도 유지 | RMS(예측)={pred_rms:.3f} ({comfort})")
                else:
                    print(f"[Control] 판단: 높이 중간값 ⇒ 속도 유지 | RMS(예측)={pred_rms:.3f} ({comfort})")

                if action_taken:
                    set_speed_once_kmh(driver, target_speed)
        
        except queue.Empty:
            # Vision으로부터 받은 신호가 없으면 현재 속도만 출력
            print(f"[Control] 현재 속도: {v_kmh_now:.2f} km/h, Vision 신호 대기 중...", end='\r')
            pass
        except Exception as e:
            print(f"[Control] 루프 에러: {e}")
            break

        time.sleep(max(0.0, DT - (time.time() - loop_t)))