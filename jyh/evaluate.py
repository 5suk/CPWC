# evaluate.py
import math, time, queue, pythoncom
from win32com.client import Dispatch, GetActiveObject
from logger import print_at
from samples.UCwinRoadCOM import UCwinRoadComProxy
from samples.UCwinRoadUtils import Distance

PROGID = "UCwinRoad.F8ApplicationServicesProxy"; CAL_GAIN = 0.050
TYPE_TO_KEYWORD = {"A": "typea", "B": "typeb", "C": "typec"}

def attach_or_launch():
    try: return GetActiveObject(PROGID)
    except: return Dispatch(PROGID)

def read_speed_kmh(car):
    try: return float(car.Speed(1))
    except: return float(car.Speed()) * 3.6

def vector_magnitude(v_obj):
    try: return math.sqrt(v_obj.X**2 + v_obj.Y**2 + v_obj.Z**2)
    except Exception: return 0.0

def find_next_speed_bump_and_gt(project, car, bump_type):
    """차량 전방에서 가장 가까운 과속방지턱 인스턴스와 GT 데이터를 반환"""
    keyword = TYPE_TO_KEYWORD.get(bump_type)
    if not keyword: return None, None, None

    closest_bump_in_front = None
    min_dist = float('inf')
    
    try:
        car_pos = car.Position
        car_dir = car.Direction # 차량의 현재 주행 방향 벡터

        for i in range(project.ThreeDModelInstancesCount):
            instance = project.ThreeDModelInstance(i)
            if keyword.lower() in instance.Name.lower():
                
                # === [핵심 수정] 차량 전방에 있는지 판별하는 로직 ===
                bump_pos = instance.Position
                vec_to_bump_x = bump_pos.X - car_pos.X
                vec_to_bump_z = bump_pos.Z - car_pos.Z

                # 내적(Dot Product)을 사용하여 방향 일치 여부 확인
                dot_product = (car_dir.X * vec_to_bump_x) + (car_dir.Z * vec_to_bump_z)

                # 내적이 양수일 때만 차량 전방에 있는 것으로 간주
                if dot_product > 0:
                    dist = Distance(car_pos, bump_pos)
                    if dist < min_dist:
                        min_dist = dist
                        closest_bump_in_front = instance
                # =================================================

        if closest_bump_in_front and closest_bump_in_front.BoundingBoxesCount > 0:
            bbox = closest_bump_in_front.BoundingBox(0)
            height = vector_magnitude(bbox.yAxis) * 2
            width = vector_magnitude(bbox.zAxis) * 2
            return closest_bump_in_front, height, width
            
    except Exception: return None, None, None
    return None, None, None

def compute_rms(v_kmh, h_m, L_m):
    if not h_m or not L_m or h_m <= 0 or L_m <= 0: return None
    v = v_kmh / 3.6
    return CAL_GAIN * (1.0 / math.sqrt(2.0)) * h_m * (v * math.pi / L_m)**2

def classify_rms(rms_value):
    if rms_value < 0.315: return "쾌적함"
    if rms_value < 0.5: return "쾌적함"
    if rms_value < 0.8: return "보통"
    if rms_value < 1.25: return "불쾌함"
    return "매우 불쾌함"

def run_evaluate_node(control_to_eval_queue, eval_to_control_queue):
    pythoncom.CoInitialize()
    try:
        winRoadProxy = UCwinRoadComProxy()
        project = winRoadProxy.Project
        driver = winRoadProxy.SimulationCore.TrafficSimulation.Driver
        my_car = None
        while my_car is None:
            my_car = driver.CurrentCar; time.sleep(0.5)
    except Exception: return

    while True:
        try:
            data = control_to_eval_queue.get() 
            if data.get("msg") != "control": continue
            
            tS_kmh, eR_rms, bump_type = data['tS'], data['eR'], data['type']
            
            if 'D' in str(bump_type).upper(): continue
            
            # === [수정] "전방에서 가장 가까운" 객체를 찾는 함수 호출 ===
            bump_instance, gt_h, gt_w = find_next_speed_bump_and_gt(project, my_car, bump_type)
            if bump_instance is None: continue

            while True:
                try:
                    car_pos = my_car.Position
                    bump_pos = bump_instance.Position
                    distance_to_bump = Distance(car_pos, bump_pos)
                    
                    log_msg = f"과속방지턱까지 남은 거리: {distance_to_bump:.1f}m"
                    print_at('EVALUATE_DISTANCE', log_msg)

                    if distance_to_bump < 1.0: # 충돌 임계값
                        break
                    
                    time.sleep(0.05)
                except Exception:
                    time.sleep(0.1)
                    continue

            rS_kmh = read_speed_kmh(my_car)

            if gt_h is not None and gt_w is not None:
                tR_rms = compute_rms(rS_kmh, gt_h, gt_w)
                if tR_rms is None: continue

                comfort_level = classify_rms(tR_rms)
                print_at('EVALUATE_DETAIL', f"[Evaluate] rS:{rS_kmh:.1f}km/h|tR:{tR_rms:.2f}(GTh:{gt_h*100:.1f}cm)|실제 승차감:{comfort_level}")

                er_error = (abs(eR_rms - tR_rms) / eR_rms) * 100 if eR_rms > 0 else 0
                ts_error = (abs(tS_kmh - rS_kmh) / tS_kmh) * 100 if tS_kmh > 0 else 0
                print_at('EVALUATION', f"[Evaluate] eR<>tR:{er_error:.1f}%|tS<>rS:{ts_error:.1f}%")

                cal_gain_scale = (tR_rms / eR_rms) if eR_rms > 0 else 1.0
                pwm_weight_scale = (tS_kmh / rS_kmh) if rS_kmh > 0 else 1.0
                
                eval_to_control_queue.put({
                    "msg": "evaluate", "CAL_GAIN_SCALE": cal_gain_scale, "PWM_WEIGHT_SCALE": pwm_weight_scale
                })
                
                print_at('EVALUATE_DISTANCE', "") # 로그 라인 정리

        except queue.Empty: continue
        except Exception: time.sleep(1)