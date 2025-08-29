# vision.py
import cv2
import numpy as np
import win32gui, win32ui, win32con
import time
import collections
import queue
from logger import print_at

def get_bump_width(bump_type_str):
    if 'a' in bump_type_str.lower(): return 3.6
    if 'b' in bump_type_str.lower(): return 1.8
    return 3.0

def capture_window_by_title(window_title):
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

def get_road_roi(frame, roi_settings):
    h, w, _ = frame.shape
    top_y = int(h * roi_settings['top_y']); bottom_y = int(h * roi_settings['bottom_y'])
    top_x_start = int(w/2-(w*roi_settings['top_w']/2)); top_x_end = int(w/2+(w*roi_settings['top_w']/2))
    bottom_x_start = int(w/2-(w*roi_settings['bottom_w']/2)); bottom_x_end = int(w/2+(w*roi_settings['bottom_w']/2))
    roi_points = np.array([(top_x_start,top_y),(top_x_end,top_y),(bottom_x_end,bottom_y),(bottom_x_start,bottom_y)],dtype=np.int32)
    mask = np.zeros_like(frame[:,:,0]); cv2.fillPoly(mask,[roi_points],255)
    return roi_points, mask

def detect_pattern(frame, roi_mask, pattern_settings):
    hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array(pattern_settings['yellow_lower']); upper_yellow = np.array(pattern_settings['yellow_upper'])
    color_mask = cv2.inRange(hsv_img, lower_yellow, upper_yellow)
    detection_mask = cv2.bitwise_and(color_mask, roi_mask)
    if np.sum(detection_mask > 0) > pattern_settings['min_pixel_area']: return True
    return False

