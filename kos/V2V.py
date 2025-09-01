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
    print("[V2V] 시나리오에서 과속방지턱 객체를 스캔합니다...")
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
                except Exception:
                    print(f"  -> 경고: {instance.Name}의 BoundingBox 정보를 가져올 수 없습니다.")
                speed_bumps.append({
                    "id": instance.ID, "name": instance.Name, "position": instance.Position,
                    "height": height, "width": width
                })
        print(f"[V2V] 스캔 완료. 총 {len(speed_bumps)}개의 과속방지턱을 발견했습니다.")
        return speed_bumps
    except Exception as e:
        print(f"\n[V2V][오류] 3D 모델 스캔 중 오류: {e}")
        return []

def run_v2v_simulation(v2v_to_vision_queue, forward_vehicle_distance):
    print("[V2V] V2V 시뮬레이션 프로세스 시작")
    pythoncom.CoInitialize()
    try:
        winRoadProxy = UCwinRoadComProxy()
        driver = winRoadProxy.SimulationCore.TrafficSimulation.Driver
        project = winRoadProxy.Project
        const = win32com.client.constants
        my_car = None
        t0 = time.time()
        while my_car is None and time.time() - t0 < 15.0:
            my_car = driver.CurrentCar
            time.sleep(0.2)
        if my_car is None: raise RuntimeError("내 차량(CurrentCar)을 찾을 수 없습니다.")
        print("[V2V] UC-win/Road 연결 및 내 차량 핸들 확보 완료.")

        speed_bumps = find_and_scan_speed_bumps(project)
        tracked_vehicle_id = -1
        bump_sent_status = {bump['id']: False for bump in speed_bumps}
        TRIGGER_DISTANCE_BUMP = 2.0
        
        was_tracking = False # [버그 수정] 이전에 추적 중이었는지 상태를 기억

        while True:
            try:
                front_car = my_car.DriverAheadInTraffic(const._primaryPath)
                if front_car and front_car.TransientType == const._TransientCar and front_car.ID != 0:
                    was_tracking = True
                    if tracked_vehicle_id != front_car.ID:
                        tracked_vehicle_id = front_car.ID
                        bump_sent_status = {bump['id']: False for bump in speed_bumps}
                        print(f"\n[V2V] 새로운 전방 차량 추적 시작 -> ID: {front_car.ID}, 이름: {front_car.Name}")

                    my_pos = my_car.Position
                    front_pos = front_car.Position
                    distance_to_front_car = Distance(my_pos, front_pos)
                    forward_vehicle_distance.value = distance_to_front_car

                    if distance_to_front_car <= 30.0:
                        for bump in speed_bumps:
                            if not bump_sent_status[bump['id']]:
                                dist_front_to_bump = Distance(front_pos, bump['position'])
                                if dist_front_to_bump < TRIGGER_DISTANCE_BUMP:
                                    distance_to_bump = Distance(my_pos, bump['position'])
                                    bump_type = get_type_from_name(bump['name'])
                                    data_packet = {
                                        'type': bump_type, 'height_m': bump['height'],
                                        'distance_m': distance_to_bump, 'width_m': bump['width']
                                    }
                                    try:
                                        v2v_to_vision_queue.put_nowait(data_packet)
                                        print(f"\n[V2V] GT 정보 전송 성공 (ID: {bump['id']}, Type: {bump_type})")
                                        bump_sent_status[bump['id']] = True
                                    except queue.Full:
                                        print(f"\n[V2V] GT 정보 전송 실패 (ID: {bump['id']}): Queue full")
                    
                    message = f"전방 차량과의 거리: {distance_to_front_car:.2f}m (ID: {tracked_vehicle_id})"
                    print_at('V2V', message)
                else:
                    # [버그 수정] 이전에 추적 중이었다가(was_tracking) 지금 차가 없어졌을 때만 메시지 출력
                    if was_tracking:
                        print("\n[V2V] 전방 차량이 시야에서 벗어남. 추적 종료.")
                    
                    forward_vehicle_distance.value = 999.9
                    print_at('V2V', '탐색 중...')
                    tracked_vehicle_id = -1
                    was_tracking = False # 추적 상태 초기화
            
            except Exception:
                forward_vehicle_distance.value = 999.9
                print_at('V2V', '오류 발생. 재연결 시도 중...')
                tracked_vehicle_id = -1
                was_tracking = False
                time.sleep(0.5)

            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[V2V] V2V 프로세스 종료 중...")
    except Exception as e:
        print(f"[V2V] 프로세스 실행 중 심각한 오류 발생: {e}")
    finally:
        pythoncom.CoUninitialize()
        print("[V2V] COM 라이브러리 해제 완료.")