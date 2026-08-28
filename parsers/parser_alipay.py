import os
import zipfile
import shutil
import tempfile
import email.header
import base64
import re

from .zip_password import PasswordNotFoundError, recover_numeric_zip_password


def match(subject, sender):
    return "支付宝" in (subject or "") or "支付宝" in (sender or "")


def decode_mime_filename(filename):
    """Decode MIME-encoded filename, especially for Chinese characters"""
    if not filename:
        return filename
    
    # Try standard email.header.decode_header first
    try:
        decoded_parts = email.header.decode_header(filename)
        if decoded_parts and decoded_parts[0][1]:
            # Has encoding info
            decoded_bytes = decoded_parts[0][0]
            if isinstance(decoded_bytes, bytes):
                return decoded_bytes.decode(decoded_parts[0][1], errors='ignore')
            return decoded_bytes
    except:
        pass
    
    # Handle specific MIME format like ?gb2312?B?base64?=
    match = re.search(r'\?([^?]+)\?B\?([^?]+)\?=', filename)
    if match:
        encoding = match.group(1)
        encoded_content = match.group(2)
        try:
            decoded_bytes = base64.b64decode(encoded_content)
            return decoded_bytes.decode(encoding, errors='ignore')
        except:
            pass
    
    # Fallback: return original filename
    return filename


def parse(msg, msg_id, output_dir):
    try:
        for part in msg.walk():
            filename = part.get_filename()
            if filename:  # Has attachment
                # Decode MIME-encoded filename
                decoded_filename = decode_mime_filename(filename)
                
                filepath = os.path.join(output_dir, f"alipay_{decoded_filename}")
                with open(filepath, "wb") as f:
                    f.write(part.get_payload(decode=True))
                print(f"  Attachment saved: {filepath}")
        return True
    except Exception as e:
        print(f"  Error parsing Alipay email: {e}")
        return False


def extract(filename, extract_dir, config):
    # Check if filename meets the conditions
    base_filename = os.path.basename(filename)
    if not (base_filename.startswith("alipay_") and base_filename.endswith(".zip")):
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
                        new_name = f"alipay_{file}"
                        new_path = os.path.join(extract_dir, new_name)
                        shutil.move(old_path, new_path)
                        print(f"  Moved file: {file} -> {new_name}")

        return True, True
    except PasswordNotFoundError as error:
        print(f"  Failed to extract zip file: {filename} - {error}")
        return True, False
    except Exception as e:
        print(f"  Error extracting Alipay zip file: {e}")
        return True, False
