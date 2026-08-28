import os
import re
import requests
import shutil
import tempfile
import zipfile
from urllib.parse import unquote

from .zip_password import PasswordNotFoundError, recover_numeric_zip_password


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
        result = recover_numeric_zip_password(filename)
        print(f"  Recovered six-digit ZIP password in {result.elapsed_seconds:.2f}s")

        with zipfile.ZipFile(filename) as zip_ref:
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_ref.extractall(temp_dir, pwd=result.password)

                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        old_path = os.path.join(root, file)
                        new_name = f"wechat_{file}"
                        new_path = os.path.join(extract_dir, new_name)
                        shutil.move(old_path, new_path)
                        print(f"  Moved file: {file} -> {new_name}")

        return True, True
    except PasswordNotFoundError as error:
        print(f"  Failed to extract zip file: {filename} - {error}")
        return True, False
    except Exception as e:
        print(f"  Error extracting WeChat zip file: {e}")
        return True, False
