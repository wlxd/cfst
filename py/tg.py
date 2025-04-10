import os
import re
import requests
import json
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

def clean_ansi_codes(text: str) -> str:
    """清理文本中的ANSI颜色代码"""
    return re.sub(r'\x1B\[[\d;]*[A-Za-z]', '', text)

def escape_markdown(text: str) -> str:
    """转义MarkdownV2特殊字符"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def send_direct_telegram_message(bot_token: str, chat_id: str, message: str) -> dict:
    """直接发送Telegram消息（自动清理ANSI代码）"""
    # 清理ANSI代码并转义Markdown
    cleaned_message = clean_ansi_codes(message)
    escaped_message = escape_markdown(cleaned_message)
    
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(
            api_url,
            json={
                "chat_id": chat_id,
                "text": escaped_message,
                "parse_mode": "MarkdownV2"
            },
            timeout=3
        )
        
        if response.status_code == 200:
            return {"status": "success", "method": "direct", "response": response.json()}
        else:
            return {
                "status": "error",
                "method": "direct",
                "code": response.status_code,
                "message": response.text
            }

    except requests.exceptions.RequestException as e:
        print(f"原始消息内容：{cleaned_message}")
        return {
            "status": "error",
            "method": "direct",
            "message": f"请求失败: {str(e)}"
        }

def send_via_cloudflare_worker(worker_url: str, bot_token: str, chat_id: str, message: str, secret_token: str = None) -> dict:
    """通过Cloudflare Worker代理发送消息（自动清理ANSI代码）"""
    # 清理ANSI代码
    cleaned_message = clean_ansi_codes(message)
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        'bot_token': bot_token,
        'chat_id': chat_id,
        'message': cleaned_message
    }
    
    if secret_token:
        payload['secret_token'] = secret_token

    try:
        response = requests.post(
            worker_url,
            data=json.dumps(payload),
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            return {"status": "success", "method": "worker", "response": response.text}
        else:
            return {
                "status": "error",
                "method": "worker",
                "code": response.status_code,
                "message": response.text
            }
            
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "method": "worker",
            "message": str(e)
        }

def send_message_with_fallback(worker_url: str, bot_token: str, chat_id: str, message: str, secret_token: str = None) -> dict:
    """消息发送主逻辑（带ANSI清理和双通道发送）"""
    # 清理原始消息中的ANSI代码
    cleaned_message = clean_ansi_codes(message)
    
    # 优先尝试直连发送
    direct_result = send_direct_telegram_message(bot_token, chat_id, cleaned_message)
    
    if direct_result.get("status") == "success":
        return direct_result
    
    print(f"直连发送失败，开始尝试通过Worker发送。原因：{direct_result.get('message')}")
    
    # 使用Worker发送备用方案
    worker_result = send_via_cloudflare_worker(
        worker_url=worker_url,
        bot_token=bot_token,
        chat_id=chat_id,
        message=cleaned_message,
        secret_token=secret_token
    )
    
    return worker_result

if __name__ == "__main__":
    # 从环境变量读取配置
    WORKER_URL = os.getenv("CF_WORKER_URL")
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    SECRET_TOKEN = os.getenv("SECRET_TOKEN")
    
    # 发送测试消息（包含ANSI代码）
    test_msg = (
        "[\x1B[31m错误\x1B[0m] 测试ANSI代码清理\n"
        "*正常Markdown内容* \n"
        "原始日志: \x1B[34m2023-01-01 12:00:00\x1B[0m"
    )
    
    result = send_message_with_fallback(
        worker_url=WORKER_URL,
        bot_token=BOT_TOKEN,
        chat_id=CHAT_ID,
        message=test_msg,
        secret_token=SECRET_TOKEN
    )
    
    print("发送结果：")
    print(json.dumps(result, indent=2, ensure_ascii=False))
