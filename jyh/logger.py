# logger.py
import os
import sys

if sys.platform == "win32":
    os.system("")

# 로그 라인 순서 (9줄로 확장)
PROCESS_LINES = {
    'DETECTION': 1,
    'CONTROL_RECV': 2,
    'CONTROL_PLAN': 3,
    'CONTROL_STATE': 4,
    'EVALUATE_DETAIL': 5,
    'EVALUATION': 6,
    'CORRECTION': 7,
    'FORWARD_VEHICLE': 8,
    'EVALUATE_DISTANCE': 9 # (최하단) Evaluate 모듈의 실시간 추적 거리
}

# ANSI 이스케이프 코드
CURSOR_SAVE = "\033[s"
CURSOR_RESTORE = "\033[u"
CLEAR_LINE = "\033[K"

def get_line(process_name):
    """프로세스 이름에 맞는 라인 번호를 반환"""
    return PROCESS_LINES.get(process_name.upper(), 10)

def print_at(line_key, message):
    """지정된 키의 라인에 메시지를 출력합니다."""
    line = get_line(line_key)
    
    sys.stdout.write(CURSOR_SAVE)
    sys.stdout.write(f"\033[{line};0H")
    sys.stdout.write(CLEAR_LINE)
    sys.stdout.write(message)
    sys.stdout.write(CURSOR_RESTORE)
    sys.stdout.flush()