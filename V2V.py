# V2V.py
import time
import pythoncom
import win32com.client
from samples.UCwinRoadCOM import UCwinRoadComProxy
from samples.UCwinRoadUtils import Distance
from logger import print_at # 새로 만든 print_at 함수 import

def run_v2v_simulation(vision_queue):
    """
    V2V 프로세스의 메인 함수.
    단순 Polling 방식으로 안정성을 확보합니다.
    """
    print("[V2V] V2V 시뮬레이션 프로세스 시작")
    pythoncom.CoInitialize()  # 각 프로세스에서 COM 라이브러리 초기화

    try:
        # UC-win/Road 연결
        winRoadProxy = UCwinRoadComProxy()
        driver = winRoadProxy.SimulationCore.TrafficSimulation.Driver
        const = win32com.client.constants

        # 내 차량 핸들 확보
        my_car = None
        t0 = time.time()
        while my_car is None and time.time() - t0 < 15.0:
            my_car = driver.CurrentCar
            time.sleep(0.2)
        if my_car is None:
            raise RuntimeError("내 차량 핸들을 가져오지 못했습니다.")

        print("[V2V] UC-win/Road 연결 및 내 차량 핸들 확보 완료. Polling을 시작합니다.")

        tracked_vehicle_id = -1

        # 안정적인 Polling을 위한 무한 루프
        while True:
            try:
                # --- 전방 차량 탐색 ---
                front_car = my_car.DriverAheadInTraffic(const._primaryPath)

                if front_car and front_car.TransientType == const._TransientCar and front_car.ID != 0:
                    if tracked_vehicle_id != front_car.ID:
                        tracked_vehicle_id = front_car.ID
                        # 일반 print는 줄바꿈을 위해 그대로 사용
                        print(f"\n[V2V] 새로운 전방 차량 추적 시작 -> ID: {front_car.ID}, 이름: {front_car.Name}")

                    # --- 거리 계산 및 정보 출력 ---
                    my_pos = my_car.Position
                    front_pos = front_car.Position
                    distance = Distance(my_pos, front_pos)

                    if distance <= 50.0:
                        # [수정] print_at 사용
                        message = f"전방 차량과의 거리: {distance:.2f}m (ID: {tracked_vehicle_id})"
                        print_at('V2V', message)
                    else:
                        # [수정] print_at 사용
                        message = f"전방 차량 추적 중 (50m 초과)..."
                        print_at('V2V', message)

                else:
                    if tracked_vehicle_id != -1:
                        # 일반 print는 줄바꿈을 위해 그대로 사용
                        print("\n[V2V] 전방 차량이 시야에서 벗어남. 추적 종료.")
                    # [추가] 상태가 없을 때도 빈 메시지를 출력하여 이전 로그를 지움
                    print_at('V2V', '탐색 중...')
                    tracked_vehicle_id = -1
            
            except Exception:
                # COM 객체가 일시적으로 응답하지 않을 경우를 대비
                if tracked_vehicle_id != -1:
                     print(f"\n[V2V] Polling 중 오류 발생. 추적을 리셋합니다.")
                print_at('V2V', '오류 발생. 재연결 시도 중...')
                tracked_vehicle_id = -1
                time.sleep(0.5) # 오류 발생 시 잠시 대기

            # 루프 주기 제어
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[V2V] V2V 프로세스 종료 중...")
    except Exception as e:
        print(f"[V2V] 프로세스 실행 중 심각한 오류 발생: {e}")
    finally:
        pythoncom.CoUninitialize() # COM 라이브러리 해제
        print("[V2V] COM 라이브러리 해제 완료.")