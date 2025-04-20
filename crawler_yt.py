import os
import time
import requests
import threading
from dotenv import load_dotenv 
import memory

load_dotenv()  # 加载 .env 文件
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") # YouTube API 密钥

live_chat_id = "" # Youtube 直播视频 ID
next_page_token = None # 下一页令牌

def get_live_chat_id():
    """获取直播聊天频道 ID"""
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?id={live_chat_id}&part=liveStreamingDetails&key={YOUTUBE_API_KEY}"
        response = requests.get(url)
        data = response.json()

        if response.status_code != 200:
            print(f"获取 Youtube 直播聊天频道 ID 失败: {response.status_code} {data}")
        else:
            return data['items'][0]['liveStreamingDetails']['activeLiveChatId']
    except Exception as e:
        print(f"获取 Youtube 直播聊天频道 ID 错误: {e}")

    return None

def get_channel_info(channel_id):
    """获取频道信息"""
    try:
        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&key={YOUTUBE_API_KEY}"
        response = requests.get(url)
        data = response.json()

        if response.status_code != 200:
            print(f"获取 Youtube 频道信息失败: {response.status_code} {data}")
        else:
            return data['items'][0]['snippet']['title']
    except Exception as e:
        print(f"获取 Youtube 频道信息错误: {e}")

    return None
    
def crawl_youtube_messages():
    """爬取 YouTube 直播聊天消息"""
    global next_page_token
    live_chat_id = get_live_chat_id()

    if live_chat_id:
        while True:
            try:
                chat_url = f"https://www.googleapis.com/youtube/v3/liveChat/messages?liveChatId={live_chat_id}&part=snippet&key={YOUTUBE_API_KEY}"
                if next_page_token:
                    chat_url += f"&pageToken={next_page_token}" # 添加分页令牌

                response = requests.get(chat_url)
                data = response.json()

                if response.status_code != 200:
                    print(f"获取 Youtube 直播消息失败: {response.status_code} {data}")
                else:
                    for message in data['items']: 
                        display_message = message['snippet']['displayMessage'] # 获取消息
                        author_channel_id = message['snippet']['authorChannelId'] # 频道 ID
                        display_name = get_channel_info(author_channel_id)  # 获取频道名称
                        memory.save_chat_record(display_name, 'live_message', display_message) # 添加消息记录
   
                    next_page_token = data['nextPageToken'] # 获取下一页令牌
            except Exception as e:
                print(f"获取 YouTube 直播消息错误: {e}")

            time.sleep(1)

threading.Thread(target=crawl_youtube_messages, daemon=True).start() 