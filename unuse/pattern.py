import cv2
import numpy as np

img = cv2.imread('1.png')
if img is None:
    print("이미지를 찾을 수 없습니다. 파일 경로를 확인하세요.")
else:
    src_points = np.float32([[155, 80], [270, 80], [140, 112], [283, 112]])
    width, height = 400, 100
    dst_points = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    bev_img = cv2.warpPerspective(img, matrix, (width, height))

    # BGR 'to' HSV -> 2가 추가되었습니다.
    hsv_img = cv2.cvtColor(bev_img, cv2.COLOR_BGR2HSV) 

    lower_yellow = np.array([20, 80, 80])
    upper_yellow = np.array([35, 255, 255])
    mask = cv2.inRange(hsv_img, lower_yellow, upper_yellow)

    kernel = np.ones((5, 15), np.uint8)
    closed_mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    cv2.polylines(img, [np.int32(src_points)], isClosed=True, color=(0, 255, 0), thickness=2)

    found = False
    if len(contours) > 0:
        main_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(main_contour)
        
        if area > 1000:
            print(f"통합된 과속방지턱 패턴을 찾았습니다! (총 면적: {area:.0f})")
            x, y, w, h = cv2.boundingRect(main_contour)
            cv2.rectangle(bev_img, (x, y), (x + w, y + h), (0, 0, 255), 2)
            found = True

    if not found:
        print("과속방지턱 패턴을 찾지 못했습니다.")

    cv2.imshow('Original Image with ROI', img)
    cv2.imshow('Bird\'s-Eye View (BEV)', bev_img)
    cv2.imshow('Original Yellow Mask', mask)
    cv2.imshow('Closed Mask', closed_mask)

    cv2.waitKey(0)
    cv2.destroyAllWindows()