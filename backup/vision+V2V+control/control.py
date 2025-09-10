# control.py
import time
import math
import queue
import numpy as np
from win32com.client import Dispatch, GetActiveObject
from logger import print_at

# ================== 튜닝 파라미터 ==================
# 제동 강도(PWM) 계산 시 각 요소의 가중치
# 두 값의 합이 1.0이 되도록 조절하는 것을 추천합니다.
PWM_WEIGHT_SPEED_DIFF = 0.7  # 속도 차이의 영향력 (클수록 속도를 빨리 줄이려 함)
PWM_WEIGHT_DISTANCE = 0.7    # 남은 거리의 영향력 (클수록 가까워졌을 때 급하게 제동)
PWM_WEIGHT = 1.2
# =======================================================

# (다른 함수들은 이전과 동일합니다)
PROGID = "UCwinRoad.F8ApplicationServicesProxy"

def attach_or_launch():
    try: return GetActiveObject(PROGID)
    except: return Dispatch(PROGID)

def restart_scenario(sim_core, proj, idx=0):
    try:
        if hasattr(sim_core, "StopAllScenarios"):
            sim_core.StopAllScenarios(); time.sleep(0.3)
    except: pass
    sc = proj.Scenario(idx); sim_core.StartScenario(sc); time.sleep(0.8)
    print("\n============시나리오 시작============")

def read_speed_kmh(car):
    try: return float(car.Speed(1))
    except: return float(car.Speed()) * 3.6

def get_bump_width(bump_type_str):
    if 'typea' in bump_type_str.lower(): return 3.6
    if 'typeb' in bump_type_str.lower(): return 1.8
    return 3.0

def calculate_rms(h_m, L_m, v_mps, gain):
    if v_mps <= 0 or L_m <= 0: return 0.0
    term1 = gain * (1.0 / math.sqrt(2.0)) * h_m
    term2 = (v_mps * math.pi / L_m)**2
    return term1 * term2

def classify_rms(rms_value):
    if rms_value < 0.315: return "매우 쾌적함"
    if rms_value < 0.5: return "쾌적함"
    if rms_value < 0.8: return "보통"
    if rms_value < 1.25: return "불쾌함"
    return "매우 불쾌함"
    
def solve_speed_for_target_rms(h_m, L_m, target_rms, gain):
    if h_m <= 0 or L_m <= 0 or target_rms <= 0 or gain <=0: return 0.0
    denominator = gain * (1.0/math.sqrt(2.0)) * h_m * (math.pi/L_m)**2
    if denominator <= 0: return 0.0
    v_mps_squared = target_rms / denominator
    return math.sqrt(v_mps_squared)

def estimate_min_speed_kmh(current_speed_kmh):
    speed_map = {
        40: np.mean([5.19, 2.79, 3.71]), 50: np.mean([21.42, 17.17, 20.84]),
        60: np.mean([37.08, 39.03, 35.63]), 70: np.mean([55.02, 52.70, 53.09]),
        80: np.mean([63.87, 65.28, 64.04]), 90: np.mean([72.35, 70.13, 71.02]),
    }
    x_speeds = sorted(speed_map.keys())
    y_ms = [speed_map[s] for s in x_speeds]
    if current_speed_kmh <= x_speeds[0]: return y_ms[0]
    if current_speed_kmh >= x_speeds[-1]: return y_ms[-1]
    return np.interp(current_speed_kmh, x_speeds, y_ms)

# --- [핵심 수정] PWM 계산 함수 ---
def calculate_brake_pwm(current_speed_kmh, target_speed_kmh, distance_to_bump_m):
    """
    속도 차이와 남은 거리를 모두 고려하여 최적의 PWM 값을 계산합니다.
    """
    # 1. 속도 차이 계수 (0.0 ~ 1.0 정규화)
    speed_diff = max(0, current_speed_kmh - target_speed_kmh)
    # 현재 속도가 80km/h이고 목표가 20km/h일 때 speed_diff는 60. 이 값을 기준으로 정규화.
    speed_diff_factor = min(1.0, speed_diff / 60.0) 

    # 2. 거리 긴급도 계수 (0.0 ~ 1.0 정규화)
    # V2V가 감지하는 최대 유효 거리인 50m를 기준으로, 가까울수록 1.0에 가까워짐
    # 거리가 0에 가까워지면 긴급도는 1.0, 50m 이상이면 긴급도는 0.0
    urgency_distance = 50.0 
    distance_factor = 1.0 - min(1.0, distance_to_bump_m / urgency_distance)

    # 3. 가중치를 적용하여 최종 PWM 계산
    # 속도차가 많이 나거나, 거리가 가까울수록 강하게 제동
    raw_pwm = PWM_WEIGHT*((PWM_WEIGHT_SPEED_DIFF * speed_diff_factor) + (PWM_WEIGHT_DISTANCE * distance_factor))

    # 4. 최소/최대 제동 강도 제한
    # 최소 50%의 제동은 하되, 최대 100%를 넘지 않도록 조정
    final_pwm = max(0.5, min(1.0, raw_pwm))
    
    return final_pwm
