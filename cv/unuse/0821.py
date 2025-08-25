import cv2
import numpy as np

# ==============================================================================
# 기능 1: 일반 카메라 이미지에서 패턴 존재 여부 감지
# ==============================================================================
def detect_pattern(image_path):
    """
    일반 카메라 이미지를 입력받아 과속방지턱 패턴 유무를 반환합니다.
    패턴이 있으면 True, 없으면 False를 반환합니다.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"[패턴 감지 오류] {image_path} 파일을 찾을 수 없습니다.")
        return False

    # BEV 변환을 위한 좌표 (이전 단계에서 찾은 값)
    src_points = np.float32([[155, 80], [270, 80], [140, 112], [283, 112]])
    width, height = 400, 100
    dst_points = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
    
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    bev_img = cv2.warpPerspective(img, matrix, (width, height))

    # 패턴의 노란색 부분 감지
    hsv_img = cv2.cvtColor(bev_img, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([20, 80, 80])
    upper_yellow = np.array([35, 255, 255])
    mask = cv2.inRange(hsv_img, lower_yellow, upper_yellow)

    # Morphological 연산으로 흩어진 줄무늬 통합
    kernel = np.ones((5, 15), np.uint8)
    closed_mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(closed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) > 0:
        main_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(main_contour)
        
        # 일정 면적 이상일 경우에만 패턴이 있는 것으로 간주
        if area > 1000:
            return True
            
    return False

# ==============================================================================
# 기능 2: 높이맵 이미지에서 최고 높이 분류
# ==============================================================================
def classify_height(image_path):
    """
    높이맵 이미지를 입력받아 분류된 높이(0.0, 0.1, 0.2)를 반환합니다.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"[높이 분류 오류] {image_path} 파일을 찾을 수 없습니다.")
        return 0.0

    # BEV 변환 (패턴 감지와 동일한 좌표 사용)
    src_points = np.float32([[155, 80], [270, 80], [140, 112], [283, 112]])
    width, height = 400, 100
    dst_points = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
    
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    bev_img = cv2.warpPerspective(img, matrix, (width, height))

    # 파란색 배경 제외
    lower_blue_bg = np.array([100, 0, 0])
    upper_blue_bg = np.array([255, 100, 100])
    bg_mask = cv2.inRange(bev_img, lower_blue_bg, upper_blue_bg)
    bump_mask = cv2.bitwise_not(bg_mask)

    # Hue 기반 높이 분류
    hsv_img = cv2.cvtColor(bev_img, cv2.COLOR_BGR2HSV)
    h_channel, _, v_channel = cv2.split(hsv_img)
    
    pixels_indices = np.nonzero(bump_mask)
    v_values = v_channel[pixels_indices]

    if len(v_values) == 0:
        return 0.0 # 과속방지턱 영역 없음 (평지)

    top_10_percent_threshold = np.percentile(v_values, 90)
    top_v_mask_bool = (v_channel >= top_10_percent_threshold)
    top_v_mask_uint8 = top_v_mask_bool.astype(np.uint8) * 255
    final_mask = cv2.bitwise_and(bump_mask, top_v_mask_uint8)
    
    top_hue_values = h_channel[np.nonzero(final_mask)]
    
    if len(top_hue_values) > 0:
        min_hue = np.min(top_hue_values)
        if min_hue < 15:
            return 0.2
        elif 15 <= min_hue < 40:
            return 0.1
            
    return 0.0

# ==============================================================================
# 메인 로직: 두 기능 통합 및 최종 타입 판정
# ==============================================================================
if __name__ == "__main__":
    
    ## --- 분석할 이미지 파일 지정 ---
    # 여기에 분석하고 싶은 실제 파일 경로를 입력하세요.
    REGULAR_VIEW_IMAGE = '1.png' # 일반 카메라 뷰 이미지
    HEIGHT_MAP_IMAGE = '4.png'   # 높이맵 뷰 이미지
    ## ---------------------------------

    print(f"'{REGULAR_VIEW_IMAGE}' 와 '{HEIGHT_MAP_IMAGE}' 분석 시작...")
    
    # 각 기능 수행
    pattern_present = detect_pattern(REGULAR_VIEW_IMAGE)
    estimated_height = classify_height(HEIGHT_MAP_IMAGE)

    # 결과 조합하여 최종 타입 판정
    final_type = "알 수 없음"
    if estimated_height == 0.2:
        final_type = "B 타입"
    elif estimated_height == 0.1:
        if pattern_present:
            final_type = "A 타입"
        else:
            final_type = "D 타입"
    elif estimated_height == 0.0:
        final_type = "C 타입 (평지)"

    # 최종 결과 출력
    print("\n--- 최종 분석 결과 ---")
    print(f"패턴 존재 여부: {pattern_present}")
    print(f"추정 높이: {estimated_height:.2f} m")
    print(f"==> 최종 판정: {final_type}")