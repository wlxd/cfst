"""
智能代理节点维护系统
功能：
1. 自动检测节点健康状态
2. 清理失效DNS记录
3. 触发自动更新机制
4. 多协议支持(IPv4/IPv6/Proxy)
"""

import re
import os
import sys
import json
import glob
import time
import socket
import logging
import argparse
import requests
import subprocess
from typing import List, Dict, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from py.tg import send_message_with_fallback  # 假设存在的Telegram通知模块

# 加载环境变量
load_dotenv()

# 自定义日志颜色过滤器
class ColorFilter(logging.Filter):
    """为控制台日志添加ANSI颜色"""
    def filter(self, record):
        color_map = {
            logging.DEBUG: "\033[37m",   # 灰
            logging.INFO: "\033[92m",    # 绿
            logging.WARNING: "\033[93m", # 黄
            logging.ERROR: "\033[91m",   # 红
            logging.CRITICAL: "\033[91m" # 红
        }
        reset = "\033[0m"
        record.msg = f"{color_map.get(record.levelno, '')}{record.msg}{reset}"
        return True

def setup_logging(ip_type: str) -> str:
    """配置分级日志系统
    Args:
        ip_type: 协议类型(ipv4/ipv6/proxy)
    Returns:
        日志文件路径
    """
    log_dir = os.path.join("logs", ip_type)
    os.makedirs(log_dir, exist_ok=True)

    # 清理旧日志（保留最近3个）
    log_files = sorted(glob.glob(os.path.join(log_dir, "dns_check_*.log")), reverse=True)
    for old_log in log_files[1:]:
        try:
            os.remove(old_log)
        except Exception as e:
            logging.error(f"删除旧日志失败: {str(e)}")

    # 创建新日志文件
    log_filename = datetime.now().strftime("dns_check_%Y%m%d_%H%M%S.log")
    log_path = os.path.join(log_dir, log_filename)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # 文件处理器配置
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # 控制台处理器配置
    console_handler = logging.StreamHandler()
    console_handler.addFilter(ColorFilter())
    console_handler.setFormatter(logging.Formatter('%(message)s'))

    # 更新处理器
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

def resolve_dns(host: str, ip_type: str) -> List[str]:
    """增加DNS解析重试机制"""
    family = socket.AF_INET if ip_type in ("ipv4", "proxy") else socket.AF_INET6
    for _ in range(3):  # 重试3次
        try:
            addrinfos = socket.getaddrinfo(host, None, family=family)
            ips = list({info[4][0] for info in addrinfos})
            if ips:
                return ips
        except (socket.gaierror, socket.timeout) as e:
            logging.debug(f"DNS解析重试中 {host}: {str(e)}")
            time.sleep(1)
    return []

def get_port_from_speed(ip: str, ip_type: str, colo: str) -> int:
    """从speed文件获取端口配置
    Args:
        ip: 目标IP
        ip_type: 协议类型
        colo: 区域代码(HKG/LAX等)
    Returns:
        端口号（默认443）
    """
    speed_file = os.path.join("speed", ip_type, f"{colo}.json")
    if not os.path.exists(speed_file):
        return 443  # 默认端口
    
    try:
        with open(speed_file, "r") as f:
            records = json.load(f)
            return next((r["port"] for r in records if r["ip"] == ip), 443)
    except Exception as e:
        logging.error(f"读取speed文件失败: {str(e)}")
        return 443

def test_connectivity(ip: str, port: int, timeout: float, retries: int) -> (bool, str):
    """增加端口扫描前的ICMP ping检查"""
    try:
        # 先进行ICMP ping检测
        subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except subprocess.CalledProcessError:
        return False, "ICMP不可达"

    """测试IP端口连通性，返回状态和错误信息"""
    errors = []
    for _ in range(retries):
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True, ""
        except socket.timeout as e:
            errors.append(f"超时: {str(e)}")
        except ConnectionRefusedError as e:
            errors.append(f"连接被拒绝")
        except OSError as e:
            errors.append(f"系统错误: {str(e)}")
    return False, "，".join(errors[-1:])  # 仅返回最后一次错误

