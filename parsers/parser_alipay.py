import os
import zipfile
import shutil
import tempfile
import email.header
import base64
import re


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
        
        # Try to extract zip file
        with zipfile.ZipFile(filename, 'r') as zip_ref:
            for password in passwords:
                try:
                    # Create temporary directory
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Try to extract to temporary directory with password
                        zip_ref.extractall(temp_dir, pwd=password.encode('utf-8'))
                        print(f"  Successfully extracted with password: {password}")
                        
                        # Move files from temporary directory to extract_dir and add "alipay_" prefix
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                old_path = os.path.join(root, file)
                                new_name = f"alipay_{file}"
                                new_path = os.path.join(extract_dir, new_name)
                                shutil.move(old_path, new_path)
                                print(f"  Moved file: {file} -> {new_name}")
                        
                        return True, True
                    
                except (zipfile.BadZipFile, RuntimeError):
                    # Wrong password, continue trying next one
                    continue
        
        # All password attempts failed
        print(f"  Failed to extract zip file: {filename} - no valid password found")
        return True, False
        
    except Exception as e:
        print(f"  Error extracting Alipay zip file: {e}")
        return True, False