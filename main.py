import app
from chat import construct_message
from common import processing, player, stt_status
import time
import subprocess
import signal
#import crawler_bili
#import crawler_yt

word_process = subprocess.Popen(["python", "word.py"]) # 启动子进程

def cleanup():
    """清理进程"""
    word_process.terminate()
    word_process.wait()

# 捕捉退出信号
signal.signal(signal.SIGINT, lambda s, f: (cleanup()))
signal.signal(signal.SIGTERM, lambda s, f: (cleanup()))
time.sleep(2)

while True:
    if word_process.poll() != None: # 子进程结束
        break
    if not processing() and not player.is_playing:
        if not stt_status(): # 无语音转录事件
            construct_message()
    time.sleep(0.01)