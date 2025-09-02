# main.py
import multiprocessing
import sys
from vision import run_vision_processing
from control import run_control_simulation
from V2V import run_v2v_simulation
from logger import setup_logging_area # 로거 초기화 함수 임포트

if sys.platform == "win32":
    multiprocessing.freeze_support()

def main():
    setup_logging_area() # 메인 함수 시작 시 터미널 정리

    vision_to_control_queue = multiprocessing.Queue()
    v2v_to_vision_queue = multiprocessing.Queue()
    forward_vehicle_distance = multiprocessing.Value('d', 999.9)

    processes = [
        multiprocessing.Process(target=run_vision_processing, args=(vision_to_control_queue, v2v_to_vision_queue, forward_vehicle_distance)),
        multiprocessing.Process(target=run_control_simulation, args=(vision_to_control_queue,)),
        multiprocessing.Process(target=run_v2v_simulation, args=(v2v_to_vision_queue, forward_vehicle_distance))
    ]
    
    for p in processes:
        p.start()

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join()

if __name__ == '__main__':
    main()