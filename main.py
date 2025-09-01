# main.py
import multiprocessing
import sys
from vision import run_vision_processing
from control import run_control_simulation
from V2V import run_v2v_simulation
from evaluate import run_evaluate_node

if sys.platform == "win32":
    multiprocessing.freeze_support()

def main():
    print("[Main] 프로그램 시작")

    # Vision → Control
    vision_to_control_queue = multiprocessing.Queue()
    # Vision → Evaluate
    vision_to_evaluate_queue = multiprocessing.Queue()
    # Control ↔ Evaluate (양방향)
    control_to_evaluate_queue = multiprocessing.Queue()
    evaluate_to_control_queue = multiprocessing.Queue()
    # V2V → Vision (현재 미사용)
    v2v_to_vision_queue = multiprocessing.Queue()

    # Vision
    vision_process = multiprocessing.Process(
        target=run_vision_processing,
        args=(vision_to_control_queue, vision_to_evaluate_queue)
    )
    # Control
    control_process = multiprocessing.Process(
        target=run_control_simulation,
        args=(vision_to_control_queue, control_to_evaluate_queue, evaluate_to_control_queue)
    )
    # V2V
    v2v_process = multiprocessing.Process(
        target=run_v2v_simulation,
        args=(v2v_to_vision_queue,)
    )
    # Evaluate
    evaluate_process = multiprocessing.Process(
        target=run_evaluate_node,
        args=(vision_to_evaluate_queue, control_to_evaluate_queue, evaluate_to_control_queue)
    )

    vision_process.start(); print("[Main] Vision 프로세스 시작됨")
    control_process.start(); print("[Main] Control 프로세스 시작됨")
    v2v_process.start(); print("[Main] V2V 프로세스 시작됨")
    evaluate_process.start(); print("[Main] Evaluate 프로세스 시작됨")

    try:
        vision_process.join()
        control_process.join()
        v2v_process.join()
        evaluate_process.join()
    except KeyboardInterrupt:
        print("\n[Main] 사용자 종료 요청. 모든 프로세스 종료 중...")
        for p in [vision_process, control_process, v2v_process, evaluate_process]:
            if p.is_alive():
                p.terminate()
        for p in [vision_process, control_process, v2v_process, evaluate_process]:
            p.join()
        print("[Main] 종료 완료.")

if __name__ == '__main__':
    main()
