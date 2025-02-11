import socket
import requests
import dns.resolver  # 解析 DNS
from urllib.parse import urlparse
import subprocess
import os
import glob
from datetime import datetime

# 日志文件夹路径
log_folder = "logs"
# 日志文件名（包含日期和时间）
log_file_name = f"gfw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
# 日志文件完整路径
log_file_path = os.path.join(log_folder, log_file_name)

# 删除旧的日志文件
old_log_files = glob.glob(os.path.join(log_folder, "gfw_*.log"))
for old_log in old_log_files:
    os.remove(old_log)

# 确保日志文件夹存在
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

# 日志写入函数
def log(message):
    with open(log_file_path, "a") as log_file:
        log_file.write(message + "\n")

# 打印并记录日志的函数
def print_and_log(message):
    print(message)
    log(message)
    
CHINA_DNS = "114.114.114.114"  # 国内 DNS 服务器
GLOBAL_DNS = "8.8.8.8"  # 谷歌 DNS

# 要检测的常见端口
PORTS_TO_CHECK = [80, 443, 2053, 2083, 2087, 2096, 8443]

def resolve_with_dns(hostname, dns_server):
    """使用指定 DNS 服务器解析域名 IP，修复 Termux 无 /etc/resolv.conf 问题"""
    resolver = dns.resolver.Resolver(configure=False)  # 关键：避免读取 /etc/resolv.conf
    resolver.nameservers = [dns_server]  # 手动指定 DNS 服务器
    try:
        answers = resolver.resolve(hostname)
        ip_list = [ip.address for ip in answers]
        return True, ", ".join(ip_list) if ip_list else "未解析到 IP"
    except dns.resolver.NXDOMAIN:
        return False, "域名不存在"
    except dns.resolver.NoAnswer:
        return False, "无响应"
    except dns.exception.DNSException as e:
        return False, f"解析错误: {str(e)}"

def check_tcp(ip, port, timeout=5):
    """检测 TCP 端口是否可连接"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))
        return True, f"端口 {port} 可连接"
    except (socket.timeout, ConnectionRefusedError):
        return False, f"端口 {port} 连接失败"
    except Exception as e:
        return False, f"端口 {port} 错误: {str(e)}"

def check_http(url, timeout=5):
    """检测 HTTP 访问是否正常"""
    try:
        response = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code >= 400:
            return False, f"HTTP错误: {response.status_code}"
        return True, "HTTP访问正常"
    except requests.exceptions.SSLError:
        return False, "SSL证书错误"
    except requests.exceptions.ConnectionError as e:
        if "Connection reset" in str(e):
            return False, "连接被重置（可能被墙）"
        return False, "HTTP连接失败"
    except Exception as e:
        return False, f"HTTP未知错误: {str(e)}"

def ping_host(hostname, retries=3):
    """对主机进行PING测试，重试多次"""
    for attempt in range(retries):
        try:
            # 使用系统命令进行PING测试
            output = subprocess.check_output(
                ["ping", "-c", "1", "-W", "2", hostname],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            return True, "✅ PING成功"
        except subprocess.CalledProcessError as e:
            if attempt == retries - 1:  # 最后一次重试失败
                return False, "❌ PING失败"
            continue  # 重试
    return False, "❌ PING失败"

def check_url(url):
    """综合检测域名是否被墙"""
    parsed = urlparse(url.strip())  # 确保去除空格，避免错误
    if not parsed.scheme or not parsed.hostname:
        print_and_log("无效的 URL")
        return False, "无效的 URL"

    hostname = parsed.hostname
    print_and_log(f"\n检测URL: {url}")

    # 1. DNS 解析检测
    china_dns_ok, china_dns_result = resolve_with_dns(hostname, CHINA_DNS)
    global_dns_ok, global_dns_result = resolve_with_dns(hostname, GLOBAL_DNS)

    if not china_dns_ok and global_dns_ok:
        print_and_log(f"  ⚠️ DNS污染: 国内无法解析, 国外解析成功")
        return False, "DNS污染"

    # 显示解析出的 IP 地址
    china_ip = china_dns_result if china_dns_ok else "无"
    global_ip = global_dns_result if global_dns_ok else "无"

    print_and_log(f"  ✅ 国内DNS解析: {china_ip}")
    print_and_log(f"  ✅ 国外DNS解析: {global_ip}")

    # 2. 获取 IP 并测试 TCP 端口
    try:
        ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        print_and_log(f"  ❌ DNS解析失败: 无法解析 {hostname}")
        return False, "DNS解析失败"

    success_ports = []  # 用于记录成功连接的端口
    for port in PORTS_TO_CHECK:
        tcp_ok, tcp_result = check_tcp(ip, port)
        if tcp_ok:
            success_ports.append(f"端口 {port} 可连接")
            break  # 只显示第一个成功的端口

    if success_ports:
        print_and_log(f"  ✅ {success_ports[0]}")
    else:
        print_and_log("  ❌ 所有端口连接失败")

    # 3. HTTP 访问检测
    http_ok, http_result = check_http(url)
    if http_ok:
        print_and_log(f"  ✅ HTTP访问正常")
        return True, "可正常访问"
    else:
        # HTTP访问失败后进行PING测试
        ping_ok, ping_result = ping_host(hostname, retries=3)
        print_and_log(f"  {ping_result}")
        return ping_ok, ping_result

# 测试 URL 列表
url_list = [
    "https://us.616049.xyz",
    "https://sjc.616049.xyz",
    "https://sea.616049.xyz",
    "https://lax.616049.xyz",
    "https://de.616049.xyz",
    "https://fra.616049.xyz",
    "https://hk.616049.xyz",
    "https://hkg.616049.xyz",
    "https://jp.616049.xyz",
    "https://nrt.616049.xyz",
    "https://sg.616049.xyz",
    "https://sin.616049.xyz",
    "https://kr.616049.xyz",
    "https://icn.616049.xyz",
    "https://proxy.us.616049.xyz",
    "https://proxy.sjc.616049.xyz",
    "https://proxy.sea.616049.xyz",
    "https://proxy.lax.616049.xyz",
    "https://proxy.de.616049.xyz",
    "https://proxy.fra.616049.xyz",
    "https://proxy.hk.616049.xyz",
    "https://proxy.hkg.616049.xyz",
    "https://proxy.jp.616049.xyz",
    "https://proxy.nrt.616049.xyz",
    "https://proxy.sg.616049.xyz",
    "https://proxy.sin.616049.xyz",
    "https://proxy.kr.616049.xyz",
    "https://proxy.icn.616049.xyz",
]

# 执行检测
for url in url_list:
    result, reason = check_url(url)
    status = "✅ 正常" if result else "❌ 可能被墙"
    print_and_log(f"{url.ljust(30)} {status.ljust(10)} {reason}")
    print_and_log('-' * 60)  # 分隔符
