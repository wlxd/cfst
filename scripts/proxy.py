import os
import re
import logging
import shutil  # 用于删除非空文件夹
import subprocess  # 新增导入
from glob import glob
from dotenv import load_dotenv
from datetime import datetime
from telethon.sync import TelegramClient

# 加载环境变量
load_dotenv()

# --------------------------
# 配置区
# --------------------------
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_NAME = os.getenv('SESSION_NAME', 'default_session')  # 默认值为 default_session
CHANNEL = '@Marisa_kristi'
DOWNLOAD_DIR = 'results'
OUTPUT_FILE = 'proxy.txt'
LOG_DIR = 'logs'

# 配置日志系统
os.makedirs(LOG_DIR, exist_ok=True)

# 删除旧日志文件
for old_log in glob(os.path.join(LOG_DIR, 'proxyip_*.log')):
    try:
        os.remove(old_log)
    except Exception as e:
        pass  # 初始化阶段日志系统尚未就绪

# 创建新日志文件
log_filename = datetime.now().strftime("proxyip_%Y%m%d_%H%M%S.log")
log_path = os.path.join(LOG_DIR, log_filename)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def sanitize_filename(filename):
    """清理文件名中的特殊字符"""
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

async def main():
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        try:
            logger.info("=== 程序启动 ===")
            
            # --------------------------
            # 新增文件清理模块
            # --------------------------
            # 删除旧输出文件
            try:
                os.remove(OUTPUT_FILE)  # [1,3](@ref)
                logger.info(f"已删除旧输出文件: {OUTPUT_FILE}")
            except FileNotFoundError:
                pass  # 文件不存在无需处理
            except Exception as e:
                logger.error(f"删除输出文件失败: {str(e)}")

            # 重新创建下载目录
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            
            # 获取群组实体
            try:
                group = await client.get_entity(CHANNEL)
                logger.debug(f"成功连接频道: {CHANNEL}")
            except Exception as e:
                logger.error(f"获取群组实体失败: {str(e)}")
                return

            region_files = {}
            message_count = 0

            logger.info("开始扫描频道消息...")
            async for message in client.iter_messages(group, limit=100):
                message_count += 1
                if message.document:
                    try:
                        file_name = getattr(message.document.attributes[0], 'file_name', '')
                        file_name = sanitize_filename(file_name)
                        
                        # 使用改进正则表达式匹配文件名
                        match = re.match(r'^(.+?)(\d{8})ip.*?\.txt$', file_name)
                        if not match:
                            continue
                            
                        region, date_str = match.groups()
                        
                        try:
                            file_date = datetime.strptime(date_str, "%Y%m%d").date()
                        except ValueError as e:
                            logger.warning(f"无效日期格式: {file_name} - {str(e)}")
                            continue
                            
                        # 更新区域最新文件
                        if region not in region_files or \
                           file_date > region_files[region]['date'] or \
                           (file_date == region_files[region]['date'] and 
                            message.date > region_files[region]['msg_time']):
                            
                            region_files[region] = {
                                'date': file_date,
                                'msg_time': message.date,
                                'document': message.document,
                                'file_name': file_name
                            }
                            logger.info(f"发现新版本文件: {file_name}")

                    except Exception as e:
                        logger.error(f"处理消息异常: {str(e)}", exc_info=True)

            logger.info(f"共处理 {message_count} 条消息，找到 {len(region_files)} 个区域的最新文件")

            # 下载文件
            downloaded_files = []
            for region, info in region_files.items():
                safe_filename = sanitize_filename(info['file_name'])
                file_path = os.path.join(DOWNLOAD_DIR, safe_filename)
                try:
                    logger.info(f"开始下载: {safe_filename}")
                    await client.download_media(info['document'], file_path)
                    
                    if os.path.exists(file_path):
                        if os.path.getsize(file_path) > 0:
                            downloaded_files.append(file_path)
                            logger.info(f"下载成功: {safe_filename} ({os.path.getsize(file_path)} bytes)")
                        else:
                            os.remove(file_path)
                            logger.warning(f"空文件已删除: {safe_filename}")
                    else:
                        logger.error(f"文件未找到: {safe_filename}")
                except Exception as e:
                    logger.error(f"下载失败: {safe_filename} - {str(e)}", exc_info=True)

            # 文件合并模块（增加正则过滤）
            if downloaded_files:
                logger.info(f"开始合并 {len(downloaded_files)} 个文件")
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
                    for file_path in downloaded_files:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as infile:
                                content = infile.read().strip()
                                if content:
                                    content = re.sub(r':\d+', '', content)  # 移除端口
                                    content = re.sub(r'#.*', '', content)    # 移除注释
                                    content = re.sub(r'\n+', '\n', content)  # 合并空行
                                    outfile.write(content + '\n\n')
                                else:
                                    logger.warning(f"空内容跳过: {os.path.basename(file_path)}")
                        except Exception as e:
                            logger.error(f"文件读取失败: {file_path} - {str(e)}")
                logger.info(f"合并完成 → {OUTPUT_FILE}")

                # 正则表达式清理模块
                logger.info("开始精准清理临时文件...")
                file_pattern = re.compile(r'^.+?\d{8}ip.*\.txt$')  # 与下载匹配相同的正则
                deleted_count = 0
                error_count = 0
                
                for filename in os.listdir(DOWNLOAD_DIR):
                    file_path = os.path.join(DOWNLOAD_DIR, filename)
                    if os.path.isfile(file_path):
                        try:
                            # 严格匹配文件名格式
                            if file_pattern.match(filename):
                                os.remove(file_path)
                                logger.debug(f"正则匹配删除: {filename}")
                                deleted_count += 1
                        except Exception as e:
                            logger.error(f"删除失败 {filename}: {str(e)}")
                            error_count += 1
                            
                logger.info(f"清理完成: 成功删除 {deleted_count} 个文件，失败 {error_count} 个")

            else:
                logger.warning("没有找到可合并的文件")
           
        except Exception as e:
            logger.error(f"主程序异常: {str(e)}", exc_info=True)
        finally:
            logger.info("=== 程序结束 ===")
            
if __name__ == '__main__':
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断操作")
    except Exception as e:
        logger.error(f"运行时异常: {str(e)}", exc_info=True)