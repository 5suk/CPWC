# control.py
import time
import math
import queue
import win32com.client
from win32com.client import Dispatch, GetActiveObject
import numpy as np

# ================== UC-win/Road 연결 및 기본 함수 ==================
PROGID = "UCwinRoad.F8ApplicationServicesProxy"

def attach_or_launch():
    try: return GetActiveObject(PROGID)
    except: return Dispatch(PROGID)

def restart_scenario(sim_core, proj, idx=0):
    try:
        if hasattr(sim_core, "StopAllScenarios"):
            sim_core.StopAllScenarios(); time.sleep(0.3)
    except: pass
    sc = proj.Scenario(idx)
    sim_core.StartScenario(sc)
    time.sleep(1.0)
    print("============시나리오 시작============")

def read_speed_kmh(car):
    try: return float(car.Speed(1))
    except: return float(car.Speed()) * 3.6

# ================== PWM 제어 관련 함수 ==================
CAL_GAIN = 0.08

def get_bump_width(bump_type):
    if bump_type == 'A': return 3.6
    if bump_type == 'B': return 1.8
    return 3.0

def calculate_rms(h_m, L_m, v_mps):
    if v_mps <= 0 or h_m <= 0 or L_m <= 0: return 0.0, "N/A"
    rms = CAL_GAIN * (1.0 / math.sqrt(2.0)) * h_m * (v_mps * math.pi / L_m)**2
    if rms < 0.315: comfort = "매우 쾌적함"
    elif rms < 0.5: comfort = "쾌적함"
    elif rms < 0.8: comfort = "약간 불쾌함"
    else: comfort = "불쾌함"
    return rms, comfort

# ================== [신규] 동적 목표 속도 계산 함수 ==================
def calculate_dynamic_target_speed(h_m, L_m):
    """'쾌적함'을 유지하는 가장 높은 통과 속도를 계산합니다."""
    COMFORT_RMS_THRESHOLD = 0.5 # '쾌적함'의 RMS 기준값
    
    # 통과 가능한 속도를 30km/h부터 1km/h씩 낮춰가며 확인
    for speed_kmh in range(30, 9, -1):
        v_mps = speed_kmh / 3.6
        rms, _ = calculate_rms(h_m, L_m, v_mps)
        if rms <= COMFORT_RMS_THRESHOLD:
            # 기준을 만족하는 가장 높은 속도를 목표로 설정
            return float(speed_kmh)
            
    # 모든 속도에서 기준을 만족하지 못하면 안전하게 10km/h로 설정
    return 10.0

# ================== 고정 PWM 제어 함수 ==================
def fixed_pwm_brake(car, plan):
    fixed_pwm = plan['calculated_pwm']
    target_v_kmh = plan['target_speed_kmh']
    
    print("============차량감속 시작============")
    
    PWM_CYCLE = 0.3
    on_time = PWM_CYCLE * fixed_pwm
    cycle_start_time = time.time()

    while True:
        current_v_kmh = read_speed_kmh(car)
        
        if current_v_kmh <= target_v_kmh:
            # 로그 형식 수정
            print(f"\n[Control] 목표 속도({target_v_kmh:.1f}km/h) 도달 성공.")
            break

        try:
            if fixed_pwm > 0:
                car.Throttle = 0.0
                car.ParkingBrake = True
                if on_time > 0.001: time.sleep(on_time)
            
            car.ParkingBrake = False

            # 로그 형식 수정
            print(f"[Control] 현재속도: {current_v_kmh:.1f}km/h | ts:{target_v_kmh:.1f}km/h | PWM:{int(fixed_pwm*100)}%", end='\r')
            
            elapsed = time.time() - cycle_start_time
            sleep_time = max(0, PWM_CYCLE - on_time)
            time.sleep(sleep_time)
            cycle_start_time = time.time()

        except Exception as e:
            print(f"\n[Control] 제어 중 오류: {e}")
            break
            
    try:
        car.ParkingBrake = False
        # 로그 형식 수정
        print("[Control] 강제 제어 종료. 차량 상태를 복구")
    except: pass

# ================== 메인 제어 로직 함수 ==================
def run_control_simulation(vision_queue):
    print("[Control] 제어 시뮬레이션 프로세스 시작")
    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore
        proj = ucwin.Project
        driver = sim_core.TrafficSimulation.Driver
        restart_scenario(sim_core, proj, 0)
        car = driver.CurrentCar
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        print(f"[Control] UC-win/Road 연결 및 차량 핸들 확보 완료.")
    except Exception as e:
        print(f"[Control] UC-win/Road 연결 실패: {e}")
        return

    # === 튜닝 파라미터 ===
    SPEED_ERROR_GAIN = 0.3
    DISTANCE_WEIGHT_GAIN = 2.0
    PWM_GAIN = 1.5

    is_controlling = False
    while True:
        if not is_controlling:
            try:
                data = vision_queue.get(timeout=0.2)
                bump_type, dist_m, h_m = data['type'], data['distance_m'], data['height_m']
                
                # 로그 형식 수정
                print(f"\n[Control][수신 완료]T:{bump_type}|D:{dist_m:.1f}m|H:{h_m*100:.1f}cm")
                
                if bump_type in ['A', 'B', 'C']:
                    is_controlling = True
                    current_speed_kmh = read_speed_kmh(car)
                    
                    # [수정된 핵심] 동적 목표 속도 계산
                    bump_width = get_bump_width(bump_type)
                    target_speed_kmh = calculate_dynamic_target_speed(h_m, bump_width)
                    
                    expected_rms, comfort_level = calculate_rms(h_m, bump_width, target_speed_kmh / 3.6)
                    # 로그 형식 수정
                    print(f"[Control][Respond]S:{current_speed_kmh:.1f}km/h|tS:{target_speed_kmh:.1f}km/h|eR:{expected_rms:.3f}|승차감:{comfort_level}")
                    
                    speed_error = current_speed_kmh - target_speed_kmh
                    distance_weight = 1.0 / max(dist_m, 1.0)
                    calculated_pwm = ((speed_error * SPEED_ERROR_GAIN) + (distance_weight * DISTANCE_WEIGHT_GAIN)) * PWM_GAIN
                    final_fixed_pwm = max(0.0, min(1.0, calculated_pwm))
                    
                    control_plan = {
                        'calculated_pwm': final_fixed_pwm,
                        'target_speed_kmh': target_speed_kmh
                    }
                    
                    fixed_pwm_brake(car, control_plan)
                    is_controlling = False
                    
            except queue.Empty:
                current_speed = read_speed_kmh(car)
                print(f"[Control] 현재 속도: {current_speed:.1f} km/h | Vision 신호 대기 중...", end='\r')
            except Exception as e:
                print(f"\n[Control] 메인 루프 오류 발생: {e}")
                is_controlling = False
                time.sleep(1)