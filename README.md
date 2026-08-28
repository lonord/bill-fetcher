# Bill Fetcher

An automated Python tool that extracts billing information from emails and converts them into structured data. Supports automatic parsing and extraction of various bill formats including Alipay, China Merchants Bank Credit Card, and WeChat Pay.

[English README](README.md) | [中文说明](README_zh.md)

## Features

- 📧 **Automatic Email Retrieval**: Automatically fetch billing emails from specified mailboxes via IMAP protocol
- 🔍 **Smart Recognition**: Automatically identify email types and select appropriate parsers
- 📊 **Multi-format Support**: Supports mainstream billing formats including Alipay, China Merchants Bank Credit Card, and WeChat Pay
- 🔐 **Password Protection**: Supports automatic extraction of encrypted ZIP files (Alipay, WeChat Pay)
- 📈 **Data Extraction**: Extract billing data to CSV format for further analysis
- ⚙️ **Flexible Configuration**: Supports custom email configuration, output directories, and other parameters
- 🚀 **Multiple Modes**: Supports parse-only, extract-only, and full workflow modes

## Supported Bill Types

| Bill Type | Email Recognition | File Format | Output Format |
|-----------|------------------|-------------|---------------|
| Alipay | Subject or sender contains "支付宝" | ZIP archive | CSV file |
| China Merchants Bank Credit Card | Subject or sender contains "招商银行信用卡" | HTML email | CSV file |
| WeChat Pay | Subject or sender contains "微信支付" | ZIP archive | Excel file |

## Installation

```bash
pip install pyyaml beautifulsoup4 requests
./scripts/build_native.sh
```

The native helper requires a C++17 compiler and zlib development files. If it is
not built or cannot run, password recovery automatically falls back to Python.

## Configuration

### 1. Email Configuration

Edit the `config.yaml` file to configure your email settings:

```yaml
# IMAP server configuration
imap_server: "imap.gmail.com"  # or your email provider's IMAP address
email_user: "your-email@gmail.com"
email_pass: "your-app-password"  # recommend using app-specific password
mailbox: "bills"  # optional, defaults to INBOX

# Directory configuration
output_dir: "output"     # directory to save email attachments
extract_dir: "extract"   # directory to save extracted files

# Sender filter (optional)
# sender_filter: 
#   - "alipay@alipay.com"
#   - "cmb@cmbchina.com"

```

Alipay and WeChat Pay ZIP passwords are expected to be exactly six digits. The
program searches the numeric password space automatically and does not write the
recovered password to logs or disk.

## Usage

### Basic Usage

```bash
# Full workflow: fetch emails + parse + extract
python main.py

# Parse emails only (skip data extraction)
python main.py -p

# Extract data only (skip email fetching)
python main.py -e

# Keep intermediate files
python main.py -k

# Use custom config file
python main.py -c my_config.yaml
```

### Command Line Arguments

- `-c, --config`: Specify config file path (default: config.yaml)
- `-k, --keep`: Keep intermediate files (default: deleted)
- `-p, --parse-only`: Only perform email parsing, skip data extraction
- `-e, --extract-only`: Only perform data extraction, skip email fetching
- `-h, --help`: Show help information

## Output File Formats

### China Merchants Bank Credit Card
- Filename: `cmbcc_YYYY_MM.csv`
- Fields: Transaction Date, Posting Date, Transaction Description, RMB Amount, Last 4 Card Digits, Local Amount, Local Currency

### Alipay
- Filename: `alipay_支付宝交易明细(YYYYMMDD-YYYYMMDD).csv`
- Contains all Alipay transaction detail fields

### WeChat Pay
- Filename: `wechat_微信支付账单流水文件(YYYYMMDD-YYYYMMDD).xlsx`
- Maintains original Excel format

## Project Structure

```
bill-fetcher/
├── main.py                 # Main program entry point
├── config.yaml            # Configuration file
├── native/
│   └── zip_password.cpp   # Fast native ZipCrypto password recovery
├── parsers/               # Parser modules
│   ├── __init__.py
│   ├── parser_alipay.py   # Alipay parser
│   ├── parser_cmbcc.py    # China Merchants Bank Credit Card parser
│   ├── parser_wechat.py   # WeChat Pay parser
│   └── zip_password.py    # Six-digit numeric ZipCrypto password recovery
├── scripts/
│   └── build_native.sh    # Build the native helper
├── tests/                 # Automated tests
├── output/                # Email attachment storage directory
└── extract/               # Extracted file storage directory
```

## Important Notes

1. **Email Security**: Recommend using app-specific passwords, not your main password
2. **Network Connection**: Ensure stable network connection, WeChat Pay requires file downloads
3. **ZIP Encryption**: Automatic recovery supports traditional ZipCrypto archives with six-digit numeric passwords
4. **File Permissions**: Ensure program has read/write permissions for output and extract directories

## Troubleshooting

### Common Issues

1. **IMAP Connection Failed**
   - Check if email configuration is correct
   - Confirm IMAP service is enabled
   - Verify app-specific password

2. **Parsing Failed**
   - Check if email format is supported
   - View log output for detailed error information

3. **Extraction Failed**
   - Confirm the archive uses a six-digit numeric password
   - Confirm the archive uses traditional ZipCrypto rather than AES encryption

4. **File Download Failed**
   - Check network connection
   - Confirm download links are valid

## Development

### Adding New Parsers

1. Create a new parser file in the `parsers/` directory
2. Implement three functions:
   - `match(subject, sender)`: Determine if email matches this parser
   - `parse(msg, msg_id, output_dir)`: Parse email content
   - `extract(filename, extract_dir, config)`: Extract file data
3. Register the new parser in `parsers/__init__.py`

### Logging Level

The program uses Python's standard logging module. You can adjust the output verbosity by modifying the log level in `main.py`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
