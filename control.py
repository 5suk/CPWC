# control.py
import time
import math
import queue
import numpy as np
import pythoncom
from win32com.client import Dispatch, GetActiveObject
from logger import print_at, log_sequence_to_file
from samples.UCwinRoadCOM import UCwinRoadComProxy
from samples.UCwinRoadUtils import Distance

PROGID = "UCwinRoad.F8ApplicationServicesProxy"
TYPE_TO_KEYWORD = {"A": "typea", "B": "typeb", "C": "typec"}

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

def vector_magnitude(v_obj):
    try: return math.sqrt(v_obj.X**2 + v_obj.Y**2 + v_obj.Z**2)
    except Exception: return 0.0

def find_all_bumps_and_cache(project):
    speed_bumps_cache = []
    try:
        instance_count = project.ThreeDModelInstancesCount
        for i in range(instance_count):
            instance = project.ThreeDModelInstance(i)
            if any(keyword in instance.Name.lower() for keyword in TYPE_TO_KEYWORD.values()):
                height, depth = 0.0, 0.0
                if instance.BoundingBoxesCount > 0:
                    bbox = instance.BoundingBox(0)
                    height = vector_magnitude(bbox.yAxis) * 2
                    depth = vector_magnitude(bbox.zAxis) * 2
                speed_bumps_cache.append({
                    "instance": instance, "name": instance.Name,
                    "gt_h": height, "gt_d": depth
                })
    except Exception:
        pass
    return speed_bumps_cache


def find_target_bump(car, bump_type, bump_cache):
    keyword = TYPE_TO_KEYWORD.get(bump_type)
    if not keyword or not bump_cache: return None

    car_pos = car.Position
    car_dir = car.Direction
    
    closest_dist = float('inf')
    target_bump = None

    for bump_data in bump_cache:
        if keyword in bump_data["name"].lower():
            bump_pos = bump_data["instance"].Position
            vec_to_bump_x = bump_pos.X - car_pos.X
            vec_to_bump_z = bump_pos.Z - car_pos.Z
            dot_product = (car_dir.X * vec_to_bump_x) + (car_dir.Z * vec_to_bump_z)

            if dot_product > 0:
                dist = Distance(car_pos, bump_pos)
                if dist < closest_dist:
                    closest_dist = dist
                    target_bump = bump_data
    return target_bump

def calculate_rms(h_m, L_m, v_mps, gain):
    if not all(isinstance(x, (int, float)) for x in [h_m, L_m, v_mps, gain if gain is not None else 0]): return 0.0
    if v_mps <= 0 or L_m <= 0: return 0.0
    return gain * (1.0 / math.sqrt(2.0)) * h_m * (v_mps * math.pi / L_m)**2

def classify_rms(rms_value):
    if rms_value is None: return "계산 불가"
    if rms_value < 0.315: return "매우 쾌적함"
    if rms_value < 0.5: return "쾌적함"
    if rms_value < 0.8: return "보통"
    if rms_value < 1.25: return "불쾌함"
    return "매우 불쾌함"
    
def solve_speed_for_target_rms(h_m, L_m, target_rms, gain):
    if not all(isinstance(x, (int, float)) for x in [h_m, L_m, target_rms, gain if gain is not None else 0]): return 0.0
    if h_m <= 0 or L_m <= 0 or target_rms <= 0 or gain <=0: return 0.0
    denominator = gain * (1.0/math.sqrt(2.0)) * h_m * (math.pi/L_m)**2
    if denominator <= 0: return 0.0
    return math.sqrt(target_rms / denominator)

def estimate_min_speed_kmh(current_speed_kmh):
    speed_map = {
        40: np.mean([5.19, 2.79, 3.71]), 50: np.mean([21.42, 17.17, 20.84]),
        60: np.mean([37.08, 39.03, 35.63]), 70: np.mean([55.02, 52.70, 53.09]),
        80: np.mean([63.87, 65.28, 64.04]), 90: np.mean([72.35, 70.13, 71.02]),
    }
    x_speeds, y_ms = list(speed_map.keys()), list(speed_map.values())
    if current_speed_kmh <= x_speeds[0]: return y_ms[0]
    if current_speed_kmh >= x_speeds[-1]: return y_ms[-1]
    return np.interp(current_speed_kmh, x_speeds, y_ms)

