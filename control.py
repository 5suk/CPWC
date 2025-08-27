# control.py
import time, math, queue
import win32com.client
from win32com.client import Dispatch, GetActiveObject

# ================== UC-win/Road 연결 및 제어 함수 ==================
PROGID = "UCwinRoad.F8ApplicationServicesProxy"
def attach_or_launch():
    try:    return GetActiveObject(PROGID)
    except: return Dispatch(PROGID)

def restart_scenario(sim, proj, idx=0):
    try:
        if hasattr(sim, "StopScenario"): sim.StopScenario(); time.sleep(0.5)
    except Exception: pass
    sc = proj.Scenario(idx)
    sim.StartScenario(sc)
    time.sleep(1.0)

# ================== 유틸리티 및 RMS 계산 함수 ==================
def kmh_to_mps(v): return v/3.6
def mps_to_kmh(v): return v*3.6

def _vec3(v):
    for names in (("X","Y","Z"), ("x","y","z")):
        if all(hasattr(v, n) for n in names): return float(getattr(v, names[0])), float(getattr(v, names[1])), float(getattr(v, names[2]))
    for m in ("Item","get_Item","GetAt","Get"):
        if hasattr(v, m): f = getattr(v, m); return float(f(0)), float(f(1)), float(f(2))
    seq = list(v); return float(seq[0]), float(seq[1]), float(seq[2])

def speed_kmh(drv):
    c = drv.CurrentCar
    if c is None: return 0.0
    try: sv = c.SpeedVector(0)
    except TypeError: sv = c.SpeedVector()
    vx,vy,vz = _vec3(sv)
    v_mps = (vx**2 + vy**2 + vz**2)**0.5
    return mps_to_kmh(v_mps)

def set_speed_once_kmh(drv, v_kmh):
    c = drv.CurrentCar
    if c is None: return
    try: c.SetSpeed(kmh_to_mps(v_kmh), 0)
    except Exception: pass

def solve_speed_for_target_rms(h_m, L_m, target_rms, gain):
    if h_m <= 0 or L_m <= 0 or target_rms <= 0: return 0.0
    denom = gain * (1.0/math.sqrt(2.0)) * h_m
    if denom <= 0: return 0.0
    v_mps = (L_m / math.pi) * math.sqrt(target_rms / denom)
    return v_mps

def get_bump_width(bump_type):
    if bump_type == 'A': return 3.6
    if bump_type == 'B': return 1.8
    return 3.0

