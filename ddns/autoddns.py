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

# 加载环境变量
load_dotenv()

# 定义全局变量
fd = "ip"

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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 确保环境变量正确加载
if not all([API_KEY, EMAIL, ZONE_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    logging.error("缺少必要的配置信息，请检查 GitHub Secrets 配置。")
    sys.exit(1)

# 在环境变量加载之后添加代理配置读取
TELEGRAM_PROXY = os.getenv('TELEGRAM_PROXY')  # 新增代理配置

# 传入区域参数
def parse_args():
    parser = argparse.ArgumentParser(description='自动更新DNS记录')
    parser.add_argument('--regions', nargs='*', help='区域代码列表（如 HKG LAX）')
    return parser.parse_args()

# 修改后的发送函数
def send_to_telegram(message):
    """支持代理的Telegram消息发送"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"  # 新增Markdown支持
    }
    
    # 代理配置处理
    proxies = {}
    if TELEGRAM_PROXY:
        parsed = urlparse(TELEGRAM_PROXY)
        if parsed.scheme in ('socks5', 'http', 'https'):
            proxies = {
                "http": TELEGRAM_PROXY,
                "https": TELEGRAM_PROXY
            }
            logging.debug(f"使用代理服务器：{parsed.hostname}:{parsed.port}")
        else:
            logging.warning("不支持的代理协议，仅支持socks5/http/https")

    try:
        response = requests.post(
            url,
            json=payload,
            proxies=proxies,
            timeout=15  # 延长超时时间
        )
        response.raise_for_status()
        logging.debug("Telegram消息发送成功")
    except requests.exceptions.ProxyError as e:
        logging.error(f"代理连接失败：{str(e)}")
    except requests.exceptions.SSLError as e:
        logging.error(f"SSL验证失败：{str(e)}")
    except requests.exceptions.ConnectTimeout as e:
        logging.error(f"连接超时：{str(e)}")
    except requests.exceptions.RequestException as e:
        logging.error(f"请求异常：{str(e)}")
    except Exception as e:
        logging.error(f"未知错误：{str(e)}")

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
    "🇺🇸SJC": "us.616049.xyz",  # 圣何塞
    "🇺🇸LAX": "us.616049.xyz",  # 洛杉矶
    "🇺🇸SEA": "us.616049.xyz",  # 西雅图
    "🇺🇸JFK": "us.616049.xyz",  # 纽约 - 肯尼迪国际机场
    "🇺🇸ORD": "us.616049.xyz",  # 芝加哥 - 奥黑尔国际机场
    "🇺🇸IAD": "us.616049.xyz",  # 华盛顿杜勒斯国际机场
    "🇺🇸EWR": "us.616049.xyz",  # 纽瓦克自由国际机场
    "🇺🇸CMH": "us.616049.xyz",  # 哥伦布国际机场
    "🇺🇸PDX": "us.616049.xyz",  # 俄勒冈州 - 波特兰国际机场
    "🇺🇸US": "us.616049.xyz",  # 美国

    # 加拿大
    "🇨🇦YUL": "ca.616049.xyz",  # 蒙特利尔皮埃尔·埃利奥特·特鲁多国际机场
    "🇨🇦YYZ": "ca.616049.xyz",  # 多伦多皮尔逊国际机场
    "🇨🇦YVR": "ca.616049.xyz",  # 温哥华国际机场
    "🇨🇦CA": "ca.616049.xyz",  # 加拿大

    # 德国
    "🇩🇪FRA": "de.616049.xyz",  # 法兰克福机场
    "🇩🇪DE": "de.616049.xyz",  # 德国

    # 法国
    "🇫🇷CDG": "fr.616049.xyz",  # 巴黎戴高乐机场
    "🇫🇷FR": "fr.616049.xyz",  # 法国
    
    # 英国
    "🇬🇧LHR": "uk.616049.xyz",  # 伦敦
    "🇬🇧UK": "uk.616049.xyz",  # 英国

    # 荷兰
    "🇳🇱AMS": "nl.616049.xyz",  # 阿姆斯特丹史基浦机场
    "🇳🇱NL": "nl.616049.xyz",  # 荷兰
    
    # 日本
    "🇯🇵NRT": "jp.616049.xyz",  # 东京成田
    "🇯🇵HND": "jp.616049.xyz",  # 东京羽田
    "🇯🇵JP": "jp.616049.xyz",  # 日本

    # 香港
    "🇭🇰HKG": "hk.616049.xyz",  # 香港国际机场
    "🇭🇰HK": "hk.616049.xyz",  # 香港

    # 韩国
    "🇰🇷ICN": "kr.616049.xyz",  # 仁川国际机场
    "🇰🇷KR": "kr.616049.xyz",  # 韩国

    # 台湾
    "🇹🇼TPE": "tw.616049.xyz",  # 台北桃园机场
    "🇹🇼TW": "tw.616049.xyz",  # 台湾

    # 新加坡
    "🇸🇬SIN": "sg.616049.xyz",   # 樟宜机场
    "🇸🇬SG": "sg.616049.xyz",  # 新加坡

    # 印度
    "🇮🇳BOM": "in.616049.xyz",  # 孟买国际机场
    "🇮🇳IN": "in.616049.xyz",  # 印度

    # 瑞典
    "🇸🇪ARN": "se.616049.xyz",  # 斯德哥尔摩阿兰达机场
    "🇸🇪SE": "se.616049.xyz",  # 瑞典

    # 芬兰
    "🇫🇮HEL": "fi.616049.xyz",  # 赫尔辛基
    "🇫🇮FI": "fi.616049.xyz",  # 芬兰

    # 巴西
    "🇧🇷GRU": "br.616049.xyz",  # 圣保罗瓜鲁柳斯国际机场
    "🇧🇷BR": "br.616049.xyz",  # 巴西

    # 波兰
    "🇵🇱WAW": "pl.616049.xyz",  # 华沙
    "🇵🇱PL": "pl.616049.xyz",  # 波兰
    
    # 澳大利亚
    "🇦🇺SYD": "au.616049.xyz",  # 悉尼国际机场（澳大利亚）
    "🇦🇺AU": "au.616049.xyz",  # 澳大利亚
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

# 批量添加 DNS 记录并同步到 ddns/ip/ip.txt
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
            prefix = domain.split(".")[0]
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

# 删除指定前缀的 DNS 记录，并从 ddns/ip/ip.txt 删除对应 IP
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

# 记录 IP、PORT、DOMAIN 到 ddns/ip/ip.txt
def write_to_ddns(ip, port, domain):
    try:
        with open(f"ddns/{fd}/{fd}.txt", "a", encoding="utf-8") as file:
            file.write(f"{ip}:{port} -> {domain}\n")
            logging.info(f"写入 ddns/{fd}/{fd}.txt: {ip}:{port} -> {domain}\n")
    except IOError as e:
        logging.error(f"写入 ddns/{fd}/{fd}.txt 失败: {e}")

# 从 ddns/ip/ip.txt 删除 IP 记录
def remove_from_ddns(ip):
    try:
        lines = []
        with open(f"ddns/{fd}/{fd}.txt", "r", encoding="utf-8") as file:
            lines = file.readlines()
        with open(f"ddns/{fd}/{fd}.txt", "w", encoding="utf-8") as file:
            for line in lines:
                if not line.startswith(f"{ip}:"):
                    file.write(line)
    except IOError as e:
        logging.error(f"删除 ddns/{fd}/{fd}.txt 中的 {ip} 失败: {e}")

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

    if not ip_data:
        logging.error(f"未找到匹配 {target_regions} 的IP记录")
    else:
        add_dns_records_bulk(ip_data)
