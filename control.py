# control.py
import time
import math
import queue
import win32com.client
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
    print(">> 시나리오 시작")

# ================== 유틸리티 및 계산 함수 ==================
def read_speed_kmh(car):
    try:
        return float(car.Speed(1))
    except:
        return float(car.Speed()) * 3.6

def get_bump_width(bump_type):
    if bump_type == 'A': return 3.6
    if bump_type == 'B': return 1.8
    return 3.0

def calculate_rms(h_m, L_m, v_mps, gain):
    if v_mps <= 0: return 0.0
    term1 = gain * (1.0 / math.sqrt(2.0)) * h_m
    term2 = (v_mps * math.pi / L_m)**2
    return term1 * term2

# ================== 새로운 동적 제동 함수 ==================
def smooth_dynamic_brake(car, brake_plan, poll_dt, p_gain):
    """
    계산된 감속 계획에 따라 Brake 값을 유동적으로 조절하여 부드럽게 감속합니다.
    """
    print("[Control] 동적 감속 시퀀스 시작.")
    
    # --- 1. 감속 시작 지점(Bp)까지 대기 ---
    initial_dist_to_bump = brake_plan['initial_dist_m']
    dist_to_brake_point = brake_plan['dist_to_brake_point']
    
    while True:
        current_pos = car.DistanceAlongRoad
        dist_traveled = current_pos - brake_plan['start_pos']
        remaining_dist = initial_dist_to_bump - dist_traveled
        
        if remaining_dist <= dist_to_brake_point:
            print(f"\n[Control] 감속 시작 지점 도달. (남은 거리: {remaining_dist:.1f}m)")
            break
        
        current_speed = read_speed_kmh(car)
        print(f"[Control] 감속 지점 접근 중... (남은 거리: {remaining_dist:.1f}m, 현재 속도: {current_speed:.1f} km/h)", end='\r')
        time.sleep(poll_dt)

    # --- 2. 과속방지턱까지 동적 제동 실행 ---
    braking_duration_est = brake_plan['braking_duration']
    start_braking_pos = car.DistanceAlongRoad
    
    while True:
        # 현재 주행 정보 업데이트
        current_pos = car.DistanceAlongRoad
        dist_traveled_while_braking = current_pos - start_braking_pos
        
        # 감속 완료 조건: 과속방지턱을 통과했거나, 감속 시작점보다 뒤로 간 경우
        if dist_traveled_while_braking >= dist_to_brake_point or dist_traveled_while_braking < 0:
            print("\n[Control] 과속방지턱 통과. 동적 감속을 종료합니다.")
            break

        # S-Curve(Ease-in-out) 보간을 사용하여 부드러운 감속 프로파일 생성
        progress = dist_traveled_while_braking / dist_to_brake_point
        eased_progress = 0.5 * (1 - math.cos(progress * math.pi))

        # 현재 위치에서 가져야 할 이상적인 속도 계산
        start_v_mps = brake_plan['start_speed_mps']
        target_v_mps = brake_plan['target_speed_mps']
        ideal_speed_mps = start_v_mps - (start_v_mps - target_v_mps) * eased_progress
        
        # 실제 속도와 이상적 속도의 차이(오차) 계산
        current_speed_mps = read_speed_kmh(car) / 3.6
        speed_error = current_speed_mps - ideal_speed_mps
        
        # 오차에 비례하여 Brake 값 결정 (비례 제어)
        brake_value = 0.0
        if speed_error > 0: # 실제 속도가 더 빠를 때만 제동
            brake_value = speed_error * p_gain
        
        # Brake 값은 0.0 ~ 1.0 사이로 제한
        brake_value = max(0.0, min(1.0, brake_value))

        try:
            car.Throttle = 0.0
            car.Brake = brake_value
        except Exception:
            pass
        
        print(f"[Control] 동적 제어 중... 실제 속도: {current_speed_mps*3.6:.1f} km/h | 이상적 속도: {ideal_speed_mps*3.6:.1f} km/h | Brake: {brake_value:.2f}", end='\r')
        time.sleep(poll_dt)

    # 제동 종료 후 차량 상태 복구
    try:
        car.Brake = 0.0
    except Exception:
        pass


