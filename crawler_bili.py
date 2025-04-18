import websocket
import struct
import json
import zlib
import threading
import time
import requests
from dotenv import load_dotenv 
import os
import memory

load_dotenv() # 加载 .env 文件
SESSDATA = os.getenv("SESSDATA") # Bilibili 登入 Cookies

ws_global = None # 全局 WebSocket 连接
room_id = "" # Bilibili 直播间 ID

headers = {
    "Cookie": f"SESSDATA={SESSDATA}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5756.197 Safari/537.36"
} # 验证头部信息

payload = {
    "uid": int,
    "roomid": room_id,
    "protover": 2,
    "platform": "web",
    "type": 2,
    "key": str,
} # 验证数据

def get_host():
    """获取直播间端口信息"""
    try:
        url = f"https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo?id={room_id}"
        response = requests.get(url, headers=headers)
        data = response.json()

        if response.status_code != 200:
            print(f"获取 Bilibili 直播间端口信息失败: {response.status_code} {data}")
        else:
            token = data["data"]["token"]
            host_info = data["data"]["host_list"][0]
            ws_url = f"wss://{host_info['host']}:{host_info['wss_port']}/sub"
            return token, ws_url
    except Exception as e:
        print(f"获取 Bilibili 直播间端口信息错误: {e}")
        
    return None

def get_uid():
    """获取验证过的用户 UID"""
    try:
        response = requests.get("https://api.bilibili.com/x/web-interface/nav", headers=headers)
        data = response.json()

        if response.status_code != 200:
            print(f"获取 Bilibili 用户 UID 失败: {response.status_code} {data}")
        else:
            return data["data"]["mid"]
    except Exception as e:
        print(f"获取 Bilibili 用户 UID 错误: {e}")
    
    return None

def decode_message(message_bytes):
    """解码直播间弹幕数据"""
    messages = []
    offset = 0

    while offset + 16 <= len(message_bytes): 
        try:
            header = message_bytes[offset:offset + 16]
            packet_len, header_len, ver, op, seq = struct.unpack(">IHHII", header)

            if packet_len < 16:
                print(f"弹幕数据长度异常: {packet_len}")
                break

            body = message_bytes[offset + header_len : offset + packet_len] # 取出正文部分

            if ver == 2:
                decompressed = zlib.decompress(body) # 解压
                messages += decode_message(decompressed) # 递归解码
            elif ver in (0, 1): # 普通 JSON 消息
                if not body:
                    continue
                try:
                    text = body.decode("utf-8")
                    data = json.loads(text)
                    messages.append(data)
                except json.JSONDecodeError:
                    pass # 非 JSON 格式正常系统包，不处理即可
        except Exception as e:
            print(f"弹幕数据处理错误: {e}")

        offset += packet_len # 处理下一个包

    return messages

def send_heartbeat():
    """定时发送心跳包"""
    while True:
        try:
            ws_global.send(struct.pack('>IHHII', 16, 16, 1, 2, 1))
            time.sleep(30)
        except Exception as e:
            print(f"发送心跳包到 Bilibili WebSocket 失败: {e}")

def on_message(ws, message):
    """处理 WebSocket 收到的消息"""
    for msg in decode_message(message):
        if isinstance(msg, dict):
            cmd = msg.get("cmd", "")

            if cmd == "DANMU_MSG": # 弹幕消息
                info = msg['info']
                user = info[2][1]  
                text = info[1]     
                message =  text

            elif cmd == "SEND_GIFT": # 送礼消息
                data = msg['data']
                user = data['uname']
                gift = data['giftName']
                num = data['num']
                message = f"送出 {num} 个 {gift}"

            if cmd in ["DANMU_MSG", "SEND_GIFT"]:
                memory.save_chat_record(user, 'live_message', message) # 添加消息记录

def on_open(ws):
    """WebSocket 打开触发"""
    data = json.dumps(payload).encode("utf-8")
    packet = struct.pack(">IHHII", 16 + len(data), 16, 1, 7, 1) + data
    ws_global.send(packet)
    threading.Thread(target=send_heartbeat, daemon=True).start()
    
def on_error(ws, error):
    """WebSocket 错误触发"""
    print(f"Bilibili WebSocket 错误: {error}")

def on_close(ws, close_status_code, close_msg):
    """WebSocket 关闭触发"""
    print(f"Bilibili WebSocket 连接关闭: {close_status_code} {close_msg}")
    connect_ws() # 重新连接

def connect_ws():
    """建立 WebSocket 连接"""
    token, ws_url = get_host()
    uid = get_uid()

    if all([token, uid, ws_url]):
        payload['uid'] = uid
        payload['key'] = token
        
        global ws_global
        try:
            ws_global = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            threading.Thread(target=ws_global.run_forever, daemon=True).start()
        except Exception as e:
            print(f"Bilibili WebSocket 连接失败: {e}")

connect_ws()