def delete_cloudflare_record(host: str, ip: str, ip_type: str) -> bool:
    """删除Cloudflare DNS记录
    Args:
        host: 目标域名
        ip: 需要删除的IP
        ip_type: 协议类型
    Returns:
        是否成功删除
    """
    # 获取环境变量
    cf_email = os.getenv("CLOUDFLARE_EMAIL")
    cf_key = os.getenv("CLOUDFLARE_API_KEY")
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID")
    
    if not all([cf_email, cf_key, zone_id]):
        logging.error("缺少Cloudflare环境变量")
        return False

    record_type = "A" if ip_type in ("ipv4", "proxy") else "AAAA"
    headers = {
        "X-Auth-Email": cf_email,
        "X-Auth-Key": cf_key,
        "Content-Type": "application/json"
    }

    try:
        # 查询现有记录
        list_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
        params = {"name": host, "type": record_type}
        response = requests.get(list_url, headers=headers, params=params)
        response.raise_for_status()

        # 删除匹配记录
        deleted = False
        for record in response.json()["result"]:
            if record["content"] == ip:
                del_url = f"{list_url}/{record['id']}"
                del_res = requests.delete(del_url, headers=headers)
                if del_res.status_code == 200:
                    logging.info(f"已删除 {record_type} 记录: {ip}")
                    deleted = True
        return deleted

    except requests.HTTPError as e:
        logging.error(f"API请求失败: {e.response.text}")
        return False

    # 新增：验证记录是否已实际删除
    try:
        remaining = resolve_dns(host, ip_type)
        if ip in remaining:
            logging.warning(f"记录删除验证失败，{ip}仍存在")
            return False
        return True
    except Exception as e:
        logging.error(f"删除验证失败: {str(e)}")
        return False

def clean_data_files(ip: str, port: int, host: str, ip_type: str, colo: str):
    """清理相关数据文件
    Args:
        ip: 需要清理的IP
        port: 关联端口
        host: 域名
        ip_type: 协议类型
        colo: 区域代码
    """
    # 清理ddns文件
    ddns_file = os.path.join("ddns", ip_type, f"{colo}.txt")
    if os.path.exists(ddns_file):
        try:
            with open(ddns_file, "r+") as f:
                lines = [l for l in f if f"{ip}:{port}" not in l]
                f.seek(0)
                f.writelines(lines)
                f.truncate()
            logging.info(f"清理ddns/txt文件: 移除 {ip}:{port} 相关条目")
        except Exception as e:
            logging.error(f"清理ddns文件失败: {str(e)}")

    # 清理speed/json文件
    speed_file = os.path.join("speed", ip_type, f"{colo}.json")
    if os.path.exists(speed_file):
        try:
            with open(speed_file, "r+") as f:
                records = [r for r in json.load(f) if r["ip"] != ip]
                f.seek(0)
                json.dump(records, f, indent=2)
                f.truncate()
            logging.info(f"清理speed/json文件: 移除 {ip} 相关条目")
        except Exception as e:
            logging.error(f"清理speed/json文件失败: {str(e)}")

    # 清理speed/txt文件
    speed_txt_file = os.path.join("speed", ip_type, f"{colo}.txt")
    if os.path.exists(speed_txt_file):
        try:
            # 读取并过滤含目标IP:PORT的行
            with open(speed_txt_file, "r") as f:
                lines = [line.strip() for line in f 
                        if not line.startswith(f"{ip}:{port}#")]

            # 重写文件内容
            with open(speed_txt_file, "w") as f:
                f.write("\n".join(lines))
                
            logging.info(f"清理speed/txt文件: 移除 {ip}:{port} 相关条目")
        except Exception as e:
            logging.error(f"清理speed/txt文件失败: {str(e)}")

def trigger_cfst_update(colo: str, ip_type: str, git_commit: bool) -> bool:
    """触发CFST更新流程
    Args:
        colo: 区域代码
        ip_type: 协议类型
        git_commit: 是否提交git
    Returns:
        是否成功触发
    """
    try:
        cmd = ["python", "cfst.py", "-t", ip_type, "-c", colo]
        if git_commit:
            cmd.append("--git-commit")
        subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"CFST更新失败: {e.stderr}")
        return False

