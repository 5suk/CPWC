# test_speed_control_fixed.py
import time
import math
import win32com.client
from win32com.client import Dispatch, GetActiveObject

# ================== UC-win/Road 연결 및 제어 함수 ==================
PROGID = "UCwinRoad.F8ApplicationServicesProxy"

def attach_or_launch():
    """실행 중인 UC-win/Road에 연결하거나 새로 실행합니다."""
    try:
        return GetActiveObject(PROGID)
    except:
        return Dispatch(PROGID)

def restart_scenario(sim, proj, idx=0):
    """시나리오를 정지하고 다시 시작합니다."""
    try:
        if hasattr(sim, "StopScenario"):
            sim.StopScenario()
            time.sleep(0.5)
    except Exception:
        pass
    sc = proj.Scenario(idx)
    sim.StartScenario(sc)
    time.sleep(1.0)

# ================== 유틸리티 및 계산 함수 ==================
def kmh_to_mps(v): return v / 3.6
def mps_to_kmh(v): return v * 3.6

def _vec3(v):
    """COM 객체의 3차원 벡터를 Python 튜플로 변환합니다."""
    for names in (("X", "Y", "Z"), ("x", "y", "z")):
        if all(hasattr(v, n) for n in names):
            return float(getattr(v, names[0])), float(getattr(v, names[1])), float(getattr(v, names[2]))
    for m in ("Item", "get_Item", "GetAt", "Get"):
        if hasattr(v, m):
            f = getattr(v, m)
            return float(f(0)), float(f(1)), float(f(2))
    seq = list(v)
    return float(seq[0]), float(seq[1]), float(seq[2])

def get_current_speed_kmh(drv):
    """현재 차량의 속도를 km/h 단위로 가져옵니다."""
    c = drv.CurrentCar
    if c is None: return 0.0
    try:
        sv = c.SpeedVector(0)
    except TypeError:
        sv = c.SpeedVector()
    vx, vy, vz = _vec3(sv)
    v_mps = (vx**2 + vy**2 + vz**2)**0.5
    return mps_to_kmh(v_mps)

# ▼▼▼▼▼ [핵심 수정 부분] ▼▼▼▼▼
def set_ai_target_speed_kmh(drv, v_kmh):
    """차량 AI의 목표 주행 속도(SpeedLimit)를 '속성'으로 직접 설정합니다."""
    try:
        target_v_mps = kmh_to_mps(v_kmh)
        # SetSpeedLimit() 호출이 아닌 SpeedLimit 속성에 직접 값을 할당합니다.
        drv.SpeedLimit = target_v_mps
    except Exception as e:
        print(f"[Error] SpeedLimit 속성 설정 실패: {e}")
# ▲▲▲▲▲ [핵심 수정 부분] ▲▲▲▲▲

# ================== 메인 테스트 로직 ==================
def run_speed_test():
    """가속 및 감속을 반복적으로 테스트하는 메인 함수입니다."""
    print("[Test] 가감속 제어 테스트 스크립트 시작")

    # === 테스트 파라미터 ===
    DECEL_AMOUNT_KMH = 30
    ACCEL_AMOUNT_KMH = 50
    SPEED_TOLERANCE_KMH = 2.0
    INITIAL_SPEED_KMH = 80
    
    # === UC-win/Road 연결 ===
    try:
        ucwin = attach_or_launch()
        sim = ucwin.SimulationCore
        proj = ucwin.Project
        driver = sim.TrafficSimulation.Driver
        
        print("[Test] 시나리오를 다시 시작합니다...")
        restart_scenario(sim, proj, 0)
        
        car = None
        t0 = time.time()
        while car is None and time.time() - t0 < 15.0:
            car = driver.CurrentCar
            if car is None: time.sleep(0.2)
        if car is None: raise RuntimeError("차량 핸들을 가져오지 못했습니다.")
        
        print(f"[Test] UC-win/Road 연결 및 차량 핸들 확보 완료.")
    except Exception as e:
        print(f"[Test] UC-win/Road 연결 실패: {e}")
        return

    current_mode = "START"
    target_speed_kmh = INITIAL_SPEED_KMH

    while True:
        try:
            current_speed_kmh = get_current_speed_kmh(driver)
            
            set_ai_target_speed_kmh(driver, target_speed_kmh)
            
            print(f"[Test] 모드: {current_mode} | 현재 속도: {current_speed_kmh:.1f} km/h | 목표 속도: {target_speed_kmh:.1f} km/h", end='\r')

            if abs(current_speed_kmh - target_speed_kmh) < SPEED_TOLERANCE_KMH:
                print("\n" + "="*80)
                print(f"[Test] 목표 속도 {target_speed_kmh:.1f} km/h 도달 성공!")
                
                if current_mode == "START" or current_mode == "ACCELERATING":
                    current_mode = "DECELERATING"
                    new_target_speed = get_current_speed_kmh(driver) - DECEL_AMOUNT_KMH
                    target_speed_kmh = max(10, new_target_speed) # 최소 속도를 10으로 유지
                    print(f"[Test] 다음 단계: 감속을 시작합니다. (목표: {target_speed_kmh:.1f} km/h)")
                
                elif current_mode == "DECELERATING":
                    current_mode = "ACCELERATING"
                    target_speed_kmh = get_current_speed_kmh(driver) + ACCEL_AMOUNT_KMH
                    print(f"[Test] 다음 단계: 가속을 시작합니다. (목표: {target_speed_kmh:.1f} km/h)")
                
                print("="*80)
                time.sleep(2)
            
            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n[Test] 테스트를 중단합니다.")
            # 테스트 종료 시, 차량이 계속 주행하도록 적절한 속도를 설정해주는 것이 좋습니다.
            set_ai_target_speed_kmh(driver, 50)
            break
        except Exception as e:
            print(f"\n[Test] 루프 중 오류 발생: {e}")
            break

if __name__ == '__main__':
    run_speed_test()