# V2V_final_test.py
import time
import pythoncom
import win32com.client
import math
from samples.UCwinRoadCOM import UCwinRoadComProxy
from samples.UCwinRoadUtils import Distance

# --- 헬퍼 함수들 (debug_final_check.py와 동일하게 보장) ---
def _vec3_tuple(v):
    """COM 벡터를 계산용 튜플로 변환"""
    try: return (v.X, v.Y, v.Z)
    except Exception: return (0.0, 0.0, 0.0)

def vector_magnitude(v_obj):
    """COM 벡터 객체의 크기(길이)를 계산"""
    try: return math.sqrt(v_obj.X**2 + v_obj.Y**2 + v_obj.Z**2)
    except Exception: return 0.0

def read_speed_kmh(car):
    """차량 속도를 km/h로 반환"""
    try: return float(car.Speed(1))
    except: return float(car.Speed()) * 3.6

def classify_bump_type(height_m):
    """높이(GT)를 기반으로 타입을 분류"""
    if height_m <= 0.04: return "N/A (낮음)"
    if height_m <= 0.13: return "A 타입 (추정)"
    return "B/C 타입 (추정)"

def find_and_scan_speed_bumps(project):
    """
    시나리오에서 과속방지턱 객체를 스캔하고 GT 정보를 추출합니다.
    debug_final_check.py의 검증된 로직을 그대로 사용합니다.
    """
    print("[INFO] 시나리오에서 과속방지턱 객체를 스캔합니다...")
    target_names = ["typea", "typeb", "typec"]
    speed_bumps = []
    try:
        instance_count = project.ThreeDModelInstancesCount
        for i in range(instance_count):
            instance = project.ThreeDModelInstance(i)
            if any(instance.Name.lower().startswith(target) for target in target_names):
                height, depth = 0.0, 0.0
                
                # --- [핵심 수정] debug_final_check.py의 검증된 로직을 그대로 적용 ---
                try:
                    if instance.BoundingBoxesCount > 0:
                        bbox = instance.BoundingBox(0)
                        height = vector_magnitude(bbox.yAxis) * 2
                        depth = vector_magnitude(bbox.zAxis) * 2
                except Exception:
                     print(f"  -> 경고: {instance.Name}의 BoundingBox 정보를 가져올 수 없습니다.")
                # -----------------------------------------------------------------

                speed_bumps.append({
                    "id": instance.ID, "name": instance.Name, "position": instance.Position,
                    "height": height, "depth": depth
                })
        print(f"[INFO] 스캔 완료. 총 {len(speed_bumps)}개의 과속방지턱을 발견했습니다.")
        return speed_bumps
    except Exception as e:
        print(f"\n[오류] 3D 모델 스캔 중 오류: {e}")
        return []

def main_final_test():
    """요청하신 모든 기능을 수행하는 최종 테스트 함수"""
    print("[INFO] V2V 최종 통합 테스트를 시작합니다.")
    pythoncom.CoInitialize()
    
    try:
        winRoadProxy = UCwinRoadComProxy()
        sim = winRoadProxy.SimulationCore
        driver = sim.TrafficSimulation.Driver
        project = winRoadProxy.Project
        const = win32com.client.constants
        
        SCENARIO_INDEX = 0
        try:
            print(f"[INFO] 시나리오 {SCENARIO_INDEX}번을 시작합니다...")
            sc = project.Scenario(SCENARIO_INDEX)
            sim.StartScenario(sc)
            time.sleep(1)
        except Exception as e:
            raise RuntimeError(f"시나리오 {SCENARIO_INDEX}번 시작에 실패했습니다: {e}")

        my_car = None
        for _ in range(50):
            my_car = driver.CurrentCar
            if my_car: break
            time.sleep(0.2)
        if my_car is None:
            raise RuntimeError("내 차량(CurrentCar)을 찾을 수 없습니다.")
        
        speed_bumps = find_and_scan_speed_bumps(project)
        if not speed_bumps:
            print("[경고] 감지할 과속방지턱이 없습니다. 스크립트를 종료합니다.")
            return

        TRIGGER_DISTANCE_BUMP = 2.0
        last_logged_bump_id = None

        print("\n" + "="*50)
        print("실시간 주행 감시를 시작합니다...")
        print("="*50)

        while True:
            front_car = my_car.DriverAheadInTraffic(const._primaryPath)
            
            if front_car and front_car.TransientType == const._TransientCar and front_car.ID != 0:
                my_pos = my_car.Position
                front_pos = front_car.Position
                distance_to_front_car = Distance(my_pos, front_pos)
                
                if distance_to_front_car <= 50.0:
                    print(f"\r[감시 중] 전방 차량과의 거리: {distance_to_front_car:.2f} m", end="")

                if distance_to_front_car <= 30.0:
                    for bump in speed_bumps:
                        if last_logged_bump_id != bump['id']:
                            dist_front_to_bump = Distance(front_pos, bump['position'])
                            
                            if dist_front_to_bump < TRIGGER_DISTANCE_BUMP:
                                current_speed = read_speed_kmh(my_car)
                                dist_my_to_bump = Distance(my_pos, bump['position'])
                                bump_type = classify_bump_type(bump['height'])
                                
                                log_message = (
                                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 이벤트 감지!\n"
                                    f"  - 현재 내 차량 속도: {current_speed:.2f} km/h\n"
                                    f"  - 방지턱 GT 정보: 높이={bump['height']*100:.2f}cm, 깊이={bump['depth']*100:.2f}cm\n"
                                    f"  - 방지턱 타입 (추정): {bump_type}\n"
                                    f"  - 거리 정보:\n"
                                    f"    - 전방차량 <-> 방지턱: {dist_front_to_bump:.2f} m\n"
                                    f"    - 전방차량 <-> 내차량: {distance_to_front_car:.2f} m\n"
                                    f"    - 내차량 <-> 방지턱: {dist_my_to_bump:.2f} m\n"
                                )
                                
                                print("\n" + "="*50 + "\n" + log_message + "="*50)
                                
                                with open("r.txt", "a", encoding="utf-8") as f:
                                    f.write(log_message + "="*50 + "\n")
                                    
                                last_logged_bump_id = bump['id']
                                break
            else:
                last_logged_bump_id = None
                print("\r[감시 중] 전방에 차량 없음...                                  ", end="")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n[INFO] 사용자 요청으로 테스트를 종료합니다.")
    except Exception as e:
        print(f"\n[오류] 테스트 실행 중 오류 발생: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == '__main__':
    main_final_test()