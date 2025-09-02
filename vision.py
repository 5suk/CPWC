# vision.py
import cv2
import numpy as np
import win32gui, win32ui, win32con
import time
import collections
import queue
import pythoncom
import win32com.client
import math
from samples.UCwinRoadCOM import UCwinRoadComProxy
from samples.UCwinRoadUtils import Distance
from logger import print_at

def vector_magnitude(v_obj):
    """COM 벡터 객체의 크기를 계산합니다."""
    try:
        return math.sqrt(v_obj.X**2 + v_obj.Y**2 + v_obj.Z**2)
    except Exception:
        return 0.0

def find_and_scan_speed_bumps_gt(project):
    """
    시뮬레이션 시작 시 모든 과속방지턱 3D 객체를 스캔하여 GT 데이터를 미리 로드합니다.
    """
    # print("[Vision] 시나리오에서 과속방지턱 GT 객체를 스캔합니다...")
    target_names = ["typea", "typeb", "typec"]
    speed_bumps_gt = []
    try:
        instance_count = project.ThreeDModelInstancesCount
        for i in range(instance_count):
            instance = project.ThreeDModelInstance(i)
            instance_name_lower = instance.Name.lower()
            if any(instance_name_lower.startswith(target) for target in target_names):
                height, depth = 0.0, 0.0
                try:
                    if instance.BoundingBoxesCount > 0:
                        bbox = instance.BoundingBox(0)
                        height = vector_magnitude(bbox.yAxis) * 2
                        depth = vector_magnitude(bbox.zAxis) * 2
                except Exception as e:
                    # print(f"  -> 경고: {instance.Name} BoundingBox 읽기 실패: {e}")
                    pass
                
                bump_type = "UNKNOWN"
                if "typea" in instance_name_lower: bump_type = "A"
                elif "typeb" in instance_name_lower: bump_type = "B"
                elif "typec" in instance_name_lower: bump_type = "C"

                speed_bumps_gt.append({
                    "id": instance.ID, "name": instance.Name, "type": bump_type,
                    "position": instance.Position, "height_m": height, "depth_m": depth
                })
        # print(f"[Vision] 스캔 완료. 총 {len(speed_bumps_gt)}개의 GT 객체 정보를 불러왔습니다.")
        return speed_bumps_gt
    except Exception as e:
        # print(f"\n[Vision][오류] 3D 모델 스캔 중 오류 발생: {e}")
        return []

def get_gt_depth(confirmed_type, speed_bumps_gt, car_position):
    """
    감지된 타입과 현재 차량 위치를 기반으로 가장 적합한 GT 객체의 Depth 값을 반환합니다.
    """
    if not speed_bumps_gt:
        if 'a' in confirmed_type.lower(): return 3.6
        if 'b' in confirmed_type.lower(): return 1.8
        return 3.0

    relevant_bumps = [b for b in speed_bumps_gt if b['type'] == confirmed_type]
    if not relevant_bumps:
        if 'a' in confirmed_type.lower(): return 3.6
        if 'b' in confirmed_type.lower(): return 1.8
        return 3.0

    closest_bump = min(relevant_bumps, key=lambda b: Distance(car_position, b['position']))
    return closest_bump['depth_m']

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
    pythoncom.CoInitialize()
    winRoadProxy, my_car = None, None
    try:
        winRoadProxy = UCwinRoadComProxy()
        driver = winRoadProxy.SimulationCore.TrafficSimulation.Driver
        project = winRoadProxy.Project
        speed_bumps_gt_data = find_and_scan_speed_bumps_gt(project)
        t0 = time.time()
        while my_car is None and time.time() - t0 < 15.0:
            my_car = driver.CurrentCar
            time.sleep(0.2)
        if my_car is None: raise RuntimeError("[Vision] 내 차량(CurrentCar)을 찾을 수 없습니다.")
    except Exception as e:
        print(f"[Vision] UC-win/Road 연결 실패: {e}")
        pythoncom.CoUninitialize()
        return

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

    while True:
        try:
            if not my_car:
                my_car = winRoadProxy.SimulationCore.TrafficSimulation.Driver.CurrentCar
                time.sleep(0.5)
                continue
            current_car_pos = my_car.Position
        except Exception:
            my_car = None
            time.sleep(0.5)
            continue

        fwd_dist = forward_vehicle_distance.value
        is_v2v_mode = (fwd_dist <= 30.0)

        if is_v2v_mode:
            try:
                v2v_data = v2v_to_vision_queue.get_nowait()
                vehicle_name = v2v_data.get('vehicle_name', 'Vehicle')
                distance_m = v2v_data.get('distance_m', 0.0)
                depth_m = v2v_data.get('width_m', 0.0)

                log_msg = f"[{v2v_data.get('source', 'V2V')}]{vehicle_name} | Dt:{distance_m:.1f}m | Dp:{depth_m:.2f}m"
                print_at('INFO_SOURCE', log_msg)

                data_packet = {
                    'type': v2v_data.get('type'), 'height_m': v2v_data.get('height_m'),
                    'distance_m': distance_m, 'depth_m': depth_m,
                    'source': v2v_data.get('source', 'V2V')
                }
                vision_to_control_queue.put_nowait(data_packet)

            except queue.Empty:
                log_msg = f"[V2V]전방차량:{fwd_dist:.1f}m"
                print_at('INFO_SOURCE', log_msg)
                
                data_packet = {
                    'type': 'None', 'height_m': 0.0,
                    'distance_m': 0.0, 'depth_m': 0.0, 'source': 'V2V_Standby'
                }
                try:
                    vision_to_control_queue.put_nowait(data_packet)
                except queue.Full:
                    pass

        else:
            regular_frame = capture_window_by_title(REGULAR_WINDOW_TITLE)
            height_frame = capture_window_by_title(HEIGHT_WINDOW_TITLE)
            if regular_frame is None or height_frame is None: time.sleep(1); continue

            _, road_mask_pattern = get_road_roi(regular_frame, ROI_SETTINGS_PATTERN)
            _, road_mask_height = get_road_roi(height_frame, ROI_SETTINGS_HEIGHT)
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
            confirmed_type = "None"
            if len(detection_history) == CONFIRM_FRAME_COUNT and len(set(detection_history)) == 1:
                confirmed_type = detection_history[0]
            if current_type_str == "None": detection_history.clear()
            
            gt_depth_m = 0.0
            if confirmed_type != "None":
                gt_depth_m = get_gt_depth(confirmed_type, speed_bumps_gt_data, current_car_pos)

            log_msg = f"[Vision] H:{current_h:.2f}m|Dt:{current_d:.1f}m|Dp:{gt_depth_m:.2f}m|T:{confirmed_type}|P:{current_p}"
            print_at('INFO_SOURCE', log_msg)

            data_packet = {
                'type': confirmed_type, 'height_m': current_h,
                'distance_m': current_d, 'depth_m': gt_depth_m,
                'source': 'Vision'
            }
            try: vision_to_control_queue.put_nowait(data_packet)
            except queue.Full: pass

        time.sleep(0.1)

    pythoncom.CoUninitialize()