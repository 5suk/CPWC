# config/config.py

# ================== 시스템 공통 설정 ==================
UCWIN_PROG_ID = "UCwinRoad.F8ApplicationServicesProxy"

# ================== Vision 모듈 설정 ==================
REGULAR_VIEW_WINDOW_TITLE = "경관 위치 <top>"
HEIGHT_MAP_WINDOW_TITLE = "경관 위치 <test>"
ROI_SETTINGS_HEIGHT = {'top_y': 0.6, 'bottom_y': 0.98, 'top_w': 0.25, 'bottom_w': 0.95}
ROI_SETTINGS_PATTERN = {'top_y': 0.4, 'bottom_y': 0.98, 'top_w': 0.4, 'bottom_w': 1.0}
HEIGHT_ANALYSIS_SETTINGS = {
    'hue_lower': 0, 'hue_upper': 95, 'min_contour_area': 1400, 'min_aspect_ratio': 1.5,
    'distance_calibration': {0.0: 21.0, 0.5: 11.0, 1.0: 0.0},
    'height_interpolation_hue': [15, 55], 'height_interpolation_m': [0.25, 0.05]
}
PATTERN_ANALYSIS_SETTINGS = {
    'yellow_lower': [20, 80, 80], 'yellow_upper': [35, 255, 255],
    'min_pixel_area': 500
}
CLASSIFICATION_THRESHOLDS = {
    'A_MIN_H': 0.02,
    'A_MAX_H': 0.13,
    'C_MIN_H': 0.04,
    'D_MAX_H': 0.04
}
DETECTION_CONFIRM_FRAME_COUNT = 2

# ================== Control 모듈 설정 ==================
CONTROL_POLL_DT = 0.15
TARGET_SPEED_MARGIN_KMH = 3.0
SCENARIO_RESTART_TRIGGER_X = 2100.0
BUMP_PASS_DETECTION_THRESHOLD_M = 3.0
COMFORT_TARGETS_RMS = {
    '매우 쾌적함': 0.315,
    '쾌적함': 0.5,
    '보통': 0.8
}
INITIAL_PR_CALIBRATION = 0.06
INITIAL_PWM_CALIBRATION = 1.0

# ================== Evaluate 모듈 설정 ==================
LEARNING_RATE_PR_CALIBRATION = 0.1
LEARNING_RATE_PWM_CALIBRATION = 0.1

# ================== Calibration 모듈 설정 ==================
CALIBRATION_DATA_FILE_PATH = "speed_map.json"