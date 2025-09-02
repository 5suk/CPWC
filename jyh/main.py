# main.py
import multiprocessing
import sys
import os
from vision import run_vision_processing
from control import run_control_simulation
from V2V import run_v2v_simulation
from evaluate import run_evaluate_node

if sys.platform == "win32":
    multiprocessing.freeze_support()

def main():
    # 프로그램 시작 시 터미널 화면을 지움
    os.system('cls' if os.name == 'nt' else 'clear')

    # 프로세스 간 통신을 위한 Queue 생성
    vision_to_control_queue = multiprocessing.Queue()
    v2v_to_vision_queue = multiprocessing.Queue()
    control_to_eval_queue = multiprocessing.Queue()
    eval_to_control_queue = multiprocessing.Queue()
    
    forward_vehicle_distance = multiprocessing.Value('d', 999.9)

    processes = [
        multiprocessing.Process(target=run_vision_processing, args=(vision_to_control_queue, v2v_to_vision_queue, forward_vehicle_distance)),
        multiprocessing.Process(target=run_control_simulation, args=(vision_to_control_queue, control_to_eval_queue, eval_to_control_queue)),
        multiprocessing.Process(target=run_v2v_simulation, args=(v2v_to_vision_queue, forward_vehicle_distance)),
        multiprocessing.Process(target=run_evaluate_node, args=(control_to_eval_queue, eval_to_control_queue))
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