# --------------------------------

def execute_control(car, target_speed_kmh, pwm, poll_dt):
    print("\n============차량감속 시작============")
    start_time = time.time()
    while time.time() - start_time < 10.0:
        current_speed_kmh = read_speed_kmh(car)
        message = f"현재속도: {current_speed_kmh:.2f}km/h | 목표:{target_speed_kmh:.2f}km/h| 제동강도:{int(pwm*100)}%"
        print_at('CONTROL', message)
        if current_speed_kmh <= target_speed_kmh:
            print(f"\n[Control] 목표 속도({target_speed_kmh:.2f}km/h) 도달 성공.")
            break
        try:
            on_time = poll_dt * pwm
            off_time = poll_dt * (1.0 - pwm)
            car.Throttle = 0.0
            if on_time > 0: car.ParkingBrake = True; time.sleep(on_time)
            if off_time > 0: car.ParkingBrake = False; time.sleep(off_time)
        except Exception: break
    try:
        car.Brake = 0.0; car.ParkingBrake = False
    except Exception: pass
    print("============차량감속 종료============")

def run_control_simulation(vision_queue):
    print("[Control] 제어 시뮬레이션 프로세스 시작")
    POLL_DT = 0.15; CAL_GAIN = 0.050
    COMFORT_TARGETS_RMS = {'매우 쾌적함': 0.315, '쾌적함': 0.5, '보통': 0.8}
    TARGET_SPEED_MARGIN_KMH = 3.0

    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore; proj = ucwin.Project; driver = sim_core.TrafficSimulation.Driver
        restart_scenario(sim_core, proj, 0)
        car = None; t0 = time.time()
        while car is None and time.time() - t0 < 15.0:
            car = driver.CurrentCar; time.sleep(0.2)
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        print(f"[Control] UC-win/Road 연결 및 차량 핸들 확보 완료.")
    except Exception as e:
        print(f"[Control] UC-win/Road 연결 실패: {e}"); return

    is_controlling = False
    while True:
        if not is_controlling:
            try:
                data = vision_queue.get_nowait()
                bump_type, dist_m, h_m = data['type'], data['distance_m'], data['height_m']
                bump_width_m = data.get('width_m', get_bump_width(bump_type))

                print(f"\n[Control][수신 완료] T:{bump_type}|D:{dist_m:.1f}m|H:{h_m*100:.1f}cm|W:{bump_width_m:.2f}m")

                if 'D' in str(bump_type).upper():
                    print(f"[Control] 타입 '{bump_type}' 감지. 감속을 진행하지 않습니다.")
                    continue

                is_controlling = True
                current_speed_kmh = read_speed_kmh(car)
                mS_kmh = estimate_min_speed_kmh(current_speed_kmh)
                eR_rms = calculate_rms(h_m, bump_width_m, mS_kmh / 3.6, CAL_GAIN)
                comfort_level = classify_rms(eR_rms)
                
                print(f"[Control] S:{current_speed_kmh:.1f}km/h|mS:{mS_kmh:.1f}km/h|eR:{eR_rms:.2f}|승차감:{comfort_level}")

                if comfort_level in ["불쾌함", "매우 불쾌함"]:
                    tS_kmh = mS_kmh
                else:
                    target_rms_level = COMFORT_TARGETS_RMS.get(comfort_level, 0.5)
                    optimal_speed_mps = solve_speed_for_target_rms(h_m, bump_width_m, target_rms_level, CAL_GAIN)
                    optimal_speed_kmh = optimal_speed_mps * 3.6
                    tS_kmh = max(mS_kmh, optimal_speed_kmh) + TARGET_SPEED_MARGIN_KMH
                
                # --- [핵심 수정] 새로운 PWM 계산 함수 호출 ---
                brake_pwm = calculate_brake_pwm(current_speed_kmh, tS_kmh, dist_m)
                
                execute_control(car, tS_kmh, brake_pwm, POLL_DT)
                is_controlling = False

            except queue.Empty:
                current_speed = read_speed_kmh(car)
                message = f"현재 속도: {current_speed:.1f} km/h | 시스템 대기 중..."
                print_at('CONTROL', message)
            except Exception as e:
                print(f"\n[Control] 제어 중 오류 발생: {e}")
                is_controlling = False
        
        time.sleep(0.1)