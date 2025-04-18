from play import AudioPlayer
import threading
import queue

player = AudioPlayer() # 播放器

is_processing = False # 处理事件状态
stt = False # 语音转录状态
mic = True # 麦克风状态

id_list = [] # 聊天纪录 ID 列表
delta_list= [] # 实时流字串列表 
question = "" # 提问内容
write_queue = queue.Queue() # 备份队列

def processing(status: bool = None):
    """返回或修改处理事件状态"""
    global is_processing
    if isinstance(status, bool):
        is_processing = status
    else:
        return is_processing

def stt_status(status: bool = None):
    """返回或修改语音转录状态"""
    global stt
    if isinstance(status, bool):
        stt = status
    else:
        return stt

def mic_status(status: bool = None):
    """返回或修改麦克风状态"""
    global mic
    if isinstance(status, bool):
        mic = status
    else:
       return mic

def chat_ids(data=None):
    """返回或修改聊天记录 ID 列表"""
    global id_list
    if isinstance(data, list):
        id_list = data
    else:
        return id_list

def question_text(data=None):
    """返回或修改 question 内容"""
    global question
    if isinstance(data, str):
        question = data
    else:
        return question

def delta_text(data=None):
    """返回或添加 delta 字串列表"""
    global delta_list
    if isinstance(data, str):
        delta_list.append(data)
        write_queue.put(data)
    else:
        delta = ''.join(delta_list)
        delta_list.clear()
        return delta

def file_writer():
    """写入备份文件"""
    with open("backup.txt", "a", encoding="utf-8") as f:
        while True:
            try:
                data = write_queue.get(timeout=0.01)
                f.write(data)
                f.flush()
            except queue.Empty:
                continue  

threading.Thread(target=file_writer, daemon=True).start()