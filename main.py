# main.py
import multiprocessing
import sys
from vision import run_vision_processing
from control import run_control_simulation
from V2V import run_v2v_simulation

# 윈도우에서 multiprocessing 사용 시 필수 설정
if sys.platform == "win32":
    multiprocessing.freeze_support()

def main():
    """
    메인 프로세스: Vision, Control, V2V 프로세스를 생성하고 관리합니다.
    """
    print("[Main] 프로그램 시작")

    vision_to_control_queue = multiprocessing.Queue()
    v2v_to_vision_queue = multiprocessing.Queue()
    forward_vehicle_distance = multiprocessing.Value('d', 999.9)

    vision_process = multiprocessing.Process(
        target=run_vision_processing, 
        args=(vision_to_control_queue, v2v_to_vision_queue, forward_vehicle_distance)
    )
    control_process = multiprocessing.Process(
        target=run_control_simulation, 
        args=(vision_to_control_queue,)
    )
    v2v_process = multiprocessing.Process(
        target=run_v2v_simulation, 
        args=(v2v_to_vision_queue, forward_vehicle_distance)
    )

    processes = [vision_process, control_process, v2v_process]
    process_names = ["Vision", "Control", "V2V"]

    for process, name in zip(processes, process_names):
        process.start()
        print(f"[Main] {name} 프로세스 시작됨")

    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        print("\n[Main] 사용자에 의해 프로그램 종료 중...")
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
        print("[Main] 모든 프로세스 종료 완료.")

if __name__ == '__main__':
    main()