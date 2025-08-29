# -*- coding: utf-8 -*-
"""
[3D 객체 실시간 감지 최종 버전 - 폴링 방식 적용]
이벤트 핸들러를 제거하고, 메인 스크립트가 0.1초마다 직접 UC-win/Road의
상태를 확인하는 '폴링' 방식으로 구조를 변경하여 프레임 드랍을 해결합니다.
"""

import os
import time
import threading
import math
from samples.UCwinRoadCOM import *
from samples.UCwinRoadUtils import *
# CallbackHandlers는 더 이상 필요하지 않습니다.

# ================== ⚙️ 사용자 설정 ==================
TARGET_MODEL_NAMES = ["typeA", "typeB", "typeC", "typeD"]
TRIGGER_DISTANCE = 2.5
COMMUNICATION_RANGE = 30.0
SCENARIO_TO_RUN = 0
CHECK_INTERVAL = 0.1 # 0.1초마다 상태 확인

# ================== 🌎 전역 변수 ==================
g_comm_distance_float = -1.0
g_current_distance_str = "대기 중..."
g_stop_thread = False
g_target_models = []
g_passed_models = set()
g_was_in_comm_range = False

# ================== 헬퍼 함수 (기존과 동일) ==================
def _vec3(v):
    try: return float(v.X), float(v.Y), float(v.Z)
    except Exception: return 0.0, 0.0, 0.0

def vector_magnitude(vec_tuple):
    x, y, z = vec_tuple
    return math.sqrt(x**2 + y**2 + z**2)

def find_target_models(proj, target_names):
    found_models = []
    try:
        instance_count = proj.ThreeDModelInstancesCount
        for i in range(instance_count):
            instance = proj.ThreeDModelInstance(i)
            model_name = instance.Name
            for target in target_names:
                if model_name.startswith(target):
                    height_y = 0.0
                    if target == 'typeD':
                        if hasattr(instance, 'Scale'):
                            scale_vec = _vec3(instance.Scale)
                            height_y = scale_vec[1]
                        elif instance.BoundingBoxesCount > 0:
                            bbox = instance.BoundingBox(0)
                            height_y = vector_magnitude(_vec3(bbox.yAxis)) * 2
                    else:
                        if instance.BoundingBoxesCount > 0:
                            bbox = instance.BoundingBox(0)
                            height_y = vector_magnitude(_vec3(bbox.yAxis)) * 2
                    model_data = {"id": i, "name": target, "position": instance.Position, "height_y": height_y}
                    found_models.append(model_data)
                    break
    except Exception as e:
        print(f"\n[오류] 3D 모델 스캔 중 오류 발생: {e}")
    return found_models

# ================== 실시간 상태 표시 스레드 (기존과 동일) ==================
def display_status_thread():
    while not g_stop_thread:
        try:
            distance = g_comm_distance_float
            if distance > COMMUNICATION_RANGE or distance < 0:
                status_line = f" [INFO] 전방 {COMMUNICATION_RANGE}m 이내 통신 가능 차량 없음      "
            else:
                status_line = f" [LIVE] 앞차와의 거리: {g_current_distance_str}      "
            print(status_line, end='\r')
            time.sleep(0.1)
        except Exception:
            pass

