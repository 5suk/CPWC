# logger.py
import os
import sys
import datetime

if sys.platform == "win32":
    os.system("")

# --- [최종 수정] 터미널 로그 라인 재구성 ---
LINE_KEYS = {
    'INFO_SOURCE': 1,        # 감지 정보 (Vision/V2V)
    'CONTROL_RECV': 2,       # 수신 정보 (Control)
    'CONTROL_PLAN': 3,       # 제어 계획 (Control)
    'CONTROL_STATE': 4,      # 제어 상태 (Control)
    'EVALUATE_RESULT': 5,    # 평가 결과 (Evaluate)
    'EVALUATE_ACCURACY': 6,  # 평가 정확도 (Evaluate)
    'CONTROL_CORRECTION': 7, # 보정 적용 (Control)
    # 8번 라인은 공백으로 사용
    'DEBUG_DISTANCE': 9      # 실시간 거리 추적 (Control)
}
# ----------------------------------------

CURSOR_SAVE = "\033[s"
CURSOR_RESTORE = "\033[u"
CLEAR_LINE = "\033[K"

def setup_logging_area():
    """터미널을 지우고 로그를 출력할 공간을 확보합니다."""
    os.system('cls' if os.name == 'nt' else 'clear')
    sys.stdout.write("\n" * (len(LINE_KEYS) + 2))
    sys.stdout.flush()

def print_at(line_key, message):
    """지정된 키의 라인에 메시지를 출력합니다."""
    line = LINE_KEYS.get(line_key.upper())
    if line is None:
        return

    sys.stdout.write(CURSOR_SAVE)
    sys.stdout.write(f"\033[{line};0H")
    sys.stdout.write(CLEAR_LINE)
    sys.stdout.write(message)
    sys.stdout.write(CURSOR_RESTORE)
    sys.stdout.flush()

# --- [최종 수정] log.txt 파일 저장 형식 변경 ---
def log_sequence_to_file(log_data):
    """
    한 시퀀스의 로그 데이터를 최종 형식에 맞춰 log.txt 파일에 추가합니다.
    """
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write("="*80 + "\n")
            f.write(f"시퀀스 기록 시간: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-"*80 + "\n")
            f.write(f"[DETECT]: {log_data.get('DETECT', '')}\n")
            f.write(f"[PLAN]: {log_data.get('PLAN', '')}\n")
            f.write(f"[RESULT]: {log_data.get('RESULT', '')}\n")
            f.write(f"[EVAL_ACCURACY]: {log_data.get('CORRECTION', '')}\n")
            f.write(f"[COLLISION]: {log_data.get('COLLISION', '')}\n")
            f.write("="*80 + "\n\n")
    except Exception as e:
        # 파일 접근 오류 발생 시 터미널에만 메시지 표시
        pass
# -------------------------------------------