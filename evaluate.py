# evaluate.py
import math
import time
import queue
import pythoncom
from logger import print_at
import config

def compute_rms(v_kmh, h_m, L_m):
    if not all([isinstance(v_kmh, (int, float)), isinstance(h_m, (int, float)), isinstance(L_m, (int, float))]):
        return 0.0
    if h_m <= 0 or L_m <= 0: return 0.0
    v = v_kmh / 3.6
    fixed_physical_gain = 0.050
    return fixed_physical_gain * (1.0 / math.sqrt(2.0)) * h_m * (v * math.pi / L_m)**2

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

            cS = data.get('current_speed')
            tS = data.get('target_speed')
            pR = data.get('prediction_RMS')
            gt_h = data.get('GT_Height')
            gt_d = data.get('GT_Depth')
            current_gain = data.get('current_gain')
            current_pwm_weight = data.get('current_pwm_weight')

            actual_RMS = compute_rms(cS, gt_h, gt_d)
            comfort_level = classify_rms(actual_RMS)
            
            result_log = (f"cS:{cS:.1f} | actual_RMS:{actual_RMS:.2f} "
                          f"(GT_H:{gt_h*100:.1f}cm, GT_Dp:{gt_d:.2f}m) | Comfort: {comfort_level}")
            print_at('EVALUATE_RESULT', f"[Evaluate] {result_log}")

            er_error = (abs(pR - actual_RMS) / pR) * 100 if pR > 0.01 else 0
            ts_error = (abs(tS - cS) / tS) * 100 if tS > 0.01 else 0
            accuracy_log = f"pR<>aR 오차: {er_error:.1f}% | tS<>cS 오차: {ts_error:.1f}%"
            print_at('EVALUATE_ACCURACY', f"[Evaluate] {accuracy_log}")

            # [수정] 이동 평균 필터 적용
            # 1. 새로운 목표 보정값 계산
            target_gain = current_gain * (actual_RMS / pR) if pR > 0.01 else current_gain
            target_pwm_weight = current_pwm_weight * (cS / tS) if tS > 0.01 else current_pwm_weight

            # 2. 이동 평균 필터(학습률)를 적용하여 최종 보정값 계산
            alpha_pr = config.LEARNING_RATE_PR
            updated_gain = (current_gain * (1 - alpha_pr)) + (target_gain * alpha_pr)

            alpha_pwm = config.LEARNING_RATE_PWM
            updated_pwm_weight = (current_pwm_weight * (1 - alpha_pwm)) + (target_pwm_weight * alpha_pwm)

            response_data = {
                "msg": "final_correction_factors",
                "updated_gain": updated_gain,
                "updated_pwm_weight": updated_pwm_weight,
                "result_log": result_log,
                "accuracy_log": accuracy_log
            }
            eval_to_control_queue.put(response_data)

        except queue.Empty:
            continue
        except Exception:
            time.sleep(1)

    pythoncom.CoUninitialize()