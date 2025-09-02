# logger.py
import os
import sys

if sys.platform == "win32":
    os.system("")

# 로그 라인 순서 (요청사항 반영)
LINE_KEYS = {
    'INFO_SOURCE': 1,
    'CONTROL_RECV': 2,
    'CONTROL_PLAN': 3,
    'CONTROL_STATE': 4,
    'EVALUATE_RESULT': 5,
    'EVALUATE_ACCURACY': 6,
    'CONTROL_CORRECTION': 7,
}

# ANSI 이스케이프 코드
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
    sys.stdout.write(f"\033[{line};0H") # (line)행, 0열로 커서 이동
    sys.stdout.write(CLEAR_LINE)
    sys.stdout.write(message)
    sys.stdout.write(CURSOR_RESTORE)
    sys.stdout.flush()