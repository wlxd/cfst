```markdown
# Cloudflare IP 优选与代理管理工具集

## 📖 项目简介
本项目包含多个自动化脚本，用于Cloudflare IP优选、代理管理、DNS自动更新及健康检测。支持Telegram通知、多地区测速、IPv6适配等功能，适用于CDN优化和代理服务器维护。

---

## 🛠️ 功能列表
- **IP优选**：自动抓取并测试Cloudflare各节点IP（支持IPv4/IPv6）
- **代理管理**：从Telegram频道获取代理IP并生成配置文件
- **健康检测**：实时检测节点连通性，自动触发更新
- **DNS同步**：通过Cloudflare API自动更新DNS记录
- **通知系统**：Telegram实时通知运行状态和故障告警
- **日志管理**：自动清理旧日志，记录详细运行信息

---

## 📦 安装依赖
```bash
pip install -r requirements.txt
```

---

## ⚙️ 配置说明
1. 复制环境模板文件：
```bash
cp .env.example .env
```

2. 编辑`.env`文件：
```ini
# Telegram
API_ID=123456
API_HASH=your_telegram_api_hash
SESSION_NAME=cf_bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Cloudflare
CLOUDFLARE_API_KEY=your_cf_api_key
CLOUDFLARE_EMAIL=your_account@email.com
CLOUDFLARE_ZONE_ID=your_zone_id

# 代理配置（可选）
TELEGRAM_PROXY=socks5://127.0.0.1:1080
```

---

## 🚀 使用指南

### 基础测速（IPv4）
```bash
python cfst.py
```

### 代理专用测速
```bash
python cfstfd.py
```

### IPv6测速
```bash
python cfstv6.py
```

### 代理列表更新
```bash
python fdip.py
```

### 健康监测（主节点）
```bash
python ip_checker.py
```

### 健康监测（代理节点）
```bash
python proxy_checker.py
```

---

## 📌 注意事项
1. 脚本依赖环境变量配置，请确保`.env`文件正确设置
2. 首次使用Telethon需要验证手机号：
   ```bash
   python -m telethon -c "your_phone_number"
   ```
3. Cloudflare API需要Zone级别的权限
4. 建议配置cron定时任务：
   ```bash
   # 每天凌晨执行测速
   0 0 * * * /usr/bin/python3 /path/to/cfst.py
   ```

---

## 📄 许可证
MIT License | Copyright © 2023 你的名字
```