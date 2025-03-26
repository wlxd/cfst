import os
import requests
import json
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

def send_telegram_message(worker_url, bot_token, chat_id, message, secret_token=None):
    """
    通过 Cloudflare Worker 发送 Telegram 消息
    """
    headers = {'Content-Type': 'application/json'}
    payload = {
        'bot_token': bot_token,
        'chat_id': chat_id,
        'message': message
    }
    
    if secret_token:
        payload['secret_token'] = secret_token  # 确保键名与 Worker 代码中的参数名一致

    try:
        response = requests.post(
            worker_url,
            data=json.dumps(payload),
            headers=headers
        )
        
        if response.status_code == 200:
            return {"status": "success", "response": response.text}
        else:
            return {
                "status": "error",
                "code": response.status_code,
                "message": response.text
            }
            
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # 从环境变量读取配置
    WORKER_URL = os.getenv("CF_WORKER_URL")
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    SECRET_TOKEN = os.getenv("SECRET_TOKEN")  # 可选
    
    # 调用时使用正确的参数名
    result = send_telegram_message(
        worker_url=WORKER_URL,
        bot_token=BOT_TOKEN,
        chat_id=CHAT_ID,
        message="Hello from Python!",
        secret_token=SECRET_TOKEN  # 确保此处参数名与函数定义一致
    )
    
    print(result)
