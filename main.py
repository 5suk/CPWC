# main.py
import multiprocessing as mp
import sys
import os

if __name__ == '__main__':
    # Windows에서 multiprocessing을 안전하게 사용하기 위한 설정
    mp.freeze_support()

    print("메인 프로그램을 시작합니다.")
    
    # 모듈 검색 경로에 현재 폴더를 추가 (import 오류 방지)
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from vision import run_vision_processing
    from control import run_control_simulation

    manager = mp.Manager()
    vision_queue = manager.Queue() # 프로세스 간 통신용 큐

    vision_process = mp.Process(target=run_vision_processing, args=(vision_queue,))
    control_process = mp.Process(target=run_control_simulation, args=(vision_queue,))

    print("Vision 및 Control 프로세스를 시작합니다...")
    vision_process.start()
    control_process.start()

    # 두 프로세스가 모두 작업을 마칠 때까지 대기
    vision_process.join()
    control_process.join()

    print("모든 프로세스가 종료되었습니다. 프로그램을 마칩니다.")