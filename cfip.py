import requests
from bs4 import BeautifulSoup
import re
import os
import logging
import hashlib
from datetime import datetime
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from colo_emojis import colo_emojis  # 确保colo_emojis.py存在并导出字典
import glob
import subprocess
import sys

def setup_logging(log_filename):
    """配置日志，同时输出到文件和控制台"""
    logger = logging.getLogger()
    # 清除之前的处理器，避免重复
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(logging.INFO)
    
    # 文件处理器
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def calculate_md5(file_path):
    """计算文件的MD5哈希值"""
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def update_to_github():
    """提交所有变更到GitHub"""
    try:
        logging.info("变更已提交到GitHub")
        subprocess.run(["git", "add", "."], check=True)
        commit_message = f"cfst: Update cfip.txt on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"提交GitHub失败: {e}")

def fetch_page_content(url, headers, session):
    try:
        response = session.get(url, headers=headers)
        response.encoding = 'utf-8'
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"获取页面内容失败: {e}")
        return None

def parse_table_data(soup):
    table = soup.find('table')
    if not table:
        logging.error("未找到表格")
        return None
    tbody = table.find('tbody')
    if not tbody:
        logging.error("表格缺少tbody")
        return None
    rows = tbody.find_all('tr')
    data = []
    for row in rows:
        tds = row.find_all('td')
        if len(tds) < 6:  # 确保有足够列
            continue
        ip_tag = tds[0].find('a')
        if not ip_tag:
            continue
        ip = ip_tag.get_text(strip=True)
        avg_latency = tds[4].get_text(strip=True)
        download_speed = tds[5].get_text(strip=True)
        data.append({'ip': ip, 'avg_latency': avg_latency, 'download_speed': download_speed})
    return data

def fetch_trace_info(ip, session, headers):
    trace_url = f'http://{ip}/cdn-cgi/trace'
    try:
        response = session.get(trace_url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"获取{ip}的Trace信息失败: {e}")
        return None

def process_ip_data(data, session, headers):
    lines_speed = []
    lines_cfip = []
    for entry in data:
        ip = entry['ip']
        download_speed = entry['download_speed']
        trace_text = fetch_trace_info(ip, session, headers)
        if not trace_text:
            continue
        colo_match = re.search(r'colo=(\w+)', trace_text)
        if colo_match:
            colo = colo_match.group(1)
            emoji = colo_emojis.get(colo, '☁️')
            line_speed = f"{ip}#{emoji}{colo}┃⚡{download_speed}\n"
            line_cfip = f"{ip}#{emoji}{colo}\n"
            lines_speed.append(line_speed)
            lines_cfip.append(line_cfip)
            logging.info(f"处理成功: {line_speed.strip()}")
        else:
            logging.warning(f"未找到{ip}的colo信息")
    return lines_speed, lines_cfip

def main():
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f'logs/cfip_{current_time}.log'
    os.makedirs('logs', exist_ok=True)
    # 清理旧日志
    for old_log in glob.glob('logs/cfip_*.log'):
        try:
            os.remove(old_log)
            logging.info(f"删除日志文件: {old_log}")
        except Exception as e:
            logging.error(f"删除日志失败: {old_log} - {e}")
    setup_logging(log_filename)
    
    url = 'https://ip.164746.xyz/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))
    
    # 获取页面内容
    html = fetch_page_content(url, headers, session)
    if not html:
        return
    soup = BeautifulSoup(html, 'html.parser')
    data = parse_table_data(soup)
    if not data:
        return
    
    # 处理IP数据
    lines_speed, lines_cfip = process_ip_data(data, session, headers)
    if not lines_speed or not lines_cfip:
        logging.error("处理后的数据为空，无法写入文件")
        return
    
    # 写入文件
    os.makedirs('speed', exist_ok=True)
    os.makedirs('cfip', exist_ok=True)
    
    file_path_speed = 'speed/cfip.txt'
    file_path_cfip = 'cfip/cfip.txt'
    
    # 计算旧哈希
    old_hash_speed = calculate_md5(file_path_speed)
    old_hash_cfip = calculate_md5(file_path_cfip)
    logging.info(f"旧文件speed MD5哈希: {old_hash_speed}")
    logging.info(f"旧文件cfip MD5哈希: {old_hash_cfip}")
    
    # 写入新内容
    with open(file_path_speed, 'w', encoding='utf-8') as f:
        f.writelines(lines_speed)
    with open(file_path_cfip, 'w', encoding='utf-8') as f:
        f.writelines(lines_cfip)
    
    # 计算新哈希
    new_hash_speed = calculate_md5(file_path_speed)
    new_hash_cfip = calculate_md5(file_path_cfip)
    logging.info(f"新文件speed MD5哈希: {new_hash_speed}")
    logging.info(f"新文件cfip MD5哈希: {new_hash_cfip}")
    
    # 检测变更并提交
    if old_hash_speed != new_hash_speed or old_hash_cfip != new_hash_cfip:
        logging.info("检测到变更，提交到GitHub")
        update_to_github()
    else:
        logging.info("内容未变更，无需提交")
    logging.info("脚本执行完毕")

if __name__ == "__main__":
    main()