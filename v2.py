import requests
import time
import json

# ----------------配置區域----------------
SESSDATA = "xxx" #sessdata和csrf請f12自己去控制台找
CSRF = "xxx"
ROOM_ID = 114514                # 直播間id
OLLAMA_API_URL = "http://localhost:11434/api/generate"  # Ollama DeepSeek API 地址
MODEL_NAME = "deepseek-r1:8b"       # 使用的Ollama DeepSeek Model
MAX_DANMAKU_LENGTH = 20            # 回覆彈幕最大字數
MY_USER_ID = 1297061623            # 替換自己的Bilibili 用戶ID


# ----------------發送彈幕----------------
def send_danmaku(content):
    """發送彈幕到 B站"""
    url = "https://api.live.bilibili.com/msg/send"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://live.bilibili.com/{ROOM_ID}",
        "Origin": "https://live.bilibili.com",
        "Cookie": f"SESSDATA={SESSDATA}; bili_jct={CSRF};"
    }
    data = {
        "color": 16777215,
        "fontsize": 25,
        "mode": 1,
        "msg": content,
        "rnd": int(time.time()),
        "roomid": ROOM_ID,
        "bubble": 0,
        "csrf": CSRF,
        "csrf_token": CSRF
    }
    try:
        response = requests.post(url, headers=headers, data=data, timeout=5)
        res_json = response.json()
        if response.status_code == 200 and res_json.get("code") == 0:
            print(f"[發送彈幕成功] {content}")
            return True
        else:
            print(f"[發送彈幕失敗] {res_json}")
            return False
    except Exception as e:
        print("發送彈幕異常:", e)
        return False


# ----------------爬取彈幕函數----------------
def crawl_danmaku():
    """
    爬取當前彈幕，並返回一個列表，每個元素為 (text, uid)。
    注意：返回的數據中需包含 uid 欄位。
    """
    url = f"https://api.live.bilibili.com/xlive/web-room/v1/dM/gethistory?roomid={ROOM_ID}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://live.bilibili.com/{ROOM_ID}",
        "Cookie": f"SESSDATA={SESSDATA}; bili_jct={CSRF};"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        if data.get("code") == 0:
            room = data.get("data", {}).get("room", [])
            print(f"獲取到 {len(room)} 條彈幕")
            return [(dm["text"], dm["uid"]) for dm in room if isinstance(dm, dict) and "text" in dm]
        else:
            print(f"爬取彈幕失敗，錯誤訊息：{data}")
    except Exception as e:
        print("爬取彈幕異常:", e)
    return []


# ----------------從 DeepSeek 結果擷取 20 字以內的句子----------------
def extract_short_sentence(text):
    """
    從 DeepSeek 生成的完整回覆中提取一個不超過20字的完整句子，
    優先尋找包含標點的句子，否則直接擷取前20字。
    """
    sentences = text.replace("！", "！|").replace("？", "？|").replace("。", "。|").split("|")
    for sentence in sentences:
        trimmed = sentence.strip()
        if 0 < len(trimmed) <= MAX_DANMAKU_LENGTH:
            return trimmed
    return text[:MAX_DANMAKU_LENGTH]


# ----------------DeepSeek 處理彈幕函數----------------
def process_danmaku_with_deepseek(danmaku_text):
    """
    使用 Ollama DeepSeek API 處理單條彈幕內容，
    生成一個與彈幕主題高度相關且準確的回覆，要求回覆不超過20個漢字。
    為了提高準確性，降低了 temperature 並在提示中明確要求：
      - 回覆必須與所給彈幕內容高度相關
      - 回覆必須準確反映彈幕主題
      - 回覆必須簡潔，且不超過20個漢字
    """
    prompt = (
        f"請仔細閱讀以下彈幕內容：\n{danmaku_text}\n"
        f"請生成一個與彈幕主題高度相關、準確且簡潔的回覆，回覆內容必須緊扣彈幕核心，"
        f"且不超過{MAX_DANMAKU_LENGTH}個漢字。"
    )
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "max_tokens": 1000,
        "temperature": 0.3,
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=1, stream=True)
        full_response = ""
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    full_response += data.get("response", "")
                    if data.get("done", False):
                        break
                except json.JSONDecodeError as e:
                    print("JSON解析錯誤:", e)
                    continue
        # 擷取不超過20字的回覆，並在末尾追加 "[AI]"
        short_reply = extract_short_sentence(full_response.strip())
        short_reply = short_reply + "[AI]"
        print(f"Ollama DeepSeek生成的回覆（截斷後）：{short_reply}")
        return short_reply
    except Exception as e:
        print("DeepSeek處理異常:", e)
        return ""


# ----------------主流程----------------
def main():
    print("正在測試憑證……")
    send_danmaku("測試彈幕，若看到請忽略。")
    time.sleep(2)
    is_paused = False

    while True:
        messages = crawl_danmaku()
        if messages:
            for text, uid in messages:
                if text.strip().endswith("[AI]"):
                    print(f"跳過已回覆的彈幕：{text}")
                    continue
            other_msgs = [text for text, uid in messages if uid != MY_USER_ID and not text.strip().endswith("[AI]")]
            if other_msgs:
                current_msg = other_msgs[-1]
                print(f"處理彈幕：{current_msg}")
                if not is_paused:
                    reply = process_danmaku_with_deepseek(current_msg)
                    if reply:
                        send_danmaku(reply)
            time.sleep(6)

if __name__ == "__main__":
    main()
