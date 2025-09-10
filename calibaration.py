# calibration.py
import os
import sys
import json
import time
import msvcrt
import pythoncom
import multiprocessing
from win32com.client import Dispatch, GetActiveObject

from vision import run_vision_processing
import config

def run_calibration_session(target_speed, brake_intensity):
    pythoncom.CoInitialize()
    
    try:
        ucwin = GetActiveObject(config.UCWIN_PROG_ID)
    except:
        ucwin = Dispatch(config.UCWIN_PROG_ID)

    sim_core = ucwin.SimulationCore
    project = ucwin.Project
    
    try:
        if hasattr(sim_core, "StopAllScenarios"):
            sim_core.StopAllScenarios(); time.sleep(0.3)
    except: pass
        
    scenario = project.Scenario(0)
    sim_core.StartScenario(scenario)
    time.sleep(0.8)
    
    driver = sim_core.TrafficSimulation.Driver
    vehicle = None
    t0 = time.time()
    while vehicle is None and time.time() - t0 < 15.0:
        vehicle = driver.CurrentCar
        time.sleep(0.2)
    
    if vehicle is None:
        pythoncom.CoUninitialize()
        return

    vision_to_calib_queue = multiprocessing.Queue()
    measured_speeds = []

    for i in range(3):
        print(f"\n--- 측정 {i + 1}/3 ---")
        input("차량을 출발 위치로 옮기고, AI 속도를 설정한 후 Enter를 눌러 측정을 시작하세요...")
        
        vision_process = multiprocessing.Process(target=run_vision_processing, args=(vision_to_calib_queue, None, None))
        vision_process.start()
        
        is_braking = False
        start_time = time.time()

        while time.time() - start_time < 60.0:
            try:
                if not is_braking:
                    try:
                        data = vision_to_calib_queue.get(timeout=0.01)
                        if data['type'] != "None":
                            is_braking = True
                    except queue.Empty:
                        pass
                
                if is_braking:
                    on_time = 0.1 * brake_intensity
                    off_time = 0.1 * (1.0 - brake_intensity)
                    vehicle.Throttle = 0.0
                    if on_time > 0: vehicle.ParkingBrake = True; time.sleep(on_time)
                    if off_time > 0: vehicle.ParkingBrake = False; time.sleep(off_time)

                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8').lower()
                    if key == 'c' and is_braking:
                        speed = vehicle.Speed(1)
                        vehicle.ParkingBrake = False
                        measured_speeds.append(round(speed, 2))
                        break
            except Exception:
                vehicle.ParkingBrake = False
                break
        
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

        output_dir = os.path.dirname(config.CALIBRATION_DATA_FILE_PATH)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        with open(config.CALIBRATION_DATA_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, sort_keys=True)
    
    pythoncom.CoUninitialize()

if __name__ == '__main__':
    if sys.platform == "win32":
        multiprocessing.freeze_support()
    
    try:
        speed_in = int(input(">> 테스트를 진행할 AI 목표 속도(km/h)를 입력하세요: "))
        intensity_in = float(input(">> 테스트 제동 강도를 입력하세요 (0.1 ~ 1.0): "))
        if not (0.1 <= intensity_in <= 1.0):
            raise ValueError()
    except ValueError:
        sys.exit(1)
        
    run_calibration_session(speed_in, intensity_in)