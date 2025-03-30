import re
import os
import sys
import socket
import logging
import argparse
import glob
import subprocess
from typing import Dict, List, Tuple
import concurrent.futures
from datetime import datetime

# 获取脚本所在目录的绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(script_dir, "py"))

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
def setup_logging(ip_type: str):
    # 创建日志目录
    log_dir = os.path.join("logs", ip_type)
    os.makedirs(log_dir, exist_ok=True)

    # 清理旧日志文件
    for old_log in glob.glob(os.path.join(log_dir, "ip_check_*.log")):
        try:
            os.remove(old_log)
            logging.debug(f"已删除旧日志文件: {old_log}")
        except Exception as e:
            logging.error(f"删除旧日志文件失败 {old_log}: {str(e)}")

    # 生成带时间戳的日志文件名
    log_filename = datetime.now().strftime("ip_check_%Y%m%d_%H%M%S.log")
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

# 域名映射配置
PROXY_MAP = {
    "ipv4": {
        "hk.616049.xyz": "HKG",
        "us.616049.xyz": "LAX",
        "de.616049.xyz": "FRA",
        "sg.616049.xyz": "SIN",
        "jp.616049.xyz": "NRT",
        "kr.616049.xyz": "ICN",
        "nl.616049.xyz": "AMS"
    },
    "ipv6": {
        "hkv6.616049.xyz": "HKG",
        "usv6.616049.xyz": "LAX",
        "dev6.616049.xyz": "FRA",
        "sgv6.616049.xyz": "SIN",
        "jpv6.616049.xyz": "NRT",
        "krv6.616049.xyz": "ICN",
        "nlv6.616049.xyz": "AMS"
    },
    "proxy": {
        "proxy.hk.616049.xyz": "HKG",
        "proxy.us.616049.xyz": "LAX",
        "proxy.de.616049.xyz": "FRA",
        "proxy.sg.616049.xyz": "SIN",
        "proxy.jp.616049.xyz": "NRT",
        "proxy.kr.616049.xyz": "ICN",
        "proxy.nl.616049.xyz": "AMS"
    }
}

def get_proxies(ip_type: str) -> Dict[str, str]:
    """根据协议类型获取代理配置"""
    return PROXY_MAP.get(ip_type, PROXY_MAP["ipv4"])

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

def get_ports_for_domain(ip_type: str, colo: str, domain: str) -> List[int]:
    """从 ddns/<ip_type>/<colo>.txt 获取指定域名的所有端口"""
    file_path = os.path.join("ddns", ip_type, f"{colo}.txt")
    ports = set()
    
    try:
        if not os.path.exists(file_path):
            logging.warning(f"端口文件不存在: {file_path}")
            return [443]  # 默认端口

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                # 解析格式: "时间戳 - IP:端口 -> 域名"
                match = re.search(r"(\d+\.\d+\.\d+\.\d+):(\d+)\s+->\s+" + re.escape(domain), line)
                if match:
                    ip, port = match.group(1), match.group(2)
                    if port.isdigit():
                        ports.add(int(port))
    except Exception as e:
        logging.error(f"读取端口文件 {file_path} 失败: {str(e)}")
    
    return sorted(ports) if ports else [443]

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
    # 参数解析
    parser = argparse.ArgumentParser(
        description='代理服务器健康检测工具',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-t', '--type', required=True,
                       choices=['ipv4', 'ipv6', 'proxy'],
                       help='协议类型')
    parser.add_argument('port', nargs='?', type=int, default=443,
                      help='检测端口号（默认443）')
    parser.add_argument('--timeout', type=float, default=1.0,
                       help='单次连接超时时间（秒）')
    parser.add_argument('--retries', type=int, default=3,
                       help='最大重试次数')
    # 新增git-commit参数
    parser.add_argument('--git-commit', action='store_true',
                       help='触发CFST更新时自动提交git变更')
    args = parser.parse_args()

    # 初始化日志系统（按协议类型分目录）
    log_path = setup_logging(args.type)
    logging.info(f"日志文件已创建: {log_path}")

    # 动态获取代理配置
    proxies = get_proxies(args.type)

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
        future_to_host = {}
        for host, code in proxies.items():
            # 获取当前域名的colo对应的端口
            ports = get_ports_for_domain(args.type, code, host)
            future = executor.submit(
                check_proxy_multi_ports,
                host=host,
                ports=ports,
                timeout=args.timeout,
                retries=args.retries
            )
            future_to_host[future] = (host, code)

        for future in concurrent.futures.as_completed(future_to_host):
            host, code = future_to_host[future]
            try:
                success, error_msg = future.result()
                ips = ips_cache.get(host, [])
                ips_str = '\n  - '.join(ips) if ips else '无IP地址'
                
                if success:
                    success_count += 1
                    logging.info(f"[{code}] ✅ {host} 连接成功")
                else:
                    fail_count += 1
                    logging.error(
                        f"[{code}] ❌ {host} 检测失败\n"
                        f"  解析IP:\n  - {ips_str}\n"
                        f"  错误原因: {error_msg}"
                    )
                    failed_nodes.append(code)
            except Exception as e:
                logging.error(f"处理区域 {host} 时发生异常: {str(e)}")
                fail_count += 1
                failed_nodes.append(code)

    logging.info("\n" + "="*40)
    logging.info(f"总检测区域: {len(proxies)}")
    logging.info(f"✅ 成功区域: {success_count}")
    if fail_count > 0:
        logging.error(f"❌ 失败区域: {fail_count}")
    else:
        logging.info("🎉 所有区域检测通过！")

    unique_codes = sorted(set(failed_nodes))

    # 触发CFST更新
    if unique_codes:
        codes_str = ",".join(unique_codes)
        logging.info(f"触发更新区域: {codes_str}")
        try:
            cfst_cmd = ['python', 'cfst.py', '-t', args.type, '-c', codes_str]
            if args.git_commit:
                cfst_cmd.append('--git-commit')
            subprocess.run(
                cfst_cmd,
                check=True,
                # 关键修改：将输出直接连接到主进程的标准流
                stdout=sys.stdout,
                stderr=sys.stderr,
                text=True
            )
            logging.info("CFST更新已触发")
        except subprocess.CalledProcessError as e:
            logging.error(f"CFST更新失败，退出码: {e.returncode}")

if __name__ == '__main__':
    main()