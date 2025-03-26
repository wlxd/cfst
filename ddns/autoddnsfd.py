import re
import os
import requests
import logging
import sys
import argparse
from dotenv import load_dotenv
from urllib.parse import urlparse  # 新增导入

# 获取当前文件的绝对路径
current_file_path = os.path.abspath(__file__)
# 获取当前文件所在目录的父目录
parent_dir = os.path.dirname(os.path.dirname(current_file_path))

# 将父目录下的 py 文件夹路径添加到 sys.path
sys.path.append(os.path.join(parent_dir, 'py'))

from colo_emojis import colo_emojis
from tg import send_telegram_message

# 加载环境变量
load_dotenv()

# 定义全局变量
fd = "fd"

# 日志文件路径
LOG_PATH = f"logs/dns_update_{fd}.log"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

# 读取 Cloudflare API 配置
API_KEY = os.getenv("CLOUDFLARE_API_KEY")
EMAIL = os.getenv("CLOUDFLARE_EMAIL")
ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID")

# 确保环境变量正确加载
if not all([API_KEY, EMAIL, ZONE_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    logging.error("缺少必要的配置信息，请检查 GitHub Secrets 配置。")
    sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(description='自动更新DNS记录')
    parser.add_argument('--regions', nargs='*', help='区域代码列表（如 HKG LAX）')
    return parser.parse_args()

def send_telegram_notification(message: str, parse_mode: str = 'Markdown'):
    """通过 Cloudflare Worker 发送 Telegram 消息"""
    worker_url = os.getenv("CF_WORKER_URL")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    secret_token = os.getenv("SECRET_TOKEN")  # 可选
    
    if not all([worker_url, bot_token, chat_id]):
        logging.warning("Telegram 配置不完整，跳过通知")
        return
    
    # 调用 tg.py 的发送函数
    result = send_telegram_message(
        worker_url=worker_url,
        bot_token=bot_token,
        chat_id=chat_id,
        message=message,
        secret_token=secret_token
    )
    
    if result.get("status") == "error":
        logging.error(f"Telegram通知发送失败: {result.get('message')}")
        
# 修改日志处理器格式以支持Markdown
class TelegramLogHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = self.format(record)
            # 添加Markdown格式化
            formatted_msg = f"`[DNS-UPDATE]` **{record.levelname}**\n{log_entry}"
            send_to_telegram(formatted_msg)
        except Exception as e:
            logging.error(f"日志发送失败：{str(e)}")

# 添加 Telegram 日志处理器
telegram_handler = TelegramLogHandler()
telegram_handler.setLevel(logging.INFO)
telegram_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(telegram_handler)

# 域名与标记映射关系（扩展机场三字码）
LOCATION_TO_DOMAIN = {
    # 示例映射（可根据实际需求调整）
    # 美国
    "🇺🇸SJC": "proxy.us.616049.xyz",  # 圣何塞
    "🇺🇸LAX": "proxy.us.616049.xyz",  # 洛杉矶
    "🇺🇸SEA": "proxy.us.616049.xyz",  # 西雅图
    "🇺🇸JFK": "proxy.us.616049.xyz",  # 纽约 - 肯尼迪国际机场
    "🇺🇸ORD": "proxy.us.616049.xyz",  # 芝加哥 - 奥黑尔国际机场
    "🇺🇸IAD": "proxy.us.616049.xyz",  # 华盛顿杜勒斯国际机场
    "🇺🇸EWR": "proxy.us.616049.xyz",  # 纽瓦克自由国际机场
    "🇺🇸CMH": "proxy.us.616049.xyz",  # 哥伦布国际机场
    "🇺🇸PDX": "proxy.us.616049.xyz",  # 俄勒冈州 - 波特兰国际机场
    "🇺🇸US": "proxy.us.616049.xyz",  # 美国

    # 加拿大
    "🇨🇦YUL": "proxy.ca.616049.xyz",  # 蒙特利尔皮埃尔·埃利奥特·特鲁多国际机场
    "🇨🇦YYZ": "proxy.ca.616049.xyz",  # 多伦多皮尔逊国际机场
    "🇨🇦YVR": "proxy.ca.616049.xyz",  # 温哥华国际机场
    "🇨🇦CA": "proxy.ca.616049.xyz",  # 加拿大

    # 德国
    "🇩🇪FRA": "proxy.de.616049.xyz",  # 法兰克福机场
    "🇩🇪DE": "proxy.de.616049.xyz",  # 德国

    # 法国
    "🇫🇷CDG": "proxy.fr.616049.xyz",  # 巴黎戴高乐机场
    "🇫🇷FR": "proxy.fr.616049.xyz",  # 法国
    
    # 英国
    "🇬🇧LHR": "proxy.uk.616049.xyz",  # 伦敦
    "🇬🇧UK": "proxy.uk.616049.xyz",  # 英国

    # 荷兰
    "🇳🇱AMS": "proxy.nl.616049.xyz",  # 阿姆斯特丹史基浦机场
    "🇳🇱NL": "proxy.nl.616049.xyz",  # 荷兰
    
    # 日本
    "🇯🇵NRT": "proxy.jp.616049.xyz",  # 东京成田
    "🇯🇵HND": "proxy.jp.616049.xyz",  # 东京羽田
    "🇯🇵JP": "proxy.jp.616049.xyz",  # 日本

    # 香港
    "🇭🇰HKG": "proxy.hk.616049.xyz",  # 香港国际机场
    "🇭🇰HK": "proxy.hk.616049.xyz",  # 香港

    # 韩国
    "🇰🇷ICN": "proxy.kr.616049.xyz",  # 仁川国际机场
    "🇰🇷KR": "proxy.kr.616049.xyz",  # 韩国

    # 台湾
    "🇹🇼TPE": "proxy.tw.616049.xyz",  # 台北桃园机场
    "🇹🇼TW": "proxy.tw.616049.xyz",  # 台湾

    # 新加坡
    "🇸🇬SIN": "proxy.sg.616049.xyz",   # 樟宜机场
    "🇸🇬SG": "proxy.sg.616049.xyz",  # 新加坡

    # 印度
    "🇮🇳BOM": "proxy.in.616049.xyz",  # 孟买国际机场
    "🇮🇳IN": "proxy.in.616049.xyz",  # 印度

    # 瑞典
    "🇸🇪ARN": "proxy.se.616049.xyz",  # 斯德哥尔摩阿兰达机场
    "🇸🇪SE": "proxy.se.616049.xyz",  # 瑞典

    # 芬兰
    "🇫🇮HEL": "proxy.fi.616049.xyz",  # 赫尔辛基
    "🇫🇮FI": "proxy.fi.616049.xyz",  # 芬兰

    # 巴西
    "🇧🇷GRU": "proxy.br.616049.xyz",  # 圣保罗瓜鲁柳斯国际机场
    "🇧🇷BR": "proxy.br.616049.xyz",  # 巴西

    # 波兰
    "🇵🇱WAW": "proxy.pl.616049.xyz",  # 华沙
    "🇵🇱PL": "proxy.pl.616049.xyz",  # 波兰
    
    # 澳大利亚
    "🇦🇺SYD": "proxy.au.616049.xyz",  # 悉尼国际机场（澳大利亚）
    "🇦🇺AU": "proxy.au.616049.xyz",  # 澳大利亚
}

# 解析 port/ip.txt 文件并获取 IP、PORT 和 LOCATION
def get_ips_from_file(file_path, limit=200):
    ip_data = []
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                parts = line.strip().split("#")
                if len(parts) < 2:
                    continue
                ip_port, location = parts[0], parts[1].split("┃")[0].strip()
                if ":" in ip_port:
                    ip, port = ip_port.split(":")
                    # 提取 LOCATION，不包括编号，例如 🇭🇰HK1 -> 🇭🇰HK
                    location = ''.join([c for c in location if not c.isdigit()])
                    ip_data.append((ip.strip(), port.strip(), location.strip()))
                if len(ip_data) >= limit:
                    break
        return ip_data
    except FileNotFoundError:
        logging.error(f"文件未找到: {file_path}")
        return []

# 批量添加 DNS 记录并同步到 ddns/ip.txt
def add_dns_records_bulk(ip_data):
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    headers = {
        "X-Auth-Email": EMAIL,
        "X-Auth-Key": API_KEY,
        "Content-Type": "application/json"
    }

    deleted_prefixes = set()
    prefix_counters = {}

    for ip, port, location in ip_data:
        domain = LOCATION_TO_DOMAIN.get(location)
        if domain:
            prefix = ".".join(domain.split(".", 2)[:2])  # 分割两次并取前两部分
            if prefix not in deleted_prefixes:
                delete_dns_records_with_prefix(prefix)
                deleted_prefixes.add(prefix)
                prefix_counters[prefix] = 0

            if prefix_counters.get(prefix, 0) >= 5:
                logging.info(f"前缀 {prefix} 的记录数量已达到 5 条，跳过添加: {domain} -> {ip}")
                continue

            data = {
                "type": "A",
                "name": domain,
                "content": ip,
                "ttl": 1,
                "proxied": False
            }
            try:
                response = requests.post(url, headers=headers, json=data)
                if response.status_code == 200:
                    logging.info(f"添加成功: {domain} -> {ip}")
                    prefix_counters[prefix] = prefix_counters.get(prefix, 0) + 1
                    write_to_ddns(ip, port, domain)
                elif response.status_code == 409:
                    logging.info(f"记录已存在: {domain} -> {ip}")
                else:
                    logging.error(f"添加失败: {domain} -> {ip}, 错误信息: {response.status_code}, {response.text}")
            except requests.exceptions.RequestException as e:
                logging.error(f"请求失败: {e}")
        else:
            logging.warning(f"未找到标记 {location} 对应的域名映射，跳过。")

# 删除指定前缀的 DNS 记录，并从 ddns/ip.txt 删除对应 IP
def delete_dns_records_with_prefix(prefix):
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
        headers = {
            "X-Auth-Email": EMAIL,
            "X-Auth-Key": API_KEY,
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        records = response.json().get("result", [])

        matching_records = [record for record in records if record["name"].startswith(prefix + ".")]

        if matching_records:
            for record in matching_records:
                record_id = record["id"]
                delete_url = f"{url}/{record_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                if delete_response.status_code == 200:
                    logging.info(f"已删除记录: {record['name']} -> {record['content']}")
                    remove_from_ddns(record["content"])
                else:
                    logging.error(f"删除失败: {record['name']} -> {record['content']}, 错误信息: {delete_response.status_code}, {delete_response.text}")
        else:
            logging.info(f"没有需要删除的记录，{prefix} 前缀的记录数量为 0")
    except requests.exceptions.RequestException as e:
        logging.error(f"请求失败: {e}")

# 记录 IP、PORT、DOMAIN 到 ddns/ip.txt
def write_to_ddns(ip, port, domain):
    try:
        with open(f"ddns/{fd}.txt", "a", encoding="utf-8") as file:
            file.write(f"{ip}:{port} -> {domain}\n")
            logging.info(f"写入 ddns/{fd}.txt: {ip}:{port} -> {domain}\n")
    except IOError as e:
        logging.error(f"写入 ddns/{fd}.txt 失败: {e}")

# 从 ddns/ip.txt 删除 IP 记录
def remove_from_ddns(ip):
    try:
        lines = []
        with open(f"ddns/{fd}.txt", "r", encoding="utf-8") as file:
            lines = file.readlines()
        with open(f"ddns/{fd}.txt", "w", encoding="utf-8") as file:
            for line in lines:
                if not line.startswith(f"{ip}:"):
                    file.write(line)
    except IOError as e:
        logging.error(f"删除 ddns/{fd}.txt 中的 {ip} 失败: {e}")

# 清理日志文件
def clear_log_file():
    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
            logging.info(f"已清理旧日志文件: {LOG_PATH}")
    except OSError as e:
        logging.error(f"清理日志文件失败: {e.strerror}")

# 主程序
if __name__ == "__main__":
    args = parse_args()
    target_regions = args.regions if args.regions else None

    clear_log_file()
    ip_data = get_ips_from_file(f"port/{fd}.txt")
    
    if target_regions:
        target_countries = set()
        # 转换区域代码为国家代码
        for code in target_regions:
            if code in colo_emojis:
                # 从映射中获取国家代码（如 "US"）
                target_countries.add(colo_emojis[code][1])  
            elif len(code) == 2 and code.isupper():
                # 直接使用国家代码（如 "US"）
                target_countries.add(code)
            else:
                logging.warning(f"无效区域代码: {code}，已跳过")
        
        # 过滤IP记录
        filtered_ip_data = []
        for ip, port, loc in ip_data:
            # 从location字段提取国家代码（如 "🇺🇸US" -> "US"）
            country_code = loc[-2:]  
            if country_code in target_countries:
                filtered_ip_data.append((ip, port, loc))
        
        ip_data = filtered_ip_data
        logging.warning(f"过滤IP记录: {ip_data}")

    if not ip_data:
        logging.error(f"未找到匹配 {target_regions} 的IP记录")
    else:
        add_dns_records_bulk(ip_data)
