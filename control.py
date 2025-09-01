import time
import math
import queue
import numpy as np
from win32com.client import Dispatch, GetActiveObject
from logger import print_at

# ================== UC-win/Road 연결 ==================
PROGID = "UCwinRoad.F8ApplicationServicesProxy"

def attach_or_launch():
    try:
        return GetActiveObject(PROGID)
    except:
        return Dispatch(PROGID)

def restart_scenario(sim_core, proj, idx=0):
    try:
        if hasattr(sim_core, "StopAllScenarios"):
            sim_core.StopAllScenarios()
            time.sleep(0.3)
    except:
        pass
    sc = proj.Scenario(idx)
    sim_core.StartScenario(sc)
    time.sleep(0.8)
    print("\n============시나리오 시작============")

# ================== 유틸리티 ==================
def read_speed_kmh(car):
    try:
        return float(car.Speed(1))  # km/h
    except:
        return float(car.Speed()) * 3.6  # m/s -> km/h

def get_bump_width(bump_type):
    if bump_type == 'A': return 3.6
    if bump_type == 'B': return 1.8
    return 3.0

def calculate_rms(h_m, L_m, v_mps, gain):
    if v_mps <= 0 or L_m <= 0: return 0.0
    term1 = gain * (1.0 / math.sqrt(2.0)) * h_m
    term2 = (v_mps * math.pi / L_m) ** 2
    return term1 * term2

def classify_rms(rms_value):
    if rms_value < 0.315: return "매우 쾌적함"
    if rms_value < 0.5: return "쾌적함"
    if rms_value < 0.8: return "보통"
    if rms_value < 1.25: return "불쾌함"
    return "매우 불쾌함"

def solve_speed_for_target_rms(h_m, L_m, target_rms, gain):
    if h_m <= 0 or L_m <= 0 or target_rms <= 0 or gain <= 0: return 0.0
    numerator = target_rms
    denominator = gain * (1.0/math.sqrt(2.0)) * h_m * (math.pi/L_m)**2
    if denominator <= 0: return 0.0
    v_mps_squared = numerator / denominator
    return math.sqrt(v_mps_squared)

# ================== 제어 계획 ==================
def estimate_min_speed_kmh(current_speed_kmh):
    speed_map = {
        40: np.mean([5.19, 2.79, 3.71]),
        50: np.mean([21.42, 17.17, 20.84]),
        60: np.mean([37.08, 39.03, 35.63]),
        70: np.mean([55.02, 52.70, 53.09]),
        80: np.mean([63.87, 65.28, 64.04]),
        90: np.mean([72.35, 70.13, 71.02]),
    }
    x_speeds = sorted(speed_map.keys())
    y_ms = [speed_map[s] for s in x_speeds]
    if current_speed_kmh <= x_speeds[0]: return y_ms[0]
    if current_speed_kmh >= x_speeds[-1]: return y_ms[-1]
    return np.interp(current_speed_kmh, x_speeds, y_ms)

def calculate_brake_pwm(current_speed_kmh, weight):
    base = 1.0 if current_speed_kmh >= 50 else \
           0.9 if current_speed_kmh >= 40 else \
           0.8 if current_speed_kmh >= 30 else \
           0.7 if current_speed_kmh >= 20 else 0.6
    return base * weight

def execute_control(car, target_speed_kmh, pwm, poll_dt):
    print("\n============차량감속 시작============")
    start_time = time.time()
    while time.time() - start_time < 10.0:
        current_speed_kmh = read_speed_kmh(car)
        message = f"현재속도: {current_speed_kmh:.2f}km/h | ts:{target_speed_kmh:.2f}km/h | PWM:{pwm:.2f}"
        print_at('CONTROL', message)

        if current_speed_kmh <= target_speed_kmh:
            print(f"\n[Control] 목표 속도({target_speed_kmh:.2f}km/h) 도달 성공.")
            break

        try:
            on_time = poll_dt * pwm
            off_time = poll_dt * (1.0 - pwm)
            car.Throttle = 0.0
            if on_time > 0:
                car.ParkingBrake = True
                time.sleep(on_time)
            if off_time > 0:
                car.ParkingBrake = False
                time.sleep(off_time)
        except Exception:
            break

    try:
        car.Brake = 0.0
        car.ParkingBrake = False
    except Exception:
        pass
    print("============차량감속 종료============")

