# control.py
import time
import math
import queue
import numpy as np
from win32com.client import Dispatch, GetActiveObject

# ================== UC-win/Road 연결 및 기본 함수 ==================
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

# ================== 유틸리티 및 계산 함수 ==================
def read_speed_kmh(car):
    try:
        return float(car.Speed(1)) # km/h
    except:
        return float(car.Speed()) * 3.6 # m/s -> km/h

def get_bump_width(bump_type):
    if bump_type == 'A': return 3.6
    if bump_type == 'B': return 1.8
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
    numerator = target_rms
    denominator = gain * (1.0/math.sqrt(2.0)) * h_m * (math.pi/L_m)**2
    if denominator <= 0: return 0.0
    v_mps_squared = numerator / denominator
    return math.sqrt(v_mps_squared)

# ================== 제어 계획 및 실행 함수 ==================

def estimate_min_speed_kmh(current_speed_kmh):
    """
    제공된 테스트 데이터 기반, 현재 속도에 따른 예상 최저 도달 속도(mS)를 계산합니다.
    """
    speed_map = {
        40: np.mean([13.19, 0.79, 3.71]),
        50: np.mean([24.42, 17.17, 20.84]),
        60: np.mean([37.08, 41.03, 35.63]),
        70: np.mean([57.02, 52.70, 53.09]),
        80: np.mean([63.87, 66.28, 64.04]),
        90: np.mean([72.35, 70.13, 73.02]),
    }
    
    x_speeds = sorted(speed_map.keys())
    y_ms = [speed_map[s] for s in x_speeds]
    
    if current_speed_kmh <= x_speeds[0]:
        return y_ms[0]
    if current_speed_kmh >= x_speeds[-1]:
        return y_ms[-1]
        
    return np.interp(current_speed_kmh, x_speeds, y_ms)


def calculate_brake_pwm(current_speed_kmh):
    """
    현재 속도에 따라 제동 강도(PWM)를 결정합니다.
    """
    if current_speed_kmh >= 50:
        return 1.0
    elif current_speed_kmh >= 40:
        return 0.9
    elif current_speed_kmh >= 30:
        return 0.8
    elif current_speed_kmh >= 20:
        return 0.7
    else:
        return 0.6

def execute_control(car, target_speed_kmh, pwm, poll_dt):
    """
    계산된 고정 PWM 값으로 목표 속도에 도달할 때까지 차량을 제어합니다.
    """
    print("============차량감속 시작============")
    
    start_time = time.time()
    while time.time() - start_time < 10.0:
        current_speed_kmh = read_speed_kmh(car)
        print(f"[Control] 현재속도: {current_speed_kmh:.2f}km/h | ts:{target_speed_kmh:.2f}km/h| PWM:{pwm:.2f}", end='\r')

        if current_speed_kmh <= target_speed_kmh:
            print(f"\n[Control] 목표 속도({target_speed_kmh:.2f}km/h) 도달 성공.")
            break
            
        try:
            car.Throttle = 0.0
            car.Brake = pwm
            car.ParkingBrake = True
        except Exception:
            pass
            
        time.sleep(poll_dt)
        
    try:
        car.Brake = 0.0
        car.ParkingBrake = False
    except Exception:
        pass
    print("============차량감속 종료============")


# ================== 메인 제어 로직 함수 ==================
def run_control_simulation(vision_queue):
    print("[Control] 제어 시뮬레이션 프로세스 시작")

    # ===튜닝 파라미터===
    POLL_DT = 0.2
    # CAL_GAIN: RMS 계산 보정 계수. 값을 낮출수록 RMS가 낮게 계산됩니다.
    CAL_GAIN = 0.080 # 기존 0.124에서 하향 조정
    COMFORT_TARGETS_RMS = {'매우 쾌적함': 0.315, '쾌적함': 0.5, '보통': 0.8}
    TARGET_SPEED_MARGIN_KMH = 3.0

    # === UC-win/Road 연결 ===
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

    while True:
        if not is_controlling:
            try:
                # 1단계: T/D/H 수신
                data = vision_queue.get_nowait()
                bump_type, dist_m, h_m = data['type'], data['distance_m'], data['height_m']
                
                print(f"\n[Control][수신 완료]T:{bump_type}|D:{dist_m:.1f}m|H:{h_m*100:.1f}cm")

                if bump_type in ['A', 'B', 'C']:
                    is_controlling = True
                    current_speed_kmh = read_speed_kmh(car)
                    
                    # 2단계: mS 계산
                    mS_kmh = estimate_min_speed_kmh(current_speed_kmh)
                    
                    # 3단계: eR 도출
                    bump_width_m = get_bump_width(bump_type)
                    eR_rms = calculate_rms(h_m, bump_width_m, mS_kmh / 3.6, CAL_GAIN)
                    comfort_level = classify_rms(eR_rms)
                    
                    print(f"[Control]D:{dist_m:.1f}m|H:{h_m*100:.1f}cm|S:{current_speed_kmh:.2f}km/h|mS:{mS_kmh:.2f}km/h|eR:{eR_rms:.2f}|승차감:{comfort_level}")

                    # 4단계: tS 설정
                    # 1. '불쾌' 또는 '매우 불쾌'일 경우, 안전을 위해 즉시 mS를 목표 속도로 설정
                    if comfort_level in ["불쾌함", "매우 불쾌함"]:
                        tS_kmh = mS_kmh
                        print(f"[Control] 승차감 '불쾌' 이상 감지. 안전을 위해 목표 속도를 {tS_kmh:.2f}km/h로 설정합니다.")
                    else:
                        target_rms_level = COMFORT_TARGETS_RMS.get(comfort_level, 0.5)
                        optimal_speed_mps = solve_speed_for_target_rms(h_m, bump_width_m, target_rms_level, CAL_GAIN)
                        optimal_speed_kmh = optimal_speed_mps * 3.6
                        
                        tS_kmh = max(mS_kmh, optimal_speed_kmh) + TARGET_SPEED_MARGIN_KMH
                    
                    # 5단계: PWM 계산 및 제어 실행
                    brake_pwm = calculate_brake_pwm(current_speed_kmh)
                    execute_control(car, tS_kmh, brake_pwm, POLL_DT)

                    is_controlling = False
                else:
                    pass

            except queue.Empty:
                current_speed = read_speed_kmh(car)
                print(f"[Control] 현재 속도: {current_speed:.1f} km/h | Vision 신호 대기 중...", end='\r')
            
            except Exception as e:
                print(f"\n[Control] 제어 중 오류 발생: {e}")
                is_controlling = False
        
        time.sleep(POLL_DT)