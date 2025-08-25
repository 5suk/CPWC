import cv2
import numpy as np

def classify_height_by_hue(image_path, true_height):
    """
    이미지의 최소 Hue 값을 기준으로 높이를 '분류'합니다.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"{image_path}를 찾을 수 없습니다.")
        return

    lower_blue_bg = np.array([100, 0, 0])
    upper_blue_bg = np.array([255, 100, 100])
    bg_mask = cv2.inRange(img, lower_blue_bg, upper_blue_bg)
    bump_mask = cv2.bitwise_not(bg_mask)
    
    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h_channel, s_channel, v_channel = cv2.split(hsv_img)

    pixels_indices = np.nonzero(bump_mask)
    
    v_values = v_channel[pixels_indices]
    
    # --- 수정된 부분 시작 ---
    if len(v_values) == 0:
        print(f"{image_path}에서 과속방지턱 영역을 찾지 못했습니다.")
        return
        
    top_10_percent_threshold = np.percentile(v_values, 90)
    
    # boolean 마스크를 생성
    top_v_mask_bool = (v_channel >= top_10_percent_threshold)
    
    # boolean 마스크를 uint8 타입(0 또는 255)으로 변환
    top_v_mask_uint8 = top_v_mask_bool.astype(np.uint8) * 255
    
    # uint8 타입 마스크를 사용하여 bitwise_and 연산 수행
    final_mask = cv2.bitwise_and(bump_mask, top_v_mask_uint8)
    # --- 수정된 부분 끝 ---
    
    top_hue_values = h_channel[np.nonzero(final_mask)]
    
    estimated_height = 0.0
    min_hue = -1 # 초기화
    if len(top_hue_values) > 0:
        min_hue = np.min(top_hue_values)
        
        if min_hue < 15:
            estimated_height = 0.2
        elif 15 <= min_hue < 40:
            estimated_height = 0.1
        
    print(f"--- 분석 결과: {image_path} (실제 높이: {true_height:.2f}m) ---")
    print(f"최상단부 최소 Hue 값: {min_hue:.2f}")
    print(f"분류 기반 추정 높이 : {estimated_height:.2f} m")
    print("-" * 30)


# 'image_132e88.png', 'image_1331ab.png' 파일 이름으로 수정하여 실행하세요.
# classify_height_by_hue('2.png', 0.1) # A 타입
# classify_height_by_hue('3.png', 0.2) # B 타입
classify_height_by_hue('2.png', 0.1)
classify_height_by_hue('3.png', 0.2)