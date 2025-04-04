import requests
import os
import sys
import time  # 新增导入time模块
from dotenv import load_dotenv
# 在文件顶部添加以下代码
from pathlib import Path

# 动态添加py目录到系统路径
current_dir = Path(__file__).parent  # scripts目录
project_root = current_dir.parent    # 项目根目录
sys.path.append(str(project_root / "py"))  # 添加py目录

# 然后导入tg模块
from tg import send_message_with_fallback

load_dotenv()

# 配置信息（建议使用环境变量）
ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID")
NAMESPACE_ID = os.getenv("CF_KV_NAMESPACE_ID")
API_TOKEN = os.getenv("CF_API_TOKEN")
KEY_NAME = "LINK.txt"  # 你的键名

# API 端点
BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def delete_from_kv(mode='line_number', target=0, keyword=None):
    get_url = f"{BASE_URL}/values/{KEY_NAME}"
    response = requests.get(get_url, headers=headers)
    
    if not response.ok and response.status_code != 404:
        response.raise_for_status()
    
    current_value = response.text if response.status_code == 200 else ""
    original_lines = current_value.split('\n') if current_value else []
    deleted_lines = []  # 新增：记录被删除的内容

    # 删除逻辑优化
    if mode == 'line_number':
        if 0 <= target < len(original_lines):
            deleted_lines.append(original_lines[target])  # 记录被删除行
            del original_lines[target]
    elif mode == 'content' and keyword:
        # 使用列表推导式记录所有匹配行
        deleted_lines = [line for line in original_lines if keyword in line]
        original_lines = [line for line in original_lines if keyword not in line]
    
    # 打印被删除内容（新增功能）
    if deleted_lines:
        print(f"已删除内容（共 {len(deleted_lines)} 行）:")
        for i, line in enumerate(deleted_lines, 1):
            print(f"[{i}] {line}")
    else:
        print("未删除任何内容")

    # 重建时强化换行处理（优化点）
    updated_value = '\n'.join(original_lines)
    # 确保非空内容必有换行符
    if updated_value:
        if not updated_value.endswith('\n'):
            updated_value += '\n'
    else:  # 空内容时不加换行
        updated_value = ''

    put_url = f"{BASE_URL}/values/{KEY_NAME}"
    response = requests.put(put_url, headers=headers, data=updated_value)
    
    if response.ok:
        print(f"已成功删除 {mode}.")
    else:
        print(f"删除失败: {response.text}")

def append_to_kv(content):
    get_url = f"{BASE_URL}/values/{KEY_NAME}"
    response = requests.get(get_url, headers=headers)
    
    current_value = ""
    if response.status_code == 200:
        current_value = response.text
        # 强化换行检查逻辑
        if current_value:
            # 先去除可能存在的末尾空行
            while current_value.endswith('\n'):
                current_value = current_value.rstrip('\n')
            current_value += '\n'  # 确保追加前有且仅有一个换行
    
    new_content = f"\n{content}\n"  # 确保新内容自带换行符
    updated_value = current_value + new_content
    
    put_url = f"{BASE_URL}/values/{KEY_NAME}"
    response = requests.put(put_url, headers=headers, data=updated_value)
    
    if response.ok:
        print("KV更新成功.")
        # 新增：发送KV内容到Telegram
        BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        WORKER_URL = os.getenv("CF_WORKER_URL")
        SECRET_TOKEN = os.getenv("SECRET_TOKEN")
        if BOT_TOKEN and CHAT_ID:
            # 直接使用更新后的内容
            message = f"*KV更新成功*\n当前内容:\n```\n{updated_value}\n```"
            send_message_with_fallback(
                worker_url=WORKER_URL,
                bot_token=BOT_TOKEN,
                chat_id=CHAT_ID,
                message=message,
                secret_token=SECRET_TOKEN
            )
    else:
        print(f"失败: {response.status_code}, {response.text}")

def print_kv():
    get_url = f"{BASE_URL}/values/{KEY_NAME}"
    response = requests.get(get_url, headers=headers)
    if response.status_code == 200:
        print("当前KV内容:\n", response.text)
    else:
        print("无法获取 KV（键值对）内容.")

if __name__ == "__main__":
    # 检查是否提供了订阅地址参数
    if len(sys.argv) > 1:
        subscription_url = sys.argv[1]
        
        # 删除包含"otcopusvpn"的行
        delete_from_kv(mode='content', keyword="subscribe")

        # 追加新的订阅地址
        append_to_kv(subscription_url)
        
        # 延迟5秒后打印KV内容
        print("等待5秒后显示KV内容...")
        time.sleep(10)  # 延迟10秒
        print_kv()
    else:
        print("请提供订阅地址作为参数")
