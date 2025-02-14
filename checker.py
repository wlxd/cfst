import os
import socket
import subprocess
import time
import logging
import re
import sys
import glob
from datetime import datetime

# 设置日志
def setup_logger(log_file):
    """配置日志记录器"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, mode="a")
        ]
    )
    return logging.getLogger()

def is_ipv4(ip):
    """检测是否是 IPv4 地址"""
    return re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) is not None

def is_ipv6(ip):
    """检测是否是 IPv6 地址"""
    return re.match(r"^[0-9a-fA-F:]+$", ip) is not None

def extract_ip_port(line):
    """解析 IP 和端口（仅在 IPv6 被 [] 包裹时去掉 []，否则保留原样）"""
    line = line.split('#')[0].strip()  # 去掉注释
    if not line:
        return None, None

    # 解析 IPv6（带 []），格式如 [IPv6]:端口
    ipv6_match = re.match(r"^\[([0-9a-fA-F:]+)\](?::(\d+))?$", line)
    if ipv6_match:
        ip = ipv6_match.group(1)  # 去掉 []
        port = ipv6_match.group(2)
        port = int(port) if port else 443  # 默认端口 443
        return ip, port

    # 解析 IPv6（不带 []），格式如 IPv6:端口
    ipv6_match = re.match(r"^([0-9a-fA-F:]+)(?::(\d+))?$", line)
    if ipv6_match:
        ip = ipv6_match.group(1)  # 保留原样
        port = ipv6_match.group(2)
        port = int(port) if port else 443  # 默认端口 443
        return ip, port

    # 解析 IPv4，格式如 IPv4:端口
    ipv4_match = re.match(r"^([0-9.]+)(?::(\d+))?$", line)
    if ipv4_match:
        ip = ipv4_match.group(1)
        port = ipv4_match.group(2)
        port = int(port) if port else 443
        return ip, port

    return None, None

def load_ips_from_file(filename):
    """从文件中读取 IP 和端口"""
    if not os.path.exists(filename):
        logger.error(f"文件 {filename} 不存在")
        return []
    
    ips = []
    with open(filename, "r") as file:
        for line in file:
            ip, port = extract_ip_port(line)
            if ip:
                ips.append((ip, port))
            else:
                logger.warning(f"无法解析的 IP: {line.strip()}")

    logger.info(f"加载 {len(ips)} 个 IP 地址")
    return ips

def ping_ip(ip, retries=3):
    """使用 Ping 检测 IP 是否可达"""
    ip_type = 'ipv4' if is_ipv4(ip) else 'ipv6'
    cmd = ["ping", "-c", "1", ip] if ip_type == 'ipv4' else ["ping", "-6", "-c", "1", ip]
    
    for attempt in range(1, retries + 1):
        try:
            output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "ttl=" in output.stdout.lower():
                return True
            logger.warning(f"IP {ip} 第 {attempt} 次 Ping 失败")
        except Exception as e:
            logger.warning(f"IP {ip} Ping 失败: {str(e)}")
        time.sleep(1)

    return False

def tcp_check(ip, port=443, timeout=3, retries=3):
    """使用 TCP 端口检测目标是否可达"""
    for attempt in range(1, retries + 1):
        try:
            family = socket.AF_INET6 if is_ipv6(ip) else socket.AF_INET
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((ip, port))
                return True
        except (socket.timeout, ConnectionRefusedError):
            logger.warning(f"IP {ip} 端口 {port} 第 {attempt} 次 TCP 检测失败")
        except Exception as e:
            logger.warning(f"IP {ip} TCP 检测错误: {str(e)}")
        time.sleep(1)

    return False

def remove_ip_from_file(filename, ip):
    """从文件中删除指定的 IP 行"""
    with open(filename, "r") as file:
        lines = file.readlines()

    new_lines = [line for line in lines if not line.startswith(f"[{ip}]") and not line.startswith(ip)]
    if len(new_lines) != len(lines):
        with open(filename, "w") as file:
            file.writelines(new_lines)
        logger.info(f"IP {ip} 已从文件中删除")

def process_ip_list(input_file, log_file):
    """处理 IP 列表"""
    global logger
    logger = setup_logger(log_file)  # 初始化日志记录器

    ip_list = load_ips_from_file(input_file)
    
    if not ip_list:
        logger.warning("没有找到可用的 IP 地址")
        return

    for ip, port in ip_list:
        logger.info(f"检测 IP: {ip}:{port}")
        
        if not ping_ip(ip):
            logger.warning(f"IP {ip} Ping 不可达，删除")
            remove_ip_from_file(input_file, ip)
            continue

        if not tcp_check(ip, port):
            logger.warning(f"IP {ip} 端口 {port} 不可达，删除")
            remove_ip_from_file(input_file, ip)

        time.sleep(1)

def main():
    # 默认值为 cfip/xx.txt
    default_file = "port/ip.txt"
    if len(sys.argv) > 1:
        cfip_file = sys.argv[1]  # 使用传递的参数
    else:
        cfip_file = default_file  # 使用默认值
        print(f"No input file specified. Using default file: {cfip_file}")

    # 删除旧的日志文件
    log_pattern = "logs/checker_*.txt"
    old_logs = glob.glob(log_pattern)
    for log in old_logs:
        os.remove(log)
        print(f"Deleted old log file: {log}")

    # 生成新的日志文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"logs/checker_{current_time}.txt"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)  # 确保日志目录存在

    process_ip_list(cfip_file, log_file)

if __name__ == "__main__":
    main()
