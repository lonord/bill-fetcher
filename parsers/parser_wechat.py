import os
import re
import requests
import shutil
import tempfile
import subprocess
from urllib.parse import unquote


def match(subject, sender):
    return "微信支付" in (sender or "") or "微信支付" in (subject or "")


def parse(msg, msg_id, output_dir):
    try:
        body_html = None
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    charset = part.get_content_charset() or "utf-8"
                    body_html = part.get_payload(decode=True).decode(
                        charset, errors="ignore"
                    )
                    break
        else:
            if msg.get_content_type() == "text/html":
                charset = msg.get_content_charset() or "utf-8"
                body_html = msg.get_payload(decode=True).decode(
                    charset, errors="ignore"
                )

        if not body_html:
            print("  No HTML body found")
            return False

        # Find <a> tag with text "点击下载"
        links = re.findall(
            r'<a[^>]*href="([^"]+)"[^>]*>\s*点击下载\s*</a>', body_html, flags=re.IGNORECASE | re.DOTALL
        )
        if not links:
            print("  No download link found")
            return False

        url = links[0]
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            print(f"  Download failed: {url}")
            return False

        # Try to get filename
        filename = None
        if "Content-Disposition" in response.headers:
            m = re.findall(
                r'filename="?([^"]+)"?', response.headers["Content-Disposition"]
            )
            if m:
                filename = unquote(m[0])  # URL decode the filename

        if not filename:
            filename = f"wechat_{msg_id}.dat"

        filepath = os.path.join(output_dir, f"wechat_{filename}")
        with open(filepath, "wb") as f:
            f.write(response.content)

        print(f"  Downloaded file saved: {filepath}")
        return True

    except Exception as e:
        print(f"  Error parsing WeChat payment email: {e}")
        return False


def extract(filename, extract_dir, config):
    # Check if filename meets the conditions
    base_filename = os.path.basename(filename)
    if not (base_filename.startswith("wechat_") and base_filename.endswith(".zip")):
        return False, False
    
    try:
        # 7zip路径 - 从系统PATH中查找
        seven_zip_path = shutil.which("7z")
        if not seven_zip_path:
            print("  7zip not found in system PATH")
            return True, False
        
        # Read password file path from config
        password_file = config.get("password_file")
        if not password_file or not os.path.exists(password_file):
            print(f"  Password file not found: {password_file}")
            return True, False
        
        # Read password list (from back to front)
        with open(password_file, 'r', encoding='utf-8') as f:
            passwords = [line.strip() for line in f.readlines() if line.strip()]
        
        if not passwords:
            print(f"  No passwords found in password file: {password_file}")
            return True, False
        
        # Try passwords from back to front
        passwords.reverse()
        
        # Try to extract zip file using 7zip
        for password in passwords:
            try:
                # Create temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Try to extract to temporary directory with password using 7zip
                    result = subprocess.run([
                        seven_zip_path, "x", filename, f"-o{temp_dir}", "-y", f"-p{password}"
                    ], capture_output=True, text=True, encoding='utf-8')
                    
                    if result.returncode == 0:
                        print(f"  Successfully extracted with password: {password}")
                        
                        # Move files from temporary directory to extract_dir and add "wechat_" prefix
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                old_path = os.path.join(root, file)
                                new_name = f"wechat_{file}"
                                new_path = os.path.join(extract_dir, new_name)
                                shutil.move(old_path, new_path)
                                print(f"  Moved file: {file} -> {new_name}")
                        
                        return True, True
                    else:
                        continue
                    
            except Exception as e:
                print(f"  Error extracting WeChat zip file with password {password}: {e}")
                continue
        
        # All password attempts failed
        print(f"  Failed to extract zip file: {filename} - no valid password found")
        return True, False
        
    except Exception as e:
        print(f"  Error extracting WeChat zip file: {e}")
        return True, False