def calculate_brake_pwm(current_speed_kmh, target_speed_kmh, distance_to_bump_m, weight):
    speed_diff = max(0, current_speed_kmh - target_speed_kmh)
    speed_diff_factor = min(1.0, speed_diff / 60.0) 
    urgency_distance = 50.0 
    distance_factor = 1.0 - min(1.0, distance_to_bump_m / urgency_distance)
    raw_pwm = weight * ((0.7 * speed_diff_factor) + (0.7 * distance_factor))
    return max(0.5, min(1.0, raw_pwm))

def run_control_simulation(vision_to_control_queue, control_to_eval_queue, eval_to_control_queue):
    pythoncom.CoInitialize()
    POLL_DT = 0.15; CAL_GAIN = 0.050; PWM_WEIGHT = 1.2
    COMFORT_TARGETS_RMS = {'매우 쾌적함': 0.315, '쾌적함': 0.5, '보통': 0.8}
    TARGET_SPEED_MARGIN_KMH = 3.0
    PASS_DETECTION_THRESHOLD_M = 3.0

    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore; proj = ucwin.Project; driver = sim_core.TrafficSimulation.Driver
        restart_scenario(sim_core, proj, 0)
        car = None; t0 = time.time()
        while car is None and time.time() - t0 < 15.0:
            car = driver.CurrentCar; time.sleep(0.2)
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        
        bump_cache = find_all_bumps_and_cache(proj)
        
    except Exception:
        return

    is_controlling = False
    last_bump_type = "None"
    
    current_scenario = 0
    SWITCH_TRIGGER_X = 2100.0
    switched_this_round = False
    last_x = None
    
    pending_correction_data = None
    correction_log_for_file = "" # 파일 로깅용 보정 로그 저장 변수

    while True:
        try:
            pos = car.Position
            x = float(pos.X)
            if last_x is not None and last_x > SWITCH_TRIGGER_X and x <= SWITCH_TRIGGER_X and not switched_this_round:
                current_scenario = 1 if current_scenario == 0 else 0
                restart_scenario(sim_core, proj, current_scenario)
                
                car = None; t0 = time.time()
                while car is None and time.time() - t0 < 15.0: car = driver.CurrentCar; time.sleep(0.2)
                if car is None: raise RuntimeError("재시작 후 차량 핸들 획득 실패")

                bump_cache = find_all_bumps_and_cache(proj)
                
                is_controlling = False
                last_bump_type = "None"
                pending_correction_data = None
                print_at('DEBUG_DISTANCE', "")

                switched_this_round = True
            elif x > 3500: 
                switched_this_round = False
            last_x = x

            if not is_controlling and pending_correction_data:
                if pending_correction_data.get("msg") == "correction_factors":
                    old_gain, old_pwm = CAL_GAIN, PWM_WEIGHT
                    CAL_GAIN *= pending_correction_data.get("CAL_GAIN_SCALE", 1.0)
                    PWM_WEIGHT *= pending_correction_data.get("PWM_WEIGHT_SCALE", 1.0)
                    
                    correction_log = (f"[Control] 보정 적용: Gain {old_gain:.4f}→{CAL_GAIN:.4f} | "
                                      f"PWM_W {old_pwm:.2f}→{PWM_WEIGHT:.2f}")
                    print_at('CONTROL_CORRECTION', correction_log)
                    correction_log_for_file = correction_log # 파일 로깅을 위해 저장
                pending_correction_data = None

            data = vision_to_control_queue.get(timeout=0.1)
            
            if data['type'] != "None" and last_bump_type == "None" and not is_controlling:
                
                h_m = data.get('height_m')
                dist_m = data.get('distance_m')
                depth_m = data.get('depth_m')
                bump_type = data.get('type')
                
                if not all([isinstance(h_m, float), isinstance(dist_m, float), isinstance(depth_m, float), bump_type]):
                    last_bump_type = data.get('type', 'None')
                    continue

                if 'D' in str(bump_type).upper() or h_m <= 0 or depth_m <= 0:
                    last_bump_type = data.get('type', 'None')
                    continue

                is_controlling = True
                
                current_speed_kmh = read_speed_kmh(car)
                mS_kmh = estimate_min_speed_kmh(current_speed_kmh)
                eR_rms = calculate_rms(h_m, depth_m, mS_kmh / 3.6, CAL_GAIN)
                comfort_level = classify_rms(eR_rms)
                
                if comfort_level in ["불쾌함", "매우 불쾌함"]: tS_kmh = mS_kmh
                else:
                    target_rms = COMFORT_TARGETS_RMS.get(comfort_level, 0.5)
                    optimal_v_mps = solve_speed_for_target_rms(h_m, depth_m, target_rms, CAL_GAIN)
                    tS_kmh = max(mS_kmh, (optimal_v_mps * 3.6 if optimal_v_mps else 0) + TARGET_SPEED_MARGIN_KMH)
                
                brake_pwm = calculate_brake_pwm(current_speed_kmh, tS_kmh, dist_m, PWM_WEIGHT)

                source = data.get('source', 'N/A')
                recv_log_content = f"T:{bump_type}, H:{h_m*100:.1f}cm, Dt:{dist_m:.1f}m, Dp:{depth_m:.2f}m"
                plan_log_content = f"tS:{tS_kmh:.1f}km/h, eR:{eR_rms:.2f}, 예상 승차감:{comfort_level}"
                
                print_at('CONTROL_RECV', f"[{source}] {recv_log_content}")
                print_at('CONTROL_PLAN', f"[Control] {plan_log_content}")

                target_bump_obj = find_target_bump(car, bump_type, bump_cache)
                if not target_bump_obj:
                    print_at('DEBUG_DISTANCE', f"[Control] 경고: 추적할 {bump_type}타입 과속방지턱 객체를 찾지 못했습니다.")
                    is_controlling = False
                    last_bump_type = data['type']
                    continue
                
                min_dist_so_far = float('inf')
                has_approached = False
                
                start_time = time.time()
                while time.time() - start_time < 15.0:
                    car_pos = car.Position
                    bump_pos = target_bump_obj["instance"].Position
                    current_dist = Distance(car_pos, bump_pos)
                    
                    min_dist_so_far = min(min_dist_so_far, current_dist)
                    
                    if not has_approached and current_dist < PASS_DETECTION_THRESHOLD_M:
                        has_approached = True
                    
                    print_at('DEBUG_DISTANCE', f"({target_bump_obj['name']})과의 거리: {current_dist:.1f}m")
                    
                    s = read_speed_kmh(car)
                    print_at('CONTROL_STATE', f"[Control] S:{s:.1f}km/h | B:{int(brake_pwm*100)}%(tS:{tS_kmh:.1f}km/h)")
                    if s > tS_kmh:
                        try:
                            on_time = POLL_DT * brake_pwm; off_time = POLL_DT * (1.0 - brake_pwm)
                            car.Throttle = 0.0
                            if on_time > 0: car.ParkingBrake = True; time.sleep(on_time)
                            if off_time > 0: car.ParkingBrake = False; time.sleep(off_time)
                        except Exception: break
                    else:
                        car.ParkingBrake = False

                    if has_approached and current_dist > min_dist_so_far + 0.1:
                        break
                
                rS_kmh = read_speed_kmh(car)
                car.ParkingBrake = False
                
                eval_request = {
                    "msg": "evaluate_request", "rS_kmh": rS_kmh, "tS_kmh": tS_kmh, "eR_rms": eR_rms,
                    "gt_h": target_bump_obj["gt_h"], "gt_d": target_bump_obj["gt_d"]
                }
                control_to_eval_queue.put(eval_request)
                
                file_log_data = {
                    "DETECT": f"[{source}] {recv_log_content}",
                    "PLAN": f"[Control] {plan_log_content}",
                    "COLLISION": f"충돌 속도(rS): {rS_kmh:.1f}km/h (최소 근접 거리: {min_dist_so_far:.2f}m)"
                }
                
                try:
                    eval_response = eval_to_control_queue.get(timeout=2.0)
                    pending_correction_data = eval_response
                    
                    # 파일 로그에 Evaluate 결과와 보정 로그 추가
                    file_log_data["RESULT"] = f"[Evaluate] {eval_response.get('result_log', '')}"
                    file_log_data["CORRECTION"] = correction_log_for_file # 이전에 저장해둔 보정 로그 사용

                except queue.Empty:
                    file_log_data["RESULT"] = "Evaluate 응답 시간 초과"
                    file_log_data["CORRECTION"] = "보정 없음"
                
                log_sequence_to_file(file_log_data)
                
                print_at('DEBUG_DISTANCE', "")
                is_controlling = False

            last_bump_type = data['type']

        except queue.Empty:
            if not is_controlling:
                print_at('CONTROL_STATE', f"[Control] S:{read_speed_kmh(car):.1f}km/h | B:0%")
        except Exception:
            is_controlling = False
            last_bump_type = "None"
    
    pythoncom.CoUninitialize()