# ================== 메인 제어 로직 함수 ==================
def run_control_simulation(vision_queue):
    print("[Control] 제어 시뮬레이션 프로세스를 시작합니다. (실제 제어 실행)")
    
    # === 최종 튜닝 파라미터 ===
    CAL_GAIN = 0.124
    SAMPLE_HZ = 20.0
    DT = 1.0 / SAMPLE_HZ
    COMFORT_TARGETS_RMS = {'매우 쾌적함': 0.315, '쾌적함': 0.5}
    BRAKING_GENTLENESS_SEC_PER_10KMH = 1.5
    
    # [수정] 제어 명령을 내릴 속도 오차의 허용 범위 (km/h)
    # 실제 속도와 이상적인 속도의 차이가 이 값보다 클 때만 SetSpeed 명령을 내립니다.
    SPEED_CONTROL_TOLERANCE_KMH = 2.0

    # ... (UC-win/Road 연결 부분은 이전과 동일) ...
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
        loop_t = time.time()
        v_kmh_now = speed_kmh(driver)
        
        try:
            if braking_plan is None:
                data = vision_queue.get_nowait()
                # ... (이하 계획 수립 로직은 이전과 동일) ...
                h_m = data['height_m']
                dist_m = data['distance_m']
                v_mps_now = kmh_to_mps(v_kmh_now)
                bump_type = data['type']
                bump_width = get_bump_width(bump_type)
                print(f"\n[Control] Vision 신호 수신: 타입={bump_type}, 높이={h_m*100:.1f}cm, 거리={dist_m:.1f}m. 최적 감속 계획 수립...")
                if bump_type == 'D' or h_m <= 0:
                    print("--- [계획(무시)] 감속 불필요. 현재 주행 상태 유지 ---")
                else:
                    plan_found = False
                    for comfort_level, target_rms in COMFORT_TARGETS_RMS.items():
                        target_v_mps = solve_speed_for_target_rms(h_m, bump_width, target_rms, CAL_GAIN)
                        if target_v_mps >= v_mps_now or dist_m <= 0: continue
                        effective_deceleration_rate = (10 / 3.6) / BRAKING_GENTLENESS_SEC_PER_10KMH
                        braking_dist_needed = (target_v_mps**2 - v_mps_now**2) / (2 * -effective_deceleration_rate)
                        if braking_dist_needed <= dist_m:
                            dist_to_brake_point = dist_m - braking_dist_needed
                            time_to_brake_point = dist_to_brake_point / v_mps_now if v_mps_now > 0 else 0
                            braking_duration = (v_mps_now - target_v_mps) / effective_deceleration_rate
                            braking_plan = {'status': 'active', 'wait_duration': time_to_brake_point,
                                            'braking_duration': braking_duration, 'start_speed_mps': v_mps_now,
                                            'target_speed_mps': target_v_mps}
                            print(f"--- [계획({comfort_level})] {braking_plan['wait_duration']:.1f}초 후, {braking_plan['braking_duration']:.1f}초 동안 감속하여 {mps_to_kmh(braking_plan['target_speed_mps']):.1f}km/h 도달 ---")
                            plan_creation_time = loop_t
                            plan_found = True
                            break
                    if not plan_found:
                        effective_deceleration_rate = (10 / 3.6) / BRAKING_GENTLENESS_SEC_PER_10KMH
                        braking_duration = (v_mps_now - 0) / effective_deceleration_rate
                        braking_plan = {'status': 'active', 'wait_duration': 0, 'braking_duration': braking_duration,
                                        'start_speed_mps': v_mps_now, 'target_speed_mps': 0}
                        print(f"--- [계획(최선 노력)] 즉시 {braking_plan['braking_duration']:.1f}초 동안 최대 감속 ---")
                        plan_creation_time = loop_t
        except queue.Empty:
            pass
        except Exception as e:
            print(f"제어 중 오류 발생: {e}")
            braking_plan = None
            
        # 2. 수립된 계획에 따라 능동 감속 프로파일 실행
        if braking_plan and braking_plan.get('status') == 'active':
            elapsed_time = loop_t - plan_creation_time
            if elapsed_time < braking_plan['wait_duration']:
                print(f"[Control] 감속 지점 접근 중... ({elapsed_time / braking_plan['wait_duration'] * 100:.1f}%)", end='\r')
            else:
                braking_progress = (elapsed_time - braking_plan['wait_duration']) / braking_plan['braking_duration'] if braking_plan['braking_duration'] > 0 else 1.0
                
                if braking_progress < 1.0:
                    start_v = braking_plan['start_speed_mps']
                    target_v = braking_plan['target_speed_mps']
                    
                    # S-Curve(Ease-in-out) 보간을 위한 진행률 재계산
                    eased_progress = 0.5 * (1 - math.cos(braking_progress * math.pi))
                    ideal_target_v_mps = start_v - (start_v - target_v) * eased_progress
                    
                    # [수정] 실제 속도와 이상적인 속도의 차이가 허용 오차보다 클 때만 제어 명령 전송
                    speed_error_kmh = mps_to_kmh(ideal_target_v_mps) - v_kmh_now
                    if abs(speed_error_kmh) > SPEED_CONTROL_TOLERANCE_KMH:
                        set_speed_once_kmh(driver, mps_to_kmh(ideal_target_v_mps))

                    print(f"[Control] 능동 감속 진행 중... 실제 속도: {v_kmh_now:.1f} km/h | 이상적 속도: {mps_to_kmh(ideal_target_v_mps):.1f} km/h", end='\r')
                else:
                    print("\n[Control] 감속 완료. 다음 방지턱을 준비합니다.")
                    final_target_speed = braking_plan['target_speed_mps']
                    set_speed_once_kmh(driver, mps_to_kmh(final_target_speed))
                    braking_plan = None
        
        elif braking_plan is None:
            print(f"[Control] 현재 속도: {v_kmh_now:.2f} km/h, Vision 신호 대기 중...", end='\r')

        time.sleep(max(0.0, DT - (time.time() - loop_t)))