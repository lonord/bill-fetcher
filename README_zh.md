# Bill Fetcher

一个自动从邮件中提取账单信息并转换为结构化数据的Python工具。支持支付宝、招商银行信用卡、微信支付等多种账单格式的自动解析和提取。

[English README](README.md) | [中文说明](README_zh.md)

## 功能特性

- 📧 **邮件自动获取**: 通过IMAP协议自动获取指定邮箱中的账单邮件
- 🔍 **智能识别**: 自动识别邮件类型并选择合适的解析器
- 📊 **多格式支持**: 支持支付宝、招商银行信用卡、微信支付等主流账单格式
- 🔐 **密码保护**: 支持加密ZIP文件的自动解压（支付宝、微信支付）
- 📈 **数据提取**: 将账单数据提取为CSV格式，便于后续分析
- ⚙️ **灵活配置**: 支持自定义邮箱配置、输出目录等参数
- 🚀 **多种模式**: 支持仅解析、仅提取、完整流程等多种运行模式

## 支持的账单类型

| 账单类型 | 邮件识别 | 文件格式 | 输出格式 |
|---------|---------|---------|---------|
| 支付宝 | 主题或发件人包含"支付宝" | ZIP压缩包 | CSV文件 |
| 招商银行信用卡 | 主题或发件人包含"招商银行信用卡" | HTML邮件 | CSV文件 |
| 微信支付 | 主题或发件人包含"微信支付" | ZIP压缩包 | Excel文件 |

## 安装依赖

```bash
pip install pyyaml beautifulsoup4 requests
```

## 配置说明

### 1. 邮箱配置

编辑 `config.yaml` 文件，配置你的邮箱信息：

```yaml
# IMAP服务器配置
imap_server: "imap.gmail.com"  # 或你的邮箱服务商IMAP地址
email_user: "your-email@gmail.com"
email_pass: "your-app-password"  # 建议使用应用专用密码
mailbox: "bills"  # 可选，默认为INBOX

# 目录配置
output_dir: "output"     # 邮件附件保存目录
extract_dir: "extract"   # 提取后文件保存目录

# 发件人过滤（可选）
# sender_filter: 
#   - "alipay@alipay.com"
#   - "cmb@cmbchina.com"

# 额外参数
extra_params:
  password_file: "password.txt"  # 解压密码文件路径
```

### 2. 密码文件

创建 `password.txt` 文件，每行一个解压密码（用于支付宝和微信支付的加密ZIP文件）：

```
password1
password2
password3
```

## 使用方法

### 基本用法

```bash
# 完整流程：获取邮件 + 解析 + 提取
python main.py

# 仅解析邮件（不提取数据）
python main.py -p

# 仅提取数据（不获取邮件）
python main.py -e

# 保留中间文件
python main.py -k

# 使用自定义配置文件
python main.py -c my_config.yaml
```

### 命令行参数

- `-c, --config`: 指定配置文件路径（默认：config.yaml）
- `-k, --keep`: 保留中间文件（默认会删除）
- `-p, --parse-only`: 仅执行邮件解析，跳过数据提取
- `-e, --extract-only`: 仅执行数据提取，跳过邮件获取
- `-h, --help`: 显示帮助信息

## 输出文件格式

### 招商银行信用卡
- 文件名：`cmbcc_YYYY_MM.csv`
- 字段：交易日, 记账日, 交易摘要, 人民币金额, 卡号末四位, 交易地金额, 交易地

### 支付宝
- 文件名：`alipay_支付宝交易明细(YYYYMMDD-YYYYMMDD).csv`
- 包含支付宝交易明细的所有字段

### 微信支付
- 文件名：`wechat_微信支付账单流水文件(YYYYMMDD-YYYYMMDD).xlsx`
- 保持原始Excel格式

## 项目结构

```
bill-fetcher/
├── main.py                 # 主程序入口
├── config.yaml            # 配置文件
├── password.txt           # 解压密码文件
├── parsers/               # 解析器模块
│   ├── __init__.py
│   ├── parser_alipay.py   # 支付宝解析器
│   ├── parser_cmbcc.py    # 招商银行信用卡解析器
│   └── parser_wechat.py   # 微信支付解析器
├── output/                # 邮件附件保存目录
└── extract/               # 提取后文件保存目录
```

## 注意事项

1. **邮箱安全**: 建议使用应用专用密码，不要使用主密码
2. **网络连接**: 确保网络连接稳定，微信支付需要下载文件
3. **7zip依赖**: 微信支付解压需要系统安装7zip命令行工具
4. **文件权限**: 确保程序有读写output和extract目录的权限
5. **密码文件**: 确保password.txt文件存在且包含正确的解压密码

## 故障排除

### 常见问题

1. **IMAP连接失败**
   - 检查邮箱配置是否正确
   - 确认已开启IMAP服务
   - 验证应用专用密码

2. **解析失败**
   - 检查邮件格式是否支持
   - 查看日志输出获取详细错误信息

3. **解压失败**
   - 确认password.txt文件存在
   - 检查密码是否正确
   - 微信支付需要安装7zip

4. **文件下载失败**
   - 检查网络连接
   - 确认下载链接有效

## 开发说明

### 添加新的解析器

1. 在 `parsers/` 目录下创建新的解析器文件
2. 实现三个函数：
   - `match(subject, sender)`: 判断邮件是否匹配
   - `parse(msg, msg_id, output_dir)`: 解析邮件内容
   - `extract(filename, extract_dir, config)`: 提取文件数据
3. 在 `parsers/__init__.py` 中注册新解析器

### 日志级别

程序使用Python标准logging模块，可以通过修改 `main.py` 中的日志级别来调整输出详细程度。

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。
