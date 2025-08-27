# control.py
import time
import math
import queue
import win32com.client
from win32com.client import Dispatch, GetActiveObject

# ================== UC-win/Road 연결 및 제어 함수 ==================
PROGID = "UCwinRoad.F8ApplicationServicesProxy"

def attach_or_launch():
    try:
        return GetActiveObject(PROGID)
    except:
        return Dispatch(PROGID)

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

# ================== 유틸리티 및 계산 함수 ==================
def kmh_to_mps(v): return v / 3.6
def mps_to_kmh(v): return v * 3.6

def _vec3(v):
    for names in (("X", "Y", "Z"), ("x", "y", "z")):
        if all(hasattr(v, n) for n in names): return float(getattr(v, names[0])), float(getattr(v, names[1])), float(getattr(v, names[2]))
    for m in ("Item", "get_Item", "GetAt", "Get"):
        if hasattr(v, m):
            f = getattr(v, m)
            return float(f(0)), float(f(1)), float(f(2))
    seq = list(v)
    return float(seq[0]), float(seq[1]), float(seq[2])

def speed_kmh(drv):
    c = drv.CurrentCar
    if c is None: return 0.0
    try:
        sv = c.SpeedVector(0)
    except TypeError:
        sv = c.SpeedVector()
    vx, vy, vz = _vec3(sv)
    v_mps = (vx**2 + vy**2 + vz**2)**0.5
    return mps_to_kmh(v_mps)

def set_driving_ai_target_speed_kmh(drv, v_kmh):
    """
    차량 AI의 목표 주행 속도(SpeedLimit)를 설정합니다. (단위: km/h)
    이 함수가 부드러운 제어의 핵심입니다.
    """
    try:
        target_v_mps = kmh_to_mps(v_kmh)
        drv.SetSpeedLimit(target_v_mps)
    except Exception as e:
        print(f"[Control Error] SetSpeedLimit 호출 실패: {e}")

def get_bump_width(bump_type):
    if bump_type == 'A': return 3.6
    if bump_type == 'B': return 1.8
    return 3.0

def solve_target_speed_mps(h_m, L_m, target_rms, gain):
    """목표 승차감(RMS)을 만족하기 위한 목표 통과 속도를 계산합니다."""
    if h_m <= 0 or L_m <= 0 or target_rms <= 0: return 0.0
    denom = gain * (1.0 / math.sqrt(2.0)) * h_m
    if denom <= 0: return float('inf')
    inner_value = target_rms / denom
    if inner_value < 0: return float('inf')
    v_mps = (L_m / math.pi) * math.sqrt(inner_value)
    return v_mps

