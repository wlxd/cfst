```markdown
# Cloudflare 自动化管理工具集

本项目提供了一套自动化工具，用于优选Cloudflare IP、管理DNS记录、执行健康检查，并支持Telegram通知。适用于需要优化Cloudflare CDN性能及自动化维护DNS记录的场景。

---

## 📋 功能特性

- **IP优选测速**：自动下载测速工具，筛选优质Cloudflare IP。
- **DNS自动化管理**：根据优选IP自动更新Cloudflare DNS记录。
- **健康检查**：定时检测DNS记录的连通性，自动清理无效记录。
- **多平台支持**：适配x86_64、ARM架构，支持Linux环境。
- **通知提醒**：通过Telegram发送操作日志和异常告警。

---

## 🛠️ 环境配置

### 环境变量
在 GitHub Secrets 或本地 `.env` 文件中设置以下变量：

```ini
CLOUDFLARE_API_KEY="您的Cloudflare API密钥"
CLOUDFLARE_EMAIL="您的Cloudflare账户邮箱"
CLOUDFLARE_ZONE_ID="您的域名Zone ID"
TELEGRAM_BOT_TOKEN="Telegram Bot Token"
TELEGRAM_CHAT_ID="Telegram接收消息的Chat ID"
API_ID=""  # 可选（如使用其他API）
API_HASH="" # 可选
```

### 依赖安装
```bash
pip install -r requirements.txt
# 依赖示例：requests, beautifulsoup4, python-dotenv
```

---

## 🚀 使用说明

### 1. 克隆仓库
```bash
git clone https://github.com/your-repo/cloudflare-automation.git
cd cloudflare-automation
```

### 2.1. 运行主脚本
```bash
python cfst.py
```
- **功能**：自动测速并生成IPV4列表（保存至 `cfip/ip.txt` 和 `speed/ip.txt`）。
- **日志**：输出到 `logs/cfst_*.log`。

### 2.2. 运行主脚本
```bash
python cfstv6.py
```
- **功能**：自动测速并生成IPV6列表（保存至 `cfip/ipv6.txt` 和 `speed/ipv6.txt`）。
- **日志**：输出到 `logs/cfstv6_*.log`。

### 2.3. 运行主脚本
```bash
python cfstfd.py
```
- **功能**：自动测速并生成反代IP列表（保存至 `cfip/fd.txt`）。
- **日志**：输出到 `logs/cfstfd_*.log`。

### 3.1. 更新DNS记录
```bash
python autoddns.py       # 更新IPV4主域名记录（如 lax.616049.xyz）
```
- **输入文件**：`cfip/ip.txt`。
- **限制**：每个域名前缀最多保留5条记录。

### 3.2. 更新DNS记录
```bash
python autoddnsv6.py     # 更新IPV6主域名记录（如 laxv6.616049.xyz）
```
- **输入文件**：`cfip/ipv6.txt`。
- **限制**：每个域名前缀最多保留5条记录。

### 3.3. 更新DNS记录
```bash
python autoddnsfd.py     # 更新反代IP主域名记录（如 proxy.lax.616049.xyz）
```
- **输入文件**：`cfip/ipfd.txt`。
- **限制**：每个域名前缀最多保留5条记录。

### 4. 健康检查
```bash
python dns_checker.py
```
- **检测逻辑**：Ping + TCP端口检测（443, 2053等）。
- **自动清理**：删除不可达的DNS记录。



---

## 📂 脚本说明

| 脚本名称         | 功能描述                               | 输入文件                | 输出文件                |
|------------------|----------------------------------------|-------------------------|-------------------------|
| `cfst.py`        | Cloudflare IPV4测速与优选                | -                       | `cfip/ip.txt`           |
| `cfstv6.py`        | Cloudflare IPV6测速与优选                | -                       | `cfip/ipv6.txt`           |
| `cfst.py`        | Cloudflare 反代IP测速与优选                | -                       | `cfip/fd.txt`           |
| `autoddns.py`    | 更新IPV4主域名DNS记录                      | `cfip/ip.txt`           | Cloudflare DNS          |
| `autoddnsv6.py`    | 更新IPV6主域名DNS记录                      | `cfip/ipv6.txt`           | Cloudflare DNS          |
| `autoddnsfd.py`  | 更新反代IP主域名的DNS记录                | `cfip/fd.txt`           | Cloudflare DNS          |
| `dns_checker.py`   | 检查DNS记录健康状态并清理              | Cloudflare API          | 日志文件                |
| `checker.py`     | 校验IP连通性并过滤无效IP               | `cfip/fd.txt`           | 更新后的`cfip/fd.txt`   |
| `cfip.py`        | 从网页抓取IP数据并格式化保存           | 网页数据                | `speed/cfip.txt`        |

---

## ⚠️ 注意事项

1. **权限要求**：确保脚本有执行权限（`chmod +x *.py`）。
2. **目录结构**：首次运行会自动生成 `logs`、`csv` 等目录。
3. **速率限制**：Cloudflare API 有调用限制，建议间隔运行。
4. **代理配置**：若网络受限，需在脚本中配置代理。

---

## 📄 许可证

本项目采用 [MIT License](LICENSE)，欢迎贡献代码或提出建议。
```