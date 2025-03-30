import requests
from threading import Lock
from urllib.parse import urlparse
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
results_lock = Lock()
results = defaultdict(set)
def send_request(url, proxies=None):
    try: return requests.get(url, proxies=proxies, timeout=15, headers=REQUEST_HEADERS)
    except: return None
def extract_country(response_text):
    try: return response_text.strip().split()[1]
    except IndexError: return None
def process_single_url(proxy_url):
    try:
        parsed = urlparse(proxy_url)
        if not parsed.scheme: return
        scheme = parsed.scheme.lower()
        proxies = {"http": proxy_url, "https": proxy_url}
        if not (resp := send_request("https://ping0.cc/geo", proxies=proxies)): return
        if resp.status_code != 200: return
        if not (country := extract_country(resp.text)): return
        entry = f"{proxy_url}#{country}"
        with results_lock: results[scheme].add(entry)
        print(f"[✓] {proxy_url[:40]:<40} => {country}")
    except Exception: pass
def show_country_stats():
    all_countries = [entry.split('#', 1)[1] for entries in results.values() for entry in entries]
    if not all_countries: print("\n没有检测到有效的国家信息!"); return
    country_counts = Counter(all_countries)
    total = len(all_countries)
    sorted_countries = country_counts.most_common()
    print("\n国家统计结果：")
    print(f"总有效代理数量: {total} ==>")
    max_name_len = max(len(c[0]) for c in sorted_countries)
    for country, count in sorted_countries:
        print(f"     [♚] {country.ljust(max_name_len)} : {count} ({(count / total) * 100:.2f}%).")
def process_urls(input_file, max_workers=500):
    with open(input_file, "r") as f: urls = {line.strip() for line in f if line.strip()}
    with ThreadPoolExecutor(max_workers=max_workers) as executor: executor.map(process_single_url, urls)
    for scheme, entries in results.items():
        with open(f"{scheme}.txt", "w", encoding="utf-8") as f: f.write("\n".join(sorted(entries)))
        print(f"[+] {scheme}.txt 已写入 {len(entries)} 条记录!")
    show_country_stats()
if __name__ == "__main__":
    input_path = input("请输入代理URL文件路径：").strip()
    process_urls(input_path)