# evaluate.py
import math
import time
import queue
import pythoncom
from win32com.client import Dispatch, GetActiveObject
from logger import print_at

PROGID = "UCwinRoad.F8ApplicationServicesProxy"
CAL_GAIN = 0.050

def compute_rms(v_kmh, h_m, L_m):
    if not all([isinstance(v_kmh, (int, float)), isinstance(h_m, (int, float)), isinstance(L_m, (int, float))]):
        return 0.0
    if h_m <= 0 or L_m <= 0: return 0.0
    v = v_kmh / 3.6
    return CAL_GAIN * (1.0 / math.sqrt(2.0)) * h_m * (v * math.pi / L_m)**2

def classify_rms(rms_value):
    if rms_value < 0.315: return "매우 쾌적함"
    if rms_value < 0.5: return "쾌적함"
    if rms_value < 0.8: return "보통"
    if rms_value < 1.25: return "불쾌함"
    return "매우 불쾌함"

def run_evaluate_node(control_to_eval_queue, eval_to_control_queue):
    pythoncom.CoInitialize()
    
    while True:
        try:
            data = control_to_eval_queue.get()
            
            if data.get("msg") != "evaluate_request":
                continue

            rS_kmh = data.get('rS_kmh')
            tS_kmh = data.get('tS_kmh')
            eR_rms = data.get('eR_rms')
            gt_h = data.get('gt_h')
            gt_d = data.get('gt_d')

            tR_rms = compute_rms(rS_kmh, gt_h, gt_d)
            comfort_level = classify_rms(tR_rms)
            
            # 터미널 출력용 로그 생성
            result_log_terminal = (f"[Evaluate] rS:{rS_kmh:.1f}km/h | tR:{tR_rms:.2f} "
                                   f"(GTh:{gt_h*100:.1f}cm, GTd:{gt_d:.2f}m) | 실제 승차감: {comfort_level}")
            print_at('EVALUATE_RESULT', result_log_terminal)

            er_error = (abs(eR_rms - tR_rms) / eR_rms) * 100 if eR_rms > 0.01 else 0
            ts_error = (abs(tS_kmh - rS_kmh) / tS_kmh) * 100 if tS_kmh > 0.01 else 0
            
            accuracy_log_terminal = f"[Evaluate] eR<>tR 오차: {er_error:.1f}% | tS<>rS 오차: {ts_error:.1f}%"
            print_at('EVALUATE_ACCURACY', accuracy_log_terminal)

            # 보정 계수 계산
            cal_gain_scale = (tR_rms / eR_rms) if eR_rms > 0.01 else 1.0
            pwm_weight_scale = (tS_kmh / rS_kmh) if rS_kmh > 0.01 else 1.0
            
            cal_gain_scale = max(0.5, min(1.5, cal_gain_scale))
            pwm_weight_scale = max(0.5, min(1.5, pwm_weight_scale))
            
            # Control 노드로 전송할 데이터 구성 (파일 로그용 문자열 포함)
            response_data = {
                "msg": "correction_factors",
                "CAL_GAIN_SCALE": cal_gain_scale,
                "PWM_WEIGHT_SCALE": pwm_weight_scale,
                "result_log": result_log_terminal.replace("[Evaluate] ", ""), # 파일용 로그는 prefix 제외
                "accuracy_log": accuracy_log_terminal.replace("[Evaluate] ", "")
            }
            eval_to_control_queue.put(response_data)

        except queue.Empty:
            continue
        except Exception as e:
            # print(f"[Evaluate] 오류 발생: {e}") # 터미널 로그 최소화를 위해 주석 처리
            time.sleep(1)

    pythoncom.CoUninitialize()