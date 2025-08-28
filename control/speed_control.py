# practice_refined.py
import time
from win32com.client import Dispatch, GetActiveObject

PROGID = "UCwinRoad.F8ApplicationServicesProxy"
SCENARIO_INDEX = 0

TARGET_KMH = 100.0      # 최종 목표 속도
POLL_DT = 0.05        # 50ms 주기 (AI의 판단보다 빠르게 덮어쓰기 위한 설정)
FORCE_SEC = 6.0       # 최대 강제 제어 시간

def attach():
    """실행 중인 UC-win/Road에 연결하거나 새로 실행합니다."""
    try:
        return GetActiveObject(PROGID)
    except:
        return Dispatch(PROGID)

def start_scenario(sim_core, proj, idx=SCENARIO_INDEX):
    """시나리오를 다시 시작합니다."""
    try:
        if hasattr(sim_core, "StopAllScenarios"):
            sim_core.StopAllScenarios()
            time.sleep(0.3)
    except:
        pass
    sc = proj.Scenario(idx)
    sim_core.StartScenario(sc)
    time.sleep(0.8)
    print(">> 시나리오 시작")

def read_speed_kmh(car):
    """차량의 현재 속도를 km/h 단위로 읽어옵니다."""
    try:
        # 가장 기본적인 속도 읽기 방법 (km/h 단위)
        return float(car.Speed(1))
    except:
        try:
            # m/s 단위로 반환될 경우 변환
            return float(car.Speed()) * 3.6
        except:
            # 위 방법들이 모두 실패할 경우, 거리 변화량으로 속도 추정
            s0 = float(car.DistanceAlongRoad)
            t0 = time.time()
            time.sleep(0.04)
            s1 = float(car.DistanceAlongRoad); t1 = time.time()
            v_ms = max(0.0, (s1 - s0) / max(1e-6, (t1 - t0)))
            return v_ms * 3.6

def can_set(prop_setter):
    """해당 속성을 설정할 수 있는지 테스트하는 함수."""
    try:
        prop_setter()
        return True
    except:
        return False

def hard_takeover_and_brake(car, target_kmh):
    """
    사용 가능한 모든 제어 채널을 통해 고주기로 강제 제동을 시도합니다.
    AI의 덮어쓰기 로직에 대항하여 계속해서 제어 값을 강제로 설정합니다.
    """
    # 제어 가능한 채널이 있는지 한번만 확인
    has_throttle = can_set(lambda: setattr(car, "Throttle", 0.0))
    has_brake = can_set(lambda: setattr(car, "Brake", 1.0))
    has_pbrake = can_set(lambda: setattr(car, "ParkingBrake", True))
    has_engine = can_set(lambda: setattr(car, "EngineOn", False))

    print(f"사용 가능한 제어 채널: Throttle={has_throttle}, Brake={has_brake}, ParkingBrake={has_pbrake}, EngineOn={has_engine}")
    print(f"최대 {FORCE_SEC:.1f}초 동안 강제 제동을 시작합니다...")

    t0 = time.time()
    hit_target = False
    while time.time() - t0 < FORCE_SEC:
        # 확인된 채널에 대해서만 반복적으로 강제 제어 명령 전송
        try:
            if has_throttle: car.Throttle = 0.0
            if has_brake: car.Brake = 1.0
            if has_pbrake: car.ParkingBrake = True
            if has_engine: car.EngineOn = False
        except Exception:
            # 루프 중 COM 오류가 발생해도 중단되지 않도록 방지
            pass

        spd = read_speed_kmh(car)
        print(f"[강제 제어 중] 현재 속도={spd:.1f} km/h (목표: {target_kmh:.0f} km/h)", end='\r')

        # 목표 속도에 도달하면 루프 종료
        if spd <= target_kmh + 0.5:
            hit_target = True
            print("\n[성공] 강제 제어로 목표 속도에 도달했습니다.")
            break

        time.sleep(POLL_DT)

    # 강제 제어 루프 종료 후, 차량 상태를 정상으로 복구 시도
    print("강제 제어 종료. 차량 상태를 복구합니다.")
    try:
        if has_brake: car.Brake = 0.0
        if has_pbrake: car.ParkingBrake = False
        if has_engine: car.EngineOn = True
    except Exception:
        pass

    return hit_target

def main():
    """메인 실행 함수"""
    sim = attach()
    proj = sim.Project
    sim_core = sim.SimulationCore

    try:
        start_scenario(sim_core, proj, SCENARIO_INDEX)
    except Exception as e:
        print(f"시나리오 자동 시작 실패: {e}")

    car = sim_core.TrafficSimulation.Driver.CurrentCar

    try:
        start_speed = read_speed_kmh(car)
        print(f"시작 속도: {start_speed:.1f} km/h")
    except Exception as e:
        print(f"시작 속도 읽기 실패: {e}")

    # Plan-B 없이 직접 제어만 실행
    hard_takeover_and_brake(car, TARGET_KMH)

    try:
        final_speed = read_speed_kmh(car)
        print(f"최종 속도: {final_speed:.1f} km/h")
        print("AI가 제어권을 되찾아 원래 속도로 복귀를 시도할 것입니다.")
    except Exception:
        pass

if __name__ == "__main__":
    main()