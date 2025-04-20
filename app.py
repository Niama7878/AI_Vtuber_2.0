import os
import time
import json
import sqlite3
import threading
from flask import Flask, render_template, jsonify, Response
import common  
import logging

app = Flask(__name__)

log = logging.getLogger('werkzeug') 
log.setLevel(logging.ERROR) 

DATABASE = "chat_memory.db" # 数据库文件路径

def get_db_mtime():
    """获取数据库文件的最后修改时间"""
    try:
        return os.path.getmtime(DATABASE)
    except OSError:
        return 0 # 文件不存在或无法访问

def get_current_status():
    """从 common 模块获取当前状态"""
    return {
        'processing': common.processing(),
        'stt': common.stt_status(),
        'mic': common.mic_status(),
        'player': common.player.is_playing,
        'chat_ids': common.chat_ids()
    }

@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')

@app.route('/status')
def get_status():
    """获取一次性的当前状态"""
    status = get_current_status()
    return jsonify(status)

@app.route('/status-stream')
def status_stream():
    """服务器推送事件 (SSE) 的接口，监控状态和数据库变化并通知前端"""
    def event_stream():
        local_last_status = None
        local_last_mtime = get_db_mtime()
        local_last_question = common.question_text()

        try:
            while True:
                current_status = get_current_status()
                current_mtime = get_db_mtime()
                current_question = common.question_text()
                current_delta = common.delta_text()

                status_changed = (current_status != local_last_status)
                db_changed = (current_mtime != local_last_mtime and current_mtime != 0)
                question_changed = (current_question != local_last_question)
                delta_update_needed = bool(current_delta) # delta 非空就需要更新

                data_to_send = current_status.copy()
                data_to_send['db_updated'] = db_changed
                data_to_send['question_updated'] = question_changed
                data_to_send['delta_chunk'] = current_delta if delta_update_needed else None

                if question_changed:
                    data_to_send['question'] = current_question

                should_send_update = any([status_changed, db_changed, question_changed, delta_update_needed]) # 检测状态

                if should_send_update:
                    yield f"data: {json.dumps(data_to_send)}\n\n" # 确保格式正确

                    # 更新本地状态
                    if status_changed:
                        local_last_status = current_status
                    if db_changed:
                        local_last_mtime = current_mtime
                    if question_changed:
                        local_last_question = current_question

                time.sleep(0.05)
        except Exception as e:
            print(f"SSE 流发生错误: {e}")

    resp = Response(event_stream(), mimetype='text/event-stream')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp

@app.route('/records')
def get_records():
    """获取聊天记录"""
    records = []
    if os.path.exists(DATABASE):
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_records';") # 检查表是否存在
            if cursor.fetchone():
                cursor.execute(
                    "SELECT id, user_id, event_type, question, response, answered FROM chat_records ORDER BY id DESC"
                )
                rows = cursor.fetchall()
                for row in rows:
                    records.append({
                        "id": row[0],
                        "user_id": row[1],
                        "event_type": row[2],
                        "question": row[3],
                        "response": row[4],
                        "answered": bool(row[5]) # 确保是布尔值
                    })
            conn.close()
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return jsonify({"error": f"数据库读取错误: {e}"}), 500 
        except Exception as e:
            print(f"读取记录时发生未知错误: {e}")
            return jsonify({"error": "读取记录时发生未知错误"}), 500
        
    return jsonify(records)

def run_flask():
    """启动 Flask 服务器"""
    print("Running on http://127.0.0.1:5000")
    app.run(debug=False, threaded=True)

threading.Thread(target=run_flask, daemon=True).start()