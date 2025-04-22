import os
from dotenv import load_dotenv
import json
import base64
import threading
import pyaudio
from common import processing, player, stt_status, mic_status, chat_ids, question_text, delta_text
import websocket
import memory
from pydub import AudioSegment
import io
import time
from vts import send_host_key

load_dotenv() # 加载 .env 文件
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # OpenAI API 密钥

# WebSocket 配置
OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17"
HEADERS = [
    "Authorization: Bearer " + OPENAI_API_KEY,
    "OpenAI-Beta: realtime=v1"
]
ws_global = None # 全局 WebSocket 连接
  
CHANNELS = 1  
RATE = 24000
CHUNK = 1024 

response_create = {
    "type": "response.create",
    "response": {
        "modalities": [],
        "instructions": "",
        "conversation": None,
        "input": []
    }
}

def on_message(ws, message):
    """处理 WebSocket 收到的消息"""
    data = json.loads(message)  
    event_type = data.get("type") # 获取消息类型
   
    if event_type == "input_audio_buffer.speech_started":
        stt_status(True) 

    elif event_type == "input_audio_buffer.speech_stopped":
        mic_status(False)

    elif event_type == "conversation.item.input_audio_transcription.completed": 
        transcript = data.get("transcript", "")
        if transcript and transcript.strip(): # 确保内容不为空
            memory.save_chat_record("Niama78", "stt_message", transcript) 

        stt_status(False)

    elif event_type == "response.audio.delta":
        delta = base64.b64decode(data.get("delta", ""))
        audio = AudioSegment.from_raw(io.BytesIO(delta), sample_width=2, frame_rate=RATE, channels=CHANNELS) # 解析音频数据

        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav") # 保存为 WAV 格式
        audio_bytes = wav_io.getvalue()

        player.add_audio(audio_bytes) 
        
    elif event_type == "response.audio_transcript.delta":
        delta = data.get("delta", "")  
        delta_text(delta) # 更新实时流内容
        
    elif event_type == "response.audio_transcript.done":
        transcript = data.get("transcript", "")
        response_create["response"]["input"].append({
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": transcript}]
        }) # 添加回复的内容

        memory.update_chat_response(chat_ids(), transcript) 
        chat_ws("emotion_create") # 对话情绪检测

    elif event_type == "response.function_call_arguments.done": 
        arguments = data.get("arguments", "")
        arguments = json.loads(arguments) 
        send_host_key(arguments["emotion"]) # 触发动画
        
        response_create["response"]["input"].clear() # 清空聊天记录
        processing(False)
        mic_status(True) 
        
def on_open(ws):
    """WebSocket 打开时触发"""
    try:
        session_update = {
            "type": "session.update",
            "session": {
                "voice": "coral",
                "input_audio_transcription": {
                    "model": "whisper-1",
                    "language": "zh"
                },
                "turn_detection": {
                    "type": "server_vad", 
                    "create_response": False,
                    "silence_duration_ms": 100
                },
                "tools": [{
                    "type": "function",
                    "name": "analyze_conversation",
                    "description": "分析对话内容，并从中识别出具有代表性的情绪和对应的一句话",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "emotion": {
                                "type": "string",
                                "description": "识别出的情绪",
                                "enum": ["嘟嘴", "星星眼", "爱心眼", "脸红", "脸黑", "无"]
                            },
                            "text": {
                                "type": "string",
                                "description": "与识别出的情绪对应的一句话"
                            }
                        },
                        "required": ["emotion", "text"]
                    }
                }],
            }
        } # 初始化配置
        ws_global.send(json.dumps(session_update)) 
        threading.Thread(target=audio_stream, daemon=True).start()
    except Exception as e:
        print(f"OpenAI WebSocket 初始化配置错误: {e}")

def connect_ws():
    """建立 WebSocket 连接""" 
    global ws_global
    try:
        ws_global = websocket.WebSocketApp(
            OPENAI_WS_URL,
            header=HEADERS,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
        )
        threading.Thread(target=ws_global.run_forever, daemon=True).start()
    except Exception as e:
        print(f"OpenAI WebSocket 连接失败: {e}")

def on_close(ws, close_status_code, close_msg):
    """WebSocket 断开时触发"""
    print(f"OpenAI WebSocket 关闭信息: {close_status_code}, {close_msg}")
    connect_ws() # 重新连接

def on_error(ws, error):
    """WebSocket 错误时触发"""
    print(f"OpenAI WebSocket 错误: {error}")

def send_audio_data(pcm16_audio):
    """发送 Base64 编码的音频数据到 WebSocket 服务器"""
    try:
        base64_audio = base64.b64encode(pcm16_audio).decode()
        data = {
            "type": "input_audio_buffer.append",
            "audio": base64_audio
        }
        ws_global.send(json.dumps(data))
    except Exception as e:
        print(f"发送音频数据到 OpenAI WebSocket 失败: {e}")

def audio_stream():
    """监听麦克风的音频并发送到 WebSocket"""
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE,
                        input=True, input_device_index=audio.get_default_input_device_info()['index'], frames_per_buffer=CHUNK)
    while True:
        if mic_status() and not player.is_playing: # 麦克风启用和无音频播放
            pcm_data = stream.read(CHUNK, exception_on_overflow=False)
            send_audio_data(pcm_data)
        time.sleep(0.01)

def construct_message():
    """访问数据库并构造聊天信息"""
    record, id = memory.get_records()

    if record: # 如果有待处理记录
        with open("roleplay.txt") as f:
            roleplay = f.read()

        response_create["response"]["input"].append({
            "type": "message",
            "role": "system",
            "content": [{"type": "input_text", "text": roleplay}]
        }) # 添加角色设定

        for rec in record:
            response_create["response"]["input"].append({
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": f"{rec["user_id"]}: {rec["question"]}"}]
            })

            if rec.get("answered", False):
                response_create["response"]["input"].append({
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": rec["response"]}]
                })
        
        chat_ids(id)
        chat_ws("chat_create") # 根据对话内容生成回复
        processing(True) 

def chat_ws(event_type):
    """把构造好的信息发送到 WebSocket"""
    try:
        if event_type == "chat_create":
            response_create["response"]["modalities"] = ["audio", "text"]
            response_create["response"]["instructions"] = "根据上下文推理生成精简回复。"
            input = response_create["response"]["input"]
            for i in input:
                if i["role"] == "user":
                    question_text(i["content"][0]["text"]) # 更新用户提问
                    break 
        else:
            response_create["response"]["modalities"] = ["text"]
            response_create["response"]["input"].append({
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "根据以上对话内容，进行情绪识别。"}]
            })

        ws_global.send(json.dumps(response_create))
    except Exception as e:
        print(f"发送信息到 OpenAI WebSocket 失败: {e}")

connect_ws()