def analyze_height_map(frame, roi_mask, roi_settings, height_settings):
    h, w, _ = frame.shape
    hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV); h_channel = hsv_img[:,:,0]
    hue_mask = cv2.inRange(h_channel, height_settings['hue_lower'], height_settings['hue_upper'])
    analysis_mask = cv2.bitwise_and(hue_mask, roi_mask)
    contours, _ = cv2.findContours(analysis_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    estimated_height, estimated_distance = 0.0, 0.0
    if contours and len(contours) > 0:
        all_points = np.concatenate(contours)
        if len(all_points) > 5:
            hull = cv2.convexHull(all_points)
            if cv2.contourArea(hull) > height_settings['min_contour_area']:
                x,y,wc,hc = cv2.boundingRect(hull)
                if hc > 0 and (wc / hc) > height_settings['min_aspect_ratio']:
                    hull_mask = np.zeros_like(analysis_mask); cv2.drawContours(hull_mask, [hull], -1, 255, -1)
                    hue_values = h_channel[np.nonzero(hull_mask)]
                    if len(hue_values) > 0:
                        avg_hue = np.mean(hue_values)
                        hue_points = height_settings['height_interpolation_hue']
                        height_points = height_settings['height_interpolation_m']
                        estimated_height = np.interp(avg_hue, hue_points, height_points)
                    roi_h = max(1,int(h*roi_settings['bottom_y'])-int(h*roi_settings['top_y']))
                    yb_norm = float(np.clip((y+hc-int(h*roi_settings['top_y']))/roi_h,0.0,1.0))
                    dist_calib = height_settings['distance_calibration']
                    y_points = sorted(dist_calib.keys()); dist_points = [dist_calib[y_val] for y_val in y_points]
                    estimated_distance = float(np.interp(yb_norm,y_points,dist_points))
    return estimated_height, estimated_distance
    
def run_vision_processing(vision_to_control_queue, v2v_to_vision_queue, forward_vehicle_distance):
    print("[Vision] 비전 처리 프로세스를 시작합니다.")
    
    REGULAR_WINDOW_TITLE = "경관 위치 <top>"; HEIGHT_WINDOW_TITLE = "경관 위치 <test>"
    ROI_SETTINGS_HEIGHT = {'top_y':0.6,'bottom_y':0.98,'top_w':0.25,'bottom_w':0.95}
    ROI_SETTINGS_PATTERN = {'top_y':0.4,'bottom_y':0.98,'top_w':0.4,'bottom_w':1.0}
    HEIGHT_SETTINGS = {
        'hue_lower':0,'hue_upper':95, 'min_contour_area':1400, 'min_aspect_ratio':1.5,
        'distance_calibration':{0.0:21.0,0.5:11.0,1.0:0.0}, 'existence_threshold_m':0.04,
        'height_interpolation_hue': [15, 55], 'height_interpolation_m': [0.25, 0.05]
    }
    PATTERN_SETTINGS = {'yellow_lower':[20,80,80],'yellow_upper':[35,255,255],'min_pixel_area':500}
    CLASSIFICATION_THRESHOLDS = {'height_exist':0.04, 'height_A_max':0.13}
    CONFIRM_FRAME_COUNT = 2
    
    detection_history = collections.deque(maxlen=CONFIRM_FRAME_COUNT)
    confirmed_type = "None"; last_printed_type = None
    
    cv2.namedWindow("Height & Distance Analysis", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Pattern Recognition", cv2.WINDOW_NORMAL)

    while True:
        distance_to_front = forward_vehicle_distance.value
        is_v2v_mode = (distance_to_front <= 30.0)

        # --- [수정] 화면 캡처를 루프 최상단으로 이동하여 항상 실행 ---
        regular_frame = capture_window_by_title(REGULAR_WINDOW_TITLE)
        height_frame = capture_window_by_title(HEIGHT_WINDOW_TITLE)
        if regular_frame is None or height_frame is None:
            time.sleep(1); continue

        # 화면에 표시할 정보 초기화
        current_h, current_d, current_p, confirmed_type_str = 0.0, 0.0, False, "None"
        
        if is_v2v_mode:
            print_at('VISION', f"V2V 모드 활성화 (전방 차량: {distance_to_front:.1f}m)")
            try:
                v2v_data = v2v_to_vision_queue.get_nowait()
                print(f"\n[Vision] V2V로부터 과속방지턱 정보 수신: {v2v_data}")
                vision_to_control_queue.put_nowait(v2v_data)
            except queue.Empty: pass
        else:
            print_at('VISION', "카메라 모드 활성화")
            
            roi_points_pattern, road_mask_pattern = get_road_roi(regular_frame, ROI_SETTINGS_PATTERN)
            roi_points_height, road_mask_height = get_road_roi(height_frame, ROI_SETTINGS_HEIGHT)
            current_p = detect_pattern(regular_frame, road_mask_pattern, PATTERN_SETTINGS)
            current_h, current_d = analyze_height_map(height_frame, road_mask_height, ROI_SETTINGS_HEIGHT, HEIGHT_SETTINGS)
            current_e = current_h >= HEIGHT_SETTINGS['existence_threshold_m']
            current_type_str = "None"; h_A_max = CLASSIFICATION_THRESHOLDS['height_A_max']
            if not current_e: current_type_str = "D" if current_p else "None"
            else:
                if current_p:
                    if current_h <= h_A_max: current_type_str = "A"
                    else: current_type_str = "B"
                else: current_type_str = "C"

            detection_history.append(current_type_str)
            if len(detection_history) == CONFIRM_FRAME_COUNT and len(set(detection_history)) == 1:
                confirmed_type_str = detection_history[0]
            if current_type_str == "None":
                confirmed_type_str = "None"; detection_history.clear()
            
            if confirmed_type_str != "None" and confirmed_type_str != last_printed_type:
                print(f"\n[Vision][Camera] 과속방지턱 감지: T:{confirmed_type_str}|H:{current_h:.2f}m|D:{current_d:.1f}m")
                last_printed_type = confirmed_type_str
                data_packet = {'type': confirmed_type_str, 'height_m': current_h, 'distance_m': current_d, 'width_m': get_bump_width(confirmed_type_str)}
                try: vision_to_control_queue.put_nowait(data_packet)
                except queue.Full: pass
            elif confirmed_type_str == "None":
                last_printed_type = "None"
        
        # --- [수정] 시각화 부분을 루프 하단으로 이동하여 항상 실행 ---
        # Height 창 업데이트
        mode_text = "V2V Mode" if is_v2v_mode else "Camera Mode"
        cv2.putText(height_frame, f"Mode: {mode_text}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        if not is_v2v_mode:
            h_text=f"H: {current_h:.2f}m"; d_text=f"D: {current_d:.1f}m"
            cv2.putText(height_frame,h_text,(15,60),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,255),2)
            cv2.putText(height_frame,d_text,(15,90),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,255),2)
        cv2.imshow("Height & Distance Analysis", height_frame)

        # Pattern 창 업데이트
        cv2.putText(regular_frame, f"Mode: {mode_text}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        if not is_v2v_mode:
            p_text = f"Pattern: {current_p}"; r_text = f"Confirmed: {confirmed_type_str}"
            cv2.putText(regular_frame, p_text, (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
            cv2.putText(regular_frame, r_text, (15, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        cv2.imshow("Pattern Recognition", regular_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'): break
        time.sleep(0.1)
    
    cv2.destroyAllWindows()