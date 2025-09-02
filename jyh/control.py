# control.py
import time, math, queue, numpy as np
from win32com.client import Dispatch, GetActiveObject
from logger import print_at

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

def read_speed_kmh(car):
    try: return float(car.Speed(1))
    except: return float(car.Speed()) * 3.6

def get_bump_width(bump_type_str):
    if 'a' in bump_type_str.lower(): return 3.6
    if 'b' in bump_type_str.lower(): return 1.8
    return 3.0

def calculate_rms(h_m, L_m, v_mps, gain):
    if v_mps <= 0 or L_m <= 0: return 0.0
    return gain * (1.0 / math.sqrt(2.0)) * h_m * (v_mps * math.pi / L_m)**2

def classify_rms(rms_value):
    if rms_value < 0.315: return "쾌적함"
    if rms_value < 0.5: return "쾌적함"
    if rms_value < 0.8: return "보통"
    if rms_value < 1.25: return "불쾌함"
    return "매우 불쾌함"
    
def solve_speed_for_target_rms(h_m, L_m, target_rms, gain):
    if h_m <= 0 or L_m <= 0 or target_rms <= 0 or gain <=0: return 0.0
    denominator = gain * (1.0/math.sqrt(2.0)) * h_m * (math.pi/L_m)**2
    if denominator <= 0: return 0.0
    return math.sqrt(target_rms / denominator)

def estimate_min_speed_kmh(current_speed_kmh):
    speed_map = { 40: 3.9, 50: 19.8, 60: 37.2, 70: 54.3, 80: 64.4, 90: 71.8 }
    x_speeds, y_ms = list(speed_map.keys()), list(speed_map.values())
    if current_speed_kmh <= x_speeds[0]: return y_ms[0]
    if current_speed_kmh >= x_speeds[-1]: return y_ms[-1]
    return np.interp(current_speed_kmh, x_speeds, y_ms)

def calculate_brake_pwm(current, target, dist, weight):
    speed_diff = max(0, current - target)
    speed_factor = min(1.0, speed_diff / 60.0) 
    dist_factor = 1.0 - min(1.0, dist / 50.0)
    raw_pwm = weight * ((0.7 * speed_factor) + (0.7 * dist_factor))
    return max(0.5, min(1.0, raw_pwm))

def execute_control(car, target_speed_kmh, pwm, poll_dt):
    start_time = time.time()
    while time.time() - start_time < 10.0:
        current_speed_kmh = read_speed_kmh(car)
        log_msg = f"[Control] S:{current_speed_kmh:.1f}km/h | B:{int(pwm*100)}% (tS:{target_speed_kmh:.1f}km/h)"
        print_at('CONTROL_STATE', log_msg)
        if current_speed_kmh <= target_speed_kmh: break
        try:
            on_time = poll_dt * pwm; off_time = poll_dt * (1.0 - pwm)
            car.Throttle = 0.0
            if on_time > 0: car.ParkingBrake = True; time.sleep(on_time)
            if off_time > 0: car.ParkingBrake = False; time.sleep(off_time)
        except Exception: break
    try: car.Brake = 0.0; car.ParkingBrake = False
    except Exception: pass

def run_control_simulation(vision_to_control_queue, control_to_eval_queue, eval_to_control_queue):
    POLL_DT = 0.15; CAL_GAIN = 0.050; PWM_WEIGHT = 1.2
    COMFORT_TARGETS_RMS = {'쾌적함': 0.5, '보통': 0.8}
    TARGET_SPEED_MARGIN_KMH = 3.0

    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore; proj = ucwin.Project; driver = sim_core.TrafficSimulation.Driver
        restart_scenario(sim_core, proj, 0)
        car = None; t0 = time.time()
        while car is None and time.time() - t0 < 15.0:
            car = driver.CurrentCar; time.sleep(0.2)
        if car is None: return
    except Exception: return

    is_controlling = False
    
    # === 시나리오 자동 전환 관리 변수 ===
    current_scenario = 0
    SWITCH_TRIGGER_X = 2100.0
    switched_this_round = False
    last_x = None

    while True:
        # === 차량 좌표 확인 후 시나리오 전환 로직 (추가된 기능) ===
        try:
            pos = car.Position
            x = float(pos.X)

            if last_x is not None and last_x > SWITCH_TRIGGER_X and x <= SWITCH_TRIGGER_X and not switched_this_round:
                current_scenario = 1 if current_scenario == 0 else 0
                restart_scenario(sim_core, proj, current_scenario)

                car = None
                t0 = time.time()
                while car is None and time.time() - t0 < 15.0:
                    car = driver.CurrentCar; time.sleep(0.2)
                if car is None: raise RuntimeError("재시작 후 차량 핸들 획득 실패")
                
                switched_this_round = True
            
            elif x > 3500: # 출발지점(4000m 부근)으로 돌아오면 다시 전환 준비
                switched_this_round = False
            
            last_x = x
        except Exception:
            pass
        # =======================================================

        try:
            eval_msg = eval_to_control_queue.get_nowait()
            if eval_msg.get("msg") == "evaluate":
                old_cal, old_pwm_w = CAL_GAIN, PWM_WEIGHT
                CAL_GAIN *= eval_msg.get("CAL_GAIN_SCALE", 1.0)
                PWM_WEIGHT *= eval_msg.get("PWM_WEIGHT_SCALE", 1.0)
                log_msg = f"[Control] Ps:{old_pwm_w:.2f} -> {PWM_WEIGHT:.2f} | Rs:{old_cal:.4f} -> {CAL_GAIN:.4f}"
                print_at('CORRECTION', log_msg)
        except queue.Empty: pass

        if not is_controlling:
            try:
                data = vision_to_control_queue.get_nowait()
                source, h_m, dist_m, bump_type = data['source'], data['height_m'], data['distance_m'], data['type']
                
                print_at('CONTROL_RECV', f"[Control][{source}] H:{h_m*100:.1f}cm | D:{dist_m:.1f}m | T:{bump_type}")

                if 'D' in str(bump_type).upper(): continue

                is_controlling = True
                current_speed_kmh = read_speed_kmh(car)
                mS_kmh = estimate_min_speed_kmh(current_speed_kmh)
                bump_width_m = data.get('width_m', get_bump_width(bump_type))
                eR_rms = calculate_rms(h_m, bump_width_m, mS_kmh / 3.6, CAL_GAIN)
                comfort_level = classify_rms(eR_rms)
                
                if comfort_level in ["불쾌함", "매우 불쾌함"]: tS_kmh = mS_kmh
                else:
                    target_rms = COMFORT_TARGETS_RMS.get(comfort_level, 0.5)
                    optimal_v_mps = solve_speed_for_target_rms(h_m, bump_width_m, target_rms, CAL_GAIN)
                    tS_kmh = max(mS_kmh, optimal_v_mps * 3.6) + TARGET_SPEED_MARGIN_KMH
                
                print_at('CONTROL_PLAN', f"[Control] tS:{tS_kmh:.1f}km/h|eR:{eR_rms:.2f}|예상 승차감:{comfort_level}")
                
                control_to_eval_queue.put({"tS":tS_kmh, "eR":eR_rms, "type":bump_type, "msg":"control"})
                
                brake_pwm = calculate_brake_pwm(current_speed_kmh, tS_kmh, dist_m, PWM_WEIGHT)
                execute_control(car, tS_kmh, brake_pwm, POLL_DT)
                is_controlling = False

            except queue.Empty:
                print_at('CONTROL_STATE', f"[Control] S:{read_speed_kmh(car):.1f}km/h")
        
        time.sleep(0.1)