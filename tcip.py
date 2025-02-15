import logging
import re
import csv
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from telethon.sync import TelegramClient
from telethon.tl.types import DocumentAttributeFilename
import socks
from colo_emojis import colo_emojis
from checker import process_ip_list
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# --------------------------
# 配置区
# --------------------------
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_NAME = os.getenv('SESSION_NAME', 'default_session')  # 默认值为 default_session
CHANNEL = '@cloudflareorg'
LIMIT = 100  # 扩大限制确保覆盖当日文件
DOWNLOAD_DIR = 'csv'
OUTPUT_FILE = 'cfip/tcip.txt'
LOG_DIR = 'logs'
Path(DOWNLOAD_DIR).mkdir(exist_ok=True)
Path(LOG_DIR).mkdir(exist_ok=True)
Path("cfip").mkdir(exist_ok=True)

# 动态生成日志文件名
log_filename = datetime.now().strftime("tcip_%Y%m%d_%H%M%S.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(Path(LOG_DIR) / log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_filename(filename: str) -> str:
    """解析文件名返回日期部分"""
    # 文件名格式: XXXXX-YYYYMMDD-IP.csv，其中XXXXX可以是任意长度的数字
    date_match = re.match(r'^\d+-\d{8}-IP\.csv$', filename, re.I)
    if date_match:
        logger.info(f"解析文件名成功: {filename} -> {date_match.group(0)}")
        return date_match.group(0).split('-')[1]  # 提取日期部分
    logger.error(f"文件名解析失败: {filename}")
    return None

def is_target_file(filename: str) -> bool:
    """检查是否是当日文件"""
    date_str = parse_filename(filename)
    if not date_str:
        return False
    
    try:
        file_date = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        return False
    
    return file_date == datetime.now().date()

def delete_old_files():
    """删除非当日文件和旧版本文件"""
    for csv_file in Path(DOWNLOAD_DIR).glob("*.csv"):
        if not is_target_file(csv_file.name):
            try:
                csv_file.unlink()
                logger.info(f"删除非当日文件: {csv_file.name}")
            except Exception as e:
                logger.error(f"文件删除失败: {csv_file.name} - {e}")

def extract_data_from_csv(csv_file):
    """解析CSV并返回数据列表"""
    data = []
    with open(csv_file, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ip = row.get('IP地址', '').strip()
                port = row.get('端口', '443').strip()
                colo = row.get('数据中心', '').strip()
                if not ip or not colo:
                    continue
                
                emoji = colo_emojis.get(colo, '')
                data.append(f"{ip}:{port}#{emoji}{colo}")
            except Exception as e:
                logger.error(f"解析错误: {e}")
    return data

def main():
    delete_old_files()
    
    # 代理配置（如果需要）
    proxy = None  # 根据实际情况配置 

    with TelegramClient(SESSION_NAME, API_ID, API_HASH, proxy=proxy) as client:
        try:
            channel = client.get_entity(CHANNEL)
            logger.info(f"成功接入频道: {channel.title}")
            
            # 存储最新文件信息 {filename: (timestamp, message)}
            latest_files = {}
            
            # 遍历消息筛选文件
            for msg in client.iter_messages(channel, limit=LIMIT):
                if not msg.document:
                    continue
                
                filename = next(
                    (attr.file_name for attr in msg.document.attributes 
                     if isinstance(attr, DocumentAttributeFilename)),
                    None
                )
                if not filename or not is_target_file(filename):
                    continue
                
                # 更新最新文件记录
                if filename not in latest_files or msg.date > latest_files[filename][0]:
                    latest_files[filename] = (msg.date, msg)
            
            # 下载最新文件
            for filename, (timestamp, msg) in latest_files.items():
                save_path = Path(DOWNLOAD_DIR) / filename
                if save_path.exists():
                    logger.info(f"文件已存在: {filename}")
                    continue
                
                logger.info(f"开始下载: {filename}")
                client.download_media(msg, file=save_path)
                logger.info(f"下载完成: {save_path}")
        
        except Exception as e:
            logger.error(f"Telegram通信异常: {e}")
            return
    
    # 合并数据并去重
    all_data = []
    for csv_file in Path(DOWNLOAD_DIR).glob("*.csv"):
        if is_target_file(csv_file.name):
            logger.info(f"正在处理: {csv_file.name}")
            all_data.extend(extract_data_from_csv(csv_file))
    
    # 去重并保存
    unique_data = list({line: None for line in all_data}.keys())
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(unique_data))
    logger.info(f"去重后数据已保存至: {OUTPUT_FILE} ({len(unique_data)}条)")
    
    # IP验证和Git提交
    process_ip_list(OUTPUT_FILE, f"logs/checker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", f"自动更新 {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    subprocess.run(["git", "push"])

if __name__ == '__main__':
    main()