def process_host(host: str, colo: str, args) -> dict:
    """处理单个域名的维护任务（新增日志格式）"""
    def log(message: str, level=logging.INFO, indent=0):
        """带格式的日志记录"""
        prefix = f"[{host} ({colo})] "
        symbols = ["", "├─ ", "│  └─ ", "└─ "]
        message = prefix + symbols[indent] + message
        if level == logging.INFO:
            logging.info(message)
        elif level == logging.WARNING:
            logging.warning(message)
        elif level == logging.ERROR:
            logging.error(message)

    result = {"total": 0, "deleted": 0, "failed_ips": set(), "triggered": False, "node_healthy": False}
    
    try:
        log("开始处理节点维护", indent=0)
        
        # 解析DNS记录
        ips = resolve_dns(host, args.type)
        result["total"] = len(ips)
        
        if not ips:
            log("无有效DNS记录，触发紧急更新", logging.WARNING, indent=1)
            result["triggered"] = trigger_cfst_update(colo, args.type, args.git_commit)
            result["node_healthy"] = False
            return result

        log(f"解析到 {len(ips)} 个IP: {', '.join(ips)}", indent=1)
        
        remaining_ips = []
        for idx, ip in enumerate(ips):
            # 获取端口配置
            port = get_port_from_speed(ip, args.type, colo)
            
            # 测试连通性
            success, error_msg = test_connectivity(ip, port, args.timeout, args.retries)
            status = "✓" if success else f"✗ ({error_msg})"
            log(f"检测 [{ip}:{port}] {status}", indent=2 if idx < len(ips)-1 else 3)
            
            if success:
                remaining_ips.append(ip)
            else:
                # 删除DNS记录
                if delete_cloudflare_record(host, ip, args.type):
                    log(f"清理失效记录 {ip}", logging.WARNING, indent=3)
                    clean_data_files(ip, port, host, args.type, colo)
                    result["deleted"] += 1
                else:
                    log(f"删除记录失败 {ip}", logging.ERROR, indent=3)
                result["failed_ips"].add(ip)

        # 节点健康状态判断
        result["node_healthy"] = bool(remaining_ips)
        status_icon = "✓" if result["node_healthy"] else "✗"
        log(f"节点状态 {status_icon} 存活IP: {len(remaining_ips)}", 
            indent=1, 
            level=logging.INFO if result["node_healthy"] else logging.WARNING)

        # 触发更新条件
        if not remaining_ips:
            log("尝试触发自动更新...", logging.WARNING, indent=1)
            if trigger_cfst_update(colo, args.type, args.git_commit):
                log("更新任务已启动", indent=2)
                result["triggered"] = True
            else:
                log("更新触发失败", logging.ERROR, indent=2)

    except Exception as e:
        log(f"处理异常: {str(e)}", logging.ERROR, indent=1)
        result["node_healthy"] = False
    
    return result

def main():
    # 参数解析
    parser = argparse.ArgumentParser(description="智能代理节点维护系统")
    parser.add_argument("-t", "--type", required=True, choices=["ipv4", "ipv6", "proxy"])
    parser.add_argument("--timeout", type=float, default=1.5, help="连接超时(秒)")
    parser.add_argument("--retries", type=int, default=3, help="最大重试次数")
    parser.add_argument("--git-commit", action="store_true", help="自动提交git")
    args = parser.parse_args()

    # 初始化日志
    log_path = setup_logging(args.type)
    logging.info(f"启动维护任务 | 协议类型: {args.type.upper()}")

    # 获取代理配置
    proxies = PROXY_MAP[args.type]

    # 顺序执行维护任务
    report = {
        "total_nodes": len(proxies),
        "success_nodes": 0,
        "failed_colos": set(),
        "deleted_records": 0,
        "failed_ips": set(),
        "updated_colos": []
    }

    # 在报告生成前添加时间戳定义
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 顺序处理每个节点
    for idx, (host, colo) in enumerate(proxies.items()):
        res = process_host(host, colo, args)
        report["deleted_records"] += res["deleted"]
        report["failed_ips"].update(res["failed_ips"])
        if res["triggered"]:
            report["updated_colos"].append(colo)
        if res["node_healthy"]:
            report["success_nodes"] += 1
        else:
            report["failed_colos"].add(colo)
        
        # 添加分隔线（最后一个节点后不加）
        if idx < len(proxies)-1:
            logging.info("-" * 30)

    # 重构后的中文通知模板
    message = [
        f"🌐 代理节点状态报告 - {timestamp}",
        "├─ 健康检查汇总",
        f"│  ├─ 协议类型: {args.type.upper()}",
        f"│  ├─ 正常节点: {report['success_nodes']}/{report['total_nodes']}",
        f"│  └─ 故障区域: {', '.join(sorted(report['failed_colos'])) or '无'}",
        "└─ 维护操作记录",
        f"   ├─ 清理记录: {report['deleted_records']} 条失效DNS",
        f"   └─ 区域更新: {', '.join(report['updated_colos']) or '无触发'}"
    ]

    # 发送通知
    send_message_with_fallback(
        worker_url=os.getenv("CF_WORKER_URL"),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        message="\n".join(message),
        secret_token=os.getenv("SECRET_TOKEN")
    )

if __name__ == "__main__":
    main()
