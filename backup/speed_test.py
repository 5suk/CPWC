# ms_calculator.py (or speed_test.py)
import time
import multiprocessing
import msvcrt
import queue

from vision import run_vision_processing
from control import read_speed_kmh, restart_scenario, attach_or_launch

def test_control_logic(vision_queue):
    """
    Vision 신호를 받아 제동을 시작하고, 'c'키 입력을 받아 mS를 측정하며,
    'q'키를 누르면 모든 결과를 파일로 저장하고 종료합니다.
    """
    print("="*50)
    print("      mS (최대 감속 가능 속도) 측정 테스트")
    print("="*50)
    
    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore
        proj = ucwin.Project
        driver = sim_core.TrafficSimulation.Driver
        
        ai_speed = input(">> 테스트를 진행할 AI 목표 속도(km/h)를 입력하세요 (예: 40): ")
        brake_intensity_str = input(">> 테스트 제동 강도를 입력하세요 (0.1 ~ 1.0, 추천: 0.5): ")
        BRAKE_INTENSITY = float(brake_intensity_str)

        print(f"\n[알림] AI 목표 속도: {ai_speed}km/h | 테스트 제동 강도: {int(BRAKE_INTENSITY*100)}%")
        
        restart_scenario(sim_core, proj, 0)
        car = driver.CurrentCar
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        print("[Test Control] UC-win/Road 연결 및 차량 핸들 확보 완료.")
    except Exception as e:
        print(f"[Test Control] UC-win/Road 초기화 실패: {e}")
        return

    is_braking = False
    last_known_distance = 0.0
    test_results = []
    braking_start_time = 0

    # [신규] 최소 제어 보장 시간 (초)
    MIN_BRAKING_DURATION = 3.0

    print("\n[Test Control] Vision 프로세스의 신호를 대기합니다...")
    print("[Test Control] 충돌 시점에 'c'를 누르고, 테스트 전체 종료는 'q'를 누르세요.")
    
    running = True
    while running:
        # --- 키보드 입력 처리 ---
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8').lower()
            if key == 'c' and is_braking:
                ms_speed = read_speed_kmh(car)
                result_data = {
                    "intensity": BRAKE_INTENSITY,
                    "speed": ms_speed,
                    "distance": last_known_distance
                }
                test_results.append(result_data)

                print(f"\n\n--- [측정 완료!] ---")
                print(f"테스트 제동 강도: {int(BRAKE_INTENSITY*100)}%")
                print(f"충돌 시점 속도(mS): {ms_speed:.2f} km/h")
                print(f"충돌 시점 거리(D): {last_known_distance:.2f} m")
                print("--------------------")
                
                car.ParkingBrake = False
                is_braking = False
                while not vision_queue.empty(): vision_queue.get()
                print("\n[Test Control] 다음 과속방지턱 감지를 위해 대기합니다...")

            elif key == 'q':
                print("\n[Test Control] 'q' 키가 입력되어 테스트를 종료합니다.")
                running = False
                continue

        # --- Vision 신호 처리 ---
        try:
            data = vision_queue.get_nowait()
            last_known_distance = data['distance_m']

            if not is_braking:
                initial_speed = read_speed_kmh(car)
                print(f"\n\n--- 새로운 테스트 시작 ---")
                print(f"[감지!] 과속방지턱 감지! (S: {initial_speed:.1f}km/h, D: {last_known_distance:.1f}m)")
                print(f"[동작!] 지금부터 {int(BRAKE_INTENSITY*100)}% 강도로 감속을 시작합니다. 충돌 시점에 'c'를 누르세요!")
                is_braking = True
                braking_start_time = time.time() # 제동 시작 시간 기록

        except queue.Empty:
            # [수정된 핵심] Vision 신호가 끊겨도, 최소 제어 시간 동안은 제동을 유지
            if is_braking and (time.time() - braking_start_time > MIN_BRAKING_DURATION):
                print("\n[Test Control] Vision 신호가 끊기고 제어 보장 시간이 초과되었습니다. 제동을 중지합니다.")
                car.ParkingBrake = False
                is_braking = False
                print("\n[Test Control] 다음 과속방지턱 감지를 위해 대기합니다...")
            elif not is_braking:
                print(f"[Test Control] 현재 속도: {read_speed_kmh(car):.1f} km/h | Vision 신호 대기 중...", end='\r')
        
        # --- 제동 로직 ---
        if is_braking:
            try:
                on_time = 0.1 * BRAKE_INTENSITY
                car.Throttle = 0.0
                car.ParkingBrake = True
                if on_time > 0: time.sleep(on_time)
                car.ParkingBrake = False
                if 0.1 - on_time > 0: time.sleep(0.1 - on_time)
            except Exception:
                is_braking = False

        time.sleep(0.02)
    
    # --- 테스트 종료 후 파일 저장 ---
    if test_results:
        try:
            with open("result.txt", "w", encoding="utf-8") as f:
                f.write("="*50 + "\n")
                f.write("      mS 측정 테스트 최종 결과\n")
                f.write("="*50 + "\n\n")
                for i, result in enumerate(test_results):
                    f.write(f"--- 측정 {i+1} ---\n")
                    f.write(f"테스트 제동 강도: {int(result['intensity']*100)}%\n")
                    f.write(f"충돌 시점 속도(mS): {result['speed']:.2f} km/h\n")
                    f.write(f"충돌 시점 거리(D): {result['distance']:.2f} m\n")
                    f.write("-" * 20 + "\n")
            print("[Test Control] 테스트 결과가 result.txt 파일에 저장되었습니다.")
        except Exception as e:
            print(f"[Test Control] 파일 저장 중 오류 발생: {e}")
    else:
        print("[Test Control] 측정된 결과가 없어 파일을 저장하지 않습니다.")


if __name__ == '__main__':
    multiprocessing.freeze_support()
    vision_to_control_queue = multiprocessing.Queue(maxsize=1)
    vision_process = multiprocessing.Process(target=run_vision_processing, args=(vision_to_control_queue,))
    vision_process.start()
    print("[Main] Vision 프로세스 시작됨")

    test_control_logic(vision_to_control_queue)

    if vision_process.is_alive():
        vision_process.terminate()
        vision_process.join()
    print("[Main] 모든 프로세스 종료 완료.")