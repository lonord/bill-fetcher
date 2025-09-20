import os
import zipfile
import shutil
import tempfile


def match(subject, sender):
    return "支付宝" in (subject or "") or "支付宝" in (sender or "")


def parse(msg, msg_id, output_dir):
    try:
        for part in msg.walk():
            filename = part.get_filename()
            if filename:  # Has attachment
                filepath = os.path.join(output_dir, f"alipay_{filename}")
                with open(filepath, "wb") as f:
                    f.write(part.get_payload(decode=True))
                print(f"  Attachment saved: {filepath}")
        return True
    except Exception as e:
        print(f"  Error parsing Alipay email: {e}")
        return False


def extract(filename, extract_dir, config):
    # 检查文件名是否符合条件
    if not filename.startswith("alipay_") or not filename.endswith(".zip"):
        return False, False
    
    try:
        # 从config中读取密码文件路径
        password_file = config.get("password_file")
        if not password_file or not os.path.exists(password_file):
            print(f"  Password file not found: {password_file}")
            return True, False
        
        # 读取密码列表（从后往前）
        with open(password_file, 'r', encoding='utf-8') as f:
            passwords = [line.strip() for line in f.readlines() if line.strip()]
        
        if not passwords:
            print(f"  No passwords found in password file: {password_file}")
            return True, False
        
        # 从后往前尝试密码
        passwords.reverse()
        
        # 尝试解压zip文件
        with zipfile.ZipFile(filename, 'r') as zip_ref:
            for password in passwords:
                try:
                    # 创建临时目录
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # 尝试使用密码解压到临时目录
                        zip_ref.extractall(temp_dir, pwd=password.encode('utf-8'))
                        print(f"  Successfully extracted with password: {password}")
                        
                        # 将文件从临时目录移动到extract_dir，并添加"alipay_"前缀
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                old_path = os.path.join(root, file)
                                new_name = f"alipay_{file}"
                                new_path = os.path.join(extract_dir, new_name)
                                shutil.move(old_path, new_path)
                                print(f"  Moved file: {file} -> {new_name}")
                        
                        return True, True
                    
                except (zipfile.BadZipFile, RuntimeError):
                    # 密码错误，继续尝试下一个
                    continue
        
        # 所有密码都尝试失败
        print(f"  Failed to extract zip file: {filename} - no valid password found")
        return True, False
        
    except Exception as e:
        print(f"  Error extracting Alipay zip file: {e}")
        return True, False