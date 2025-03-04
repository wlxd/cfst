import os
import subprocess
import csv
import sys
import random
import time
import logging
import platform
import glob
import shutil

# 获取脚本所在目录的绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))
# 将 py 目录添加到模块搜索路径
sys.path.append(os.path.join(script_dir, "py"))

from datetime import datetime
from colo_emojis import colo_emojis

# ------------------------------
# 初始化设置
# ------------------------------

# 定义全局变量
fd = "ipv6"
ip_file = "ipv6.txt"

# 在文件开头添加颜色定义
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"
COLOR_BOLD = "\033[1m"
COLOR_BLINK = "\033[5m"

# ------------------------------
# 工具函数
# ------------------------------

def print_banner():
    """打印彩色横幅"""
    banner = rf"""
{COLOR_CYAN}
   ____ _      __ _       _ __ _____        _   __     ___
  / ___| | ___/ _| | __ _| / _|___ /  __ _| |_/ /_   / _ \ _ __ ___
 | |   | |/ / |_| |/ _` | | |_ |_ \ / _` | __| '_ \ | | | | '_ ` _ \
 | |___|   <|  _| | (_| | |  _|__) | (_| | |_| | | || |_| | | | | | |
  \____|_|\_\_| |_|\__,_|_|_| |____/ \__,_|\__|_| |_(_)___/|_| |_| |_|

{COLOR_RESET}
"""
    print(banner)

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

def read_csv_mode1(file_path):
    """读取批量模式CSV文件并排序（按地区码分组，同组按延迟排序）"""
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return [], [], [], []
        
        col_index = {col: idx for idx, col in enumerate(header)}
        required = ["IP 地址", "下载速度 (MB/s)", "平均延迟", "地区码(Colo)"]
        for col in required:
            if col not in col_index:
                logging.error(f"缺少必要列：{col}")
                sys.exit(1)

        combined = []
        for row in reader:
            try:
                ip = row[col_index["IP 地址"]]
                speed = row[col_index["下载速度 (MB/s)"]]
                latency_str = row[col_index["平均延迟"]].replace('ms', '').strip()
                latency = float(latency_str)
                colo = row[col_index["地区码(Colo)"]]
                combined.append( (colo, latency, ip, speed) )
            except (ValueError, IndexError) as e:
                logging.warning(f"跳过无效行：{row}，错误：{e}")
                continue
        
        # 按地区码排序，同地区按延迟升序排列
        sorted_combined = sorted(combined, key=lambda x: (x[0], x[1]))
        
        colos = [item[0] for item in sorted_combined]
        latencies = [item[1] for item in sorted_combined]
        ips = [item[2] for item in sorted_combined]
        speeds = [item[3] for item in sorted_combined]
        
        return ips, speeds, latencies, colos

def remove_entries_by_identifier(file_path, identifier):
    """从指定文件中删除包含特定标识符的所有行，并记录删除的条目"""
    if not os.path.exists(file_path):
        return 0  # 返回删除的行数
    
    removed_count = 0
    # 读取所有行
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # 写入不包含标识符的行，并记录被删除的行
    with open(file_path, "w", encoding="utf-8") as f:
        for line in lines:
            if identifier in line:
                # 记录删除的条目
                entry = line.strip()
                logging.info(f"从文件 {file_path} 中删除条目: {entry}")
                removed_count += 1
            else:
                f.write(line)
    
    return removed_count

# ------------------------------
# 核心测试函数
# ------------------------------