# ================== 메인 실행 함수 (구조 변경) ==================
def main():
    global winRoadProxy, const, g_stop_thread, g_target_models
    # EventList는 더 이상 필요하지 않습니다.
    winRoadProxy = None

    status_thread = threading.Thread(target=display_status_thread)
    status_thread.daemon = True
    status_thread.start()

    try:
        print("="*50)
        print("UC-win/Road SDK에 연결합니다...")
        winRoadProxy = UCwinRoadComProxy()
        const = winRoadProxy.const
        sim = winRoadProxy.ApplicationServices.SimulationCore
        proj = winRoadProxy.ApplicationServices.Project
        print("-> UC-win/Road에 성공적으로 연결했습니다.")

        g_target_models = find_target_models(proj, TARGET_MODEL_NAMES)

        print(f"시나리오 {SCENARIO_TO_RUN}번을 시작합니다...")
        sc = proj.Scenario(SCENARIO_TO_RUN)
        sim.StartScenario(sc)
        
        print("-> 시나리오 시작됨. '내 차'가 생성될 때까지 대기합니다...")
        myCar = None
        for _ in range(50):
            driver = sim.TrafficSimulation.Driver
            myCar = driver.CurrentCar if driver else None
            if myCar: break
            time.sleep(0.2)

        if not myCar:
            print("\n❌ 오류: '내 차(CurrentCar)'를 찾을 수 없습니다.")
            return

        print(f"-> '내 차'를 찾았습니다 (ID: {myCar.ID}).")
        # SetCallbackHandlers는 더 이상 호출하지 않습니다.
        print("-> 폴링 방식으로 실시간 감지를 시작합니다.")
        print("="*50)
        print("\n모니터링 시작! (중지하려면 터미널에서 Ctrl+C를 누르세요)\n")
        
        # --- 💡 [핵심 변경] 메인 루프를 직접 만듭니다 ---
        global g_current_distance_str, g_comm_distance_float, g_passed_models, g_was_in_comm_range
        
        loopFlg = True
        winRoadProxy.ApplicationServices.IsPythonScriptRun = loopFlg
        while loopFlg:
            # --- 이전 이벤트 핸들러의 모든 로직이 이 루프 안으로 들어옴 ---
            try:
                # '내 차'와 '앞차' 정보를 매번 직접 가져옴
                myCar = sim.TrafficSimulation.Driver.CurrentCar
                if myCar:
                    frontCar = myCar.DriverAheadInTraffic(const._primaryPath)
                    
                    if frontCar:
                        myPos = myCar.Position
                        frontPos = frontCar.Position
                        
                        comm_distance = Distance(myPos, frontPos)
                        g_comm_distance_float = comm_distance
                        g_current_distance_str = f"{comm_distance:.2f}m"

                        is_in_comm_range = (0 < comm_distance <= COMMUNICATION_RANGE)

                        if not g_was_in_comm_range and is_in_comm_range:
                            print('\r' + ' ' * 80 + '\r', end="")
                            print(f"[INFO] 승차감 개선을 위해 전방 차량과 통신을 시작합니다. (거리: {g_current_distance_str})")
                        
                        if g_was_in_comm_range and not is_in_comm_range:
                            print('\r' + ' ' * 80 + '\r', end="")
                            print(f"[INFO] 전방 차량과 {COMMUNICATION_RANGE}m 이상 멀어져 통신이 끊어졌습니다.")
                        
                        g_was_in_comm_range = is_in_comm_range

                        if is_in_comm_range:
                            for model in g_target_models:
                                if model['id'] not in g_passed_models:
                                    distance_to_bump = Distance(frontPos, model['position'])
                                    if distance_to_bump <= TRIGGER_DISTANCE:
                                        g_passed_models.add(model['id'])
                                        my_distance_to_bump = Distance(myPos, model['position'])
                                        height_cm = model['height_y'] * 100
                                        print('\r' + ' ' * 80 + '\r', end="")
                                        print(f"[INFO] 전방 {my_distance_to_bump:.2f}m 지점에 높이 {height_cm:.2f}cm인 과속방지턱({model['name']})이 있습니다.")
                    else:
                        g_current_distance_str = "차량 없음"
                        g_comm_distance_float = -1.0
                        if g_was_in_comm_range:
                            print('\r' + ' ' * 80 + '\r', end="")
                            print(f"[INFO] 전방 차량이 시야에서 사라져 통신이 끊어졌습니다.")
                            g_was_in_comm_range = False
            except Exception:
                # 루프가 오류로 중단되지 않도록 예외 처리
                pass

            # 루프의 실행 간격을 제어
            time.sleep(CHECK_INTERVAL)
            loopFlg = winRoadProxy.ApplicationServices.IsPythonScriptRun
            
    except KeyboardInterrupt:
        print("\n\n사용자 요청으로 모니터링을 중지합니다.")
    except Exception as e:
        print(f"\n\n❌ 예상치 못한 오류가 발생했습니다: {e}")
        
    finally:
        g_stop_thread = True
        status_thread.join(timeout=1)
        # CloseCallbackEvent는 더 이상 필요하지 않습니다.
        if winRoadProxy: del winRoadProxy
        print("\n스크립트가 완전히 종료되었습니다.")

if __name__ == '__main__':
    main()