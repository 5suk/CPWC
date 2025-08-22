import cv2
import numpy as np
import win32gui, win32ui, win32con
import time

# ==============================================================================
# 0. (추가) 탐지 상태 관리 클래스
# ==============================================================================
class DetectionState:
    def __init__(self, alpha=0.7, pattern_confidence_threshold=0.6, pattern_decay=0.9):
        self.stable_height = 0.0
        self.stable_distance = 0.0
        self.pattern_confidence = 0.0 # 0.0 (False) ~ 1.0 (True)
        
        self.alpha = alpha # EMA 가중치 (값이 낮을수록 부드러움)
        self.pattern_confidence_threshold = pattern_confidence_threshold
        self.pattern_decay = pattern_decay # 패턴이 안보일때 신뢰도 감소율

    def update(self, current_height, current_distance, current_pattern):
        # 높이와 거리는 EMA 필터로 부드럽게 업데이트
        self.stable_height = self.alpha * current_height + (1.0 - self.alpha) * self.stable_height
        self.stable_distance = self.alpha * current_distance + (1.0 - self.alpha) * self.stable_distance
        
        # 패턴은 신뢰도 기반으로 업데이트
        if current_pattern:
            self.pattern_confidence = 1.0 # 패턴이 보이면 신뢰도 즉시 100%
        else:
            # 패턴이 안보이면 신뢰도가 점차 감소
            self.pattern_confidence *= self.pattern_decay
            
    def get_stable_pattern(self):
        # 신뢰도가 특정 임계값 이상일 때만 True로 판단
        return self.pattern_confidence >= self.pattern_confidence_threshold

# ==============================================================================
# 1. 윈도우 캡처 함수
# ==============================================================================
def capture_window_by_title(window_title):
    # (이전과 동일한 코드)
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd == 0: return None
    left, top, right, bot = win32gui.GetClientRect(hwnd)
    w, h = right - left, bot - top
    if w < 2 or h < 2: return None
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)
    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
    bmpstr = saveBitMap.GetBitmapBits(True)
    frame = np.frombuffer(bmpstr, dtype=np.uint8).reshape((h, w, 4))
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC(); mfcDC.DeleteDC(); win32gui.ReleaseDC(hwnd, hwndDC)
    return frame[..., :3].copy()

# ==============================================================================
# 2. 분석 함수들
# ==============================================================================
def get_road_roi(frame, roi_settings):
    # (이전과 동일한 코드)
    h, w, _ = frame.shape
    top_y = int(h * roi_settings['top_y']); bottom_y = int(h * roi_settings['bottom_y'])
    top_x_start = int(w/2-(w*roi_settings['top_w']/2)); top_x_end = int(w/2+(w*roi_settings['top_w']/2))
    bottom_x_start = int(w/2-(w*roi_settings['bottom_w']/2)); bottom_x_end = int(w/2+(w*roi_settings['bottom_w']/2))
    roi_points = np.array([(top_x_start,top_y),(top_x_end,top_y),(bottom_x_end,bottom_y),(bottom_x_start,bottom_y)],dtype=np.int32)
    mask = np.zeros_like(frame[:,:,0]); cv2.fillPoly(mask,[roi_points],255)
    return roi_points, mask

def detect_pattern(frame, roi_mask, pattern_settings):
    # (이전과 동일한 코드)
    hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array(pattern_settings['yellow_lower']); upper_yellow = np.array(pattern_settings['yellow_upper'])
    color_mask = cv2.inRange(hsv_img, lower_yellow, upper_yellow)
    detection_mask = cv2.bitwise_and(color_mask, roi_mask)
    if np.sum(detection_mask > 0) > pattern_settings['min_pixel_area']: return True
    return False

