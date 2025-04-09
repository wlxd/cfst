```markdown
# Cloudflare 智能节点测速与维护系统

![GitHub](https://img.shields.io/badge/License-MIT-blue) ![Python](https://img.shields.io/badge/Python-3.8%2B-green) ![Cloudflare](https://img.shields.io/badge/Cloudflare-Workers-orange)

一个自动化管理Cloudflare节点的工具集，支持测速、DNS动态更新、健康检查与失效清理。

---

## 🌟 核心功能

- **多协议测速**  
  支持 `IPv4`/`IPv6`/`Proxy` 协议，覆盖全球主流Cloudflare节点。
- **智能DNS更新**  
  根据测速结果动态更新最优节点，支持多地区、多端口配置。
- **节点健康监控**  
  定时检测节点可用性，自动清理失效DNS记录。
- **多平台通知**  
  集成Telegram通知（直连或通过Cloudflare Worker转发）。
- **Git集成**  
  支持测速结果自动提交至Git仓库。

---

## 📁 文件说明

| 文件名          | 功能描述                                                                 |
|-----------------|------------------------------------------------------------------------|
| `_worker.js`    | Cloudflare Worker脚本，用于安全转发Telegram通知。                       |
| `cfst.py`       | 主测速脚本，支持多地区、多协议测速与DNS更新。                           |
| `colo_emojis.py`| 地区代码与国旗Emoji的映射数据。                                        |
| `ddns.py`       | 动态DNS记录管理，根据测速结果更新Cloudflare DNS。                      |
| `delete_dns.py` | 批量删除指定DNS记录的工具。                                            |
| `dns_check.py`  | 节点健康检查与自动维护脚本。                                           |
| `tg.py`         | Telegram消息通知模块，支持直连和代理发送。                             |

---

## ⚙️ 环境配置

### 依赖安装
```bash
pip install -r requirements.txt
```

### 环境变量
在项目根目录创建 `.env` 文件，配置以下参数：
```ini
# Cloudflare API
CLOUDFLARE_EMAIL = "your_cloudflare_email@example.com"
CLOUDFLARE_API_KEY = "your_cloudflare_api_key"
CLOUDFLARE_ZONE_ID = "your_zone_id"

# Telegram 通知
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
CF_WORKER_URL = "https://your-worker.subdomain.workers.dev"  # 可选
SECRET_TOKEN = "your_secure_token"  # 与_worker.js中的SECRET_TOKEN一致
```

---

## 🚀 使用指南

### 1. 启动测速任务
```bash
# 测试IPv4节点（示例）
python cfst.py -t ipv4 --colos HKG,LAX,NRT --git-commit
```
**参数说明**：
- `-t`: 协议类型 (`ipv4`/`ipv6`/`proxy`)
- `--colos`: 指定地区码（逗号分隔）
- `--git-commit`: 自动提交结果至Git仓库

---

### 2. 手动更新DNS记录
```bash
# 更新IPv4香港节点
python ddns.py -t ipv4 --colos HKG
```

---

### 3. 节点健康检查
```bash
# 检查IPv4节点状态
python dns_check.py -t ipv4 --timeout 2 --retries 3 --git-commit
```
**参数说明**：
- `--timeout`: 连接超时时间（秒）
- `--retries`: 最大重试次数

---

### 4. 删除指定DNS记录
```bash
# 删除IPv4美国节点
python delete_dns.py -t ipv4 --sub US
```

---

## 📊 通知示例

成功测速后，Telegram将收到如下格式通知：
```
🌐 CFST更新维护 - 08/25 14:30
├─ 更新区域
│  ├─ 类型: IPV4
│  ├─ ✅ 成功(3/3): HKG, LAX, NRT
│  └─ ❌ 失败(0/3): 无
└─ 自动维护
   └─ ⚡ 已触发DDNS更新
```

---

## 📝 注意事项

1. **地区码支持**  
   修改 `CFCOLO_LIST`（在 `cfst.py` 中）以扩展支持的节点地区。
2. **端口配置**  
   默认测速端口为 `443`，可在 `CLOUDFLARE_PORTS` 中修改。
3. **日志管理**  
   日志文件保存在 `logs/` 目录，按协议类型分类。

---

## 📜 开源协议

本项目基于 [MIT License](LICENSE) 开源。