# ================== 메인 제어 로직 ==================
def run_control_simulation(vision_queue, control_to_eval_queue, eval_to_control_queue):
    print("[Control] 제어 시뮬레이션 프로세스 시작")

    POLL_DT = 0.15
    CAL_GAIN = 0.050
    PWM_WEIGHT = 1.0
    COMFORT_TARGETS_RMS = {'매우 쾌적함': 0.315, '쾌적함': 0.5, '보통': 0.8}
    TARGET_SPEED_MARGIN_KMH = 3.0

    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore
        proj = ucwin.Project
        driver = sim_core.TrafficSimulation.Driver

        restart_scenario(sim_core, proj, 0)

        car = None
        t0 = time.time()
        while car is None and time.time() - t0 < 15.0:
            car = driver.CurrentCar; time.sleep(0.2)
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        print(f"[Control] UC-win/Road 연결 및 차량 핸들 확보 완료.")
    except Exception as e:
        print(f"[Control] UC-win/Road 연결 실패: {e}")
        return

    is_controlling = False
    last_eval_time = 0

    while True:
        # Evaluate에서 보정계수 수신
        try:
            eval_msg = eval_to_control_queue.get_nowait()
            if eval_msg.get("msg") == "evaluate":
                old_cal = CAL_GAIN
                old_pwm_w = PWM_WEIGHT
                CAL_GAIN *= eval_msg.get("CAL_GAIN", 1.0)
                PWM_WEIGHT = eval_msg.get("PWM_WEIGHT", 1.0)

                print(f"[Control] 보정계수 갱신 → "
                      f"PWM_WEIGHT:{PWM_WEIGHT:.2f} (prev {old_pwm_w:.2f}), "
                      f"CAL_GAIN:{CAL_GAIN:.4f} (prev {old_cal:.4f})")
        except queue.Empty:
            pass

        if not is_controlling:
            try:
                data = vision_queue.get_nowait()
                bump_type, dist_m, h_m = data['type'], data['distance_m'], data['height_m']
                print(f"\n[Control][수신 완료]T:{bump_type}|D:{dist_m:.1f}m|H:{h_m*100:.1f}cm")

                if bump_type in ['A','B','C']:
                    is_controlling = True
                    current_speed_kmh = read_speed_kmh(car)
                    mS_kmh = estimate_min_speed_kmh(current_speed_kmh)
                    bump_width_m = get_bump_width(bump_type)
                    eR_rms = calculate_rms(h_m, bump_width_m, mS_kmh/3.6, CAL_GAIN)
                    comfort_level = classify_rms(eR_rms)

                    print(f"[Control]D:{dist_m:.1f}m|H:{h_m*100:.1f}cm|"
                          f"S:{current_speed_kmh:.2f}km/h|mS:{mS_kmh:.2f}km/h|"
                          f"eR:{eR_rms:.2f}|CAL_GAIN:{CAL_GAIN:.4f}|승차감:{comfort_level}")

                    if comfort_level in ["불쾌함", "매우 불쾌함"]:
                        tS_kmh = mS_kmh
                        print(f"[Control] 승차감 '불쾌' 이상 감지. 목표 속도를 {tS_kmh:.2f}km/h로 설정.")
                    else:
                        target_rms_level = COMFORT_TARGETS_RMS.get(comfort_level,0.5)
                        optimal_speed_mps = solve_speed_for_target_rms(h_m,bump_width_m,target_rms_level,CAL_GAIN)
                        optimal_speed_kmh = optimal_speed_mps*3.6
                        tS_kmh = max(mS_kmh, optimal_speed_kmh)+TARGET_SPEED_MARGIN_KMH

                    # Evaluate에 예측값 전달
                    control_to_eval_queue.put({
                        "msg":"control",
                        "tS":tS_kmh,
                        "eR":eR_rms,
                        "type":bump_type
                    })

                    brake_pwm = calculate_brake_pwm(current_speed_kmh, PWM_WEIGHT)
                    execute_control(car,tS_kmh,brake_pwm,POLL_DT)
                    is_controlling = False

            except queue.Empty:
                current_speed = read_speed_kmh(car)
                message = f"현재 속도: {current_speed:.1f} km/h | Vision 신호 대기 중..."
                print_at('CONTROL', message)
            except Exception as e:
                print(f"[Control] 제어 중 오류 발생: {e}")
                is_controlling = False

        time.sleep(0.1)