# ================== 메인 제어 로직 함수 ==================
def run_control_simulation(vision_queue):
    print("[Control] 제어 시뮬레이션 프로세스 시작")

    # === 튜닝 파라미터 ===
    CAL_GAIN = 0.124
    SAMPLE_HZ = 20.0
    DT = 1.0 / SAMPLE_HZ
    COMFORT_TARGETS_RMS = {'매우 쾌적함': 0.315, '쾌적함': 0.5, '보통': 0.8}
    BRAKING_GENTLENESS_SEC_PER_10KMH = 1.5

    # === UC-win/Road 연결 ===
    try:
        ucwin = attach_or_launch()
        sim = ucwin.SimulationCore
        proj = ucwin.Project
        driver = sim.TrafficSimulation.Driver
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

    braking_plan = None
    plan_creation_time = 0

    while True:
        loop_start_time = time.time()
        v_kmh_now = speed_kmh(driver)

        # 1. Vision 정보 수신 및 감속 계획 수립 (기존 계획이 없을 때만)
        if braking_plan is None:
            try:
                data = vision_queue.get_nowait()
                h_m = data['height_m']
                dist_m = data['distance_m']
                bump_type = data['type']
                bump_width = get_bump_width(bump_type)
                
                print(f"\n[Control] Vision 신호 수신. 최적 감속 계획 수립 시작...")
                print(f"         - 방지턱 정보: 타입={bump_type}, 높이={h_m*100:.1f}cm, 폭={bump_width:.1f}m, 거리={dist_m:.1f}m")
                print(f"         - 현재 차량 속도: {v_kmh_now:.1f} km/h")

                if bump_type == 'D' or h_m <= 0:
                    print("         - [계산 결과] 감속 불필요. 현재 주행 상태를 유지합니다.")
                else:
                    plan_found = False
                    for comfort_level, target_rms in COMFORT_TARGETS_RMS.items():
                        target_v_mps = solve_target_speed_mps(h_m, bump_width, target_rms, CAL_GAIN)
                        v_mps_now = kmh_to_mps(v_kmh_now)
                        if target_v_mps >= v_mps_now: continue
                        
                        effective_deceleration_rate = (10 / 3.6) / BRAKING_GENTLENESS_SEC_PER_10KMH
                        braking_dist_needed = (v_mps_now**2 - target_v_mps**2) / (2 * effective_deceleration_rate)

                        print(f"         - [{comfort_level} 분석] 목표 통과 속도: {mps_to_kmh(target_v_mps):.1f} km/h, 필요 감속 거리: {braking_dist_needed:.1f}m")

                        if braking_dist_needed < dist_m:
                            dist_to_brake_point = dist_m - braking_dist_needed
                            time_to_brake_point = dist_to_brake_point / v_mps_now if v_mps_now > 0 else 0
                            braking_duration = (v_mps_now - target_v_mps) / effective_deceleration_rate
                            
                            braking_plan = {
                                'status': 'active', 'wait_duration': time_to_brake_point,
                                'braking_duration': braking_duration, 'start_speed_mps': v_mps_now,
                                'target_speed_mps': target_v_mps
                            }
                            print(f"         - [최종 계획 확정({comfort_level})]")
                            print(f"           - {braking_plan['wait_duration']:.1f}초 후 감속 시작")
                            print(f"           - {braking_plan['braking_duration']:.1f}초 동안 점진적 감속")
                            print(f"           - 최종 목표 속도: {mps_to_kmh(braking_plan['target_speed_mps']):.1f} km/h")
                            
                            plan_creation_time = loop_start_time
                            plan_found = True
                            break
                    
                    if not plan_found:
                        print("         - [계산 결과] 어떤 쾌적함 수준으로도 시간 내에 감속할 수 없습니다. 즉시 최선 감속을 시작합니다.")
                        target_v_mps = solve_target_speed_mps(h_m, bump_width, list(COMFORT_TARGETS_RMS.values())[0], CAL_GAIN)
                        effective_deceleration_rate = (10 / 3.6) / BRAKING_GENTLENESS_SEC_PER_10KMH
                        braking_duration = (kmh_to_mps(v_kmh_now) - target_v_mps) / effective_deceleration_rate
                        braking_plan = {
                                'status': 'active', 'wait_duration': 0, 'braking_duration': max(0.1, braking_duration),
                                'start_speed_mps': kmh_to_mps(v_kmh_now), 'target_speed_mps': target_v_mps
                            }
                        plan_creation_time = loop_start_time

            except queue.Empty:
                pass
            except Exception as e:
                print(f"제어 중 오류 발생: {e}")
                braking_plan = None

        # 2. 수립된 계획에 따라 AI 목표 속도(SpeedLimit) 제어
        if braking_plan and braking_plan.get('status') == 'active':
            elapsed_time = loop_start_time - plan_creation_time
            
            if elapsed_time < braking_plan['wait_duration']:
                progress = elapsed_time / braking_plan['wait_duration'] * 100
                print(f"[Control] 감속 지점 접근 중... ({progress:.1f}%) | 현재 속도: {v_kmh_now:.1f} km/h", end='\r')
            else:
                progress = (elapsed_time - braking_plan['wait_duration']) / braking_plan['braking_duration'] if braking_plan['braking_duration'] > 0 else 1.0
                progress = min(1.0, progress)
                
                if progress < 1.0:
                    start_v = braking_plan['start_speed_mps']
                    target_v = braking_plan['target_speed_mps']
                    
                    eased_progress = 0.5 * (1 - math.cos(progress * math.pi))
                    ideal_target_v_mps = start_v - (start_v - target_v) * eased_progress
                    
                    set_driving_ai_target_speed_kmh(driver, mps_to_kmh(ideal_target_v_mps))

                    print(f"[Control] 능동 감속 진행 중... ({progress*100:.1f}%) | 실제 속도: {v_kmh_now:.1f} km/h | 목표: {mps_to_kmh(ideal_target_v_mps):.1f} km/h", end='\r')
                else:
                    final_target_speed_kmh = mps_to_kmh(braking_plan['target_speed_mps'])
                    set_driving_ai_target_speed_kmh(driver, final_target_speed_kmh)
                    print(f"\n[Control] 감속 완료. 최종 목표 속도({final_target_speed_kmh:.1f} km/h) 설정. 다음 신호 대기.")
                    braking_plan = None
        
        elif braking_plan is None:
            print(f"[Control] 현재 속도: {v_kmh_now:.1f} km/h | Vision 신호 대기 중...", end='\r')
        
        time.sleep(max(0.0, DT - (time.time() - loop_start_time)))