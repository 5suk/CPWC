# V2V.py
import time
import pythoncom
import win32com.client
import math
import queue
from samples.UCwinRoadCOM import UCwinRoadComProxy
from samples.UCwinRoadUtils import Distance
from logger import print_at

def vector_magnitude(v_obj):
    try: return math.sqrt(v_obj.X**2 + v_obj.Y**2 + v_obj.Z**2)
    except Exception: return 0.0

def get_type_from_name(name):
    name_lower = name.lower()
    if name_lower.startswith('type'): return name[-1].upper()
    return "UNKNOWN"

def find_and_scan_speed_bumps(project):
    target_names = ["typea", "typeb", "typec"]
    speed_bumps = []
    try:
        instance_count = project.ThreeDModelInstancesCount
        for i in range(instance_count):
            instance = project.ThreeDModelInstance(i)
            instance_name_lower = instance.Name.lower()
            if any(instance_name_lower.startswith(target) for target in target_names):
                height, width = 0.0, 0.0
                try:
                    if instance.BoundingBoxesCount > 0:
                        bbox = instance.BoundingBox(0)
                        height = vector_magnitude(bbox.yAxis) * 2
                        width = vector_magnitude(bbox.zAxis) * 2
                except Exception: pass
                speed_bumps.append({
                    "id": instance.ID, "name": instance.Name, "position": instance.Position,
                    "height": height, "width": width
                })
        return speed_bumps
    except Exception: return []

def run_v2v_simulation(v2v_to_vision_queue, forward_vehicle_distance):
    pythoncom.CoInitialize()
    try:
        winRoadProxy = UCwinRoadComProxy()
        driver = winRoadProxy.SimulationCore.TrafficSimulation.Driver
        project = winRoadProxy.Project
        const = win32com.client.constants
        my_car = None; t0 = time.time()
        while my_car is None and time.time() - t0 < 15.0:
            my_car = driver.CurrentCar; time.sleep(0.2)
        if my_car is None: raise RuntimeError("내 차량(CurrentCar)을 찾을 수 없습니다.")

        speed_bumps = find_and_scan_speed_bumps(project)
        tracked_vehicle_id = -1
        bump_sent_status = {bump['id']: False for bump in speed_bumps}
        TRIGGER_DISTANCE_BUMP = 2.0
        
        while True:
            try:
                my_car = driver.CurrentCar
                if not my_car:
                    forward_vehicle_distance.value = 999.9; time.sleep(0.5); continue

                front_car = my_car.DriverAheadInTraffic(const._primaryPath)
                if front_car and hasattr(front_car, 'TransientType') and front_car.TransientType == const._TransientCar and front_car.ID != 0:
                    if tracked_vehicle_id != front_car.ID:
                        tracked_vehicle_id = front_car.ID
                        bump_sent_status = {bump['id']: False for bump in speed_bumps}

                    my_pos, front_pos = my_car.Position, front_car.Position
                    distance_to_front_car = Distance(my_pos, front_pos)
                    forward_vehicle_distance.value = distance_to_front_car

                    if distance_to_front_car <= 30.0:
                        for bump in speed_bumps:
                            if not bump_sent_status[bump['id']]:
                                if Distance(front_pos, bump['position']) < TRIGGER_DISTANCE_BUMP:
                                    data_packet = {
                                        'type': get_type_from_name(bump['name']), 'height_m': bump['height'],
                                        'distance_m': Distance(my_pos, bump['position']), 'width_m': bump['width'],
                                        'source': 'V2V', 'vehicle_name': front_car.Name
                                    }
                                    try:
                                        v2v_to_vision_queue.put_nowait(data_packet)
                                        bump_sent_status[bump['id']] = True
                                    except queue.Full: pass
                else:
                    forward_vehicle_distance.value = 999.9; tracked_vehicle_id = -1
            except Exception:
                forward_vehicle_distance.value = 999.9; tracked_vehicle_id = -1; my_car = None
                time.sleep(0.5)
            time.sleep(0.1)
    except Exception as e:
        if 'forward_vehicle_distance' in locals(): forward_vehicle_distance.value = 999.9
    finally: pythoncom.CoUninitialize()