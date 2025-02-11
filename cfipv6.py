import requests
import os
import logging
import subprocess
import glob
from datetime import datetime
from hashlib import md5

# 从 colo_emojis.py 导入 colo_emojis 字典
from colo_emojis import colo_emojis

# 配置日志
def setup_logging(log_file):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# 抓取 IPv6 地址
def fetch_ipv6_addresses(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        ipv6_addresses = response.text.strip().split('\n')
        logging.info(f"从 {url} 成功抓取到 {len(ipv6_addresses)} 个 IPv6 地址")
        return ipv6_addresses
    except Exception as e:
        logging.error(f"抓取 IPv6 地址时出错：{e}")
        return []

# 获取 colo 信息（模拟浏览器访问）
def get_colo(ipv6):
    url = f"http://[{ipv6}]/cdn-cgi/trace"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        for line in response.text.split('\n'):
            if line.startswith('colo='):
                return line.split('=')[1]
    except requests.RequestException as e:
        logging.warning(f"获取 {ipv6} 的 colo 信息失败：{e}")
    return None

# 处理 IPv6 地址
def process_ipv6_addresses(ipv6_addresses):
    processed_addresses = []
    for address in ipv6_addresses:
        if not address.strip():
            continue
        ipv6 = address.split('#')[0].strip('[]')
        colo = get_colo(ipv6)
        if colo:
            emoji = colo_emojis.get(colo, "")
            processed_address = address.replace("#CMCC-IPV6", f"#{emoji}{colo}┃CMCC-IPV6")
        else:
            processed_address = address
        processed_addresses.append(processed_address)
    return processed_addresses

def git_commit_and_push():
    try:
        # 获取变更文件列表
        changed_files = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        if not changed_files:
            logging.info("没有需要提交的变更。")
            return

        # 执行提交
        subprocess.run(["git", "add", "."], check=True)
        commit_message = f"cfst: Update cfipv6.txt on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push"], check=True)
        logging.info(f"成功提交变更：\n{changed_files}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Git 操作失败：{str(e)}")

def calculate_md5(file_path):
    """ 优化后的哈希计算 """
    try:
        with open(file_path, 'rb') as f:
            return md5(f.read()).hexdigest()
    except Exception as e:
        logging.error(f"哈希计算失败：{str(e)}")
        return None

# 主函数
def main():
    # 删除旧的日志文件
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f'logs/cfipv6_{current_time}.log'
    old_logs = glob.glob('logs/cfipv6_*.log')
    for old_log in old_logs:
        try:
            os.remove(old_log)
            print(f"已删除旧日志文件: {old_log}")
        except Exception as e:
            print(f"删除旧日志文件 {old_log} 时出错: {e}")
            logging.error(f"删除旧日志文件 {old_log} 时出错: {e}")

    setup_logging(log_file)

    # 获取现有文件哈希
    output_file = "speed/cfipv6.txt"
    old_hash = calculate_md5(output_file) if os.path.exists(output_file) else None

    url = "https://addressesapi.090227.xyz/cmcc-ipv6"
    ipv6_addresses = fetch_ipv6_addresses(url)
    if not ipv6_addresses:
        logging.error("未抓取到 IPv6 地址。程序退出。")
        return

    processed_addresses = process_ipv6_addresses(ipv6_addresses)
    
    output_dir = "speed"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "cfipv6.txt")

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(processed_addresses) + "\n")
        logging.info(f"已将处理后的 IPv6 地址写入 {output_file}")
    except Exception as e:
        logging.error(f"写入 {output_file} 时出错：{e}")
    
    # 检测变更
    new_hash = calculate_md5(output_file)
    if new_hash != old_hash:
        logging.info("检测到内容变更，触发 Git 提交...")
        git_commit_and_push()
    else:
        logging.info("未检测到内容变更。")

if __name__ == "__main__":
    main()