def execute_cfst_test(cfst_path, cfcolo, result_file, random_port, ping_mode, dn=3, p=3):
    """执行 CloudflareSpeedTest 测试"""
    logging.info(f"正在测试区域: {cfcolo}，模式: {'HTTPing' if ping_mode == '-httping' else 'TCPing'}")

    command = [
        f"./{cfst_path}",
        "-f", ip_file,
        "-o", result_file,
        "-url", "https://cloudflare.cdn.openbsd.org/pub/OpenBSD/7.3/src.tar.gz",
        "-cfcolo", cfcolo,
        "-tl", "288",
        "-tll", "10",
        "-tlr", "0.2",
        "-n", "500",
        "-tp", str(random_port),
        "-dn", str(dn),
        "-p", str(p)
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

# ------------------------------
# 结果处理函数
# ------------------------------

def process_test_results(cfcolo, result_file, output_txt, port_txt, output_cf_txt, random_port):
    """处理单个区域的测试结果（带详细注释版）"""
    # ----------------------------
    # 初始化地区信息
    # ----------------------------
    # 从emoji字典获取地区标识（格式：[emoji, 国家代码]）
    emoji_data = colo_emojis.get(cfcolo, ['🌐', cfcolo])
    emoji_flag = emoji_data[0]      # 获取国旗emoji（如🇭🇰）
    country_code = emoji_data[1]    # 获取国家代码（如HKG）
    identifier = f"{emoji_flag}{country_code}"  # 基础标识（如🇭🇰HKG）

    # ----------------------------
    # 清理旧数据
    # ----------------------------
    print(f"{COLOR_CYAN}🧹 清理 {cfcolo} 的旧记录...{COLOR_RESET}")
    # 需要清理的文件列表
    target_files = [output_txt, port_txt]
    for file_path in target_files:
        # 删除包含该地区标识的所有条目
        removed = remove_entries_by_identifier(file_path, identifier)
        if removed > 0:
            print(f"  已清理 {file_path} 中的 {removed} 条旧记录")

    # ----------------------------
    # 读取并处理CSV数据
    # ----------------------------
    # 读取结果文件（自动处理空文件情况）
    ip_addresses, download_speeds, latencies = read_csv(result_file)
    if not ip_addresses:
        print(f"{COLOR_RED}⚠ 未找到有效IP数据，跳过处理{COLOR_RESET}")
        return

    # 组合数据并按延迟排序（升序）
    combined = list(zip(ip_addresses, download_speeds, latencies))
    combined.sort(key=lambda x: float(x[2].replace('ms', '').strip()))

    # ----------------------------
    # 生成带序号的条目（核心修改部分）
    # ----------------------------
    output_entries = []   # 存储基础IP条目（带序号）
    port_entries = []     # 存储端口条目（带序号和延迟）
    fast_ips = []         # 存储高速IP条目（带序号和速度）
    
    # 遍历排序后的结果，生成序号
    for index, (ip, speed, latency) in enumerate(combined, start=1):
        # 生成带序号的标识符（格式：🇭🇰HKG1）
        full_identifier = f"{identifier}{index}"
        
        # 构建各类条目
        output_entries.append(f"{ip}#{full_identifier}┃{latency}ms")
        port_entries.append(f"[{ip}]:{random_port}#{full_identifier}")
        
        # 筛选下载速度超过10MB/s的IP
        if float(speed) > 10:
            fast_ips.append(f"[{ip}]:{random_port}#{full_identifier}┃⚡{speed}MB/s")

    # ----------------------------
    # 写入处理结果
    # ----------------------------
    # 写入基础IP信息文件
    write_to_file(output_txt, output_entries)
    print(f"{COLOR_GREEN}✓ 已写入 {len(output_entries)} 条IP到 {output_txt}{COLOR_RESET}")
    
    # 写入端口信息文件
    write_to_file(port_txt, port_entries)
    print(f"{COLOR_GREEN}✓ 已写入 {len(port_entries)} 条端口到 {port_txt}{COLOR_RESET}")
    
    # 写入高速IP文件（如果有符合条件的记录）
    if fast_ips:
        write_to_file(output_cf_txt, fast_ips)
        print(f"{COLOR_GREEN}✓ 已写入 {len(fast_ips)} 条高速IP到 {output_cf_txt}{COLOR_RESET}")
    else:
        print(f"{COLOR_YELLOW}⚠ 未找到下载速度>10MB/s的IP，跳过写入{COLOR_RESET}")

    # ----------------------------
    # 归档结果文件
    # ----------------------------
    csv_folder = f"csv/{fd}"
    os.makedirs(csv_folder, exist_ok=True)
    
    # 生成带时间戳的归档文件名（格式：csv/ip/HKG.csv）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(csv_folder, f"{cfcolo}.csv")
    
    # 复制结果文件到归档目录
    shutil.copy(result_file, archive_path)
    print(f"{COLOR_CYAN}📦 结果已归档到 {archive_path}{COLOR_RESET}")
    
    # 清空原始结果文件
    open(result_file, "w").close()

def process_results_mode1(result_file, output_txt, port_txt, output_cf_txt, random_port):
    """处理批量测试结果（带详细注释版）"""
    # ----------------------------
    # 读取并验证数据
    # ----------------------------
    # 读取已排序的CSV数据（数据已按地区分组，同组按延迟排序）
    ip_addresses, download_speeds, latencies, colos = read_csv_mode1(result_file)
    if not ip_addresses:
        print(f"{COLOR_RED}⚠ 未找到有效IP数据，跳过处理{COLOR_RESET}")
        return

    # ----------------------------
    # 初始化处理变量
    # ----------------------------
    current_colo = None  # 当前处理的地区码（用于检测地区变化）
    index = 0            # 序号计数器（每个地区独立计数）
    output_entries = []  # 基础IP条目缓存
    port_entries = []     # 端口条目缓存
    fast_ips = []        # 高速IP缓存

    # ----------------------------
    # 遍历处理每个IP记录
    # ----------------------------
    for i in range(len(ip_addresses)):
        # 解包数据
        ip = ip_addresses[i]
        speed = download_speeds[i]
        latency = latencies[i]
        colo = colos[i]

        # ----------------------------
        # 地区变化检测（核心逻辑）
        # ----------------------------
        if colo != current_colo:
            # 检测到新地区时：
            current_colo = colo   # 更新当前地区
            index = 1             # 重置序号计数器
            print(f"{COLOR_CYAN}🔍 开始处理地区 {colo}...{COLOR_RESET}")
        else:
            # 同一地区时：
            index += 1           # 递增序号

        # ----------------------------
        # 生成标识符和条目
        # ----------------------------
        # 获取地区信息（默认使用未知标识）
        emoji_flag, country_code = colo_emojis.get(colo, ('🌐', 'XX'))
        # 生成完整标识符（格式：🇭🇰HKG1）
        full_identifier = f"{emoji_flag}{country_code}{index}"
        
        # 构建各类条目
        output_entries.append(f"{ip}#{full_identifier}┃{latency}ms")
        port_entry = f"[{ip}]:{random_port}#{full_identifier}"
        port_entries.append(port_entry)

        # 筛选高速IP（速度>10MB/s）
        if float(speed) > 10:
            fast_entry = f"[{ip}]:{random_port}#{full_identifier}┃⚡{speed}MB/s"
            fast_ips.append(fast_entry)

    # ----------------------------
    # 写入处理结果
    # ----------------------------
    # 使用追加模式写入文件（保留历史记录）
    write_to_file(output_txt, output_entries, "a")
    print(f"{COLOR_GREEN}✓ 已追加 {len(output_entries)} 条IP到 {output_txt}{COLOR_RESET}")
    
    write_to_file(port_txt, port_entries, "a")
    print(f"{COLOR_GREEN}✓ 已追加 {len(port_entries)} 条端口到 {port_txt}{COLOR_RESET}")
    
    if fast_ips:
        write_to_file(output_cf_txt, fast_ips, "a")
        print(f"{COLOR_GREEN}✓ 已追加 {len(fast_ips)} 条高速IP到 {output_cf_txt}{COLOR_RESET}")
    else:
        print(f"{COLOR_YELLOW}⚠ 未找到下载速度>10MB/s的IP，跳过写入{COLOR_RESET}")

    # ----------------------------
    # 归档结果文件
    # ----------------------------
    csv_folder = f"csv/{fd}"
    os.makedirs(csv_folder, exist_ok=True)
    
    # 生成带时间戳的归档文件名（格式：csv/ip/HKG.csv）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(csv_folder, f"{fd}.csv")
    
    # 复制结果文件到归档目录
    shutil.copy(result_file, archive_path)
    print(f"{COLOR_CYAN}📦 结果已归档到 {archive_path}{COLOR_RESET}")
    
    # 清空原始结果文件
    open(result_file, "w").close()

# ------------------------------
# 用户交互函数
# ------------------------------

def input_with_timeout(timeout):
    """等待用户输入，超时返回 None"""
    import select
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        return sys.stdin.readline().strip()
    else:
        raise TimeoutError

def get_ping_mode():
    """交互式选择 ping 模式（美化版）"""
    print(f"{COLOR_BOLD}{COLOR_YELLOW}▶ 请选择测速模式:{COLOR_RESET}")
    print(f"{COLOR_GREEN} 1{COLOR_RESET}) {COLOR_CYAN}HTTPing{COLOR_RESET} (推荐测试网站响应)")
    print(f"{COLOR_GREEN} 2{COLOR_RESET}) {COLOR_CYAN}TCPing{COLOR_RESET} (仅测试TCP握手)")
    print(f"{COLOR_YELLOW}⏳ 5秒内未选择将自动使用 HTTPing{COLOR_RESET}")

    try:
        user_input = input_with_timeout(5)
        if user_input == "2":
            print(f"{COLOR_GREEN}✓ 已选择 TCPing 模式{COLOR_RESET}")
            return ""
        else:
            print(f"{COLOR_GREEN}✓ 已选择 HTTPing 模式{COLOR_RESET}")
            return "-httping"
    except TimeoutError:
        print(f"{COLOR_RED}⏰ 选择超时，默认使用 HTTPing{COLOR_RESET}")
        return "-httping"

def get_test_mode():
    """交互式选择测试模式（美化版）"""
    print(f"\n{COLOR_BOLD}{COLOR_YELLOW}▶ 请选择测试模式:{COLOR_RESET}")
    print(f"{COLOR_GREEN}1{COLOR_RESET}) {COLOR_CYAN}批量测试（所有区域）{COLOR_RESET}")
    print(f"{COLOR_GREEN}2{COLOR_RESET}) {COLOR_CYAN}逐个测试（分区域）{COLOR_RESET}")
    print(f"{COLOR_YELLOW}⏳ 5秒内未选择将自动使用逐个测试模式{COLOR_RESET}")  # 修改提示信息

    try:
        user_input = input_with_timeout(5)
        if user_input == "1":  # 修改判断条件
            print(f"{COLOR_GREEN}✓ 已选择批量测试模式(强制使用HTTPing){COLOR_RESET}")
            return 1
        print(f"{COLOR_GREEN}✓ 已选择逐个测试模式{COLOR_RESET}")  # 修改默认选项
        return 2
    except TimeoutError:
        print(f"{COLOR_RED}⏰ 选择超时，默认使用逐个测试模式{COLOR_RESET}")  # 修改超时默认值
        return 2

# ------------------------------
# 平台相关函数
# ------------------------------

def is_running_in_github_actions():
    """检测是否在 GitHub Actions 环境中运行"""
    return os.getenv("GITHUB_ACTIONS") == "true"

# ------------------------------
# GitHub 操作函数
# ------------------------------

def execute_git_pull():
    """执行 git pull 操作"""
    try:
        logging.info("正在执行 git pull...")
        subprocess.run(["git", "pull"], check=True)
        logging.info("git pull 成功，本地仓库已更新。")
    except subprocess.CalledProcessError as e:
        logging.error(f"git pull 失败: {e}")
        sys.exit(1)

def update_to_github():
    """检测变更并提交到 GitHub"""
    try:
        logging.info("变更已提交到GitHub")
        subprocess.run(["git", "add", "."], check=True)
        commit_message = f"cfst: Update {fd}.txt on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
        print("变更已提交到GitHub。")
    except subprocess.CalledProcessError as e:
        logging.error(f"提交 GitHub 失败: {e}")
        print(f"提交 GitHub 失败: {e}")

# ------------------------------
# 主函数
# ------------------------------

def main():
    """主函数"""
    # 新增参数解析
    no_ddns = '--no-ddns' in sys.argv
    if no_ddns:
        sys.argv.remove('--no-ddns')  # 移除参数避免干扰原有逻辑

    print_banner()

    print(f"{COLOR_BOLD}{COLOR_GREEN}🚀 开始执行 Cloudflare 优选IP自动化脚本{COLOR_RESET}\n")
    
    try:
        # 清理旧日志文件
        old_logs = glob.glob(f'logs/cfst{fd}_*.log')
        for old_log in old_logs:
            try:
                os.remove(old_log)
                print(f"已删除旧日志文件: {old_log}")
            except Exception as e:
                print(f"删除旧日志文件 {old_log} 时出错: {e}")

        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f'logs/cfst{fd}_{current_time}.log'
        setup_logging(log_file)
        setup_environment()

        # 清理旧CSV文件
        logging.info("清理旧CSV文件...")
        csv_patterns = [
            os.path.join("csv", f"{fd}", "*.csv"),
            os.path.join("csv", "result.csv")
        ]
        for pattern in csv_patterns:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    logging.info(f"已删除旧CSV文件：{file_path}")
                except Exception as e:
                    logging.error(f"删除旧CSV文件 {file_path} 失败：{e}")

        result_file = f"csv/result{fd}.csv"
        output_txt = f"delay/{fd}.txt"
        port_txt = f"port/{fd}.txt"
        output_cf_txt = f"speed/{fd}.txt"

        system_arch = platform.machine().lower()
        if system_arch in ["x86_64", "amd64"]:
            cfst_path = "amd64/cfst"
        elif system_arch in ["aarch64", "arm64"]:
            cfst_path = "arm64/cfst"
        elif system_arch in ["armv7l", "armv6l"]:
            cfst_path = "armv7/cfst"
        else:
            logging.error(f"不支持的架构: {system_arch}")
            sys.exit(1)

        # execute_git_pull()

        # 获取测试模式
        test_mode = get_test_mode()
        
        cfcolo_list = ["HKG", "LAX", "NRT", "SIN", "FRA", "ICN"]
        cf_ports = [443]

        # 处理命令行参数
        if len(sys.argv) > 1:
            input_regions = sys.argv[1].upper().split(',')
            valid_regions = [r for r in input_regions if r in colo_emojis]
            if valid_regions:
                cfcolo_list = valid_regions
                logging.info(f"自定义运行区域: {cfcolo_list}")
            else:
                logging.warning(f"无效区域参数，使用默认列表: {cfcolo_list}")
        else:
            logging.info(f"使用默认区域列表: {cfcolo_list}")

        if test_mode == 1:
            ping_mode = "-httping"  # 批量模式强制使用HTTPing
            dn = 10
            p = 10
            logging.info(f"批量测试模式启用，参数设置为 dn={dn}, p={p}")
        else:
            ping_mode = get_ping_mode()  # 逐个测试模式允许选择
            dn = 3
            p = 3
                
        # 执行测试
        if test_mode == 1:
            # 批量模式，先清理所有涉及的colo的条目
            print(f"{COLOR_BOLD}{COLOR_CYAN}🧹 正在清理旧数据...{COLOR_RESET}")
            for cfcolo in cfcolo_list:
                emoji_data = colo_emojis.get(cfcolo, ['🌐', cfcolo])
                identifier = f"{emoji_data[0]}{emoji_data[1]}"
                # 需要清理的文件列表
                target_files = [output_txt, port_txt]
                for file_path in target_files:
                    removed = remove_entries_by_identifier(file_path, identifier)
                    if removed > 0:
                        print(f"{COLOR_GREEN}✓ 已清理 {cfcolo} 在 {file_path} 中的 {removed} 条旧记录{COLOR_RESET}")
            # 执行后续测试...
            random_port = random.choice(cf_ports)
            execute_cfst_test(
                cfst_path, 
                ",".join(cfcolo_list), 
                result_file, 
                random_port, 
                ping_mode,
                dn=dn,
                p=p
            )
            process_results_mode1(
                result_file, 
                output_txt, 
                port_txt, 
                output_cf_txt, 
                random_port
            )
        else:
            # 逐个测试模式
            for idx, cfcolo in enumerate(cfcolo_list, 1):
                emoji_data = colo_emojis.get(cfcolo, ['🌐', cfcolo])
                print(f"\n{COLOR_BOLD}{COLOR_YELLOW}🔧 正在处理区域 ({idx}/{len(cfcolo_list)})：{emoji_data[0]} {cfcolo}{COLOR_RESET}")
                random_port = random.choice(cf_ports)
                execute_cfst_test(
                    cfst_path, 
                    cfcolo, 
                    result_file, 
                    random_port, 
                    ping_mode,
                    dn=dn,
                    p=p
                )
                process_test_results(
                    cfcolo, 
                    result_file, 
                    output_txt, 
                    port_txt, 
                    output_cf_txt, 
                    random_port
                )
                # 询问是否退出（非 GitHub 环境）
                if not is_running_in_github_actions():
                    print(f"\n{COLOR_BOLD}{COLOR_YELLOW}▶ 是否退出执行？({COLOR_GREEN}Y{COLOR_YELLOW}/n) [5秒后自动继续]{COLOR_RESET}")
                    try:
                        user_input = input_with_timeout(5).strip().lower()
                        if user_input == 'y':
                            print(f"{COLOR_GREEN}✓ 用户选择退出，终止测试。{COLOR_RESET}")
                            break
                    except TimeoutError:
                        print(f"{COLOR_YELLOW}⏳ 超时未响应，自动继续。{COLOR_RESET}")

        # 修改调用 autoddnsv6.py 的部分
        if not no_ddns:  # 只有未指定--no-ddns时才执行
            logging.info("正在调用 autoddnsv6.py 更新 DNS 记录...")
            try:
                subprocess.run([sys.executable, "ddns/autoddnsv6.py"], check=True)
                logging.info("autoddnsv6.py 执行完成。")
            except subprocess.CalledProcessError as e:
                logging.error(f"执行 autoddnsv6.py 失败: {e}")
                sys.exit(1)

        # 调用 checker.py 并传递 port_txt
        logging.info("正在调用 checker.py 检查 IP 列表...")
        try:
            subprocess.run([sys.executable, "checker.py", port_txt], check=True)
            logging.info("checker.py 执行完成。")
        except subprocess.CalledProcessError as e:
            logging.error(f"执行 checker.py 失败: {e}")
            sys.exit(1)
        
        # 检测是否在 GitHub Actions 环境中运行
        if is_running_in_github_actions():
            logging.info("正在 GitHub Actions 环境中运行，跳过提交代码到github")
        else:    
            # 在最终提交时添加提示
            print(f"\n{COLOR_BOLD}{COLOR_GREEN}✅ 所有测试已完成！{COLOR_RESET}")
            print(f"{COLOR_CYAN}📤 正在提交结果到 GitHub...{COLOR_RESET}")
            update_to_github()
    
    except Exception as e:  # 新增的异常捕获块
        print(f"\n{COLOR_BOLD}{COLOR_RED}💥 脚本执行遇到错误：{str(e)}{COLOR_RESET}")
        logging.exception("未捕获的异常:")
        sys.exit(1)

if __name__ == "__main__":
    main()