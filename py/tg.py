import os
import re
import requests
import json
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def send_direct_telegram_message(bot_token, chat_id, message):
    """直接发送Telegram消息"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    escaped_message = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', message)
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
        
        # 检查响应状态码
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
        print(f"原始消息内容：{message}")
        return {
            "status": "error",
            "method": "direct",
            "message": f"请求失败: {str(e)}"
        }

def send_via_cloudflare_worker(worker_url, bot_token, chat_id, message, secret_token=None):
    """
    通过Cloudflare Worker代理发送Telegram消息
    
    参数：
        worker_url:   Cloudflare Worker的URL
        bot_token:   Telegram机器人的令牌
        chat_id:     目标聊天频道的ID
        message:     要发送的文本消息
        secret_token: 可选的安全令牌（用于Worker验证）
    
    返回：
        dict: 包含状态和响应信息的字典
    """
    headers = {'Content-Type': 'application/json'}
    payload = {
        'bot_token': bot_token,
        'chat_id': chat_id,
        'message': message
    }
    
    if secret_token:
        payload['secret_token'] = secret_token

    try:
        response = requests.post(
            worker_url,
            data=json.dumps(payload),
            headers=headers,
            timeout=5  # 设置5秒超时时间
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

def send_message_with_fallback(worker_url, bot_token, chat_id, message, secret_token=None):
    """
    消息发送主逻辑：优先直连，失败后使用Worker发送
    
    参数：
        worker_url:   Cloudflare Worker的URL
        bot_token:   Telegram机器人的令牌
        chat_id:     目标聊天频道的ID
        message:     要发送的文本消息
        secret_token: 可选的安全令牌
    
    返回：
        dict: 最终发送结果
    """
    # 优先尝试直连发送
    direct_result = send_direct_telegram_message(bot_token, chat_id, message)
    
    # 如果直连发送成功，直接返回结果
    if direct_result.get("status") == "success":
        return direct_result
    
    # 记录直连发送失败信息
    print(f"直连发送失败，开始尝试通过Worker发送。原因：{direct_result.get('message')}")
    
    # 使用Worker发送作为备用方案
    worker_result = send_via_cloudflare_worker(
        worker_url=worker_url,
        bot_token=bot_token,
        chat_id=chat_id,
        message=message,
        secret_token=secret_token
    )
    
    return worker_result

if __name__ == "__main__":
    # 从环境变量读取配置
    WORKER_URL = os.getenv("CF_WORKER_URL")       # Worker代理地址
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")   # 机器人令牌
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")       # 频道/群组ID
    SECRET_TOKEN = os.getenv("SECRET_TOKEN")      # 安全令牌（可选）
    
    # 发送测试消息
    result = send_message_with_fallback(
        worker_url=WORKER_URL,
        bot_token=BOT_TOKEN,
        chat_id=CHAT_ID,
        message="*这是一条测试消息*",  # 支持Markdown格式
        secret_token=SECRET_TOKEN
    )
    
    # 打印最终结果
    print("发送结果：")
    print(json.dumps(result, indent=2, ensure_ascii=False))