def analyze_height_map(frame, roi_mask, roi_settings, height_settings):
    # (이전과 동일한 코드, 안정성 체크 강화)
    h, w, _ = frame.shape
    hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV); h_channel = hsv_img[:,:,0]
    hue_mask = cv2.inRange(h_channel, height_settings['hue_lower'], height_settings['hue_upper'])
    analysis_mask = cv2.bitwise_and(hue_mask, roi_mask)
    contours, _ = cv2.findContours(analysis_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    estimated_height, estimated_distance = 0.0, 0.0
    if contours:
        all_points = np.concatenate(contours)
        if len(all_points) > 5:
            hull = cv2.convexHull(all_points)
            if cv2.contourArea(hull) > height_settings['min_contour_area']:
                x,y,wc,hc = cv2.boundingRect(hull)
                if hc > 0 and (wc / hc) > height_settings['min_aspect_ratio']:
                    hull_mask = np.zeros_like(analysis_mask); cv2.drawContours(hull_mask, [hull], -1, 255, -1)
                    avg_hue = np.mean(h_channel[np.nonzero(hull_mask)])
                    if avg_hue < height_settings['hue_threshold_b']: estimated_height = 0.2
                    else: estimated_height = 0.1
                    roi_h = max(1,int(h*roi_settings['bottom_y'])-int(h*roi_settings['top_y']))
                    yb_norm = float(np.clip((y+hc-int(h*roi_settings['top_y']))/roi_h,0.0,1.0))
                    dist_calib = height_settings['distance_calibration']
                    y_points = sorted(dist_calib.keys()); dist_points = [dist_calib[y_val] for y_val in y_points]
                    estimated_distance = float(np.interp(yb_norm,y_points,dist_points))
    return estimated_height, estimated_distance

# ==============================================================================
# 3. 메인 로직
# ==============================================================================
if __name__ == "__main__":
    REGULAR_WINDOW_TITLE = "경관 위치 <top>"
    HEIGHT_WINDOW_TITLE = "경관 위치 <test>"
    print("실시간 통합 분석을 시작합니다. 종료하려면 'q' 키를 누르세요.")

    # ### 튜닝용 파라미터 모음 ###
    ROI_SETTINGS_HEIGHT = {'top_y':0.6,'bottom_y':0.98,'top_w':0.25,'bottom_w':0.95}
    ROI_SETTINGS_PATTERN = {'top_y':0.4,'bottom_y':0.98,'top_w':0.4,'bottom_w':1.0}
    HEIGHT_SETTINGS = {'hue_lower':0,'hue_upper':95,'min_contour_area':1200,'min_aspect_ratio':1.5,'hue_threshold_b':40,'distance_calibration':{0.0:21.0,0.5:11.0,1.0:1.0},'existence_threshold_m':0.04}
    PATTERN_SETTINGS = {'yellow_lower':[20,80,80],'yellow_upper':[35,255,255],'min_pixel_area':500}
    CLASSIFICATION_THRESHOLDS = {'height_low':0.4,'height_high':1.3}
    STATE_SETTINGS = {'alpha':0.3,'pattern_confidence_threshold':0.5,'pattern_decay':0.95}

    # 상태 관리 객체 생성
    state = DetectionState(
        alpha=STATE_SETTINGS['alpha'],
        pattern_confidence_threshold=STATE_SETTINGS['pattern_confidence_threshold'],
        pattern_decay=STATE_SETTINGS['pattern_decay']
    )
    last_printed_type = None

    while True:
        regular_frame = capture_window_by_title(REGULAR_WINDOW_TITLE)
        height_frame = capture_window_by_title(HEIGHT_WINDOW_TITLE)

        if regular_frame is None or height_frame is None:
            print("창을 찾을 수 없습니다. 1초 후 재시도합니다.")
            time.sleep(1)
            continue
        
        # 각 프레임의 raw 데이터 계산
        roi_points_pattern, road_mask_pattern = get_road_roi(regular_frame, ROI_SETTINGS_PATTERN)
        roi_points_height, road_mask_height = get_road_roi(height_frame, ROI_SETTINGS_HEIGHT)
        current_pattern = detect_pattern(regular_frame, road_mask_pattern, PATTERN_SETTINGS)
        current_height, current_distance = analyze_height_map(height_frame, road_mask_height, ROI_SETTINGS_HEIGHT, HEIGHT_SETTINGS)
        
        # 상태 업데이트
        state.update(current_height, current_distance, current_pattern)
        
        # 안정화된 값으로 최종 판단
        stable_h = state.stable_height
        stable_p = state.get_stable_pattern()
        existence_present = stable_h >= HEIGHT_SETTINGS['existence_threshold_m']
        
        final_type = "None"
        h_low, h_high = CLASSIFICATION_THRESHOLDS['height_low'], CLASSIFICATION_THRESHOLDS['height_high']

        if stable_h < h_low:
            final_type = "D" if not existence_present and stable_p else "None"
        elif stable_h >= h_low:
            if stable_p:
                if stable_h <= h_high: final_type = "A"
                else: final_type = "B"
            else:
                final_type = "C"
        
        if final_type != "None" and final_type != last_printed_type:
            print(f"\n--- Detection Result ---\n  H: {stable_h:.2f}m | D: {state.stable_distance:.1f}m\n  Exist: {existence_present} | Pattern: {stable_p}\n  Type: {final_type}\n------------------------")
            last_printed_type = final_type
        elif final_type == "None":
            last_printed_type = "None"
        
        # 시각화
        cv2.polylines(height_frame, [roi_points_height], isClosed=True, color=(0,255,0), thickness=2)
        h_text = f"H: {stable_h:.2f}m"; d_text = f"D: {state.stable_distance:.1f}m"; e_text = f"Exist: {existence_present}"
        cv2.putText(height_frame, h_text, (15,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        cv2.putText(height_frame, d_text, (15,60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        cv2.putText(height_frame, e_text, (15,90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        cv2.imshow("Height & Distance Analysis", height_frame)

        cv2.polylines(regular_frame, [roi_points_pattern], isClosed=True, color=(0,255,0), thickness=2)
        p_text = f"Pattern: {stable_p} (Conf: {state.pattern_confidence:.2f})"
        cv2.putText(regular_frame, p_text, (15,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.imshow("Pattern Recognition", regular_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.1)

    cv2.destroyAllWindows()
    print("분석을 종료합니다.")