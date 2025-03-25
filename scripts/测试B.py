import time, urllib3, requests, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
COLOR_P = "\033[1;95m"; COLOR_B = "\033[1;94m"; COLOR_G = "\033[1;92m"; COLOR_Y = "\033[1;93m"; RST = "\033[0m"
counters = {'valid': 0, 'processed': 0, 'total': 0}; lock = threading.Lock(); urllib3.disable_warnings()
def get_proxies(path):
    with open(path) as f: return [f"{p}://{i}:{po}" for i, po, p in (l.strip().split(':') for l in f if l.strip())]
def check_proxy(proxy):
    try:
       global counters; resp = requests.get("https://ping0.cc/geo", proxies={"https": proxy, "http": proxy}, timeout=5, verify=False)
       if resp.ok and len(resp.text.splitlines()) == 4:
          with lock: counters['valid'] += 1
          return proxy
    except Exception: pass
    finally:
        with lock:
            counters['processed'] += 1
            percent = counters['processed'] / counters['total'] * 100 if counters['total'] else 0
            output = [
                f"{COLOR_P}有效代理数: {COLOR_B}{counters['valid']:03d}{COLOR_P} 个代理.{RST}",
                f"Ⅰ{COLOR_G} 进度: {COLOR_Y}{counters['processed']:03d}",
                f"{COLOR_G}/{COLOR_Y}{counters['total']:03d} ",
                f"{COLOR_G}({COLOR_Y}{percent:05.2f}%{COLOR_G}).{RST}",
            ]
            print("".join(output), end='\r')
    return None
def validate(proxies):
    with ThreadPoolExecutor(500) as ex:
        futures = (ex.submit(check_proxy, p) for p in proxies)
        return [f.result() for f in as_completed(futures) if f.result()]
if __name__ == "__main__":
    proxies = get_proxies(input("请输入代理文件路径: ").strip()); start_time = time.time()
    counters.update(total=len(proxies), valid=0, processed=0); valid_proxies = validate(proxies)
    if valid_proxies: counters.update(total=len(valid_proxies), valid=0, processed=0); valid_proxies = validate(valid_proxies)
    with open("proxies.txt", "w") as f: f.write("\n".join(valid_proxies))
    print(f"\n{COLOR_P}最终有效代理数: {COLOR_B}{counters['valid']}{COLOR_P} 个.{RST}"
         f"\n{COLOR_B}总耗时: {COLOR_Y}{time.time() - start_time:.2f} 秒.{RST}")