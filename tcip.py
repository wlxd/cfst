import logging
import re
import csv
import subprocess
import sys
import socks
import os

# 获取脚本所在目录的绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))
# 将 py 目录添加到模块搜索路径
sys.path.append(os.path.join(script_dir, "py"))

from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from colo_emojis import colo_emojis
from telethon.sync import TelegramClient
from telethon.tl.types import DocumentAttributeFilename

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
DOWNLOAD_DIR = 'csv/tcip'
OUTPUT_FILE = 'port/tcip.txt'
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

def parse_filename(filename: str) -> tuple:
    """解析文件名返回前缀和日期部分"""
    # 文件名格式: XXXXX-YYYYMMDD-IP.csv，其中XXXXX可以是任意长度的数字
    date_match = re.match(r'^(\d+)-(\d{8})-IP\.csv$', filename, re.I)
    if date_match:
        logger.info(f"解析文件名成功: {filename} -> {date_match.group(0)}")
        return date_match.group(1), date_match.group(2)  # 返回前缀和日期部分
    logger.error(f"文件名解析失败: {filename}")
    return None, None

def delete_old_files():
    """删除旧CSV和日志文件"""
    # 删除CSV文件
    for csv_file in Path(DOWNLOAD_DIR).glob("*-*-IP.csv"):
        try:
            csv_file.unlink()
            logger.info(f"删除旧CSV文件: {csv_file.name}")
        except Exception as e:
            logger.error(f"CSV文件删除失败: {csv_file.name} - {e}")
    
    # 新增：删除旧日志文件
    for log_file in Path(LOG_DIR).glob("tcip_*.log"):  # 匹配所有符合命名规则的日志
        try:
            log_file.unlink()
            logger.info(f"删除旧日志: {log_file.name}")
        except Exception as e:
            logger.error(f"日志删除失败: {log_file.name} - {e}")

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

                # 修改extract_data_from_csv函数中的部分代码
                emoji_info = colo_emojis.get(colo, [])
                emoji = emoji_info[0] if emoji_info else ''
                # 获取国家代码，假设emoji_info的第二个元素是国家代码
                country_code = emoji_info[1] if len(emoji_info) > 1 else colo  # 默认使用colo以防万一
                data.append(f"{ip}:{port}#{emoji}{country_code}")
                
            except Exception as e:
                logger.error(f"解析错误: {e}")
    return data

def main():
    delete_old_files()
    
    with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        try:
            channel = client.get_entity(CHANNEL)
            logger.info(f"成功接入频道: {channel.title}")
            
            # 存储最新文件信息 {prefix: (timestamp, filename, message)}
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
                if not filename:
                    continue
                
                # 解析文件名
                prefix, date = parse_filename(filename)
                if not prefix or not date:
                    logger.error(f"文件名格式错误: {filename}")
                    continue
                
                # 更新最新文件记录
                if prefix not in latest_files or msg.date > latest_files[prefix][0]:
                    latest_files[prefix] = (msg.date, filename, msg)
            
            # 下载最新文件
            downloaded_files = set()  # 记录已下载的文件
            
            for prefix, (timestamp, filename, msg) in latest_files.items():
                save_path = Path(DOWNLOAD_DIR) / filename
                if save_path.exists():
                    logger.info(f"文件已存在: {filename}")
                    downloaded_files.add(filename)
                    continue
                
                logger.info(f"开始下载: {filename}")
                client.download_media(msg, file=save_path)
                logger.info(f"下载完成: {save_path}")
                downloaded_files.add(filename)
                
        except Exception as e:
            logger.error(f"Telegram通信异常: {e}")
            return
    
    # 合并数据并去重
    all_data = []
    for csv_file in Path(DOWNLOAD_DIR).glob("*.csv"):
        logger.info(f"正在处理: {csv_file.name}")
        all_data.extend(extract_data_from_csv(csv_file))
    
    # 去重并保存
    unique_data = list({line: None for line in all_data}.keys())

    # 新增：过滤排除特定国家代码
    excluded_countries = {'GB', 'IN', 'FR', 'BR', 'NL', 'SE'}  # 需要排除的国家代码
    filtered_data = []
    for line in unique_data:
        parts = line.split('#')
        if len(parts) < 2:
            continue  # 忽略格式不正确的行
        country_part = parts[1]
        # 提取国家代码（两位大写字母）
        country_code_match = re.search(r'([A-Z]{2})$', country_part)
        if country_code_match:
            country_code = country_code_match.group(1)
            if country_code in excluded_countries:
                logger.info(f"排除行（国家代码 {country_code}）: {line}")
                continue
        filtered_data.append(line)
    
    # 保存过滤后的数据
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(filtered_data))
    logger.info(f"过滤后数据已保存至: {OUTPUT_FILE} ({len(filtered_data)}条)")

    # 调用 checker.py 并传递 cfip_file
    logging.info("正在调用 checker.py 检查 IP 列表...")
    try:
        subprocess.run([sys.executable, "checker.py", OUTPUT_FILE], check=True)
        logging.info("checker.py 执行完成。")
    except subprocess.CalledProcessError as e:
        logging.error(f"执行 checker.py 失败: {e}")
        sys.exit(1)

    # 检测是否在 GitHub Actions 中运行
    if os.getenv('GITHUB_ACTIONS') != 'true':
        # 执行 IP 验证和 Git 提交操作
        try:               
            logging.info("开始执行 Git 操作...")
            
            # 添加文件到暂存区
            logging.info("执行 git add...")
            subprocess.run(["git", "add", "."], check=True)
            
            # 提交更改
            commit_message = f"cfst: Update tcip.txt on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            logging.info(f"执行 git commit: {commit_message}")
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            
            # 推送更改到远程仓库
            logging.info("执行 git push...")
            subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Git 操作失败: {e}")
    else:
        logging.info("检测到在 GitHub Actions 中运行，跳过 IP 验证和提交代码步骤。")
    
if __name__ == '__main__':
    main()