# utils/calibration.py
import os
import sys
import json
import time
import msvcrt
import pythoncom
import multiprocessing
import queue
from win32com.client import Dispatch, GetActiveObject

# 단독 실행을 위해 프로젝트 root 경로를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 변경된 디렉토리 구조에 맞게 import 경로 수정
from src.vision import run_vision_processing 
from config import config

# --- 시뮬레이션 제어를 위한 헬퍼 함수 ---
def attach_or_launch():
    try:
        return GetActiveObject(config.UCWIN_PROG_ID)
    except:
        return Dispatch(config.UCWIN_PROG_ID)

def read_speed_kmh(car):
    try:
        return float(car.Speed(1))
    except:
        return 0.0

def restart_scenario(sim_core, proj, idx=0):
    try:
        if hasattr(sim_core, "StopAllScenarios"):
            sim_core.StopAllScenarios()
            time.sleep(0.3)
    except:
        pass
    sc = proj.Scenario(idx)
    sim_core.StartScenario(sc)
    time.sleep(0.8)

# --- 메인 캘리브레이션 세션 함수 ---
def run_calibration_session(target_speed):
    pythoncom.CoInitialize()
    
    if target_speed >= 50:
        brake_intensity = 1.0
    else:
        steps_down = (50 - target_speed) // 10
        brake_intensity = 1.0 - (steps_down * 0.1)
        brake_intensity = max(0.1, brake_intensity)
    
    print(f"목표 속도 {target_speed}km/h에 대한 측정을 시작합니다. (계산된 제동 강도: {brake_intensity:.1f})")

    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore
        project = ucwin.Project
        driver = sim_core.TrafficSimulation.Driver
    except Exception as e:
        print(f"UC-win/Road 연결에 실패했습니다: {e}")
        pythoncom.CoUninitialize()
        return

    vision_to_calib_queue = multiprocessing.Queue(maxsize=1)
    vision_process = multiprocessing.Process(target=run_vision_processing, args=(vision_to_calib_queue, None, None))
    vision_process.start()

    measured_speeds = []
    
    restart_scenario(sim_core, project, 0)
    vehicle = None
    t0 = time.time()
    while vehicle is None and time.time() - t0 < 15.0:
        vehicle = driver.CurrentCar
        time.sleep(0.2)
    
    if vehicle is None:
        print("차량을 찾을 수 없습니다. 프로그램을 종료합니다.")
        if vision_process.is_alive():
            vision_process.terminate()
            vision_process.join()
        pythoncom.CoUninitialize()
        return

    while len(measured_speeds) < 3:
        print(f"\n--- 현재 {len(measured_speeds) + 1}/3 번째 측정 대기 중 ---")
        
        print("목표 속도 도달 및 Vision 감지를 위해 주행합니다...")
        is_braking = False
        braking_cancelled = False

        start_time = time.time()
        while time.time() - start_time < 90.0:
            current_speed = read_speed_kmh(vehicle)
            
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                if key == 'c' and is_braking:
                    speed = read_speed_kmh(vehicle)
                    vehicle.ParkingBrake = False
                    measured_speeds.append(round(speed, 2))
                    print(f"\n>> 충돌! 속도({speed:.2f} km/h)가 기록되었습니다. <<")
                    while not vision_to_calib_queue.empty(): vision_to_calib_queue.get()
                    break
                
                elif key == 'b' and is_braking:
                    vehicle.ParkingBrake = False
                    braking_cancelled = True
                    print("\n>> 잘못된 감속! 'b'키가 입력되어 이번 측정을 취소합니다. <<")
                    while not vision_to_calib_queue.empty(): vision_to_calib_queue.get()
                    break

            if not is_braking:
                print(f"\r주행 중... (현재 속도: {current_speed:.1f} km/h)", end="")
                if current_speed >= target_speed:
                    try:
                        data = vision_to_calib_queue.get(timeout=0.01)
                        if data['type'] != "None":
                            print(f"\n>>> 과속방지턱 감지! 제동(강도:{brake_intensity:.1f})을 시작합니다. (기록: 'c', 취소: 'b') <<<")
                            is_braking = True
                    except queue.Empty:
                        pass
            
            if is_braking:
                on_time = 0.1 * brake_intensity
                off_time = 0.1 * (1.0 - brake_intensity)
                vehicle.Throttle = 0.0
                if on_time > 0:
                    vehicle.ParkingBrake = True; time.sleep(on_time)
                if off_time > 0:
                    vehicle.ParkingBrake = False; time.sleep(off_time)
        
        if braking_cancelled:
            continue
        if not is_braking and not measured_speeds:
             print("\n시간 내에 과속방지턱을 감지하지 못했습니다.")

    if vision_process.is_alive():
        vision_process.terminate()
        vision_process.join()

    if measured_speeds:
        try:
            with open(config.CALIBRATION_DATA_FILE_PATH, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        avg_speed = sum(measured_speeds) / len(measured_speeds)
        data[str(target_speed)] = round(avg_speed, 2)
        
        print(f"\n--- 최종 결과 (목표 속도: {target_speed}km/h) ---")
        print(f"유효 측정 횟수: {len(measured_speeds)}회")
        print(f"측정된 속도들: {measured_speeds}")
        print(f"평균 속도: {avg_speed:.2f} km/h")

        output_dir = os.path.dirname(config.CALIBRATION_DATA_FILE_PATH)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        with open(config.CALIBRATION_DATA_FILE_PATH, "w", encoding="utf-8") as f:
            sorted_data = {k: v for k, v in sorted(data.items(), key=lambda item: int(item[0]))}
            json.dump(sorted_data, f, indent=4)
        
        print(f"'{config.CALIBRATION_DATA_FILE_PATH}' 파일에 결과가 저장(누적)되었습니다.")
    
    pythoncom.CoUninitialize()

if __name__ == '__main__':
    if sys.platform == "win32":
        multiprocessing.freeze_support()
    
    try:
        speed_in = int(input(">> 테스트를 진행할 AI 목표 속도(km/h)를 입력하세요: "))
    except ValueError as e:
        print(f"입력 오류: {e}")
        sys.exit(1)
        
    run_calibration_session(speed_in)