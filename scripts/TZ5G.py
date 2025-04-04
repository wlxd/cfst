import pyaes
import binascii
import requests
import re
import uuid
import random
import subprocess
import os
import sys
from pathlib import Path

# 动态添加py目录到系统路径
current_dir = Path(__file__).parent  # scripts目录
project_root = current_dir.parent    # 项目根目录
sys.path.append(str(project_root / "py"))  # 添加py目录

# 然后导入tg模块
from tg import send_message_with_fallback

def pad_data(data):
    padding_length = 16 - (len(data) % 16)
    return data + chr(padding_length) * padding_length

def encrypt_data(key, iv, text):
    encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv))
    ciphertext = encrypter.feed(text) + encrypter.feed()
    return binascii.hexlify(ciphertext).decode().upper()

def extract_phone_number(data):
    match = re.search(r'"phoneNumber":"([^"]+)"', data)
    return match.group(1) if match else None

def register_user(data):
    key = 'rwb6c4e7fz$6el%0'.encode('utf-8')
    iv = 'z1b6c3t4e5f6k7w8'.encode('utf-8')
    encrypted_data = encrypt_data(key, iv, pad_data(data).encode('utf-8'))
    url = f"https://api.otcopusvpn.cc:18008/netbarcloud/vpn/appRegister.do?data={encrypted_data}"
    headers = {
        'User-Agent': 'BZYuApp/1.0.4 (com.taizi.vpn; build:1; iOS 16.5.0)',
        'Accept': '*/*'
    }
    try:
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            print("注册成功")
        else:
            print(f"注册失败: {response.status_code}")
    except requests.RequestException as e:
        print(f"注册请求异常: {e}")

def login(phone_number):
    key = 'rwb6c4e7fz$6el%0'.encode('utf-8')
    iv = 'z1b6c3t4e5f6k7w8'.encode('utf-8')
    password = '255A42F2A6863798DBB392033F9D2FD7'
    session = requests.Session()
    session.trust_env = False
    headers = {
        'User-Agent': 'Octopus_Android',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip'
    }
    url = 'https://api.otcopusvpn.cc:18008/netbarcloud/vpn/phLogin.do'
    params = {
        'phoneNumber': encrypt_data(key, iv, phone_number),
        'password': password,
        'osType': 'android'
    }
    try:
        response = session.post(url, headers=headers, params=params)
        if response.status_code == 200:
            result = response.json()
            if not result.get("data"):
                print("登录失败，无数据")
                return None
            data = result.get("data")
            ph_token = data.get("phToken")
            vpn_token = data.get("vpnToken")
            node_url = 'https://api.otcopusvpn.cc:18008/netbarcloud/vpn/airportNode.do'
            headers['token'] = vpn_token
            node_response = session.post(node_url, headers=headers, params={'phToken': ph_token, 'phoneNumber': phone_number})
            subscription_url = node_response.json().get("data")
            if subscription_url:
                return subscription_url
            else:
                return None
        else:
            print(f"登录失败: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"登录请求异常: {e}")
        return None

def main():
    device_id = uuid.uuid4().hex.upper()
    phone_number = str(random.randint(1000000, 999999999))
    data = f'{{"checkPassword":"123456","phoneNumber":"{phone_number}","from":"6","id":"182265","clientIp":"192.168.1.1","password":"123456","iosDevice":"{device_id}"}}'
    extracted_phone_number = extract_phone_number(data)
    if extracted_phone_number:
        register_user(data)
        subscription_url = login(extracted_phone_number)
        # 在main函数中找到以下代码段
        if subscription_url:
            print(f"最终获取到的订阅地址: {subscription_url}")
            # 调用kv.py并传递订阅地址
            try:
                subprocess.run(["python", "scripts/kv.py", subscription_url], check=True)
            except subprocess.CalledProcessError as e:
                print(f"调用kv.py失败: {e}")
            # 新增：发送订阅地址到Telegram
            BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
            CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
            WORKER_URL = os.getenv("CF_WORKER_URL")
            SECRET_TOKEN = os.getenv("SECRET_TOKEN")
            if BOT_TOKEN and CHAT_ID:
                send_message_with_fallback(
                    worker_url=WORKER_URL,
                    bot_token=BOT_TOKEN,
                    chat_id=CHAT_ID,
                    message=f"*新订阅地址*\n`{subscription_url}`",
                    secret_token=SECRET_TOKEN
                )
            else:
                print("未配置Telegram环境变量，跳过发送")

if __name__ == "__main__":
    main()
