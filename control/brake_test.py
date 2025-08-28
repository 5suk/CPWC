# deceleration_calibrator.py
import time
import win32com.client
from win32com.client import Dispatch, GetActiveObject
import numpy as np

# ================== UC-win/Road 연결 및 기본 함수 ==================
PROGID = "UCwinRoad.F8ApplicationServicesProxy"
SCENARIO_INDEX = 0

def attach_or_launch():
    try: return GetActiveObject(PROGID)
    except: return Dispatch(PROGID)

def start_scenario(sim_core, proj, idx=SCENARIO_INDEX):
    try:
        if hasattr(sim_core, "StopAllScenarios"):
            sim_core.StopAllScenarios()
            time.sleep(0.3)
    except: pass
    sc = proj.Scenario(idx)
    sim_core.StartScenario(sc)
    time.sleep(1.0)
    print(">> 캘리브레이션을 위한 시나리오를 시작합니다.")

def read_speed_kmh(car):
    try: return float(car.Speed(1))
    except: return float(car.Speed()) * 3.6

# ================== PWM 제동 및 데이터 기록 함수 ==================
def pwm_brake_and_record(car, duty_cycle, pwm_cycle, duration, poll_dt):
    speed_readings_mps = []
    t_start = time.time()
    
    while time.time() - t_start < duration:
        cycle_start_time = time.time()
        on_time = pwm_cycle * duty_cycle
        
        try:
            if on_time > 0:
                car.Throttle = 0.0
                car.ParkingBrake = True
                time.sleep(on_time)

            car.ParkingBrake = False
            
            elapsed = time.time() - cycle_start_time
            sleep_time = max(0, pwm_cycle - elapsed)
            time.sleep(sleep_time)

            current_v_kmh = read_speed_kmh(car)
            speed_readings_mps.append(current_v_kmh / 3.6)
            print(f"  [측정 중] Duty Cycle: {int(duty_cycle*100)}% | 현재 속도: {current_v_kmh:.1f} km/h", end='\r')

        except Exception:
            break
            
    try: car.ParkingBrake = False
    except: pass
        
    return speed_readings_mps, (time.time() - t_start)

# ================== 메인 캘리브레이션 로직 ==================
def run_calibration():
    # === 캘리브레이션 설정 ===
    # 현재 시나리오의 AI 목표 속도에 맞춰 이 값을 설정하세요.
    AI_TARGET_SPEED = 60.0
    
    DUTY_CYCLES_TO_TEST = [0.1, 0.25, 0.5, 0.75, 1.0]
    PWM_CYCLE_DURATION = 0.2
    TEST_DURATION_SEC = 2.0 # 40km/h에서는 테스트 시간을 줄여도 충분합니다.
    
    # === UC-win/Road 연결 ===
    try:
        ucwin = attach_or_launch()
        sim_core = ucwin.SimulationCore
        proj = ucwin.Project
        driver = sim_core.TrafficSimulation.Driver
        start_scenario(sim_core, proj, SCENARIO_INDEX)
        car = driver.CurrentCar
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        print("[Calibrator] UC-win/Road 연결 및 차량 핸들 확보 완료.")
    except Exception as e:
        print(f"[Calibrator] UC-win/Road 초기화 실패: {e}")
        return

    print(f"\nAI 목표 속도 {AI_TARGET_SPEED}km/h 환경에 맞춰 캘리브레이션을 시작합니다.")
    results = {}

    for duty_cycle in DUTY_CYCLES_TO_TEST:
        print(f"\n--- [Duty Cycle = {int(duty_cycle*100)}%] 측정 시작 ---")
        
        print(f"AI가 차량 속도를 약 {AI_TARGET_SPEED}km/h로 맞출 때까지 대기합니다...")
        while True:
            current_speed = read_speed_kmh(car)
            if abs(current_speed - AI_TARGET_SPEED) < 5.0: # 목표 속도 근처에 도달하면 시작
                print(f"속도 도달 완료! (현재 {current_speed:.1f} km/h)")
                break
            time.sleep(0.5)

        speed_data, actual_duration = pwm_brake_and_record(car, duty_cycle, PWM_CYCLE_DURATION, TEST_DURATION_SEC, 0.05)
        
        if len(speed_data) > 1:
            timestamps = np.linspace(0, actual_duration, len(speed_data))
            acceleration, _ = np.polyfit(timestamps, speed_data, 1)
            deceleration = -acceleration
            results[duty_cycle] = deceleration
            print(f"\n  [결과] 평균 감속도: {deceleration:.3f} m/s²")
        
        print("  AI가 다시 속도를 복구할 것입니다...")

    # === 최종 결과 출력 ===
    print("\n" + "="*50)
    print("       캘리브레이션 완료: DECELERATION_MAP")
    print("="*50)
    print("아래 코드를 복사하여 control.py 파일에 붙여넣으세요.")
    print("-" * 50)
    print("DECELERATION_MAP = {")
    for dc, decel in sorted(results.items()):
        # 소수점 3자리까지 반올림하여 깔끔하게 출력
        print(f"    {dc:.1f}: {round(decel, 3)},")
    print("}")
    print("-" * 50)

if __name__ == "__main__":
    run_calibration()