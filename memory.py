import sqlite3
from rapidfuzz import fuzz
import random

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect("chat_memory.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        event_type TEXT,
                        question TEXT,
                        response TEXT,
                        answered BOOLEAN
                    )''')
    conn.commit()
    conn.close()

def save_chat_record(user_id, event_type, question):
    """保存用户问题"""
    conn = sqlite3.connect("chat_memory.db")
    cursor = conn.cursor()

    cursor.execute('''SELECT user_id, question FROM chat_records 
                      WHERE answered = 0''') 
    records = cursor.fetchall() # 所有未回答问题
    for rec in records:
        if event_type == "stt_message":
            break # stt 直接保存
        if user_id == rec[0]  and fuzz.ratio(question, rec[1]) >= 50:
            conn.close()
            return # 相同用户重复问题

    cursor.execute("SELECT id FROM chat_records ORDER BY id")
    used_ids = [row[0] for row in cursor.fetchall()]
    new_id = 1
    for uid in used_ids:
        if uid != new_id: 
            break # 找到空缺 ID
        new_id += 1

    cursor.execute('''INSERT INTO chat_records (id, user_id, event_type, question, answered)
                      VALUES (?, ?, ?, ?, ?)''', (new_id, user_id, event_type, question, False))
    conn.commit()
    conn.close()

def update_chat_response(record_id_list, response):
    """更新问题回复"""
    conn = sqlite3.connect("chat_memory.db")
    cursor = conn.cursor()

    chosen_id = random.choice(record_id_list)
    cursor.execute("UPDATE chat_records SET response = ?, answered = ? WHERE id = ?", (response, True, chosen_id))

    for record_id in record_id_list: 
        if record_id != chosen_id: # chosen_id 以外
            cursor.execute("DELETE FROM chat_records WHERE id = ?", (record_id,))

    conn.commit()
    conn.close()

def get_records():
    """获取过滤过的纪录"""
    conn = sqlite3.connect("chat_memory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, event_type, question, response, answered FROM chat_records")
    records = cursor.fetchall()
    conn.close()

    if not records:
        return None, None

    formatted_records = [
        {
            "id": rec[0],
            "user_id": rec[1],
            "event_type": rec[2],
            "question": rec[3],
            "response": rec[4],
            "answered": bool(rec[5]),
        }
        for rec in records
    ] # 数据格式

    records_list = []
    id_list = []

    for event_type_priority in ["stt_message", "live_message"]:
        for record in formatted_records:
            if not record.get("answered", False) and record["event_type"] == event_type_priority:
                similar_records = [
                    rec for rec in formatted_records
                    if not rec.get("answered", False)
                    and rec["id"] != record["id"]
                    and rec["event_type"] == record["event_type"]
                    and fuzz.ratio(record.get("question", ""), rec.get("question", "")) >= 50
                ]
                similar_records.append(record) # 加入目前纪录

                for rec in similar_records:
                    id_list.append(rec["id"])

                chosen_record = random.choice(similar_records)
                records_list.append(chosen_record) # 用户提问
                break  

        if records_list:
            break  

    if not records_list:
        return None, None

    similar_answered = [
        rec for rec in formatted_records
        if rec.get("answered", False)
        and rec["event_type"] == records_list[0]["event_type"]
        and fuzz.ratio(records_list[0]["question"], rec.get("question", "")) >= 50
    ] 

    if similar_answered:
        for rec in similar_answered:
            id_list.append(rec["id"])
        records_list.append(random.choice(similar_answered)) # 相似回复（记忆）

    return records_list, id_list

init_db()