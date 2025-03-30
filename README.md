```markdown
# Cloudflare 节点测速与DNS管理工具

自动化测试Cloudflare节点速度，动态更新DNS记录，并提供健康检查与通知功能。

## 功能特性

- **多协议支持**：IPv4/IPv6/Proxy
- **节点测速**：按地区码批量测试并筛选最优节点
- **DNS管理**：自动更新/删除Cloudflare DNS记录
- **健康检查**：代理连通性检测与自动修复
- **多平台通知**：Telegram实时通知测试结果
- **日志追踪**：分类存储测速日志与操作记录

## 环境要求

- Python 3.8+
- 依赖库：
  ```bash
  pip install colorama python-dotenv requests
  ```

## 快速开始

### 1. 环境配置

创建 `.env` 文件：
```ini
CLOUDFLARE_EMAIL=您的Cloudflare邮箱
CLOUDFLARE_API_KEY=您的Global API Key
CLOUDFLARE_ZONE_ID=域名区域ID
TELEGRAM_BOT_TOKEN=Telegram机器人Token
TELEGRAM_CHAT_ID=您的Chat ID
CF_WORKER_URL=Telegram消息转发Worker地址（可选）
SECRET_TOKEN=消息验证Token（可选）
```

### 2. 核心脚本说明

#### 测速主程序 (`cfst.py`)
```bash
# 基本用法
python cfst.py -t <协议类型> [--git-commit]

# 示例：测试香港、洛杉矶的IPv4节点并提交Git
python cfst.py -t ipv4 -c HKG,LAX --git-commit
```

#### 健康检查 (`ip_checker.py`)
```bash
# 检查IPv4代理状态并自动修复
python ip_checker.py -t ipv4 --git-commit
```

#### DNS管理 (`ddns.py`)
```bash
# 更新指定colo的DNS记录
python ddns.py -t ipv4 --colos HKG,LAX
```

#### 记录删除 (`delete_dns.py`)
```bash
# 删除指定国家代码的DNS记录
python delete_dns.py -t ipv4 --sub HK,US
```

### 3. 参数说明

| 参数 | 说明 |
|------|------|
| `-t/--type` | 协议类型 (ipv4/ipv6/proxy) |
| `-c/--colos` | 地区码列表（逗号分隔） |
| `--git-commit` | 自动提交结果到Git仓库 |

## 文件结构

```
.
├── cfst.py                # 主测速程序
├── ddns.py                # DNS记录更新
├── delete_dns.py          # DNS记录删除
├── ip_checker.py          # 健康检查
├── colo_emojis.py         # 地区码映射
├── tg.py                  # Telegram通知模块
├── py/                    # 工具模块
│   ├── colo_emojis.py
│   └── tg.py
├── logs/                  # 日志目录
├── results/               # 原始测速结果
└── speed/                 # 处理后的节点数据
```

## 示例场景

### 日常维护流程
1. **定时测速**  
   ```bash
   python cfst.py -t ipv4 --git-commit
   ```
2. **健康检查**  
   ```bash
   python ip_checker.py -t ipv4 --timeout 2 --retries 5
   ```
3. **查看日志**  
   ```bash
   tail -f logs/ipv4/cfst_*.log
   ```

## 注意事项

1. **权限要求**：
   - Cloudflare API需要`DNS:Edit`权限
   - 系统需要安装`curl`和`git`命令行工具

2. **特殊处理**：
   - IPv6地址会自动添加`[]`包裹
   - 代理类型使用`proxy.{国家码}`子域名格式

3. **错误处理**：
   - 测速失败时自动清理临时文件
   - API错误自动重试3次

## 许可证

MIT License
```