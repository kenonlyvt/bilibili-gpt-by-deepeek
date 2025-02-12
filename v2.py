import requests
import time
import json

# ----------------配置区域----------------
SESSDATA = "448f0c80%2C1754658832%2C999eb%2A21CjAKOsxNQOdCa_ap9MvEcKKUL7RbvIXSR0tIZf4Eup8FQmt5LkxcBTgDuOybg9xHAJESVkloB01NTW9iMVZqVnN3N05TUzRJZ0pzYXdJdURrbV9ncUo1T2dGLU1WWlJqRHI1LUU2b28yWFRHdkMzbXpJSmVJMG9XZFFodzgxRnp5eldjaW5nIIEC"
CSRF = "2a9ea6a7093c123bdf9474ac7fa1c9f5"
ROOM_ID = 663547                # 你的直播间 ID
OLLAMA_API_URL = "http://localhost:11434/api/generate"  # 本地 Ollama DeepSeek API 地址
MODEL_NAME = "deepseek-r1:8b"       # 使用的 Ollama DeepSeek 模型名称
MAX_DANMAKU_LENGTH = 20            # 回复弹幕最大字数
MY_USER_ID = 1297061623            # 替换为你自己的 Bilibili 用户ID


# ----------------发送弹幕函数----------------
def send_danmaku(content):
    """发送弹幕到 B站"""
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
            print(f"[发送成功] {content}")
            return True
        else:
            print(f"[发送失败] {res_json}")
            return False
    except Exception as e:
        print("发送弹幕异常:", e)
        return False


# ----------------爬取弹幕函数----------------
def crawl_danmaku():
    """
    爬取当前弹幕，并返回一个列表，每个元素为 (text, uid)。
    注意：返回的数据中需包含 uid 字段。
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
            print(f"获取到 {len(room)} 条弹幕")
            return [(dm["text"], dm["uid"]) for dm in room if isinstance(dm, dict) and "text" in dm]
        else:
            print(f"爬取弹幕失败，错误信息：{data}")
    except Exception as e:
        print("爬取弹幕异常:", e)
    return []


# ----------------从 DeepSeek 结果截取 20 字以内的句子----------------
def extract_short_sentence(text):
    """
    从 DeepSeek 生成的完整回复中提取一个不超过20字的完整句子，
    优先寻找包含标点的句子，否则直接截取前20字。
    """
    sentences = text.replace("！", "！|").replace("？", "？|").replace("。", "。|").split("|")
    for sentence in sentences:
        trimmed = sentence.strip()
        if 0 < len(trimmed) <= MAX_DANMAKU_LENGTH:
            return trimmed
    return text[:MAX_DANMAKU_LENGTH]


# ----------------DeepSeek 处理弹幕函数----------------
def process_danmaku_with_deepseek(danmaku_text):
    """
    使用 Ollama DeepSeek API 处理单条弹幕内容，
    生成一个与弹幕主题高度相关且准确的回复，要求回复不超过20个汉字。
    为了提高准确性，降低了 temperature 并在提示中明确要求：
      - 回复必须与所给弹幕内容高度相关
      - 回复必须准确反映弹幕主题
      - 回复必须简洁，且不超过20个汉字
    """
    prompt = (
        f"请仔细阅读以下弹幕内容：\n{danmaku_text}\n"
        f"请生成一个与弹幕主题高度相关、准确且简洁的回复，回复内容必须紧扣弹幕核心，"
        f"且不超过{MAX_DANMAKU_LENGTH}个汉字。"
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
                    print("JSON解析错误:", e)
                    continue
        # 截取不超过20字的回复，并在末尾追加 "[AI]"
        short_reply = extract_short_sentence(full_response.strip())
        short_reply = short_reply + "[AI]"
        print(f"Ollama DeepSeek生成的回复（截断后）：{short_reply}")
        return short_reply
    except Exception as e:
        print("DeepSeek处理异常:", e)
        return ""


# ----------------主流程----------------
def main():
    print("正在测试凭证……")
    send_danmaku("测试弹幕，若看到请忽略。")
    time.sleep(2)
    is_paused = False

    while True:
        # 1. 爬取弹幕
        messages = crawl_danmaku()  # 返回 [(text, uid), ...]
        if messages:
            # 遍历所有弹幕
            for text, uid in messages:
                # 如果弹幕文本最后包含"[AI]"，则认为该弹幕已被回复过，不再处理
                if text.strip().endswith("[AI]"):
                    print(f"跳过已回复的弹幕：{text}")
                    continue
                # 如果是自己发送的弹幕，检查是否为控制指令
                if uid == MY_USER_ID:
                    cmd = text.strip().lower()
                    if cmd == "c":
                        is_paused = True
                        print("检测到自己发送的 'c'，暂停回复。")
                    elif cmd == "v":
                        is_paused = False
                        print("检测到自己发送的 'v'，恢复回复。")
            # 筛选其他用户的弹幕，且不包含"[AI]"结尾的内容
            other_msgs = [text for text, uid in messages if uid != MY_USER_ID and not text.strip().endswith("[AI]")]
            if other_msgs:
                # 取最新的一条其他用户弹幕
                current_msg = other_msgs[-1]
                print(f"处理弹幕：{current_msg}")
                if not is_paused:
                    reply = process_danmaku_with_deepseek(current_msg)
                    if reply:
                        if send_danmaku(reply):
                            print("回复已发送，刷新处理下一条弹幕。")
                        else:
                            print("回复发送失败。")
                    else:
                        print("未生成有效回复。")
                else:
                    print("暂停状态下，不处理新的弹幕。")
            else:
                print("没有其他用户的弹幕需要处理。")
        else:
            print("未获取到弹幕。")
        time.sleep(6)


if __name__ == "__main__":
    main()
