import os
import socket
import logging
import argparse
import glob
from typing import Dict, List, Tuple
import concurrent.futures
import subprocess
import requests
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 定义全局变量
fd = "fd"

# Telegram配置
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 自定义颜色过滤器
class ColorFilter(logging.Filter):
    def filter(self, record):
        color_map = {
            logging.DEBUG: "\033[37m",   # 灰色
            logging.INFO: "\033[92m",    # 绿色
            logging.WARNING: "\033[93m", # 黄色
            logging.ERROR: "\033[91m",   # 红色
            logging.CRITICAL: "\033[91m" # 红色
        }
        reset = "\033[0m"
        
        color = color_map.get(record.levelno, "")
        if color:
            record.msg = f"{color}{record.msg}{reset}"
        return True

# 配置日志系统
def setup_logging():
    # 创建日志目录
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # 清理旧日志文件
    for old_log in glob.glob(os.path.join(log_dir, "proxy_check_*.log")):
        try:
            os.remove(old_log)
            logging.debug(f"已删除旧日志文件: {old_log}")
        except Exception as e:
            logging.error(f"删除旧日志文件失败 {old_log}: {str(e)}")

    # 生成带时间戳的日志文件名
    log_filename = datetime.now().strftime("proxy_check_%Y%m%d_%H%M%S.log")
    log_path = os.path.join(log_dir, log_filename)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # 文件日志处理器
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # 控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.addFilter(ColorFilter())
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)

    # 移除现有处理器并添加新配置
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return log_path

