import os
import subprocess
import csv
import sys
import random
import time
import logging
import platform
import hashlib
import glob
import shutil
from datetime import datetime
from colo_emojis import colo_emojis

# ------------------------------
# 初始化设置
# ------------------------------

def setup_logging(log_file):
    """配置日志，将日志同时输出到控制台和文件"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode="a", encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )

def setup_environment():
    """设置脚本运行环境"""
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    os.chdir(script_dir)
    create_directories(["csv", "logs", "port", "cfip", "speed"])

def remove_file(file_path):
    """删除指定路径的文件"""
    if os.path.exists(file_path):
        os.remove(file_path)
        logging.info(f"已删除 {file_path} 文件。")

def create_directories(directories):
    """创建所需的目录"""
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logging.info(f"已创建或确认目录 {directory} 存在。")

def download_and_extract(url, target_path):
    """下载并解压文件"""
    downloaded_file = url.split("/")[-1]
    logging.info(f"正在下载文件: {downloaded_file}")
    subprocess.run(["wget", "-N", url], check=True)
    
    if downloaded_file.endswith(".tar.gz"):
        try:
            subprocess.run(["tar", "-zxf", downloaded_file], check=True)
            logging.info(f"已成功解压: {downloaded_file}")
        except subprocess.CalledProcessError as e:
            logging.error(f"解压失败: {e}")
            sys.exit(1)
    elif downloaded_file.endswith(".zip"):
        try:
            subprocess.run(["unzip", downloaded_file], check=True)
            logging.info(f"已成功解压: {downloaded_file}")
        except subprocess.CalledProcessError as e:
            logging.error(f"解压失败: {e}")
            sys.exit(1)
    else:
        logging.error("无法识别的压缩文件格式！")
        sys.exit(1)
    
    remove_file(downloaded_file)
    subprocess.run(["mv", "CloudflareST", target_path], check=True)
    subprocess.run(["chmod", "+x", target_path], check=True)

def write_to_file(file_path, data, mode="a"):
    """将数据写入文件"""
    with open(file_path, mode=mode, encoding="utf-8") as file:
        for item in data:
            file.write(item + "\n")
            logging.info(f"写入: {item}")

def read_csv(file_path):
    """读取CSV文件并返回数据（IP、下载速度、平均延迟）"""
    if os.path.getsize(file_path) == 0:
        logging.warning(f"文件 {file_path} 为空，跳过读取。")
        return None, None, None
    
    with open(file_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        try:
            header = next(reader)
        except StopIteration:
            logging.warning(f"文件 {file_path} 格式不正确或为空，跳过读取。")
            return None, None, None
        
        # 检查必要列是否存在
        required_columns = ["下载速度 (MB/s)", "平均延迟"]
        for col in required_columns:
            if col not in header:
                logging.error(f"无法找到 {col} 列，请检查 CSV 文件表头。")
                sys.exit(1)
        
        speed_index = header.index("下载速度 (MB/s)")
        latency_index = header.index("平均延迟")
        ip_addresses = []
        download_speeds = []
        latencies = []
        
        for row in reader:
            ip_addresses.append(row[0])
            download_speeds.append(row[speed_index])
            latencies.append(row[latency_index])
            if len(ip_addresses) >= 10:
                break
        
        return ip_addresses, download_speeds, latencies

def execute_git_pull():
    """执行 git pull 操作"""
    try:
        logging.info("正在执行 git pull...")
        subprocess.run(["git", "pull"], check=True)
        logging.info("git pull 成功，本地仓库已更新。")
    except subprocess.CalledProcessError as e:
        logging.error(f"git pull 失败: {e}")
        sys.exit(1)

def execute_cfst_test(cfst_path, cfcolo, result_file, random_port, ping_mode):
    """执行 CloudflareSpeedTest 测试"""
    logging.info(f"正在测试区域: {cfcolo}，模式: {'HTTPing' if ping_mode == '-httping' else 'TCPing'}")

    command = [
        f"./{cfst_path}",
        "-f", "proxy.txt",
        "-o", result_file,
        "-url", "https://cloudflare.cdn.openbsd.org/pub/OpenBSD/7.3/src.tar.gz",
        "-cfcolo", cfcolo,
        "-tl", "200",
        "-tll", "5",
        "-tlr", "0.2",
        "-tp", str(random_port),
        "-dn", "5",
        "-p", "5"
    ]

    if ping_mode:  # 只有在选择 HTTPing 时才加 `-httping`
        command.append(ping_mode)

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"CloudflareSpeedTest 测试失败: {e}")
        sys.exit(1)
    
    if not os.path.exists(result_file):
        logging.warning(f"未生成 {result_file} 文件，正在新建一个空的 {result_file} 文件。")
        with open(result_file, "w") as file:
            file.write("")
        logging.info(f"已新建 {result_file} 文件。")
    else:
        logging.info(f"{result_file} 文件已存在，无需新建。")

def process_test_results(cfcolo, result_file, output_txt, port_txt, output_cf_txt, random_port):

    # 删除 {cfcolo}-FD.csv 文件，路径为 csv 文件夹
    csv_folder = "csv/fd"
    file_to_delete = os.path.join(csv_folder, f"{cfcolo}-FD.csv")
    
    try:
        os.remove(file_to_delete)
        logging.info(f"已成功删除文件 {file_to_delete}")
    except FileNotFoundError:
        logging.warning(f"文件 {file_to_delete} 不存在，无法删除")
    except Exception as e:
        logging.error(f"删除文件 {file_to_delete} 时发生错误: {e}")
        
    """处理测试结果并写入文件（增加延迟信息）"""
    ip_addresses, download_speeds, latencies = read_csv(result_file)
    
    if not ip_addresses:
        return
    
    logging.info(f"区域 {cfcolo} 提取到的 IP 地址数量: {len(ip_addresses)}")
    
    # 写入基础IP信息（保持不变）
    write_to_file(output_txt, [f"{ip}#{colo_emojis.get(cfcolo, '☁️')}{cfcolo}" for ip in ip_addresses])
    logging.info(f"提取的 IP 地址和 colo 信息已保存到 {output_txt}") 
       
    # 新增延迟信息写入 port.txt（格式：IP:端口#地区┃延迟）
    port_entries = [
        f"{ip}:{random_port}#{colo_emojis.get(cfcolo, '☁️')}{cfcolo}┃{latency}ms"
        for ip, latency in zip(ip_addresses, latencies)
    ]
    write_to_file(port_txt, port_entries)
    logging.info(f"IP地址、端口、colo信息及延迟已追加到 {port_txt}")
    
    # 筛选高速IP（保持不变）
    fast_ips = [
        f"{ip}:{random_port}#{colo_emojis.get(cfcolo, '☁️')}{cfcolo}┃⚡{speed}(MB/s)"
        for ip, speed in zip(ip_addresses, download_speeds)
        if float(speed) > 10
    ]
    if fast_ips:
        write_to_file(output_cf_txt, fast_ips)
        logging.info(f"筛选下载速度大于 10 MB/s 的 IP 已追加到 {output_cf_txt}")
    else:
        logging.info(f"区域 {cfcolo} 未找到下载速度大于 10 MB/s 的 IP，跳过写入操作。")

    # 确保 csv 文件夹存在
    csv_folder = "csv/fd"
    os.makedirs(csv_folder, exist_ok=True)
    
    # 在清空 result_file 前，先复制文件到指定路径
    cfcolo_csv = os.path.join(csv_folder, f"{cfcolo}-FD.csv")
    shutil.copy(result_file, cfcolo_csv)
    logging.info(f"已将 {result_file} 复制为 {cfcolo_csv}")

    open(result_file, "w").close()
    logging.info(f"已清空 {result_file} 文件。")

def calculate_md5(file_path):
    """计算文件的 MD5 哈希值"""
    if not os.path.exists(file_path):
        return None
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def update_to_github(cfip_file, original_md5, new_md5):
    """检测 MD5 变化并提交到 GitHub"""
    if original_md5 == new_md5:
        logging.info("fd.txt 文件内容未变化，跳过 GitHub 提交。")
        print("文件内容未发生变化，跳过 GitHub 提交。")
        return

    try:
        logging.info("变更已提交到GitHub")
        subprocess.run(["git", "add", "."], check=True)
        commit_message = f"cfst: Update fd.txt on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("变更已提交到 GitHub。")
    except subprocess.CalledProcessError as e:
        logging.error(f"提交 GitHub 失败: {e}")
        print(f"提交 GitHub 失败: {e}")

def is_running_in_github_actions():
    """检测是否在 GitHub Actions 环境中运行"""
    return "GITHUB_ACTIONS" in os.environ

def get_ping_mode():
    """交互式选择 ping 模式，5 秒无操作默认使用 TCPing"""
    print("请选择 CloudflareSpeedTest 运行模式:")
    print("1. TCPing (默认，无参数)")
    print("2. HTTPing (-httping)")
    print("（5 秒内未选择将默认使用 TCPing）")

    try:
        user_input = input_with_timeout(5)
        if user_input == "2":
            return "-httping"  # 仅在选择 2 时添加参数
        else:
            return ""  # 默认使用 tcping，不加参数
    except TimeoutError:
        print("超时，默认使用 TCPing")
        return ""  # 默认情况下不加 -httping 参数

def input_with_timeout(timeout):
    """等待用户输入，超时返回 None"""
    import select
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        return sys.stdin.readline().strip()
    else:
        raise TimeoutError

def main():
    """主函数"""
    try:
        # 删除旧的日志文件
        old_logs = glob.glob('logs/cfstfd_*.log')
        for old_log in old_logs:
            try:
                os.remove(old_log)
                print(f"已删除旧日志文件: {old_log}")
            except Exception as e:
                print(f"删除旧日志文件 {old_log} 时出错: {e}")
                logging.error(f"删除旧日志文件 {old_log} 时出错: {e}")

        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f'logs/cfstfd_{current_time}.log'
        setup_logging(log_file)
        setup_environment()

        result_file = "csv/resultfd.csv"
        cfip_file = "cfip/fd.txt"
        output_txt = "cfip/fd.txt"
        port_txt = "port/fd.txt"
        output_cf_txt = "speed/fd.txt"

        # 计算原始 MD5
        original_md5 = calculate_md5(cfip_file)
        logging.info(f"原始 MD5: {original_md5 if original_md5 else '文件不存在'}")

        open(cfip_file, "w").close()
        logging.info(f"已清空 {cfip_file} 文件。")
        open(port_txt, "w").close()
        logging.info(f"已清空 {port_txt} 文件。")

        system_arch = platform.machine().lower()
        if system_arch in ["x86_64", "amd64"]:
            download_url = "https://github.com/XIU2/CloudflareSpeedTest/releases/download/v2.2.5/CloudflareST_linux_amd64.tar.gz"
            cfst_path = "amd64/cfst"
        elif system_arch in ["aarch64", "arm64"]:
            download_url = "https://github.com/XIU2/CloudflareSpeedTest/releases/download/v2.2.5/CloudflareST_linux_arm64.tar.gz"
            cfst_path = "arm64/cfst"
        elif system_arch in ["armv7l", "armv6l"]:
            download_url = "https://github.com/XIU2/CloudflareSpeedTest/releases/download/v2.2.5/CloudflareST_linux_armv7.tar.gz"
            cfst_path = "armv7/cfst"
        else:
            logging.error(f"不支持的架构: {system_arch}")
            sys.exit(1)

        logging.info(f"检测到系统架构为 {system_arch}，将下载对应的 CloudflareST 版本: {download_url}")

        execute_git_pull()

        # +++ 新增下载 proxy.txt 的代码 +++
        logging.info("正在下载最新 proxy.txt 文件...")
        proxy_url = "https://ipdb.api.030101.xyz/?type=proxy&down=true"
        try:
            subprocess.run(
                ["wget", "-O", "proxy.txt", proxy_url],  # -O 参数强制覆盖文件
                check=True,
                stdout=subprocess.DEVNULL,  # 隐藏控制台输出
                stderr=subprocess.DEVNULL
            )
            logging.info("proxy.txt 下载成功，已覆盖旧文件")
        except subprocess.CalledProcessError as e:
            logging.error(f"proxy.txt 下载失败: {e}")
            sys.exit(1)
        # +++ 新增代码结束 +++
        if not os.path.exists(cfst_path):
            download_and_extract(download_url, cfst_path)
        
        # 让用户选择 TCPing 或 HTTPing 模式
        ping_mode = get_ping_mode()

        cfcolo_list = ["HKG", "SJC", "SEA", "LAX", "FRA"]
        cf_ports = [443]

        for cfcolo in cfcolo_list:
            random_port = random.choice(cf_ports)
            execute_cfst_test(cfst_path, cfcolo, result_file, random_port, ping_mode)
            process_test_results(cfcolo, result_file, output_txt, port_txt, output_cf_txt, random_port)

        # 计算新的 MD5
        new_md5 = calculate_md5(cfip_file)
        logging.info(f"新 MD5: {new_md5 if new_md5 else '文件不存在'}")

        # 检测是否在 GitHub Actions 环境中运行
        if is_running_in_github_actions():
            logging.info("正在 GitHub Actions 环境中运行，跳过调用 checker.py 和 dns_checker.py")
        else:
            # 调用 checker.py 并传递 cfip_file
            logging.info("正在调用 checker.py 检查 IP 列表...")
            try:
                subprocess.run([sys.executable, "checker.py", cfip_file], check=True)
                logging.info("checker.py 执行完成。")
            except subprocess.CalledProcessError as e:
                logging.error(f"执行 checker.py 失败: {e}")
                sys.exit(1)

            # 执行 dns_checker.py
            logging.info("正在执行 DNS 记录检查脚本...")
            try:
                subprocess.run([sys.executable, "dns_checker.py"], check=True)
                logging.info("DNS 记录检查脚本执行完成。")
            except subprocess.CalledProcessError as e:
                logging.error(f"执行 DNS 检查脚本失败: {e}")
                sys.exit(1)
    
            logging.info("脚本执行完成。")
            update_to_github(cfip_file, original_md5, new_md5)
    
    except Exception as e:
        logging.exception("脚本执行过程中发生未捕获的异常:")
        sys.exit(1)

if __name__ == "__main__":
    main()