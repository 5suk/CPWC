# main.py
import multiprocessing
import sys
from vision import run_vision_processing
from control import run_control_simulation

# 윈도우에서 multiprocessing 사용 시 필수 설정
if sys.platform == "win32":
    multiprocessing.freeze_support()

def main():
    """
    메인 프로세스: Vision 프로세스와 Control 프로세스를 생성하고 관리합니다.
    - Vision: 과속방지턱 정보를 인식하여 Queue에 넣습니다.
    - Control: Queue에서 정보를 받아 차량을 제어합니다.
    """
    print("[Main] 프로그램 시작")

    # Vision과 Control 프로세스 간 통신을 위한 큐 생성
    vision_to_control_queue = multiprocessing.Queue()

    # 각 프로세스 생성
    # target: 각 프로세스가 실행할 함수
    # args: 함수에 전달할 인자 (큐 객체)
    vision_process = multiprocessing.Process(target=run_vision_processing, args=(vision_to_control_queue,))
    control_process = multiprocessing.Process(target=run_control_simulation, args=(vision_to_control_queue,))

    # 프로세스 시작
    vision_process.start()
    print("[Main] Vision 프로세스 시작됨")

    control_process.start()
    print("[Main] Control 프로세스 시작됨")

    try:
        # 메인 프로세스는 자식 프로세스들이 끝날 때까지 기다림
        vision_process.join()
        control_process.join()
    except KeyboardInterrupt:
        print("\n[Main] 사용자에 의해 프로그램 종료 중...")
        # 자식 프로세스들에게 종료 신호 전달
        if vision_process.is_alive():
            vision_process.terminate()
        if control_process.is_alive():
            control_process.terminate()
        
        vision_process.join()
        control_process.join()
        print("[Main] 모든 프로세스 종료 완료.")

if __name__ == '__main__':
    main()