def send_telegram_notification(message: str, parse_mode: str = 'Markdown'):
    """发送Telegram通知（支持代理）"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("未配置Telegram通知参数，跳过通知")
        return
    
    # 从环境变量获取代理配置
    proxy_url = os.getenv('TELEGRAM_PROXY')
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    } if proxy_url else None

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(
            api_url, 
            json=payload, 
            timeout=15,
            proxies=proxies
        )
        response.raise_for_status()
        logging.debug("Telegram通知发送成功")
    except requests.exceptions.ProxyError as e:
        logging.error(f"代理连接失败: {str(e)}")
    except requests.exceptions.ConnectTimeout:
        logging.error("连接Telegram服务器超时")
    except Exception as e:
        logging.error(f"发送Telegram通知失败: {str(e)}")

def format_telegram_message(title: str, content: str) -> str:
    """格式化Telegram消息"""
    return f"*🔍 代理检测报告 - {title}*\n\n{content}\n\n`#自动运维`"

def get_ips(host: str) -> List[str]:
    """获取域名的所有IPv4地址（自动去重）"""
    try:
        addrinfos = socket.getaddrinfo(host, None, socket.AF_INET)
        seen = set()
        ips = []
        for info in addrinfos:
            ip = info[4][0]
            if ip not in seen:
                seen.add(ip)
                ips.append(ip)
        return ips
    except socket.gaierror as e:
        logging.error(f"DNS解析失败 {host}: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"获取{host} IP地址时发生未知错误: {str(e)}")
        return []

def get_ports_for_domain(domain: str) -> List[int]:
    """从 ddns/ip/ip.txt 获取指定域名的所有端口"""
    file_path = f"ddns/{fd}/{fd}.txt"
    ports = set()
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" -> ")
                if len(parts) == 2 and parts[1] == domain:
                    ip_port = parts[0]
                    if ":" in ip_port:
                        ip, port = ip_port.split(":")
                        if port.isdigit():
                            ports.add(int(port))
    except Exception as e:
        logging.error(f"读取端口文件 {file_path} 失败: {str(e)}")
    
    return sorted(ports) if ports else [443]  # 默认使用 443 端口

def check_proxy_multi_ports(host: str, ports: List[int], timeout: float, retries: int) -> Tuple[bool, str]:
    """测试多个端口的代理连通性，只要有一个端口成功即判定成功"""
    last_error = ""
    for port in ports:
        for attempt in range(retries):
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    logging.debug(f"{host}:{port} 连接成功")
                    return True, ""
            except (socket.timeout, ConnectionRefusedError, OSError) as e:
                last_error = f"{type(e).__name__}: {str(e)}"
                logging.debug(f"{host}:{port} 第 {attempt+1} 次连接失败: {last_error}")
    
    return False, last_error

def main():
    # 初始化日志系统
    log_path = setup_logging()
    logging.info(f"日志文件已创建: {log_path}")

    parser = argparse.ArgumentParser(
        description='代理服务器健康检测工具',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('port', nargs='?', type=int, default=443,
                      help='检测端口号（默认443）')
    parser.add_argument('--timeout', type=float, default=1.0,
                       help='单次连接超时时间（秒）')
    parser.add_argument('--retries', type=int, default=3,
                       help='最大重试次数')
    args = parser.parse_args()

    proxies: Dict[str, str] = {
        "proxy.hk.616049.xyz": "HKG",
        "proxy.us.616049.xyz": "LAX",
        "proxy.de.616049.xyz": "FRA",
        "proxy.sg.616049.xyz": "SIN",
        "proxy.jp.616049.xyz": "NRT",
        "proxy.kr.616049.xyz": "ICN"
    }

    ips_cache: Dict[str, List[str]] = {}
    for host, code in proxies.items():
        ips = get_ips(host)
        ips_cache[host] = ips
        ips_formatted = '\n  - '.join(ips) if ips else '无IP地址'
        logging.info(f"[{code}] 域名解析 {host} => \n  - {ips_formatted}")

    failed_nodes: List[str] = []
    success_count = 0
    fail_count = 0

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_host = {
            executor.submit(
                check_proxy_multi_ports,
                host=host,
                ports=get_ports_for_domain(host),  # 获取多个端口
                timeout=args.timeout,
                retries=args.retries
            ): (host, code)
            for host, code in proxies.items()
        }

        for future in concurrent.futures.as_completed(future_to_host):
            host, code = future_to_host[future]
            try:
                success, error_msg = future.result()
                ips = ips_cache.get(host, [])
                ips_str = '\n  - '.join(ips) if ips else '无IP地址'
                
                if success:
                    success_count += 1
                    logging.info(f"[{code}] ✅ {host}:{args.port} 连接成功")
                    send_telegram_notification(f"[{code}] ✅ {host}:{args.port} 连接成功")
                else:
                    fail_count += 1
                    logging.error(
                        f"[{code}] ❌ {host}:{args.port} 检测失败\n"
                        f"  解析IP:\n  - {ips_str}\n"
                        f"  错误原因: {error_msg}"
                    )
                    failed_nodes.append(code)
            except Exception as e:
                logging.error(f"处理节点 {host}:{args.port} 时发生异常: {str(e)}")
                fail_count += 1
                failed_nodes.append(code)

    logging.info("\n" + "="*40)
    logging.info(f"总检测节点: {len(proxies)}")
    send_telegram_notification(f"总检测节点: {len(proxies)}")
    logging.info(f"✅ 成功节点: {success_count}")
    send_telegram_notification(f"✅ 成功节点: {success_count}")
    if fail_count > 0:
        logging.error(f"❌ 失败节点: {fail_count}")
        send_telegram_notification(f"❌ 失败节点: {fail_count}")
    else:
        logging.info("🎉 所有节点检测通过！")
        send_telegram_notification("🎉 所有节点检测通过！")

    unique_codes = sorted(set(failed_nodes))

    if unique_codes:
        codes_str = ",".join(unique_codes)
        update_msg = format_telegram_message(
            "触发节点更新", 
            f"• 失败地区: `{codes_str}`\n"
            f"• 检测端口: `{args.port}`\n"
            f"• 失败节点数: `{fail_count}/{len(proxies)}`\n"
            f"• 触发时间: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        send_telegram_notification(update_msg)
        
        logging.info("\n" + "="*40)
        logging.info(f"触发更新: {codes_str}")
        try:
            # 执行CFST更新
            result = subprocess.run(
                ['python', 'cfstfd.py', codes_str, '--no-ddns'],  # 添加参数
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 发送CFST成功通知
            success_msg = format_telegram_message(
                "更新成功",
                f"• 地区代码: `{codes_str}`\n"
                f"• 输出结果:\n```\n{result.stdout[:3800]}```"
            )
            send_telegram_notification(success_msg)
            logging.info(f"🔄 更新成功\n输出结果:\n{result.stdout}")

            # 新增CSV文件检查和DDNS执行逻辑
            codes = codes_str.split(',')
            csv_dir = os.path.join('csv', f'{fd}')
            any_valid = False
            csv_check_results = []
            
            for code in codes:
                csv_path = os.path.join(csv_dir, f"{code}.csv")
                status = ""
                try:
                    if os.path.exists(csv_path):
                        file_size = os.path.getsize(csv_path)
                        if file_size > 10:  # 基本文件大小校验
                            with open(csv_path, 'r', encoding='utf-8') as f:
                                header = f.readline()  # 读取标题行
                                first_line = f.readline()  # 读取首行数据
                                if first_line.strip():
                                    any_valid = True
                                    status = f"✅ {code}.csv 包含有效数据 ({file_size}字节)"
                                else:
                                    status = f"⚠️ {code}.csv 无有效数据"
                        else:
                            status = f"⚠️ {code}.csv 文件过小 ({file_size}字节)"
                    else:
                        status = f"❌ {code}.csv 文件不存在"
                except Exception as e:
                    status = f"⚠️ {code}.csv 检查失败: {str(e)[:50]}"
                    logging.error(f"检查CSV文件时发生错误: {str(e)}")
                csv_check_results.append(status)

            # 生成检查报告
            csv_report = "\n".join([f"• {s}" for s in csv_check_results])
            
            if any_valid:
                logging.info("\n" + "="*40)
                logging.info("检测到有效CSV文件，触发DDNS更新\n" + csv_report.replace("• ", ""))
                
                try:
                    # 执行DDNS更新
                    ddns_result = subprocess.run(
                        ['python', 'ddns/autoddnsfd.py'],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # 发送合并通知
                    combined_msg = format_telegram_message(
                        "自动维护完成",
                        f"• 更新地区: `{codes_str}`\n"
                        f"• 文件状态:\n{csv_report}\n"
                        f"• DDNS输出:\n```\n{ddns_result.stdout[:3800]}```"
                    )
                    send_telegram_notification(combined_msg)
                    logging.info(f"🔄 DDNS更新成功\n输出结果:\n{ddns_result.stdout}")
                    
                except subprocess.CalledProcessError as e:
                    error_msg = format_telegram_message(
                        "DDNS更新失败",
                        f"• 错误信息:\n```\n{e.stderr[:3800]}```"
                    )
                    send_telegram_notification(error_msg)
                    logging.error(f"⚠️ DDNS更新失败: {e.stderr}")

            else:
                logging.info("\n" + "="*40)
                logging.info("未检测到有效CSV文件，跳过DDNS更新")
                send_telegram_notification(
                    format_telegram_message(
                        "CSV文件无效",
                        f"• 未找到有效的CSV文件，跳过DDNS更新"
                    )
                )

        except subprocess.CalledProcessError as e:
            error_msg = format_telegram_message(
                "CFST更新失败",
                f"• 错误信息:\n```\n{e.stderr[:3800]}```"
            )
            send_telegram_notification(error_msg)
            logging.error(f"⚠️ CFST更新失败: {e.stderr}")

if __name__ == '__main__':
    main()