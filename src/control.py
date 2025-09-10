# control.py
import time
import math
import queue
import json
import numpy as np
import pythoncom
from win32com.client import Dispatch, GetActiveObject

import config
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
    except: return 0.0

def vector_magnitude(v_obj):
    try: return math.sqrt(v_obj.X**2 + v_obj.Y**2 + v_obj.Z**2)
    except Exception: return 0.0

def find_all_bumps_and_cache(project):
    ThreeDModelGT_cache = []
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
                ThreeDModelGT_cache.append({
                    "instance": instance, "name": instance.Name,
                    "gt_h": height, "gt_d": depth
                })
    except Exception:
        pass
    return ThreeDModelGT_cache

def find_target_bump(car, bump_type, bump_cache):
    keyword = TYPE_TO_KEYWORD.get(bump_type)
    if not keyword or not bump_cache: return None

    car_pos = car.Position
    car_dir = car.Direction
    
    relevant_bumps = [b for b in bump_cache if keyword in b["name"].lower()]
    if not relevant_bumps: return None

    closest_dist = float('inf')
    target_bump = None

    for bump_data in relevant_bumps:
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

def classify_rms_level(rms_value):
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

def estimate_min_speed_kmh(current_speed_kmh, speed_map_data):
    if not speed_map_data: return 20.0
    
    x_speeds_str = sorted(speed_map_data.keys(), key=int)
    x_speeds = [int(s) for s in x_speeds_str]
    y_ms = [speed_map_data[s] for s in x_speeds_str]
    
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
    
    CAL_GAIN = config.INITIAL_CALIBRATION_GAIN
    PWM_WEIGHT = config.INITIAL_PWM_WEIGHT

    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore; proj = ucwin.Project; driver = sim_core.TrafficSimulation.Driver
        
        car = None; t0 = time.time()
        while car is None and time.time() - t0 < 15.0:
            car = driver.CurrentCar; time.sleep(0.2)
        if car is None: raise RuntimeError()
        
        bump_cache = find_all_bumps_and_cache(proj)
        
        try:
            with open(config.CALIBRATION_DATA_FILE_PATH, 'r') as f:
                speed_map_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            speed_map_data = {}
        
    except Exception:
        pythoncom.CoUninitialize()
        return

    is_controlling = False
    last_bump_type = "None"
    current_scenario = 0
    switched_this_round = False
    last_x = None
    pending_correction_data = None
    correction_log_for_file = ""

    while True:
        try:
            pos = car.Position
            x = float(pos.X)
            if last_x is not None and last_x > config.SCENARIO_RESTART_TRIGGER_X and x <= config.SCENARIO_RESTART_TRIGGER_X and not switched_this_round:
                current_scenario = 1 if current_scenario == 0 else 0
                restart_scenario(sim_core, proj, current_scenario)
                
                car = None; t0 = time.time()
                while car is None and time.time() - t0 < 15.0: car = driver.CurrentCar; time.sleep(0.2)
                if car is None: raise RuntimeError()

                bump_cache = find_all_bumps_and_cache(proj)
                
                is_controlling = False
                last_bump_type = "None" 
                pending_correction_data = None
                while not vision_to_control_queue.empty():
                    vision_to_control_queue.get()
                print_at('DEBUG_DISTANCE', "")

                switched_this_round = True
            elif x > 3500: 
                switched_this_round = False
            last_x = x

            if not is_controlling and pending_correction_data:
                if pending_correction_data.get("msg") == "final_correction_factors":
                    old_gain, old_pwm = CAL_GAIN, PWM_WEIGHT
                    CAL_GAIN = pending_correction_data.get("updated_gain")
                    PWM_WEIGHT = pending_correction_data.get("updated_pwm_weight")
                    
                    correction_log = (f"[Control] 보정 적용: pR_CAL {old_gain:.4f}→{CAL_GAIN:.4f} | "
                                      f"PWM_CAL {old_pwm:.2f}→{PWM_WEIGHT:.2f}")
                    print_at('CONTROL_CORRECTION', correction_log)
                    correction_log_for_file = correction_log
                pending_correction_data = None

            data = vision_to_control_queue.get(timeout=0.1)
            
            if data['type'] != "None" and last_bump_type == "None" and not is_controlling:
                h_m = data.get('Measured_Height')
                dist_m = data.get('bump_distance')
                depth_m = data.get('depth_m')
                bump_type = data.get('type')
                
                if not all([isinstance(h_m, float), isinstance(dist_m, float), isinstance(depth_m, float), bump_type]):
                    last_bump_type = data.get('type', 'None')
                    continue

                if 'D' in str(bump_type).upper() or h_m <= 0 or depth_m <= 0:
                    last_bump_type = data.get('type', 'None')
                    continue

                is_controlling = True
                
                current_speed = read_speed_kmh(car)
                minimum_Speed = estimate_min_speed_kmh(current_speed, speed_map_data)
                prediction_RMS = calculate_rms(h_m, depth_m, minimum_Speed / 3.6, CAL_GAIN)
                prediction_Level = classify_rms_level(prediction_RMS)
                
                if prediction_Level in ["불쾌함", "매우 불쾌함"]: target_speed = minimum_Speed
                else:
                    target_rms = config.COMFORT_TARGETS_RMS.get(prediction_Level, 0.5)
                    optimal_v_mps = solve_speed_for_target_rms(h_m, depth_m, target_rms, CAL_GAIN)
                    target_speed = max(minimum_Speed, (optimal_v_mps * 3.6 if optimal_v_mps else 0) + config.TARGET_SPEED_MARGIN_KMH)
                
                Brake_PWM = calculate_brake_pwm(current_speed, target_speed, dist_m, PWM_WEIGHT)

                source = data.get('source', 'N/A')
                recv_log_content = f"T:{bump_type}, M_H:{h_m*100:.1f}cm, bD:{dist_m:.1f}m, GT_Dp:{depth_m:.2f}m"
                plan_log_content = f"tS:{target_speed:.1f}, pR:{prediction_RMS:.2f}, pL:{prediction_Level}"
                
                print_at('CONTROL_RECV', f"[{source}] {recv_log_content}")
                print_at('CONTROL_PLAN', f"[Control] {plan_log_content}")

                target_bump_obj = find_target_bump(car, bump_type, bump_cache)
                if not target_bump_obj:
                    is_controlling = False
                    last_bump_type = data['type']
                    continue
                
                min_dist_so_far = float('inf')
                has_approached = False
                start_time = time.time()
                initial_dist = dist_m

                while time.time() - start_time < 15.0:
                    car_pos = car.Position
                    bump_pos = target_bump_obj["instance"].Position
                    current_dist = Distance(car_pos, bump_pos)
                    
                    if current_dist > initial_dist + 5.0:
                        break
                        
                    min_dist_so_far = min(min_dist_so_far, current_dist)
                    if not has_approached and current_dist < config.BUMP_PASS_DETECTION_THRESHOLD_M:
                        has_approached = True
                    
                    print_at('DEBUG_DISTANCE', f"({target_bump_obj['name']})과의 bD: {current_dist:.1f}m")
                    
                    s = read_speed_kmh(car)
                    print_at('CONTROL_STATE', f"[Control] cS:{s:.1f} | B_PWM:{int(Brake_PWM*100)}%(tS:{target_speed:.1f})")
                    if s > target_speed:
                        try:
                            on_time = config.CONTROL_POLL_DT * Brake_PWM; off_time = config.CONTROL_POLL_DT * (1.0 - Brake_PWM)
                            car.Throttle = 0.0
                            if on_time > 0: car.ParkingBrake = True; time.sleep(on_time)
                            if off_time > 0: car.ParkingBrake = False; time.sleep(off_time)
                        except Exception: break
                    else:
                        car.ParkingBrake = False

                    if has_approached and current_dist > min_dist_so_far + 0.1:
                        break
                
                actual_collision_speed = read_speed_kmh(car)
                car.ParkingBrake = False
                
                eval_request = { "msg": "evaluate_request", "current_speed": actual_collision_speed, "target_speed": target_speed, "prediction_RMS": prediction_RMS, "GT_Height": target_bump_obj["gt_h"], "GT_Depth": target_bump_obj["gt_d"], "current_gain": CAL_GAIN, "current_pwm_weight": PWM_WEIGHT }
                control_to_eval_queue.put(eval_request)
                
                file_log_data = { "DETECT": f"[{source}] {recv_log_content}", "PLAN": f"[Control] {plan_log_content}", "COLLISION": f"충돌 속도(cS): {actual_collision_speed:.1f}km/h (최소 근접 거리: {min_dist_so_far:.2f}m)" }
                
                try:
                    eval_response = eval_to_control_queue.get(timeout=2.0)
                    pending_correction_data = eval_response
                    file_log_data["RESULT"] = f"{eval_response.get('result_log', '')}"
                    file_log_data["CORRECTION"] = correction_log_for_file
                except queue.Empty:
                    file_log_data["RESULT"] = "Evaluate 응답 시간 초과"
                    file_log_data["CORRECTION"] = "보정 없음"
                
                log_sequence_to_file(file_log_data)
                print_at('DEBUG_DISTANCE', "")
                is_controlling = False

            last_bump_type = data['type']

        except queue.Empty:
            if not is_controlling:
                print_at('CONTROL_STATE', f"[Control] cS:{read_speed_kmh(car):.1f} | B_PWM:0%")
        except Exception:
            is_controlling = False
            last_bump_type = "None"
    
    pythoncom.CoUninitialize()