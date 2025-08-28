# logger.py
import os
import sys

# Windows에서 ANSI 이스케이프 시퀀스를 활성화
if sys.platform == "win32":
    os.system("")

# 각 프로세스에 할당할 라인 번호
PROCESS_LINES = {
    'VISION': 3,
    'CONTROL': 4,
    'V2V': 5,
    'MAIN': 1 # 메인 프로세스용
}

# ANSI 이스케이프 코드
CURSOR_SAVE = "\033[s"
CURSOR_RESTORE = "\033[u"
CLEAR_LINE = "\033[K"

def get_line(process_name):
    """프로세스 이름에 맞는 라인 번호를 반환"""
    return PROCESS_LINES.get(process_name.upper(), 10) # 모르는 프로세스는 10번 라인에

def print_at(process_name, message):
    """지정된 프로세스의 라인에 메시지를 출력합니다."""
    line = get_line(process_name)
    
    # 커서 위치 저장 -> 지정된 라인으로 이동 -> 해당 라인 내용 삭제 -> 메시지 출력 -> 커서 위치 복원
    sys.stdout.write(CURSOR_SAVE)
    sys.stdout.write(f"\033[{line};0H") # (line)행, 0열로 커서 이동
    sys.stdout.write(CLEAR_LINE)
    sys.stdout.write(f"[{process_name.upper()}] {message}")
    sys.stdout.write(CURSOR_RESTORE)
    sys.stdout.flush()