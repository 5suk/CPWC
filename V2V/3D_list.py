# debug_final_check.py
import time
import pythoncom
import win32com.client
import math
from samples.UCwinRoadCOM import UCwinRoadComProxy

# --- 헬퍼 함수들 ---
def _vec3(v):
    """COM 벡터 객체를 파이썬 튜플(X, Y, Z)로 변환합니다."""
    try: return f"{v.X:.2f}, {v.Y:.2f}, {v.Z:.2f}"
    except Exception: return "N/A"

def vector_magnitude(v_obj):
    """COM 벡터 객체의 크기(길이)를 계산합니다."""
    try:
        v = v_obj
        return math.sqrt(v.X**2 + v.Y**2 + v.Z**2)
    except Exception:
        return 0.0
# -----------------------------------------

def main_final_check():
    """
    [최종 디버깅용] 'type' 객체를 찾아, 형상 정보(높이, 깊이)와
    위치 정보(절대 좌표, 도로상 거리)를 모두 계산하여 출력합니다.
    """
    print("[DEBUG] 최종 3D 객체 확인 스크립트를 시작합니다.")
    pythoncom.CoInitialize()
    
    try:
        # 1. UC-win/Road 연결
        winRoadProxy = UCwinRoadComProxy()
        project = winRoadProxy.Project
        print("[DEBUG] UC-win/Road에 연결되었습니다.")

        # 2. 'type'으로 시작하는 과속방지턱 객체 탐색 및 정보 추출
        print("\n" + "="*70)
        print("      'type'으로 시작하는 객체 탐색 및 전체 GT 정보 추출")
        print("="*70)
        
        target_names = ["typea", "typeb", "typec", "typed"]
        found_models = []
        
        instance_count = project.ThreeDModelInstancesCount
        if instance_count > 0:
            for i in range(instance_count):
                instance = project.ThreeDModelInstance(i)
                instance_name_lower = instance.Name.lower()

                if any(instance_name_lower.startswith(target) for target in target_names):
                    height_y, depth_z = 0.0, 0.0
                    position_str, road_dist_m = "N/A", 0.0
                    source = "N/A"

                    # 형상 정보 (BoundingBox)
                    try:
                        if instance.BoundingBoxesCount > 0:
                            bbox = instance.BoundingBox(0)
                            height_y = vector_magnitude(bbox.yAxis) * 2
                            depth_z = vector_magnitude(bbox.zAxis) * 2
                            source = "BoundingBox"
                    except Exception:
                        source = "형상 정보 획득 실패"

                    # --- [핵심 추가] 위치 정보 ---
                    try:
                        # 절대 좌표 (X, Y, Z)
                        position_str = _vec3(instance.Position)
                        # 도로상 거리 (m)
                        road_dist_m = instance.DistanceAlongRoad
                    except Exception:
                        pass # 위치 정보 획득 실패 시 기본값 사용
                    # -------------------------

                    model_data = {
                        "name": instance.Name, "id": instance.ID,
                        "height_m": height_y, "depth_m": depth_z,
                        "position": position_str, "road_distance": road_dist_m,
                        "source": source
                    }
                    found_models.append(model_data)

        if not found_models:
            print("-> 'type'으로 시작하는 3D 객체를 찾지 못했습니다.")
        else:
            print(f"-> 총 {len(found_models)}개의 'type' 객체를 발견했습니다.")
            for model in found_models:
                print("-" * 40)
                print(f"  이름: {model['name']} (ID: {model['id']})")
                print(f"  - 계산된 높이 (Y): {model['height_m'] * 100:.2f} cm")
                print(f"  - 계산된 깊이 (Z): {model['depth_m'] * 100:.2f} cm")
                print(f"  - 절대 좌표 (X,Y,Z): {model['position']}")
                print(f"  - 도로상 위치: {model['road_distance']:.2f} m 지점")
                print(f"  - 정보 출처: {model['source']}")

        print("="*70)
        print("[DEBUG] 확인 완료. 스크립트를 종료합니다.")

    except Exception as e:
        print(f"\n[오류] 스크립트 실행 중 심각한 오류 발생: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == '__main__':
    main_final_check()