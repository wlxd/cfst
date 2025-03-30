# delete_dns.py

import argparse
import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Style

# 初始化颜色输出
init(autoreset=True)

# 加载环境变量
load_dotenv()

# 环境变量验证
EMAIL = os.environ.get("CLOUDFLARE_EMAIL")
API_KEY = os.environ.get("CLOUDFLARE_API_KEY")
ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID")

if not all([EMAIL, API_KEY, ZONE_ID]):
    raise ValueError("缺少必要的环境变量: CLOUDFLARE_EMAIL, CLOUDFLARE_API_KEY, CLOUDFLARE_ZONE_ID")

API_BASE = "https://api.cloudflare.com/client/v4/"

def build_subdomain(ip_type, country):
    """构建子域名"""
    if ip_type == 'ipv6':
        sub = f'{country}v6'
    elif ip_type == 'proxy':
        sub = f'proxy.{country}'
    else:
        sub = country
    return sub.lower()

def cf_api(method, endpoint, data=None):
    """发送Cloudflare API请求"""
    headers = {
        "X-Auth-Email": EMAIL,
        "X-Auth-Key": API_KEY,
        "Content-Type": "application/json"
    }
    url = f"{API_BASE}{endpoint}"
    print(f"{Fore.CYAN}[API]{Style.RESET_ALL} 请求: {method} {url}")
    
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

def delete_dns_records(ip_type, colos):
    """删除指定colo的DNS记录"""
    total_deleted = 0
    
    for colo in colos:
        print(f"\n{Fore.YELLOW}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[处理]{Style.RESET_ALL} 处理站点: {colo}")
        colo_deleted = 0

        country = colo  # 假设colo直接作为国家代码
        sub = build_subdomain(ip_type, country)
        domain = f"{sub}.616049.xyz"
        record_type = 'A' if ip_type in ['ipv4', 'proxy'] else 'AAAA'

        # 获取现有记录
        print(f"{Fore.YELLOW}[DNS]{Style.RESET_ALL} 查询记录: {domain} ({record_type})")
        params = {'type': record_type, 'name': domain}
        records = cf_api('GET', f'zones/{ZONE_ID}/dns_records', params).get('result', [])

        # 删除记录
        for record in records:
            if record['name'] == domain:
                colo_deleted += 1
                print(f"{Fore.RED}[删除]{Style.RESET_ALL} 类型: {record['type']}, 内容: {record['content']}")
                cf_api('DELETE', f'zones/{ZONE_ID}/dns_records/{record["id"]}')

        # 更新统计
        total_deleted += colo_deleted
        print(f"{Fore.CYAN}[统计]{Style.RESET_ALL} {colo} 删除记录: {colo_deleted}")

    print(f"\n{Fore.BLUE}=== 最终统计 ==={Style.RESET_ALL}")
    print(f"总删除记录: {total_deleted}")
    return total_deleted

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='删除指定DNS记录')
    parser.add_argument('-t', '--type', choices=['ipv4', 'ipv6', 'proxy'], required=True)
    parser.add_argument('-s', '--sub', required=True, 
                        help="逗号分隔的国家代码列表（例如：us,hk）")
    args = parser.parse_args()
    
    selected_colos = [c.strip().upper() for c in args.sub.split(',')]
    
    try:
        total = delete_dns_records(args.type, selected_colos)
        print(f"\n{Fore.GREEN}操作完成！共删除 {total} 条DNS记录{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}发生错误: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)