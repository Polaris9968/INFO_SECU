#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask Web 应用后端
功能：用户注册/登录、JWT认证、文件上传、协作排序、隐私求交
"""

import os
import json
import re
import uuid
import subprocess
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import bcrypt
import jwt


# ==================== 配置 ====================
class Config:
    JWT_SECRET_KEY = "your-secret-key-change-in-production"
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24

    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'txt'}

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    USERS_FILE = os.path.join(BASE_DIR, 'data', 'users.json')
    GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'groups.json')
    PSI_GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'psi_groups.json')
    PSI_MATCH_GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'psi_match_groups.json')
    PSI_CARD_GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'psi_card_groups.json')
    PSI_UNION_GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'psi_union_groups.json')

    STATIC_FOLDER = os.path.join(os.path.dirname(BASE_DIR), 'frontend')

    # ==================== Kunlun 库路径（统一管理）====================
    # 所有 Kunlun 相关路径都从 KUNLUN_BASE 派生，未来迁移项目只改这里
    KUNLUN_BASE = "/root/projects/INFO_SECU_1.0/Kunlun"
    KUNLUN_BUILD_DIR = os.path.join(KUNLUN_BASE, "build")
    KUNLUN_DATA_DIR = os.path.join(KUNLUN_BASE, "PSO_data")
    KUNLUN_PSI_DATA_DIR = os.path.join(KUNLUN_DATA_DIR, "PSI_data")
    KUNLUN_PSI_CARD_DATA_DIR = os.path.join(KUNLUN_DATA_DIR, "PSI_card_data")
    KUNLUN_PSI_UNION_DATA_DIR = os.path.join(KUNLUN_DATA_DIR, "PSI_union_data")

    # ==================== 服务器配置 ====================
    HOST = "0.0.0.0"
    PORT = 5001
    DEBUG = True


# ==================== Flask 应用初始化 ====================
STATIC_FOLDER_ABS = os.path.abspath(Config.STATIC_FOLDER)
print(f"[DEBUG] 静态文件夹绝对路径: {STATIC_FOLDER_ABS}")
print(f"[DEBUG] 静态文件夹存在: {os.path.exists(STATIC_FOLDER_ABS)}")

app = Flask(__name__)
CORS(app)
app.config.from_object(Config)

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(Config.USERS_FILE), exist_ok=True)
os.makedirs(Config.STATIC_FOLDER, exist_ok=True)

# ==================== 路径配置 ====================
# Kunlun 路径统一在 Config 类里（KUNLUN_BASE / KUNLUN_BUILD_DIR / KUNLUN_PSI_*_DATA_DIR）

# ==================== 辅助函数 ====================
def load_json_file(filepath, default=None):
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default


def save_json_file(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_id(length=6):
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def extract_numbers_from_text(text):
    """从文本中提取所有数字（支持整数、小数、负数）"""
    pattern = r'-?\d+\.?\d*'
    matches = re.findall(pattern, text)
    numbers = []
    for match in matches:
        try:
            num = float(match)
            numbers.append(num)
        except ValueError:
            continue
    return numbers


def extract_items_from_text(text):
    """从文本中提取所有非空白项（支持数字、字符串、中文等）"""
    items = re.findall(r'[^\s,;\n]+', text)
    if not items:
        return []
    
    def try_convert(item):
        try:
            if '.' in item:
                return float(item)
            else:
                return int(item)
        except ValueError:
            return item
    
    return [try_convert(item) for item in items]


def calculate_statistics(numbers):
    """计算统计信息"""
    if not numbers:
        return {}
    return {
        'count': len(numbers),
        'min': min(numbers),
        'max': max(numbers),
        'average': sum(numbers) / len(numbers) if numbers else 0,
        'sum': sum(numbers)
    }


def read_intersection_from_file(group_id):
    """从 intersection.txt 读取交集结果"""
    psi_data_dir = Config.KUNLUN_PSI_DATA_DIR
    group_dir = os.path.join(psi_data_dir, f"group_{group_id}")
    result_file = os.path.join(group_dir, "intersection.txt")
    
    if not os.path.exists(result_file):
        return []
    
    with open(result_file, 'r', encoding='latin-1') as f:
        content = f.read().strip()
    
    intersection = []
    for line in content.split('\n'):
        line = line.strip()
        if line:
            try:
                if '.' in line:
                    num = float(line)
                    if num.is_integer():
                        intersection.append(int(num))
                    else:
                        intersection.append(num)
                else:
                    intersection.append(int(line))
            except ValueError:
                intersection.append(line)
    
    return intersection

def read_cardinality_from_file(group_id):
    """从 cardinality.txt 读取交集基数"""
    result_file = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f"group_{group_id}", "cardinality.txt")
    
    if not os.path.exists(result_file):
        return None
    
    with open(result_file, 'r', encoding='latin-1') as f:
        content = f.read().strip()
    
    try:
        return int(content)
    except ValueError:
        return None

def read_union_from_file(group_id):
    """从 union.txt 读取并集结果"""
    result_file = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}", "union.txt")
    
    if not os.path.exists(result_file):
        return []
    
    with open(result_file, 'r', encoding='latin-1') as f:
        content = f.read().strip()
    
    union_result = []
    for line in content.split('\n'):
        line = line.strip()
        if line:
            try:
                if '.' in line:
                    num = float(line)
                    if num.is_integer():
                        union_result.append(int(num))
                    else:
                        union_result.append(num)
                else:
                    union_result.append(int(line))
            except ValueError:
                union_result.append(line)
    
    return union_result

# ==================== Kunlun PSI 调用 ====================
def run_kunlun_psi(group_id):
    """调用 Kunlun 可执行文件执行 PSI 计算"""
    kunlun_build_dir = Config.KUNLUN_BUILD_DIR
    receiver_exec = os.path.join(kunlun_build_dir, "my_mqrpmt_psi_receiver")
    sender_exec = os.path.join(kunlun_build_dir, "my_mqrpmt_psi_sender")

    psi_data_dir = Config.KUNLUN_PSI_DATA_DIR
    group_dir = os.path.join(psi_data_dir, f"group_{group_id}")
    os.makedirs(group_dir, exist_ok=True)
    
    result_file = os.path.join(group_dir, "intersection.txt")
    
    if not os.path.exists(receiver_exec):
        return {'success': False, 'error': f'接收方可执行文件不存在: {receiver_exec}'}
    if not os.path.exists(sender_exec):
        return {'success': False, 'error': f'发送方可执行文件不存在: {sender_exec}'}
    
    if os.path.exists(result_file):
        os.remove(result_file)
    
    print(f"[Kunlun] 启动接收方进程... (group: {group_id})")
    receiver_proc = subprocess.Popen(
        [receiver_exec, group_id],
        cwd=kunlun_build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='latin-1'
    )
    
    time.sleep(1.5)
    
    print(f"[Kunlun] 启动发送方进程... (group: {group_id})")
    sender_proc = subprocess.Popen(
        [sender_exec, group_id],
        cwd=kunlun_build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='latin-1'
    )
    
    try:
        sender_stdout, sender_stderr = sender_proc.communicate(timeout=300)
        receiver_stdout, receiver_stderr = receiver_proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        sender_proc.kill()
        receiver_proc.kill()
        return {'success': False, 'error': 'PSI 计算超时（超过300秒）'}
    
    if sender_proc.returncode != 0:
        print(f"[Kunlun] 发送方错误: {sender_stderr}")
        return {'success': False, 'error': f'发送方执行失败: {sender_stderr}'}
    
    if receiver_proc.returncode != 0:
        print(f"[Kunlun] 接收方错误: {receiver_stderr}")
        return {'success': False, 'error': f'接收方执行失败: {receiver_stderr}'}
    
    if not os.path.exists(result_file):
        return {'success': False, 'error': '结果文件未生成'}
    
    with open(result_file, 'r', encoding='latin-1') as f:
        content = f.read().strip()
    
    intersection = []
    for line in content.split('\n'):
        line = line.strip()
        if line:
            try:
                if '.' in line:
                    num = float(line)
                    if num.is_integer():
                        intersection.append(int(num))
                    else:
                        intersection.append(num)
                else:
                    intersection.append(int(line))
            except ValueError:
                intersection.append(line)
    
    print(f"[Kunlun] PSI 计算完成，交集大小: {len(intersection)}")
    
    return {
        'success': True,
        'intersection': intersection,
        'count': len(intersection)
    }

# ==================== Kunlun PSI_card 调用 ====================
def run_kunlun_psi_card(group_id):
    """调用 Kunlun 可执行文件执行 PSI-Card 计算（交集基数）"""
    kunlun_build_dir = Config.KUNLUN_BUILD_DIR
    receiver_exec = os.path.join(kunlun_build_dir, "my_mqrpmt_psi_card_receiver")
    sender_exec = os.path.join(kunlun_build_dir, "my_mqrpmt_psi_card_sender")

    psi_card_data_dir = Config.KUNLUN_PSI_CARD_DATA_DIR
    group_dir = os.path.join(psi_card_data_dir, f"group_{group_id}")
    os.makedirs(group_dir, exist_ok=True)
    
    result_file = os.path.join(group_dir, "cardinality.txt")
    
    if not os.path.exists(receiver_exec):
        return {'success': False, 'error': f'接收方可执行文件不存在: {receiver_exec}'}
    if not os.path.exists(sender_exec):
        return {'success': False, 'error': f'发送方可执行文件不存在: {sender_exec}'}
    
    if os.path.exists(result_file):
        os.remove(result_file)
    
    print(f"[Kunlun-Card] 启动接收方进程... (group: {group_id})")
    receiver_proc = subprocess.Popen(
        [receiver_exec, group_id],
        cwd=kunlun_build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='latin-1'
    )
    
    time.sleep(1.5)
    
    print(f"[Kunlun-Card] 启动发送方进程... (group: {group_id})")
    sender_proc = subprocess.Popen(
        [sender_exec, group_id],
        cwd=kunlun_build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='latin-1'
    )
    
    try:
        sender_stdout, sender_stderr = sender_proc.communicate(timeout=300)
        receiver_stdout, receiver_stderr = receiver_proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        sender_proc.kill()
        receiver_proc.kill()
        return {'success': False, 'error': 'PSI-Card 计算超时（超过300秒）'}
    
    if sender_proc.returncode != 0:
        print(f"[Kunlun-Card] 发送方错误: {sender_stderr}")
        return {'success': False, 'error': f'发送方执行失败: {sender_stderr}'}
    
    if receiver_proc.returncode != 0:
        print(f"[Kunlun-Card] 接收方错误: {receiver_stderr}")
        return {'success': False, 'error': f'接收方执行失败: {receiver_stderr}'}
    
    if not os.path.exists(result_file):
        return {'success': False, 'error': '结果文件未生成'}
    
    with open(result_file, 'r', encoding='latin-1') as f:
        content = f.read().strip()
    
    try:
        cardinality = int(content)
    except ValueError:
        return {'success': False, 'error': f'无法解析基数结果: {content}'}
    
    print(f"[Kunlun-Card] PSI-Card 计算完成，交集基数: {cardinality}")
    
    return {
        'success': True,
        'cardinality': cardinality
    }

# ==================== Kunlun PSU 调用 ====================
def run_kunlun_psu(group_id):
    """调用 Kunlun 可执行文件执行 PSU 计算（并集）"""
    kunlun_build_dir = Config.KUNLUN_BUILD_DIR
    receiver_exec = os.path.join(kunlun_build_dir, "my_mqrpmt_psu_receiver")
    sender_exec = os.path.join(kunlun_build_dir, "my_mqrpmt_psu_sender")

    psi_union_data_dir = Config.KUNLUN_PSI_UNION_DATA_DIR
    group_dir = os.path.join(psi_union_data_dir, f"group_{group_id}")
    os.makedirs(group_dir, exist_ok=True)
    
    result_file = os.path.join(group_dir, "union.txt")
    
    if not os.path.exists(receiver_exec):
        return {'success': False, 'error': f'接收方可执行文件不存在: {receiver_exec}'}
    if not os.path.exists(sender_exec):
        return {'success': False, 'error': f'发送方可执行文件不存在: {sender_exec}'}
    
    if os.path.exists(result_file):
        os.remove(result_file)
    
    print(f"[Kunlun-PSU] 启动接收方进程... (group: {group_id})")
    receiver_proc = subprocess.Popen(
        [receiver_exec, group_id],
        cwd=kunlun_build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='latin-1'
    )
    
    time.sleep(1.5)
    
    print(f"[Kunlun-PSU] 启动发送方进程... (group: {group_id})")
    sender_proc = subprocess.Popen(
        [sender_exec, group_id],
        cwd=kunlun_build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='latin-1'
    )
    
    try:
        sender_stdout, sender_stderr = sender_proc.communicate(timeout=300)
        receiver_stdout, receiver_stderr = receiver_proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        sender_proc.kill()
        receiver_proc.kill()
        return {'success': False, 'error': 'PSU 计算超时（超过300秒）'}
    
    if sender_proc.returncode != 0:
        print(f"[Kunlun-PSU] 发送方错误: {sender_stderr}")
        return {'success': False, 'error': f'发送方执行失败: {sender_stderr}'}
    
    if receiver_proc.returncode != 0:
        print(f"[Kunlun-PSU] 接收方错误: {receiver_stderr}")
        return {'success': False, 'error': f'接收方执行失败: {receiver_stderr}'}
    
    if not os.path.exists(result_file):
        return {'success': False, 'error': '结果文件未生成'}
    
    with open(result_file, 'r', encoding='latin-1') as f:
        content = f.read().strip()
    
    union_result = []
    for line in content.split('\n'):
        line = line.strip()
        if line:
            try:
                if '.' in line:
                    num = float(line)
                    if num.is_integer():
                        union_result.append(int(num))
                    else:
                        union_result.append(num)
                else:
                    union_result.append(int(line))
            except ValueError:
                union_result.append(line)
    
    print(f"[Kunlun-PSU] PSU 计算完成，并集大小: {len(union_result)}")
    
    return {
        'success': True,
        'union': union_result,
        'count': len(union_result)
    }

# ==================== 用户数据管理 ====================
class UserManager:
    @staticmethod
    def load_users():
        return load_json_file(Config.USERS_FILE, {})

    @staticmethod
    def save_users(users):
        save_json_file(Config.USERS_FILE, users)

    @staticmethod
    def get_user(username):
        users = UserManager.load_users()
        return users.get(username)

    @staticmethod
    def create_user(username, password, email=None):
        users = UserManager.load_users()
        if username in users:
            return None, "用户名已存在"
        if email:
            for user in users.values():
                if user.get('email') == email:
                    return None, "该邮箱已被注册"
        
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        users[username] = {
            'username': username,
            'password': password_hash,
            'email': email,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'is_admin': False
        }
        UserManager.save_users(users)
        return users[username], "注册成功"

    @staticmethod
    def verify_password(username, password):
        user = UserManager.get_user(username)
        if not user:
            return None
        if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return user
        return None

    @staticmethod
    def get_all_users():
        users = UserManager.load_users()
        return [
            {
                'username': u['username'],
                'email': u.get('email', ''),
                'created_at': u.get('created_at', '')
            }
            for u in users.values()
        ]

    @staticmethod
    def delete_user(username):
        users = UserManager.load_users()
        if username in users:
            del users[username]
            UserManager.save_users(users)
            return True
        return False


# ==================== JWT Token 管理 ====================
class TokenManager:
    @staticmethod
    def generate_token(username, is_admin=False):
        payload = {
            'username': username,
            'is_admin': is_admin,
            'exp': datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)

    @staticmethod
    def verify_token(token):
        try:
            return jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None


def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
        if not token:
            return jsonify({'error': '未提供认证Token'}), 401
        payload = TokenManager.verify_token(token)
        if not payload:
            return jsonify({'error': 'Token无效或已过期'}), 401
        request.current_user = payload
        return f(*args, **kwargs)
    return decorated_function


# ==================== 普通小组管理 ====================
class GroupManager:
    @staticmethod
    def load_groups():
        data = load_json_file(Config.GROUPS_FILE, {"groups": []})
        if "groups" not in data:
            data["groups"] = []
        return data

    @staticmethod
    def save_groups(data):
        save_json_file(Config.GROUPS_FILE, data)

    @staticmethod
    def generate_group_id():
        import random
        import string
        while True:
            group_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            data = GroupManager.load_groups()
            existing = [g for g in data["groups"] if g["id"] == group_id]
            if not existing:
                return group_id

    @staticmethod
    def create_group(group_name, creator):
        data = GroupManager.load_groups()
        group_id = GroupManager.generate_group_id()
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        data["groups"].append(group_data)
        GroupManager.save_groups(data)
        return group_data

    @staticmethod
    def get_group(group_id):
        data = GroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                return group
        return None

    @staticmethod
    def add_member(group_id, username):
        data = GroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    return False, "你已经是该小组成员"
                group["members"].append(username)
                GroupManager.save_groups(data)
                return True, "加入小组成功"
        return False, "小组不存在"

    @staticmethod
    def remove_member(group_id, username):
        data = GroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    group["members"].remove(username)
                    group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                    GroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def add_upload(group_id, username, numbers):
        data = GroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'numbers': numbers,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                GroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def remove_user_upload(group_id, username):
        data = GroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                original_count = len(group["uploads"])
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                if len(group["uploads"]) < original_count:
                    GroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def delete_group(group_id):
        data = GroupManager.load_groups()
        for i, group in enumerate(data["groups"]):
            if group["id"] == group_id:
                del data["groups"][i]
                GroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def get_user_groups(username):
        data = GroupManager.load_groups()
        result = []
        for group in data["groups"]:
            if username in group["members"]:
                result.append({
                    'id': group['id'],
                    'name': group['name'],
                    'creator': group['creator'],
                    'member_count': len(group['members']),
                    'created_at': group['created_at']
                })
        return result

    @staticmethod
    def get_all_uploads(group_id):
        group = GroupManager.get_group(group_id)
        if not group:
            return {'all_numbers': [], 'upload_records': []}
        all_numbers = []
        upload_records = []
        for upload in group.get('uploads', []):
            all_numbers.extend(upload['numbers'])
            upload_records.append({
                'username': upload['username'],
                'count': len(upload['numbers']),
                'timestamp': upload['timestamp']
            })
        return {'all_numbers': all_numbers, 'upload_records': upload_records}


# ==================== PSI 小组 API ====================
class PSIGroupManager:
    @staticmethod
    def load_groups():
        data = load_json_file(Config.PSI_GROUPS_FILE, {"groups": []})
        if "groups" not in data:
            data["groups"] = []
        return data

    @staticmethod
    def save_groups(data):
        save_json_file(Config.PSI_GROUPS_FILE, data)

    @staticmethod
    def get_group(group_id):
        data = PSIGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                return group
        return None

    @staticmethod
    def create_group(group_name, creator):
        data = PSIGroupManager.load_groups()
        group_id = generate_id(4)
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        data["groups"].append(group_data)
        PSIGroupManager.save_groups(data)
        return group_data

    @staticmethod
    def add_member(group_id, username):
        data = PSIGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    return False, "你已经是该小组成员"
                if len(group["members"]) >= 2:
                    return False, "小组已满（最多2人）"
                group["members"].append(username)
                PSIGroupManager.save_groups(data)
                return True, "加入小组成功"
        return False, "小组不存在"

    @staticmethod
    def remove_member(group_id, username):
        data = PSIGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    group["members"].remove(username)
                    group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                    PSIGroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def add_upload(group_id, username, items):
        data = PSIGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'numbers': items,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'count': len(items)
                })
                PSIGroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def remove_user_upload(group_id, username):
        data = PSIGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                original_count = len(group["uploads"])
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                if len(group["uploads"]) < original_count:
                    PSIGroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def delete_group(group_id):
        data = PSIGroupManager.load_groups()
        for i, group in enumerate(data["groups"]):
            if group["id"] == group_id:
                del data["groups"][i]
                PSIGroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def get_user_groups(username):
        data = PSIGroupManager.load_groups()
        result = []
        for group in data["groups"]:
            if username in group["members"]:
                result.append({
                    'id': group['id'],
                    'name': group['name'],
                    'creator': group['creator'],
                    'member_count': len(group['members']),
                    'created_at': group['created_at']
                })
        return result

# ==================== PSI-Card 小组 API ====================
class PSICardGroupManager:
    @staticmethod
    def load_groups():
        data = load_json_file(Config.PSI_CARD_GROUPS_FILE, {"groups": []})
        if "groups" not in data:
            data["groups"] = []
        return data

    @staticmethod
    def save_groups(data):
        save_json_file(Config.PSI_CARD_GROUPS_FILE, data)

    @staticmethod
    def get_group(group_id):
        data = PSICardGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                return group
        return None

    @staticmethod
    def create_group(group_name, creator):
        data = PSICardGroupManager.load_groups()
        group_id = generate_id(4)
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'cardinality_result': None,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        data["groups"].append(group_data)
        PSICardGroupManager.save_groups(data)
        return group_data

    @staticmethod
    def add_member(group_id, username):
        data = PSICardGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    return False, "你已经是该小组成员"
                if len(group["members"]) >= 2:
                    return False, "小组已满（最多2人）"
                group["members"].append(username)
                PSICardGroupManager.save_groups(data)
                return True, "加入小组成功"
        return False, "小组不存在"

    @staticmethod
    def remove_member(group_id, username):
        data = PSICardGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    group["members"].remove(username)
                    group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                    PSICardGroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def add_upload(group_id, username, items):
        data = PSICardGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'items': items,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'count': len(items)
                })
                PSICardGroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def remove_user_upload(group_id, username):
        data = PSICardGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                original_count = len(group["uploads"])
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                if len(group["uploads"]) < original_count:
                    PSICardGroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def delete_group(group_id):
        data = PSICardGroupManager.load_groups()
        for i, group in enumerate(data["groups"]):
            if group["id"] == group_id:
                del data["groups"][i]
                PSICardGroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def get_user_groups(username):
        data = PSICardGroupManager.load_groups()
        result = []
        for group in data["groups"]:
            if username in group["members"]:
                result.append({
                    'id': group['id'],
                    'name': group['name'],
                    'creator': group['creator'],
                    'member_count': len(group['members']),
                    'created_at': group['created_at']
                })
        return result

    @staticmethod
    def save_cardinality_result(group_id, cardinality):
        data = PSICardGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["cardinality_result"] = cardinality
                PSICardGroupManager.save_groups(data)
                return True
        return False

# ==================== PSI-Card 路由 API ====================

@app.route('/api/psi-card-group/create', methods=['POST'])
@jwt_required
def api_create_psi_card_group():
    try:
        data = request.get_json()
        group_name = data.get('groupName', '').strip()
        if not group_name:
            return jsonify({'error': '小组名称不能为空'}), 400
        if len(group_name) > 50:
            return jsonify({'error': '小组名称不能超过50个字符'}), 400
        
        group = PSICardGroupManager.create_group(group_name, request.current_user['username'])
        return jsonify({
            'message': 'PSI-Card 小组创建成功',
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'member_count': len(group['members'])
            }
        }), 201
    except Exception as e:
        return jsonify({'error': f'创建 PSI-Card 小组失败：{str(e)}'}), 500


@app.route('/api/psi-card-group/join', methods=['POST'])
@jwt_required
def api_join_psi_card_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id or len(group_id) != 4:
            return jsonify({'error': '请输入4位小组ID'}), 400
        
        success, message = PSICardGroupManager.add_member(group_id, request.current_user['username'])
        if success:
            return jsonify({'message': message})
        return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': f'加入 PSI-Card 小组失败：{str(e)}'}), 500


@app.route('/api/psi-card-group/leave', methods=['POST'])
@jwt_required
def api_leave_psi_card_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = PSICardGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] == username:
            return jsonify({'error': '组长不能退出小组，请先解散小组'}), 400
        
        if PSICardGroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出 PSI-Card 小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出 PSI-Card 小组失败：{str(e)}'}), 500


@app.route('/api/psi-card-group/<group_id>', methods=['GET'])
@jwt_required
def api_get_psi_card_group(group_id):
    try:
        group_id = group_id.upper()
        group = PSICardGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Card 小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        my_upload = None
        other_upload = None
        for upload in group.get('uploads', []):
            if upload['username'] == username:
                my_upload = upload
            else:
                other_upload = upload
        
        # 从文件读取基数结果
        cardinality = read_cardinality_from_file(group_id)
        
        return jsonify({
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at']
            },
            'my_upload': my_upload,
            'other_upload': other_upload,
            'is_creator': group['creator'] == username,
            'cardinality_result': cardinality
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取 PSI-Card 小组信息失败：{str(e)}'}), 500


@app.route('/api/psi-card-group/<group_id>', methods=['DELETE'])
@jwt_required
def api_delete_psi_card_group(group_id):
    try:
        group_id = group_id.upper()
        group = PSICardGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Card 小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] != username:
            return jsonify({'error': '只有组长可以解散小组'}), 403
        
        if PSICardGroupManager.delete_group(group_id):
            return jsonify({'message': 'PSI-Card 小组已解散'})
        return jsonify({'error': '解散小组失败'}), 500
    except Exception as e:
        return jsonify({'error': f'解散 PSI-Card 小组失败：{str(e)}'}), 500


@app.route('/api/psi-card-group/upload', methods=['POST'])
@jwt_required
def api_psi_card_upload():
    try:
        group_id = request.form.get('groupId', '').upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = PSICardGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Card 小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if 'file' not in request.files:
            return jsonify({'error': '未上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': '只支持.txt文件'}), 400
        
        content = file.read().decode('latin-1')
        items = extract_items_from_text(content)
        
        if not items:
            return jsonify({'error': '文件中未找到有效数据'}), 400
        
        # 保存到 Kunlun 目录（PSI_Card 数据）
        psi_card_data_dir = Config.KUNLUN_PSI_CARD_DATA_DIR
        group_data_dir = os.path.join(psi_card_data_dir, f"group_{group_id}")
        os.makedirs(group_data_dir, exist_ok=True)
        
        # 判断角色：组长是 receiver，成员是 sender
        if username == group['creator']:
            file_path = os.path.join(group_data_dir, "receiver.txt")
            role = "receiver"
        else:
            file_path = os.path.join(group_data_dir, "sender.txt")
            role = "sender"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(f"{item}\n")
        
        print(f"[PSI-Card] {username} 已上传 {len(items)} 个元素到 {file_path} (角色: {role})")
        
        # 保存到小组数据
        PSICardGroupManager.add_upload(group_id, username, items)
        
        # 检查双方是否都已上传
        group_after = PSICardGroupManager.get_group(group_id)
        uploaded_users = list(set([u['username'] for u in group_after.get('uploads', [])]))
        
        card_completed = False
        cardinality = None
        
        if len(uploaded_users) >= 2:
            print("[PSI-Card] 双方均已上传，开始执行 PSI-Card 计算...")
            result = run_kunlun_psi_card(group_id)
            
            if result['success']:
                cardinality = result['cardinality']
                PSICardGroupManager.save_cardinality_result(group_id, cardinality)
                card_completed = True
        
        return jsonify({
            'message': '文件上传成功',
            'upload_count': len(items),
            'card_completed': card_completed,
            'cardinality': cardinality if card_completed else None
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'处理失败：{str(e)}'}), 500


@app.route('/api/my-psi-card-groups', methods=['GET'])
@jwt_required
def api_get_my_psi_card_groups():
    try:
        groups = PSICardGroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取 PSI-Card 小组列表失败：{str(e)}'}), 500


@app.route('/api/psi-card-group/<group_id>/upload', methods=['DELETE'])
@jwt_required
def api_delete_psi_card_upload(group_id):
    try:
        group_id = group_id.upper()
        group = PSICardGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Card 小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if PSICardGroupManager.remove_user_upload(group_id, username):
            return jsonify({'message': '上传记录已删除'})
        return jsonify({'error': '没有找到可删除的上传记录'}), 400
    except Exception as e:
        return jsonify({'error': f'删除失败：{str(e)}'}), 500
        

# ==================== PSI-Union 小组 API ====================

class PSIUnionGroupManager:
    """集合并集管理类"""
    @staticmethod
    def load_groups():
        data = load_json_file(Config.PSI_UNION_GROUPS_FILE, {"groups": []})
        if "groups" not in data:
            data["groups"] = []
        return data

    @staticmethod
    def save_groups(data):
        save_json_file(Config.PSI_UNION_GROUPS_FILE, data)

    @staticmethod
    def get_group(group_id):
        data = PSIUnionGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                return group
        return None

    @staticmethod
    def create_group(group_name, creator):
        data = PSIUnionGroupManager.load_groups()
        group_id = generate_id(4)
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'union_result': None,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        data["groups"].append(group_data)
        PSIUnionGroupManager.save_groups(data)
        return group_data

    @staticmethod
    def add_member(group_id, username):
        data = PSIUnionGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    return False, "你已经是该小组成员"
                if len(group["members"]) >= 2:
                    return False, "小组已满（最多2人）"
                group["members"].append(username)
                PSIUnionGroupManager.save_groups(data)
                return True, "加入小组成功"
        return False, "小组不存在"

    @staticmethod
    def remove_member(group_id, username):
        data = PSIUnionGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    group["members"].remove(username)
                    group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                    PSIUnionGroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def add_upload(group_id, username, items):
        data = PSIUnionGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'items': items,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'count': len(items)
                })
                PSIUnionGroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def remove_user_upload(group_id, username):
        data = PSIUnionGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                original_count = len(group["uploads"])
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                if len(group["uploads"]) < original_count:
                    PSIUnionGroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def delete_group(group_id):
        data = PSIUnionGroupManager.load_groups()
        for i, group in enumerate(data["groups"]):
            if group["id"] == group_id:
                del data["groups"][i]
                PSIUnionGroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def get_user_groups(username):
        data = PSIUnionGroupManager.load_groups()
        result = []
        for group in data["groups"]:
            if username in group["members"]:
                result.append({
                    'id': group['id'],
                    'name': group['name'],
                    'creator': group['creator'],
                    'member_count': len(group['members']),
                    'created_at': group['created_at']
                })
        return result

    @staticmethod
    def save_union_result(group_id, result):
        data = PSIUnionGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["union_result"] = result
                PSIUnionGroupManager.save_groups(data)
                return True
        return False


# ==================== PSI-Union 路由 API ====================

@app.route('/api/psi-union-group/create', methods=['POST'])
@jwt_required
def api_create_psi_union_group():
    try:
        data = request.get_json()
        group_name = data.get('groupName', '').strip()
        if not group_name:
            return jsonify({'error': '小组名称不能为空'}), 400
        if len(group_name) > 50:
            return jsonify({'error': '小组名称不能超过50个字符'}), 400
        
        group = PSIUnionGroupManager.create_group(group_name, request.current_user['username'])
        return jsonify({
            'message': 'PSI-Union 小组创建成功',
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'member_count': len(group['members'])
            }
        }), 201
    except Exception as e:
        return jsonify({'error': f'创建 PSI-Union 小组失败：{str(e)}'}), 500


@app.route('/api/psi-union-group/join', methods=['POST'])
@jwt_required
def api_join_psi_union_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id or len(group_id) != 4:
            return jsonify({'error': '请输入4位小组ID'}), 400
        
        success, message = PSIUnionGroupManager.add_member(group_id, request.current_user['username'])
        if success:
            return jsonify({'message': message})
        return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': f'加入 PSI-Union 小组失败：{str(e)}'}), 500


@app.route('/api/psi-union-group/leave', methods=['POST'])
@jwt_required
def api_leave_psi_union_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] == username:
            return jsonify({'error': '组长不能退出小组，请先解散小组'}), 400
        
        if PSIUnionGroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出 PSI-Union 小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出 PSI-Union 小组失败：{str(e)}'}), 500


@app.route('/api/psi-union-group/<group_id>', methods=['GET'])
@jwt_required
def api_get_psi_union_group(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Union 小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        my_upload = None
        other_upload = None
        for upload in group.get('uploads', []):
            if upload['username'] == username:
                my_upload = upload
            else:
                other_upload = upload
        
        # ===== 修改：从文件读取并集结果，而不是从 group 对象 =====
        union_result = read_union_from_file(group_id)
        # ===== 修改结束 =====
        
        return jsonify({
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at']
            },
            'my_upload': my_upload,
            'other_upload': other_upload,
            'is_creator': group['creator'] == username,
            'union_result': union_result  # 使用从文件读取的结果
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取 PSI-Union 小组信息失败：{str(e)}'}), 500

@app.route('/api/psi-union-group/<group_id>', methods=['DELETE'])
@jwt_required
def api_delete_psi_union_group(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Union 小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] != username:
            return jsonify({'error': '只有组长可以解散小组'}), 403
        
        if PSIUnionGroupManager.delete_group(group_id):
            return jsonify({'message': 'PSI-Union 小组已解散'})
        return jsonify({'error': '解散小组失败'}), 500
    except Exception as e:
        return jsonify({'error': f'解散 PSI-Union 小组失败：{str(e)}'}), 500


@app.route('/api/psi-union-group/upload', methods=['POST'])
@jwt_required
def api_psi_union_upload():
    try:
        group_id = request.form.get('groupId', '').upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Union 小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if 'file' not in request.files:
            return jsonify({'error': '未上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': '只支持.txt文件'}), 400
        
        content = file.read().decode('latin-1')
        items = extract_items_from_text(content)
        
        if not items:
            return jsonify({'error': '文件中未找到有效数据'}), 400
        
        # ===== 保存到 Kunlun 目录（PSI_Union 数据） =====
        psi_union_data_dir = Config.KUNLUN_PSI_UNION_DATA_DIR
        group_data_dir = os.path.join(psi_union_data_dir, f"group_{group_id}")
        os.makedirs(group_data_dir, exist_ok=True)
        
        # 判断角色：组长是 receiver，成员是 sender
        if username == group['creator']:
            file_path = os.path.join(group_data_dir, "receiver.txt")
            role = "receiver"
        else:
            file_path = os.path.join(group_data_dir, "sender.txt")
            role = "sender"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(f"{item}\n")
        
        print(f"[PSI-Union] {username} 已上传 {len(items)} 个元素到 {file_path} (角色: {role})")
        
        # 保存到小组数据
        PSIUnionGroupManager.add_upload(group_id, username, items)
        
        # 检查双方是否都已上传
        group_after = PSIUnionGroupManager.get_group(group_id)
        uploaded_users = list(set([u['username'] for u in group_after.get('uploads', [])]))
        
        union_completed = False
        union_result = None
        union_count = 0
        
        if len(uploaded_users) >= 2:
            print("[PSI-Union] 双方均已上传，开始执行 PSU 计算...")
            result = run_kunlun_psu(group_id)  # 调用 C++ 程序
            
            if result['success']:
                union_result = result['union']
                union_count = result['count']
                # 保存结果到小组数据（用于前端显示）
                PSIUnionGroupManager.save_union_result(group_id, union_result)
                union_completed = True
        
        return jsonify({
            'message': '文件上传成功',
            'upload_count': len(items),
            'union_completed': union_completed,
            'union_result': union_result if union_completed else None,
            'union_count': union_count if union_completed else 0
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'处理失败：{str(e)}'}), 500

@app.route('/api/my-psi-union-groups', methods=['GET'])
@jwt_required
def api_get_my_psi_union_groups():
    try:
        groups = PSIUnionGroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取 PSI-Union 小组列表失败：{str(e)}'}), 500


@app.route('/api/psi-union-group/<group_id>/upload', methods=['DELETE'])
@jwt_required
def api_delete_psi_union_upload(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Union 小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if PSIUnionGroupManager.remove_user_upload(group_id, username):
            return jsonify({'message': '上传记录已删除'})
        return jsonify({'error': '没有找到可删除的上传记录'}), 400
    except Exception as e:
        return jsonify({'error': f'删除失败：{str(e)}'}), 500


# ==================== 路由：静态文件服务 ====================
@app.route('/')
@app.route('/login.html')
def index():
    return send_from_directory(STATIC_FOLDER_ABS, 'login_register.html')


@app.route('/home.html')
def home():
    return send_from_directory(STATIC_FOLDER_ABS, 'home.html')


@app.route('/collaborate.html')
def collaborate():
    return send_from_directory(STATIC_FOLDER_ABS, 'collaborate.html')


@app.route('/privacy_intersection.html')
def privacy_intersection():
    return send_from_directory(STATIC_FOLDER_ABS, 'privacy_intersection.html')

@app.route('/psi_match.html')  # 新增
def psi_match():
    return send_from_directory(STATIC_FOLDER_ABS, 'psi_match.html')

@app.route('/privacy_union.html')
def privacy_union():
    return send_from_directory(STATIC_FOLDER_ABS, 'privacy_union.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER_ABS, filename)


# ==================== API 路由 ====================

# ---------- 用户认证 ----------
@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip()
        
        if not username or len(username) < 3:
            return jsonify({'error': '用户名长度应在3-20个字符之间'}), 400
        if not password or len(password) < 6:
            return jsonify({'error': '密码长度至少6位'}), 400
        
        user_data, message = UserManager.create_user(username, password, email if email else None)
        if user_data is None:
            return jsonify({'error': message}), 400
        return jsonify({'message': message, 'username': username}), 201
    except Exception as e:
        return jsonify({'error': f'注册失败：{str(e)}'}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        user = UserManager.verify_password(username, password)
        if not user:
            return jsonify({'error': '用户名或密码错误'}), 401
        
        token = TokenManager.generate_token(username, user.get('is_admin', False))
        return jsonify({'token': token, 'username': username, 'is_admin': user.get('is_admin', False)}), 200
    except Exception as e:
        return jsonify({'error': f'登录失败：{str(e)}'}), 500


@app.route('/api/me', methods=['GET'])
@jwt_required
def api_me():
    user = UserManager.get_user(request.current_user['username'])
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    return jsonify({
        'username': user['username'],
        'email': user.get('email', ''),
        'is_admin': user.get('is_admin', False)
    })


# ---------- 管理员 ----------
@app.route('/api/users', methods=['GET'])
@jwt_required
def api_get_users():
    if not request.current_user.get('is_admin'):
        return jsonify({'error': '权限不足'}), 403
    users = UserManager.get_all_users()
    return jsonify({'users': users})


@app.route('/api/users/<username>', methods=['DELETE'])
@jwt_required
def api_delete_user(username):
    if not request.current_user.get('is_admin'):
        return jsonify({'error': '权限不足'}), 403
    if username == request.current_user['username']:
        return jsonify({'error': '不能删除自己的账号'}), 400
    if UserManager.delete_user(username):
        return jsonify({'message': f'用户 {username} 已删除'})
    return jsonify({'error': '用户不存在'}), 404


# ==================== 排序功能 API ====================
@app.route('/api/sort-file', methods=['POST'])
@jwt_required
def api_sort_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未上传文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': '只支持.txt文件'}), 400

        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)

        try:
            file.save(filepath)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            numbers = extract_numbers_from_text(content)
            if not numbers:
                return jsonify({'error': '文件中未找到有效数字'}), 400

            sorted_numbers = sorted(numbers, reverse=True)
            stats = calculate_statistics(numbers)

            return jsonify({
                'original': numbers,
                'sorted': sorted_numbers,
                'statistics': stats
            }), 200

        finally:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

    except Exception as e:
        return jsonify({'error': f'处理失败：{str(e)}'}), 500


# ==================== 协作排序 API ====================
@app.route('/api/group/create', methods=['POST'])
@jwt_required
def api_create_group():
    try:
        data = request.get_json()
        group_name = data.get('groupName', '').strip()
        if not group_name:
            return jsonify({'error': '小组名称不能为空'}), 400
        if len(group_name) > 50:
            return jsonify({'error': '小组名称不能超过50个字符'}), 400
        
        group = GroupManager.create_group(group_name, request.current_user['username'])
        return jsonify({
            'message': '小组创建成功',
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'member_count': len(group['members'])
            }
        }), 201
    except Exception as e:
        return jsonify({'error': f'创建小组失败：{str(e)}'}), 500


@app.route('/api/group/join', methods=['POST'])
@jwt_required
def api_join_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id or len(group_id) != 6:
            return jsonify({'error': '请输入6位小组ID'}), 400
        
        success, message = GroupManager.add_member(group_id, request.current_user['username'])
        if success:
            return jsonify({'message': message})
        return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': f'加入小组失败：{str(e)}'}), 500


@app.route('/api/group/leave', methods=['POST'])
@jwt_required
def api_leave_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = GroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] == username:
            return jsonify({'error': '组长不能退出小组，请先解散小组'}), 400
        
        if GroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出小组失败：{str(e)}'}), 500


@app.route('/api/my-groups', methods=['GET'])
@jwt_required
def api_get_my_groups():
    try:
        groups = GroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取小组列表失败：{str(e)}'}), 500


@app.route('/api/group/<group_id>', methods=['GET'])
@jwt_required
def api_get_group(group_id):
    try:
        group_id = group_id.upper()
        group = GroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        uploads_data = GroupManager.get_all_uploads(group_id)
        all_numbers = uploads_data['all_numbers']
        sorted_numbers = sorted(all_numbers, reverse=True) if all_numbers else []
        stats = calculate_statistics(all_numbers) if all_numbers else {}
        
        return jsonify({
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at']
            },
            'uploads': uploads_data['upload_records'],
            'sorted_numbers': sorted_numbers,
            'statistics': stats,
            'is_creator': group['creator'] == username
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取小组信息失败：{str(e)}'}), 500


@app.route('/api/group/<group_id>', methods=['DELETE'])
@jwt_required
def api_delete_group(group_id):
    try:
        group_id = group_id.upper()
        group = GroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] != username:
            return jsonify({'error': '只有组长可以解散小组'}), 403
        
        if GroupManager.delete_group(group_id):
            return jsonify({'message': '小组已解散'})
        return jsonify({'error': '解散小组失败'}), 500
    except Exception as e:
        return jsonify({'error': f'解散小组失败：{str(e)}'}), 500


@app.route('/api/group/upload', methods=['POST'])
@jwt_required
def api_group_upload():
    try:
        group_id = request.form.get('groupId', '').upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = GroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if 'file' not in request.files:
            return jsonify({'error': '未上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': '只支持.txt文件'}), 400
        
        content = file.read().decode('utf-8', errors='ignore')
        numbers = extract_numbers_from_text(content)
        
        if not numbers:
            return jsonify({'error': '文件中未找到有效数字'}), 400
        
        GroupManager.add_upload(group_id, username, numbers)
        
        uploads_data = GroupManager.get_all_uploads(group_id)
        all_numbers = uploads_data['all_numbers']
        sorted_numbers = sorted(all_numbers, reverse=True)
        stats = calculate_statistics(all_numbers)
        
        return jsonify({
            'message': '文件上传成功',
            'sorted_numbers': sorted_numbers,
            'statistics': stats,
            'upload_count': len(numbers)
        }), 200
    except Exception as e:
        return jsonify({'error': f'处理失败：{str(e)}'}), 500


@app.route('/api/group/upload', methods=['DELETE'])
@jwt_required
def api_delete_group_upload():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = GroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if GroupManager.remove_user_upload(group_id, username):
            return jsonify({'message': '上传记录已删除'})
        return jsonify({'error': '没有找到可删除的上传记录'}), 400
    except Exception as e:
        return jsonify({'error': f'删除失败：{str(e)}'}), 500


# ==================== 隐私求交 API ====================
@app.route('/api/psi-group/create', methods=['POST'])
@jwt_required
def api_create_psi_group():
    try:
        data = request.get_json()
        group_name = data.get('groupName', '').strip()
        if not group_name:
            return jsonify({'error': '小组名称不能为空'}), 400
        if len(group_name) > 50:
            return jsonify({'error': '小组名称不能超过50个字符'}), 400
        
        group = PSIGroupManager.create_group(group_name, request.current_user['username'])
        return jsonify({
            'message': '隐私求交小组创建成功',
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'member_count': len(group['members'])
            }
        }), 201
    except Exception as e:
        return jsonify({'error': f'创建隐私求交小组失败：{str(e)}'}), 500


@app.route('/api/psi-group/join', methods=['POST'])
@jwt_required
def api_join_psi_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id or len(group_id) != 4:
            return jsonify({'error': '请输入4位小组ID'}), 400
        
        success, message = PSIGroupManager.add_member(group_id, request.current_user['username'])
        if success:
            return jsonify({'message': message})
        return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': f'加入隐私求交小组失败：{str(e)}'}), 500


@app.route('/api/psi-group/leave', methods=['POST'])
@jwt_required
def api_leave_psi_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] == username:
            return jsonify({'error': '组长不能退出小组，请先解散小组'}), 400
        
        if PSIGroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出隐私求交小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出隐私求交小组失败：{str(e)}'}), 500


@app.route('/api/my-psi-groups', methods=['GET'])
@jwt_required
def api_get_my_psi_groups():
    try:
        groups = PSIGroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取隐私求交小组列表失败：{str(e)}'}), 500


@app.route('/api/psi-group/<group_id>', methods=['GET'])
@jwt_required
def api_get_psi_group(group_id):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        my_upload = None
        other_upload = None
        for upload in group.get('uploads', []):
            if upload['username'] == username:
                my_upload = upload
            else:
                other_upload = upload
        
        intersection = read_intersection_from_file(group_id)
        
        return jsonify({
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at']
            },
            'my_upload': my_upload,
            'other_upload': other_upload,
            'is_creator': group['creator'] == username,
            'psi_result': intersection
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取隐私求交小组信息失败：{str(e)}'}), 500


@app.route('/api/psi-group/<group_id>', methods=['DELETE'])
@jwt_required
def api_delete_psi_group(group_id):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] != username:
            return jsonify({'error': '只有组长可以解散小组'}), 403
        
        if PSIGroupManager.delete_group(group_id):
            return jsonify({'message': '隐私求交小组已解散'})
        return jsonify({'error': '解散小组失败'}), 500
    except Exception as e:
        return jsonify({'error': f'解散隐私求交小组失败：{str(e)}'}), 500


@app.route('/api/psi-group/upload', methods=['POST'])
@jwt_required
def api_psi_upload():
    try:
        group_id = request.form.get('groupId', '').upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if 'file' not in request.files:
            return jsonify({'error': '未上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': '只支持.txt文件'}), 400
        
        content = file.read().decode('latin-1')
        data = extract_items_from_text(content)
        
        if not data:
            return jsonify({'error': '文件中未找到有效数据'}), 400
        
        # 保存到 Kunlun 目录
        psi_data_dir = Config.KUNLUN_PSI_DATA_DIR
        group_data_dir = os.path.join(psi_data_dir, f"group_{group_id}")
        os.makedirs(group_data_dir, exist_ok=True)
        
        if username == group['creator']:
            file_path = os.path.join(group_data_dir, "receiver.txt")
            role = "receiver"
        else:
            file_path = os.path.join(group_data_dir, "sender.txt")
            role = "sender"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(f"{item}\n")
        
        print(f"[PSI] {username} 已上传 {len(data)} 个元素到 {file_path} (角色: {role})")
        
        PSIGroupManager.add_upload(group_id, username, data)
        
        group_after = PSIGroupManager.get_group(group_id)
        uploaded_users = list(set([u['username'] for u in group_after.get('uploads', [])]))
        
        if len(uploaded_users) >= 2:
            print("[PSI] 双方均已上传，开始执行 PSI 计算...")
            result = run_kunlun_psi(group_id)
            
            if result['success']:
                return jsonify({
                    'message': '文件上传成功，PSI 计算已完成！',
                    'upload_count': len(data),
                    'psi_completed': True,
                    'intersection': result['intersection'],
                    'intersection_count': len(result['intersection'])
                }), 200
            else:
                return jsonify({
                    'message': '文件上传成功，但 PSI 计算失败',
                    'upload_count': len(data),
                    'psi_completed': False,
                    'error': result.get('error', '计算失败')
                }), 200
        
        return jsonify({
            'message': '文件上传成功，等待对方上传...',
            'upload_count': len(data),
            'psi_completed': False
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'处理失败：{str(e)}'}), 500


@app.route('/api/psi-group/<group_id>/upload', methods=['DELETE'])
@jwt_required
def api_delete_psi_upload(group_id):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if PSIGroupManager.remove_user_upload(group_id, username):
            return jsonify({'message': '上传记录已删除'})
        return jsonify({'error': '没有找到可删除的上传记录'}), 400
    except Exception as e:
        return jsonify({'error': f'删除失败：{str(e)}'}), 500


# ==================== PSI 预览 / 下载接口 ====================
# 返回“己方密文前 20”，供前端展示运算过程中要发给对方的密文
@app.route('/api/psi-group/<group_id>/preview-ciphertext', methods=['GET'])
@jwt_required
def api_psi_preview_ciphertext(group_id):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404

        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        # 组长是接收方（receiver），成员是发送方（sender）
        role = 'receiver' if username == group['creator'] else 'sender'
        ciphertext_file = os.path.join(
            Config.KUNLUN_PSI_DATA_DIR,
            f'group_{group_id}',
            f'{role}_ciphertext.txt'
        )

        if not os.path.exists(ciphertext_file):
            return jsonify({'error': f'密文文件不存在，请先完成计算 ({role}_ciphertext.txt)'}), 404

        with open(ciphertext_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().split('\n')[:20]

        return jsonify({
            'role': role,
            'ciphertext': lines,
            'total_count': sum(1 for _ in open(ciphertext_file, 'r', encoding='utf-8'))
        }), 200
    except Exception as e:
        return jsonify({'error': f'读取密文失败：{str(e)}'}), 500


# 下载 PSI 结果文件（交集）
@app.route('/api/psi-group/<group_id>/download-result', methods=['GET'])
@jwt_required
def api_psi_download_result(group_id):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404

        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        result_file = os.path.join(
            Config.KUNLUN_PSI_DATA_DIR,
            f'group_{group_id}',
            'intersection.txt'
        )

        if not os.path.exists(result_file):
            return jsonify({'error': '结果文件不存在，请先完成 PSI 计算'}), 404

        from flask import send_file
        return send_file(
            result_file,
            as_attachment=True,
            download_name=f'psi_intersection_{group_id}.txt',
            mimetype='text/plain'
        )
    except Exception as e:
        return jsonify({'error': f'下载失败：{str(e)}'}), 500


# ==================== 隐私求并小组密文预览 / 下载 ====================

@app.route('/api/psi-union-group/<group_id>/preview-ciphertext', methods=['GET'])
@jwt_required
def api_psi_union_preview_ciphertext(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求并小组不存在'}), 404

        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        # 组长是接收方（receiver），成员是发送方（sender）
        role = 'receiver' if username == group['creator'] else 'sender'
        ciphertext_file = os.path.join(
            Config.KUNLUN_PSI_UNION_DATA_DIR,
            f'group_{group_id}',
            f'{role}_ciphertext.txt'
        )

        if not os.path.exists(ciphertext_file):
            return jsonify({'error': f'密文文件不存在，请先完成计算 ({role}_ciphertext.txt)'}), 404

        with open(ciphertext_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().split('\n')[:20]

        return jsonify({
            'role': role,
            'ciphertext': lines,
            'total_count': sum(1 for _ in open(ciphertext_file, 'r', encoding='utf-8'))
        }), 200
    except Exception as e:
        return jsonify({'error': f'读取密文失败：{str(e)}'}), 500


# 下载 PSU 结果文件（并集）
@app.route('/api/psi-union-group/<group_id>/download-result', methods=['GET'])
@jwt_required
def api_psi_union_download_result(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求并小组不存在'}), 404

        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        result_file = os.path.join(
            Config.KUNLUN_PSI_UNION_DATA_DIR,
            f'group_{group_id}',
            'union.txt'
        )

        if not os.path.exists(result_file):
            return jsonify({'error': '结果文件不存在，请先完成 PSU 计算'}), 404

        from flask import send_file
        return send_file(
            result_file,
            as_attachment=True,
            download_name=f'psu_union_{group_id}.txt',
            mimetype='text/plain'
        )
    except Exception as e:
        return jsonify({'error': f'下载失败：{str(e)}'}), 500


# ==================== 隐私集合匹配小组 API ====================

# 匹配小组管理类
class PSIMatchGroupManager:
    @staticmethod
    def load_groups():
        data = load_json_file(Config.PSI_MATCH_GROUPS_FILE, {"groups": []})
        if "groups" not in data:
            data["groups"] = []
        return data

    @staticmethod
    def save_groups(data):
        save_json_file(Config.PSI_MATCH_GROUPS_FILE, data)

    @staticmethod
    def get_group(group_id):
        data = PSIMatchGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                return group
        return None

    @staticmethod
    def create_group(group_name, creator):
        data = PSIMatchGroupManager.load_groups()
        group_id = generate_id(4)
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'subset_result': None,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        data["groups"].append(group_data)
        PSIMatchGroupManager.save_groups(data)
        return group_data

    @staticmethod
    def add_member(group_id, username):
        data = PSIMatchGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    return False, "你已经是该小组成员"
                if len(group["members"]) >= 2:
                    return False, "小组已满（最多2人）"
                group["members"].append(username)
                PSIMatchGroupManager.save_groups(data)
                return True, "加入小组成功"
        return False, "小组不存在"

    @staticmethod
    def remove_member(group_id, username):
        data = PSIMatchGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                if username in group["members"]:
                    group["members"].remove(username)
                    group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                    PSIMatchGroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def add_upload(group_id, username, items):
        data = PSIMatchGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'items': items,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'count': len(items)
                })
                PSIMatchGroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def remove_user_upload(group_id, username):
        data = PSIMatchGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                original_count = len(group["uploads"])
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                if len(group["uploads"]) < original_count:
                    PSIMatchGroupManager.save_groups(data)
                    return True
        return False

    @staticmethod
    def delete_group(group_id):
        data = PSIMatchGroupManager.load_groups()
        for i, group in enumerate(data["groups"]):
            if group["id"] == group_id:
                del data["groups"][i]
                PSIMatchGroupManager.save_groups(data)
                return True
        return False

    @staticmethod
    def get_user_groups(username):
        data = PSIMatchGroupManager.load_groups()
        result = []
        for group in data["groups"]:
            if username in group["members"]:
                result.append({
                    'id': group['id'],
                    'name': group['name'],
                    'creator': group['creator'],
                    'member_count': len(group['members']),
                    'created_at': group['created_at']
                })
        return result

    @staticmethod
    def save_subset_result(group_id, result):
        data = PSIMatchGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["subset_result"] = result
                PSIMatchGroupManager.save_groups(data)
                return True
        return False


# 匹配小组 API
@app.route('/api/psi-match-group/create', methods=['POST'])
@jwt_required
def api_create_psi_match_group():
    try:
        data = request.get_json()
        group_name = data.get('groupName', '').strip()
        if not group_name:
            return jsonify({'error': '小组名称不能为空'}), 400
        if len(group_name) > 50:
            return jsonify({'error': '小组名称不能超过50个字符'}), 400
        
        group = PSIMatchGroupManager.create_group(group_name, request.current_user['username'])
        return jsonify({
            'message': '匹配小组创建成功',
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'member_count': len(group['members'])
            }
        }), 201
    except Exception as e:
        return jsonify({'error': f'创建匹配小组失败：{str(e)}'}), 500


@app.route('/api/psi-match-group/join', methods=['POST'])
@jwt_required
def api_join_psi_match_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id or len(group_id) != 4:
            return jsonify({'error': '请输入4位小组ID'}), 400
        
        success, message = PSIMatchGroupManager.add_member(group_id, request.current_user['username'])
        if success:
            return jsonify({'message': message})
        return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': f'加入匹配小组失败：{str(e)}'}), 500


@app.route('/api/psi-match-group/leave', methods=['POST'])
@jwt_required
def api_leave_psi_match_group():
    try:
        data = request.get_json()
        group_id = data.get('groupId', '').strip().upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] == username:
            return jsonify({'error': '组长不能退出小组，请先解散小组'}), 400
        
        if PSIMatchGroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出匹配小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出匹配小组失败：{str(e)}'}), 500


@app.route('/api/psi-match-group/<group_id>', methods=['GET'])
@jwt_required
def api_get_psi_match_group(group_id):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        my_upload = None
        other_upload = None
        for upload in group.get('uploads', []):
            if upload['username'] == username:
                my_upload = upload
            else:
                other_upload = upload
        
        return jsonify({
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at']
            },
            'my_upload': my_upload,
            'other_upload': other_upload,
            'is_creator': group['creator'] == username,
            'subset_result': group.get('subset_result', None)
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取匹配小组信息失败：{str(e)}'}), 500


@app.route('/api/psi-match-group/<group_id>', methods=['DELETE'])
@jwt_required
def api_delete_psi_match_group(group_id):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404
        
        username = request.current_user['username']
        if group['creator'] != username:
            return jsonify({'error': '只有组长可以解散小组'}), 403
        
        if PSIMatchGroupManager.delete_group(group_id):
            return jsonify({'message': '匹配小组已解散'})
        return jsonify({'error': '解散小组失败'}), 500
    except Exception as e:
        return jsonify({'error': f'解散匹配小组失败：{str(e)}'}), 500


@app.route('/api/psi-match-group/upload', methods=['POST'])
@jwt_required
def api_psi_match_upload():
    try:
        group_id = request.form.get('groupId', '').upper()
        if not group_id:
            return jsonify({'error': '小组ID不能为空'}), 400
        
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404
        
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        
        if 'file' not in request.files:
            return jsonify({'error': '未上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': '只支持.txt文件'}), 400
        
        content = file.read().decode('latin-1')
        items = extract_items_from_text(content)

        if not items:
            return jsonify({'error': '文件中未找到有效数据'}), 400

        # 保存上传
        PSIMatchGroupManager.add_upload(group_id, username, items)

        # ===== 保存到 Kunlun PSI-Card 目录（receiver.txt / sender.txt）=====
        psi_card_data_dir = Config.KUNLUN_PSI_CARD_DATA_DIR
        group_data_dir = os.path.join(psi_card_data_dir, f"group_{group_id}")
        os.makedirs(group_data_dir, exist_ok=True)

        if username == group['creator']:
            file_path = os.path.join(group_data_dir, "receiver.txt")
            role = "receiver"
        else:
            file_path = os.path.join(group_data_dir, "sender.txt")
            role = "sender"

        with open(file_path, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(f"{item}\n")

        print(f"[PSI-Match] {username} 已上传 {len(items)} 个元素到 {file_path} (角色: {role})")

        # 检查双方是否都已上传
        group_after = PSIMatchGroupManager.get_group(group_id)
        uploaded_users = list(set([u['username'] for u in group_after.get('uploads', [])]))

        is_subset = False
        subset_completed = False
        intersection_cardinality = 0
        missing_count = 0

        if len(uploaded_users) >= 2:
            print("[PSI-Match] 双方均已上传，开始执行 PSI-Card 计算...")
            result = run_kunlun_psi_card(group_id)

            if result['success']:
                intersection_cardinality = result['cardinality']
                # receiver 集合大小 = creator 上传的元素数
                receiver_size = next((len(u['items']) for u in group_after.get('uploads', [])
                                      if u['username'] == group['creator']), 0)
                missing_count = max(0, receiver_size - intersection_cardinality)
                is_subset = (missing_count == 0)

                # 保存结果（不存 missingElements——PSIcard 不暴露）
                PSIMatchGroupManager.save_subset_result(group_id, {
                    'isSubset': is_subset,
                    'intersectionCardinality': intersection_cardinality,
                    'missingCount': missing_count
                })
                subset_completed = True

        return jsonify({
            'message': '文件上传成功',
            'upload_count': len(items),
            'subset_completed': subset_completed,
            'is_subset': is_subset if subset_completed else None,
            'intersection_cardinality': intersection_cardinality if subset_completed else None,
            'missing_count': missing_count if subset_completed else None
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'处理失败：{str(e)}'}), 500


@app.route('/api/my-psi-match-groups', methods=['GET'])
@jwt_required
def api_get_my_psi_match_groups():
    try:
        groups = PSIMatchGroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取匹配小组列表失败：{str(e)}'}), 500


@app.route('/api/psi-match-group/<group_id>/upload', methods=['DELETE'])
@jwt_required
def api_delete_psi_match_upload(group_id):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404

        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        if PSIMatchGroupManager.remove_user_upload(group_id, username):
            return jsonify({'message': '上传记录已删除'})
        return jsonify({'error': '没有找到可删除的上传记录'}), 400
    except Exception as e:
        return jsonify({'error': f'删除失败：{str(e)}'}), 500


# ==================== 集合匹配 密文预览 ====================
# 返回“己方密文前 20”，供前端展示 PSI-Card 协议跑出来的 OPRF 密文
@app.route('/api/psi-match-group/<group_id>/preview-ciphertext', methods=['GET'])
@jwt_required
def api_psi_match_preview_ciphertext(group_id):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404

        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        # 组长是接收方（receiver），成员是发送方（sender）
        role = 'receiver' if username == group['creator'] else 'sender'
        ciphertext_file = os.path.join(
            Config.KUNLUN_PSI_CARD_DATA_DIR,
            f'group_{group_id}',
            f'{role}_ciphertext.txt'
        )

        if not os.path.exists(ciphertext_file):
            return jsonify({'error': f'密文文件不存在，请先完成计算 ({role}_ciphertext.txt)'}), 404

        with open(ciphertext_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().split('\n')[:20]

        return jsonify({
            'role': role,
            'ciphertext': lines,
            'total_count': sum(1 for _ in open(ciphertext_file, 'r', encoding='utf-8'))
        }), 200
    except Exception as e:
        return jsonify({'error': f'读取密文失败：{str(e)}'}), 500


# ==================== 启动程序 ====================
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Flask 服务器启动中...")
    print("=" * 50)
    print(f"📁 静态文件目录: {STATIC_FOLDER_ABS}")
    print(f"📁 上传文件目录: {Config.UPLOAD_FOLDER}")
    print(f"📄 用户数据文件: {Config.USERS_FILE}")
    print("=" * 50)
    print(f"🌐 访问地址: http://localhost:{Config.PORT}/login.html")
    print(f"🌐 访问地址: http://127.0.0.1:{Config.PORT}/login.html")
    print("=" * 50)
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)

    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)