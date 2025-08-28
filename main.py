# main.py
import multiprocessing
import sys
from vision import run_vision_processing
from control import run_control_simulation

if sys.platform == "win32":
    multiprocessing.freeze_support()

def main():
    print("[Main] 프로그램 시작")
    vision_to_control_queue = multiprocessing.Queue(maxsize=1)
    vision_process = multiprocessing.Process(target=run_vision_processing, args=(vision_to_control_queue,))
    control_process = multiprocessing.Process(target=run_control_simulation, args=(vision_to_control_queue,))

    vision_process.start()
    print("[Main] Vision 프로세스 시작됨")
    control_process.start()
    print("[Main] Control 프로세스 시작됨")

    try:
        vision_process.join()
        control_process.join()
    except KeyboardInterrupt:
        print("\n[Main] 사용자에 의해 프로그램 종료 중...")
        if vision_process.is_alive(): vision_process.terminate()
        if control_process.is_alive(): control_process.terminate()
        vision_process.join()
        control_process.join()
        print("[Main] 모든 프로세스 종료 완료.")

if __name__ == '__main__':
    main()