# ================== 메인 제어 로직 함수 ==================
def run_control_simulation(vision_queue):
    print("[Control] 제어 시뮬레이션 프로세스 시작")

    # === ⭐ 튜닝 파라미터 ⭐ ===
    # 이 값을 조절하여 제동의 반응성을 튜닝할 수 있습니다.
    # 값이 크면: 오차에 민감하게 반응하여 더 강하게 제동 (반응성 좋음, 승차감 나쁨)
    # 값이 작으면: 오차에 둔감하게 반응하여 더 약하게 제동 (반응성 나쁨, 승차감 좋음)
    P_GAIN = 0.8        # 비례 제어 게인 (Proportional Gain)

    POLL_DT = 0.1       # 제어 주기 (사용자 요청에 따라 0.1초 유지)
    BRAKING_GENTLENESS_SEC_PER_10KMH = 1.5
    CAL_GAIN = 0.124
    COMFORT_TARGETS_RMS = {'매우 쾌적함': 0.315, '쾌적함': 0.5, '보통': 0.8}

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
            car = driver.CurrentCar
            if car is None: time.sleep(0.2)
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        
        print(f"[Control] UC-win/Road 연결 및 차량 핸들 확보 완료.")
    except Exception as e:
        print(f"[Control] UC-win/Road 연결 실패: {e}")
        return

    is_controlling = False

    while True:
        if not is_controlling:
            try:
                data = vision_queue.get_nowait()
                bump_type, dist_m, h_m = data['type'], data['distance_m'], data['height_m']
                
                print(f"\n[Control][수신 완료]T:{bump_type}|D:{dist_m:.1f}m|H:{h_m*100:.1f}cm")

                if bump_type in ['A', 'B', 'C']:
                    is_controlling = True
                    
                    v_kmh_now = read_speed_kmh(car)
                    v_mps_now = v_kmh_now / 3.6
                    bump_width = get_bump_width(bump_type)
                    plan_found = False
                    
                    for comfort_level, target_rms in sorted(COMFORT_TARGETS_RMS.items(), key=lambda item: item[1]):
                        if h_m > 0 and CAL_GAIN > 0:
                            target_v_mps = (bump_width / math.pi) * math.sqrt(target_rms / (CAL_GAIN * (1.0/math.sqrt(2.0)) * h_m))
                        else:
                            target_v_mps = 30 / 3.6

                        effective_deceleration_rate = (10 / 3.6) / BRAKING_GENTLENESS_SEC_PER_10KMH
                        braking_dist_needed = (v_mps_now**2 - target_v_mps**2) / (2 * effective_deceleration_rate)

                        if braking_dist_needed < dist_m:
                            dist_to_brake_point = dist_m - braking_dist_needed
                            expected_rms = calculate_rms(h_m, bump_width, target_v_mps, CAL_GAIN)
                            braking_duration = (v_mps_now - target_v_mps) / effective_deceleration_rate

                            print(f"[Control][Respond]Bp:{dist_to_brake_point:.1f}m|S:{v_kmh_now:.1f}km/h|tS:{target_v_mps*3.6:.1f}km/h|eR:{expected_rms:.3f}|승차감:{comfort_level}")
                            
                            brake_plan = {
                                'start_pos': car.DistanceAlongRoad,
                                'initial_dist_m': dist_m,
                                'dist_to_brake_point': dist_to_brake_point,
                                'start_speed_mps': v_mps_now,
                                'target_speed_mps': target_v_mps,
                                'braking_duration': braking_duration
                            }

                            smooth_dynamic_brake(car, brake_plan, POLL_DT, P_GAIN)
                            plan_found = True
                            break
                    
                    if not plan_found:
                        target_v_mps = 10 / 3.6
                        expected_rms = calculate_rms(h_m, bump_width, target_v_mps, CAL_GAIN)
                        print(f"[Control][Respond]Bp:즉시|S:{v_kmh_now:.1f}km/h|tS:{target_v_ps*3.6:.1f}km/h|eR:{expected_rms:.3f}|승차감:비상")
                        # 비상 시에는 기존의 강한 제동을 유지할 수 있습니다.
                        # hard_takeover_and_brake(car, target_v_mps*3.6, POLL_DT, 4.0)

                    is_controlling = False
                    print("\n[Control] AI가 제어권을 되찾아 주행을 재개합니다. 다음 신호를 대기합니다.")
                else:
                    print("[Control] 감속 불필요. 주행을 유지합니다.")

            except queue.Empty:
                current_speed = read_speed_kmh(car)
                print(f"[Control] 현재 속도: {current_speed:.1f} km/h | Vision 신호 대기 중...", end='\r')
            
            except Exception as e:
                print(f"\n[Control] 제어 중 오류 발생: {e}")
                is_controlling = False
        
        time.sleep(POLL_DT)