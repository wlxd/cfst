import argparse
import json
import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Style

from py.tg import send_telegram_message

# 初始化颜色输出
init(autoreset=True)

# 加载环境变量
load_dotenv()

# 从环境变量读取配置
EMAIL = os.environ.get("CLOUDFLARE_EMAIL")
API_KEY = os.environ.get("CLOUDFLARE_API_KEY")
ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID")

if not all([EMAIL, API_KEY, ZONE_ID]):
    raise ValueError("缺少必要的环境变量: CLOUDFLARE_EMAIL, CLOUDFLARE_API_KEY, CLOUDFLARE_ZONE_ID")

API_BASE = "https://api.cloudflare.com/client/v4/"

class OutputCollector:
    """收集控制台输出的类"""
    def __init__(self):
        self.content = []
        
    def write(self, text):
        self.content.append(text)
        
    def get_output(self):
        return "".join(self.content)

# 在 main 执行前重定向输出
original_stdout = sys.stdout
output_collector = OutputCollector()

def load_json(file_path):
    """加载JSON文件"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            print(f"{Fore.GREEN}[成功]{Style.RESET_ALL} 已加载 {len(data)} 条记录")  # 修改输出信息
            return data
    except FileNotFoundError:
        print(f"{Fore.RED}[错误]{Style.RESET_ALL} 文件未找到: {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"{Fore.RED}[错误]{Style.RESET_ALL} JSON 解码错误: {file_path}")
        return []

def get_dns_record_type(ip_type):
    """获取DNS记录类型"""
    return 'A' if ip_type in ['ipv4', 'proxy'] else 'AAAA'

def build_subdomain(ip_type, country):
    """构建子域名"""
    if ip_type == 'ipv6':
        sub = f'{country}v6'
    elif ip_type == 'proxy':
        sub = f'proxy.{country}'
    else:
        sub = country
    return sub.lower()

def update_dns_log(ip_type, colo, ip, port, sub, operation='add'):
    """更新DNS日志"""
    log_dir = f"ddns/{ip_type}"
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{log_dir}/{colo}.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if operation == 'delete':
        print(f"{Fore.RED}[删除日志]{Style.RESET_ALL} 搜索IP: {ip}:{port}")
        deleted_lines = []
        if os.path.exists(log_file):
            # 读取所有行并过滤
            with open(log_file, 'r') as f:
                lines = f.readlines()
            # 重新写入不匹配的行
            with open(log_file, 'w') as f:
                for line in lines:
                    if f"{ip}:{port}" in line:
                        deleted_line = line.strip()
                        deleted_lines.append(deleted_line)
                    else:
                        f.write(line)
            # 打印被删除的行
            if deleted_lines:
                print(f"{Fore.RED}已删除以下日志行:{Style.RESET_ALL}")
                for dl in deleted_lines:
                    print(f"  {Fore.YELLOW}{dl}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}未找到匹配的日志行{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}日志文件不存在: {log_file}{Style.RESET_ALL}")
    else:
        log_line = f"{timestamp} - {ip}:{port} -> {sub}.616049.xyz\n"
        print(f"{Fore.GREEN}[添加日志]{Style.RESET_ALL} {log_line.strip()}")
        with open(log_file, 'a') as f:
            f.write(log_line)

def cf_api(method, endpoint, data=None):
    """发送Cloudflare API请求"""
    headers = {
        "X-Auth-Email": EMAIL,
        "X-Auth-Key": API_KEY,
        "Content-Type": "application/json"
    }
    url = f"{API_BASE}{endpoint}"
    print(f"{Fore.CYAN}[API]{Style.RESET_ALL} 请求: {method} {url}")
    if data: 
        print(f"{Fore.CYAN}[API]{Style.RESET_ALL} 请求数据:\n{json.dumps(data, indent=2)}")
    
    try:
        response = requests.request(method, url, headers=headers, json=data)
        result = response.json()
        if not result.get('success'):
            errors = result.get('errors', [{'message': '未知错误'}])
            print(f"{Fore.RED}[API 错误]{Style.RESET_ALL} 操作失败: {errors[0].get('message')}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}[API 错误]{Style.RESET_ALL} 网络错误: {str(e)}")
        return {'success': False}

def manage_dns_records(ip_type, colos):
    """主逻辑"""
    total_deleted = 0  # 新增统计变量
    total_added = 0    # 新增统计变量
    
    for colo in colos:
        print(f"\n{Fore.YELLOW}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[处理]{Style.RESET_ALL} 处理站点: {colo}")
        colo_deleted = 0  # 当前colo删除计数
        colo_added = 0    # 当前colo新增计数
        
        json_path = f'speed/{ip_type}/{colo}.json'
        colo_data = load_json(json_path)
        if not colo_data:
            print(f"{Fore.YELLOW}[警告]{Style.RESET_ALL} 跳过空数据集: {json_path}")
            continue
        
        country = colo_data[0].get('country', 'XX') if colo_data else 'XX'
        sub = build_subdomain(ip_type, country)
        domain = f"{sub}.616049.xyz"
        record_type = get_dns_record_type(ip_type)
        
        print(f"{Fore.YELLOW}[DNS]{Style.RESET_ALL} 查询现有记录: {domain} ({record_type})")
        params = {'type': record_type, 'name': domain}
        records = cf_api('GET', f'zones/{ZONE_ID}/dns_records', params).get('result', [])
        
        # 删除完全匹配相同子域名的记录
        for record in records:
            if record['name'] == domain:
                colo_deleted += 1  # 计数递增
                print(f"{Fore.RED}[完全匹配]{Style.RESET_ALL} 类型: {record['type']}, 内容: {record['content']}")  # 新增详细信息
                result = cf_api('DELETE', f'zones/{ZONE_ID}/dns_records/{record["id"]}')
                if result.get('success'):
                    update_dns_log(ip_type, colo, record['content'], 443, sub, 'delete')

        for entry in colo_data:
            ip = entry.get('ip')
            port = entry.get('port', 443)
            print(f"\n{Fore.CYAN}[IP]{Style.RESET_ALL} 处理 IP: {ip}:{port}")
            
            # 创建新记录
            data = {
                "type": record_type,
                "name": domain,
                "content": ip,
                "ttl": 1
            }
            print(f"{Fore.GREEN}[创建]{Style.RESET_ALL} 添加新记录: {ip} -> {domain}")
            result = cf_api('POST', f'zones/{ZONE_ID}/dns_records', data)
            if result.get('success'):
                colo_added += 1  # 计数递增
                update_dns_log(ip_type, colo, ip, port, sub)
            else:
                print(f"{Fore.RED}[失败]{Style.RESET_ALL} 未能为 {ip} 创建记录")

        # 打印当前colo统计
        print(f"{Fore.CYAN}[统计]{Style.RESET_ALL} {colo} 删除: {colo_deleted} 条，新增: {colo_added} 条")
        total_deleted += colo_deleted
        total_added += colo_added

    # 最终统计
    print(f"\n{Fore.BLUE}=== 最终统计 ==={Style.RESET_ALL}")
    print(f"总删除记录: {total_deleted}")
    print(f"总新增记录: {total_added}")
    return total_deleted, total_added

if __name__ == '__main__':
    # 重定向标准输出
    sys.stdout = output_collector
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', choices=['ipv4', 'ipv6', 'proxy'], required=True)
    parser.add_argument('-c', '--colos', required=True, 
                        help="逗号分隔的colo地区码列表（例如：HKG,LAX）")
    args = parser.parse_args()
    
    selected_colos = [c.strip().upper() for c in args.colos.split(',')]
    
    try:
        deleted, added = manage_dns_records(args.t, selected_colos)
        
        # 构建Telegram消息
        message = (
            "🚀 DDNS更新完成\n"
            f"📌 类型: {args.t.upper()}\n"
            f"🌍 处理colo: {args.colos}\n"
            f"🗑 删除记录: {deleted}\n"
            f"✨ 新增记录: {added}\n"
            "📜 完整日志:\n" + 
            output_collector.get_output()
        )
        
        # 发送通知
        send_telegram_message(
            worker_url=os.getenv("CF_WORKER_URL"),
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            message=message,
            secret_token=os.getenv("SECRET_TOKEN")
        )
    finally:
        # 恢复标准输出并打印日志
        sys.stdout = original_stdout
        print(output_collector.get_output())