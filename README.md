# CPWC (Cloud Programming World Cup 2025)
### Speed Bump Response System for Autonomous Driving

### 과속방지턱 분류 기준 
| 판단 결과 | 높이 | 경과 위치<test> 를 통한 존재유무 | 패턴 |
| --- | --- | --- | --- |
| A | 0.02 이상 0.13 이하 | T | T |
| B | 0.13 초과 | T | T |
| C | 0.04 이상 | T | F |
| D | 0.04 미만 | F | T |
| None | 0.04 미만 | F | F |

### 변수 목록

| 기능 요약 | 상세 설명 | 변수명 (코드) | 약어 (발표/대화) |
| :--- | :--- | :--- | :--- |
| **제어 (Control)** | | | |
| 예측 승차감 | 제어 시작 전, 예상한 승차감 지수. | `prediction_RMS` | pR |
| 승차감 예측 보정 | evaluate 모듈에 의한 승차감 예상 보정 계수. | `pR_Calibration` | pR_CAL |
| 제동 강도 | 계산된 최종 제동 실시 강도. | `Brake_PWM` | B_PWM |
| 제동 보정 | evaluate 모듈에 의한 제동 강도 보정. | `PWM_Calibration` | PWM_CAL |
| 방지턱 거리 | 차량과 과속방지턱 사이 남은 거리. | `bump_distance` | bD |
| 현재 속도 | 차량의 현재 속도. | `current_speed` | cS |
| 목표 속도 | 제동으로 도달하려는 목표 속도. | `target_speed` | tS |
| 사전 스캔한 정보 | 시나리오 시작 시 스캔해 둔 방지턱 정보. | `ThreeDModelGT_cache` | 3DmodelGT_cache |
| 스캔한 형상 정보 | 객체 정보를 통해 스캔한 모델의 형상 정보. | `GT_Height`, `GT_Depth`, `GT_Distance` | GT_H, GT_Dp, GT_Dt |
| 감속 상태 플래그 | 감속 주행 여부에 대한 상태 플래그. | `Is_Controlling` | Is_Controlling |
| 최소 속도 | 현재 속도에서 최대 제동력으로 도달 가능한 한계 속도. | `minimum_Speed` | mS |
| 예측 승차감 레벨 | 예측 RMS 기준으로 사용자가 느끼는 예측 승차감 레벨. | `prediction_Level` | pL |
| **인지 (Perception)** | | | |
| 카메라 측정 값 | 카메라를 통해 측정한 방지턱 형상 정보. | `Measured_Height`, `Measured_Distance` | M_H, M_Dt |
| 감지 결과 저장 | 연속적 감지 결과를 저장하여 신뢰도 향상. | `Detection_History` | Detection_History |
| 방지턱 감지 패턴 | 카메라를 통해 감지한 방지턱 패턴 유무. | `Bump_Pattern` | Bump_Pattern |
| V2V 수신 정보 | V2V 통신으로 받은 데이터. | `v2v_data` | v2v_data |
| 전방 차량 거리 | V2V 통신으로 감지한 전방 차량과의 거리. | `forward_vehicle_distance` | vD |
| **평가 (Evaluate)** | | | |
| 실제 승차감 | 실제 방지턱 통과 시 계산된 승차감 지수. | `actual_RMS` | aR |
| 승차감 오차 | 예측 승차감과 실제 승차감의 오차율. | `er_error` | er_error |
| 속도 오차 | 목표 속도와 실제 통과 속도의 오차율. | `ts_error` | ts_error |