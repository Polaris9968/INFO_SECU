#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask Web 应用后端
功能:用户注册/登录、JWT认证、文件上传、隐私求交
"""

import os
import json
import re
import uuid
import subprocess
import shutil
import time
import hashlib
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import bcrypt
import jwt


# ==================== 配置 ====================
class Config:
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if not JWT_SECRET_KEY:
        raise RuntimeError(
            "JWT_SECRET_KEY env var is not set. "
            "Copy backend/.env.example to backend/.env and fill in a strong value, "
            "or: export JWT_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')"
        )
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24

    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'txt', 'csv', 'json'}

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    USERS_FILE = os.path.join(BASE_DIR, 'data', 'users.json')
    GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'groups.json')
    PSI_GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'psi_groups.json')
    PSI_MATCH_GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'psi_match_groups.json')
    PSI_CARD_GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'psi_card_groups.json')
    PSI_UNION_GROUPS_FILE = os.path.join(BASE_DIR, 'data', 'psi_union_groups.json')

    STATIC_FOLDER = os.path.join(os.path.dirname(BASE_DIR), 'frontend')

    # ==================== Kunlun 库路径(统一管理)====================
    # 所有 Kunlun 相关路径都从 KUNLUN_BASE 派生,未来迁移项目只改这里
    KUNLUN_BASE = "/root/projects/INFO_SECU_1.0/Kunlun"
    KUNLUN_BUILD_DIR = os.path.join(KUNLUN_BASE, "build")
    KUNLUN_DATA_DIR = os.path.join(KUNLUN_BASE, "PSO_data")
    KUNLUN_PSI_DATA_DIR = os.path.join(KUNLUN_DATA_DIR, "PSI_data")
    KUNLUN_PSI_CARD_DATA_DIR = os.path.join(KUNLUN_DATA_DIR, "PSI_card_data")
    KUNLUN_PSI_UNION_DATA_DIR = os.path.join(KUNLUN_DATA_DIR, "PSI_union_data")

    # ==================== 服务器配置 ====================
    HOST = "0.0.0.0"
    PORT = 5002
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
# Kunlun 路径统一在 Config 类里(KUNLUN_BASE / KUNLUN_BUILD_DIR / KUNLUN_PSI_*_DATA_DIR)

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
    """从文本中提取所有数字(支持整数、小数、负数)"""
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


def _standardize_token(item, mode):
    """单个 token 标准化(供 extract_items_from_file 和 reverse map 复用)。"""
    item = item.strip()
    if not item:
        return None
    if mode == 'auto':
        # 数字直接用,文字/中文/特殊字符走 SHA-256;范围 [-10^15, 10^15] 闭区间
        try:
            n = int(item)
            if -10**15 <= n <= 10**15:
                return str(n)
        except (ValueError, TypeError):
            pass
        h = hashlib.sha256(item.encode('utf-8')).digest()[:16]
        return str(int.from_bytes(h, 'big'))
    elif mode == 'number_only':
        try:
            n = int(item)
            if -10**15 <= n <= 10**15:
                return str(n)
        except (ValueError, TypeError):
            pass
        return None
    elif mode == 'text_all':
        h = hashlib.sha256(item.encode('utf-8')).digest()[:16]
        return str(int.from_bytes(h, 'big'))
    else:
        # fallback 当 auto
        try:
            n = int(item)
            if -10**15 <= n <= 10**15:
                return str(n)
        except (ValueError, TypeError):
            pass
        h = hashlib.sha256(item.encode('utf-8')).digest()[:16]
        return str(int.from_bytes(h, 'big'))


def _build_reverse_map(group, mode='auto'):
    """为 receiver (creator) 构建 std -> original 的 reverse map。
    用于结果列表里把 hash 显示成 receiver 自己上传的原始 token。
    """
    receiver_upload = next(
        (u for u in group.get('uploads', []) if u['username'] == group['creator']),
        None
    )
    if not receiver_upload:
        return {}
    reverse_map = {}
    for orig in receiver_upload.get('original_items', []):
        std = _standardize_token(orig, mode)
        if std and std not in reverse_map:
            reverse_map[std] = orig
    return reverse_map


def _probe_json_paths(content):
    """两阶段 JSON path 上传 - 阶段 1 扫描 JSON 结构。
    返回: [{display: "items.[].email", path: "email", type: "str", count: N, sample: "..."}]
    - display 是 UI 友好展示,如 "items.[].user.email";顶层数组是 "[].name"
    - path 是相对路径(去除 items / 顶层数组包裹),直接传给 _extract_by_path
    - 过滤掉元数据字段(description / meta / note / comment / _id / index)
    - 只支持 list-of-dict 结构;纯数组 / 嵌套 list 不展开
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e.msg}")

    if isinstance(data, list):
        source = data
        wrapper = ''  # 顶层数组:不包裹层
    elif isinstance(data, dict):
        for key in ('items', 'data', 'records'):
            if key in data and isinstance(data[key], list):
                source = data[key]
                wrapper = key  # 用作展示前缀
                break
        else:
            raise ValueError("JSON 需要是数组,或包含 items/data/records 数组的字段")
    else:
        raise ValueError("JSON 顶层必须是数组或对象")

    paths = []
    _probe_paths_recursive(source, prefix='', wrapper=wrapper, acc=paths, max_depth=3)
    return paths


# 2026-07-02 探测时跳过这些“元数据”字段 (description / id / _id 这种各 list 项都会有的辅助字段)
_META_KEY_HINTS = ('description', 'meta', '_meta', 'comment', 'note', 'remark', 'desc', 'tips')


def _probe_paths_recursive(items, prefix, wrapper, acc, max_depth=3):
    """扫描 list of dict 的结构,递归抽取所有叶子 path。
    - prefix: 当前路径前缀,如 "user.name" / "" (顶级)
    - wrapper: 顶层数组名(items/data/records/''),加在 display 前缀
    """
    if not items:
        return
    depth = prefix.count('.') + (0 if prefix == '' else 1)
    if depth >= max_depth:
        return
    if not isinstance(items, list):
        return
    # 只采样 dict 类型的元素
    dict_items = [it for it in items if isinstance(it, dict)]
    if not dict_items:
        # 全是 list/扁平 字符串/数字
        return

    for key in list(dict_items[0].keys()):
        # 收集所有该 key 的非 None 值及其类型
        values = [d.get(key) for d in dict_items]
        non_null = [v for v in values if v is not None]
        if not non_null:
            continue

        type_counts = {}
        for v in non_null:
            t = type(v).__name__
            type_counts[t] = type_counts.get(t, 0) + 1

        # 只考虑 叶子(str / int / float / bool) 类型的字段
        is_leaf = set(type_counts.keys()) <= {'str', 'int', 'float', 'bool'}
        is_pure_dict = set(type_counts.keys()) == {'dict'}

        if is_leaf:
            # 后端抽取要传的是相对 list 元素的 path: 拼 prefix + key
            actual_path = f"{prefix}.{key}" if prefix else key
            # 展示用: 脱首项 wrapper + "[]" 提示
            display_parts = []
            if wrapper:
                display_parts.append(wrapper)
            display_parts.append('[]')
            # 嵌套: prefix 里的每个层级也加 []
            if prefix:
                for part in prefix.split('.'):
                    display_parts.append(part)
                    display_parts.append('[]')
            display_parts.append(key)
            display_path = '.'.join(display_parts)

            # 2026-07-02 过滤“元数据”字段名
            is_meta = any(h == key.lower() for h in _META_KEY_HINTS)
            if is_meta:
                continue

            # 采样示例
            sample = str(non_null[0])[:60]
            acc.append({
                'display': display_path,    # "items.[].email" 或 "email"
                'path': actual_path,         # "email" (顶层数组) 或 "items.email"
                'type': next(iter(type_counts.keys())),
                'count': len(non_null),
                'sample': sample,
                'max_length': max((len(str(v)) for v in non_null[:10]), default=0),
            })
        elif is_pure_dict and depth + 1 < max_depth:
            # 全是 dict 字段 → 递归
            sub_dicts = [v for v in non_null if isinstance(v, dict)]
            if sub_dicts:
                new_prefix = f"{prefix}.{key}" if prefix else key
                _probe_paths_recursive(
                    sub_dicts,
                    prefix=new_prefix,
                    wrapper=wrapper,
                    acc=acc,
                    max_depth=max_depth
                )


def _extract_by_path(data_list, path):
    """按点分隔 path 提取每个 item 的字段值(不依赖第三方 JSONPath 库)。
    例: path="user.email" → 走 data[i]["user"]["email"]
    支持 dict 取 key 和 list 取 int index。
    """
    parts = path.split('.')
    result = []
    for idx, item in enumerate(data_list):
        cur = item
        try:
            for p in parts:
                if isinstance(cur, dict):
                    cur = cur[p]
                elif isinstance(cur, list):
                    cur = cur[int(p)]
                else:
                    raise KeyError(p)
            if cur is None:
                raise ValueError(f"item[{idx}] 路径 '{path}' 值为 null")
            result.append(str(cur))
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise ValueError(f"item[{idx}] 路径 '{path}' 走不通: {e}")
    return result


def _parse_json_items(content, path=None):
    """解析 JSON 内容,返回原始 token 列表(不标准化,交给上层统一处理)。
    档 1:
        ["a", "b"]                     → ["a", "b"]
        {"items": ["a", "b"]}          → ["a", "b"]
    档 2:
        {"path": "user.email",
         "data": [{"user": {"email": "a"}}, ...]}  → 走 path 提取
        {"path": "user.email",
         "items": [{"user": {"email": "a"}}, ...]}  → items 优先于 data
    2026-07-02:path 参数(可选)由调用方传入 ① 优先于 ② JSON 顶层字段
    失败:raise ValueError,给中文友好错误
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e.msg} (line {e.lineno} col {e.colno})")

    # 档 1a: 纯数组
    if isinstance(data, list):
        return [str(x) if x is not None else '' for x in data]

    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是数组或对象")

    # 档 2: path 模式 (2026-07-02: 调用方传入 path 优先于 JSON 顶层字段)
    effective_path = path if path is not None else data.get('path')
    if effective_path is not None:
        if not isinstance(effective_path, str) or not effective_path.strip():
            raise ValueError("path 字段必须是非空字符串")
        source = data.get('items')
        if source is None:
            source = data.get('data')
        if source is None:
            raise ValueError("path 模式下需要 items 或 data 字段")
        if not isinstance(source, list):
            raise ValueError("items/data 字段必须是数组")
        return _extract_by_path(source, effective_path)

    # 档 1b: 对象有 items 字段
    if 'items' in data:
        items = data['items']
        if not isinstance(items, list):
            raise ValueError("items 字段必须是数组")
        return [str(x) if x is not None else '' for x in items]

    raise ValueError("对象需要 items 字段,或 path + items/data 字段")


def extract_items_from_file(content, filename, mode='auto', path=None):
    """统一文件解析入口:按后缀分发(.json / 其他)。
    2026-07-02 加 path 参数:透传给 _parse_json_items,用于接收方自定义 JSON path。
    返回: (standardized_items, original_items)
    """
    if filename and filename.lower().endswith('.json'):
        try:
            raw_items = _parse_json_items(content, path=path)
        except ValueError as e:
            raise ValueError(str(e))
    else:
        raw_items = re.findall(r'[^\s,;\n]+', content)

    if not raw_items:
        return [], []

    std_items = []
    for item in raw_items:
        s = _standardize_token(item, mode)
        if s is not None:
            std_items.append(s)
    return std_items, raw_items


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
        return {'success': False, 'error': 'PSI 计算超时(超过300秒)'}

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

    print(f"[Kunlun] PSI 计算完成,交集大小: {len(intersection)}")

    return {
        'success': True,
        'intersection': intersection,
        'count': len(intersection)
    }

# ==================== Kunlun PSI_card 调用 ====================
def run_kunlun_psi_card(group_id):
    """调用 Kunlun 可执行文件执行 PSI-Card 计算(交集基数)"""
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
        return {'success': False, 'error': 'PSI-Card 计算超时(超过300秒)'}

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

    print(f"[Kunlun-Card] PSI-Card 计算完成,交集基数: {cardinality}")

    return {
        'success': True,
        'cardinality': cardinality
    }

# ==================== Kunlun PSU 调用 ====================
def run_kunlun_psu(group_id):
    """调用 Kunlun 可执行文件执行 PSU 计算(并集)"""
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
        return {'success': False, 'error': 'PSU 计算超时(超过300秒)'}

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

    print(f"[Kunlun-PSU] PSU 计算完成,并集大小: {len(union_result)}")

    return {
        'success': True,
        'union': union_result,
        'count': len(union_result)
    }


def _format_duration(seconds):
    """自适应时间显示。<60s "X.XX 秒";<3600s "X 分 Y 秒";>=3600s "X 小时 Y 分 Y 秒" """
    seconds = float(seconds)
    if seconds < 60:
        return f"{seconds:.2f} 秒"
    if seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m} 分 {s} 秒"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h} 小时 {m} 分 {s} 秒"


def _compute_with_timing(run_func, group_id):
    """包一层计时;调 run_func(group_id),success 时给返回字典塞 duration_seconds/duration_human"""
    t0 = time.time()
    result = run_func(group_id)
    elapsed = time.time() - t0
    if result.get('success'):
        result['duration_seconds'] = round(elapsed, 3)
        result['duration_human'] = _format_duration(elapsed)
        print(f"[Kunlun] {run_func.__name__} 耗时 {elapsed:.3f}s")
    return result

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
                # 2026-07-01:向后兼容,补 rounds 字段
                if 'rounds' not in group:
                    group['rounds'] = []
                return group
        return None

    @staticmethod
    def finalize_round(group_id, completed_by):
        """归档当前轮次到 rounds,清空 uploads + result。
        Returns: (success, round_record_or_error_msg)
        """
        data = PSIGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] != group_id:
                continue
            if 'rounds' not in group:
                group['rounds'] = []
            # 归档文件(Kunlun server 端输出)
            kunlun_dir = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f"group_{group_id}")
            round_num = len(group['rounds']) + 1
            archive_dir = os.path.join(kunlun_dir, f"round{round_num}")
            os.makedirs(archive_dir, exist_ok=True)
            archive_files = {}
            # 2026-07-01:A 方案 - 归档 original_*.txt(让历史轮次能下载原始)
            for fname in ('receiver.txt', 'sender.txt', 'intersection.txt',
                          'receiver_ciphertext.txt', 'sender_ciphertext.txt',
                          'sender_result.txt',
                          'original_receiver.txt', 'original_sender.txt'):
                src = os.path.join(kunlun_dir, fname)
                if os.path.exists(src):
                    dst = os.path.join(archive_dir, fname)
                    import shutil
                    shutil.copy2(src, dst)
                    archive_files[fname.replace('.txt', '')] = dst
            # 读 result
            intersection = []
            if 'intersection' in archive_files:
                try:
                    with open(archive_files['intersection'], 'r', encoding='utf-8') as f:
                        intersection = [line.strip() for line in f if line.strip()]
                except Exception:
                    pass
            # 2026-07-01:写 intersection_with_original.txt(receiver 视角的 reverse map)
            # 共同元素 = 双方都传过 → reverse_map 能查到 → 显示原始
            # 写到归档 round 目录(顶层 kunlun_dir 会被下一轮 finalize 覆盖,不存)
            if intersection:
                reverse_map = _build_reverse_map(group, group.get('standardize_mode', 'auto'))
                with_orig_path = os.path.join(archive_dir, 'intersection_with_original.txt')
                with open(with_orig_path, 'w', encoding='utf-8') as f:
                    for v in intersection:
                        f.write((reverse_map.get(v) or v) + '\n')
                archive_files['intersection_with_original'] = with_orig_path
            # 归档 uploads (server 端,存双方明文仅供审计,API 返回时只返自己那份)
            uploads_snapshot = {
                u['username']: u.get('numbers', [])
                for u in group.get('uploads', [])
            }
            round_record = {
                'round': round_num,
                'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'completed_by': completed_by,
                'uploads': uploads_snapshot,
                'archive_dir': archive_dir,
                'archive_files': archive_files,
                'result': {
                    'type': 'intersection',
                    'count': len(intersection)
                },
                'computation_seconds': (group.get('pending_computation') or {}).get('duration_seconds'),
                'computation_human': (group.get('pending_computation') or {}).get('duration_human'),
            }
            group['rounds'].append(round_record)
            # 清空当前 uploads(让双方可重新上传,开始下一轮)
            group['uploads'] = []
            # 2026-07-02:删顶层 stale 文件,防止下一轮看到老数据
            # (顶层文件是上一轮 final 时的产物,新轮开始后 Kunlun 没跑前不应残留)
            # ciphertext 也删,只有双方上传 Kunlun 跑 OPRF 后才有新密文
            # 2026-07-02:original_*.txt + uploaded_*.txt 也删,避免 sender 下一轮看到上一轮明文残留
            for stale_fname in ('intersection.txt', 'union.txt',
                                'receiver_ciphertext.txt', 'sender_ciphertext.txt',
                                'sender_result.txt',
                                'original_receiver.txt', 'original_sender.txt'):
                stale_path = os.path.join(kunlun_dir, stale_fname)
                if os.path.exists(stale_path):
                    os.remove(stale_path)
            # uploaded_<role>.<ext> 三种后缀都扫一下
            for role in ('receiver', 'sender'):
                for ext in ('txt', 'csv', 'json'):
                    p = os.path.join(kunlun_dir, f'uploaded_{role}.{ext}')
                    if os.path.exists(p):
                        os.remove(p)
            PSIGroupManager.save_groups(data)
            # 2026-07-02:清掉 pending_computation(round_record 已写入,避免污染下一轮)
            group.pop('pending_computation', None)
            PSIGroupManager.save_groups(data)
            return True, round_record
        return False, "小组不存在"

    @staticmethod
    def get_history(group_id, username):
        """返回该小组的所有 round 记录(user 视角:只暴露自己那份明文)"""
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return None
        history = []
        for r in group.get('rounds', []):
            history.append({
                'round': r['round'],
                'completed_at': r['completed_at'],
                'completed_by': r['completed_by'],
                'my_upload_count': len(r['uploads'].get(username, [])),
                'result': r['result'],
                # 标记本人是否是 receiver (用于前端权限判断)
                'is_receiver': r['uploads'].get(username, []) != [],
                # 2026-07-02:补上轮次耗时,前端可展示
                'computation_seconds': r.get('computation_seconds'),
                'computation_human': r.get('computation_human')
            })
        return history

    @staticmethod
    def get_round_data(group_id, round_num, file_type, username):
        """返回归档文件路径 + 校验权限。file_type: my_plaintext | my_oprf | result | my_original"""
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return None, "小组不存在"
        rounds = group.get('rounds', [])
        if round_num < 1 or round_num > len(rounds):
            return None, "轮次不存在"
        r = rounds[round_num - 1]
        archive_files = r.get('archive_files', {})
        if file_type == 'result':
            fpath = archive_files.get('intersection')
            if not fpath or not os.path.exists(fpath):
                return None, "结果文件不存在"
            return fpath, None
        if file_type == 'result_with_original':
            # 2026-07-01:receiver 视角的 reverse map,非数字项显示原始 token
            fpath = archive_files.get('intersection_with_original')
            if not fpath or not os.path.exists(fpath):
                return None, "原始版结果不存在(旧归档或尚未生成)"
            return fpath, None
        if file_type in ('my_plaintext', 'my_oprf'):
            # 权限:必须是小组成员
            if username not in group['members']:
                return None, "你不是该小组成员"
            # creator = receiver(Kunlun 协议角色),非 creator = sender
            if username == group['creator']:
                if file_type == 'my_plaintext':
                    # 2026-07-01:A 方案 - 优先归档的 original,fallback 标准化
                    fpath = archive_files.get('original_receiver') or archive_files.get('receiver')
                else:  # my_oprf
                    fpath = archive_files.get('receiver_ciphertext')
            else:
                if file_type == 'my_plaintext':
                    fpath = archive_files.get('original_sender') or archive_files.get('sender')
                else:  # my_oprf
                    fpath = archive_files.get('sender_ciphertext')
            if not fpath or not os.path.exists(fpath):
                return None, "文件不存在"
            return fpath, None
        if file_type == 'my_original':
            # 2026-07-01:A 方案 - 归档里有 original_*.txt,这里直接走 archive 路径
            if username not in group['members']:
                return None, "你不是该小组成员"
            if username == group['creator']:
                fpath = archive_files.get('original_receiver')
            else:
                fpath = archive_files.get('original_sender')
            if not fpath or not os.path.exists(fpath):
                return None, "原始 token 文件不存在(可能尚未上传)"
            return fpath, None
        return None, "未知文件类型"

    @staticmethod
    def create_group(group_name, creator, standardize_mode='auto'):
        data = PSIGroupManager.load_groups()
        group_id = generate_id(4)
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'rounds': [],  # 2026-07-01:多轮历史记录
            'standardize_mode': standardize_mode,  # 2026-07-01:非数字输入标准化
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
                    return False, "小组已满(最多2人)"
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
    def add_upload(group_id, username, items, original_items=None, standardize_mode='auto'):
        data = PSIGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'numbers': items,
                    'original_items': original_items or items,
                    'standardize_mode': standardize_mode,
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
    def create_group(group_name, creator, standardize_mode='auto'):
        data = PSICardGroupManager.load_groups()
        group_id = generate_id(4)
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'cardinality_result': None,
            'rounds': [],  # 2026-07-01:多轮历史记录
            'standardize_mode': standardize_mode,  # 2026-07-01:非数字输入标准化
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
                    return False, "小组已满(最多2人)"
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
    def add_upload(group_id, username, items, original_items=None, standardize_mode='auto'):
        data = PSICardGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'items': items,
                    'original_items': original_items or items,
                    'standardize_mode': standardize_mode,
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
        # 2026-07-01:标准化方式(数字/文字/混合)
        mode = data.get('standardizeMode', 'auto')
        if mode not in ('auto', 'number_only', 'text_all'):
            mode = 'auto'

        group = PSICardGroupManager.create_group(group_name, request.current_user['username'], mode)
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
        return jsonify({'error': f'创建 PSI-Card 小组失败:{str(e)}'}), 500


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
        return jsonify({'error': f'加入 PSI-Card 小组失败:{str(e)}'}), 500


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
            return jsonify({'error': '组长不能退出小组,请先解散小组'}), 400

        if PSICardGroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出 PSI-Card 小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出 PSI-Card 小组失败:{str(e)}'}), 500


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

        response_payload = {
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at'],
                'standardize_mode': group.get('standardize_mode', 'auto')
            },
            'my_upload': my_upload,
            'other_upload': other_upload,
            'is_creator': group['creator'] == username,
            'cardinality_result': cardinality,
            # 2026-07-02 双方对称: 已上传后立即显示明文前 20 + 运算后显示密文前 20
            'role': 'receiver' if group['creator'] == username else 'sender',
        }
        role = 'receiver' if group['creator'] == username else 'sender'
        kunlun_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f"group_{group_id}")
        my_original_preview = []
        my_original_full_count = 0
        original_path = os.path.join(kunlun_dir, f"original_{role}.txt")
        if os.path.exists(original_path):
            with open(original_path, 'r', encoding='utf-8') as f:
                orig_lines = [l.strip() for l in f if l.strip()]
            my_original_preview = orig_lines[:20]
            my_original_full_count = len(orig_lines)
        my_ciphertext_preview = []
        my_ciphertext_full_count = 0
        ct_path = os.path.join(kunlun_dir, f"{role}_ciphertext.txt")
        if os.path.exists(ct_path):
            with open(ct_path, 'r', encoding='utf-8') as f:
                ct_lines = [l.strip() for l in f if l.strip()]
            my_ciphertext_preview = ct_lines[:20]
            my_ciphertext_full_count = len(ct_lines)
        response_payload['my_original_preview'] = my_original_preview
        response_payload['my_original_full_count'] = my_original_full_count
        response_payload['my_ciphertext_preview'] = my_ciphertext_preview
        response_payload['my_ciphertext_full_count'] = my_ciphertext_full_count
        response_payload['download_result_url'] = f'/api/psi-card-group/{group_id}/download-result-with-original'
        return jsonify(response_payload), 200
    except Exception as e:
        return jsonify({'error': f'获取 PSI-Card 小组信息失败:{str(e)}'}), 500


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
        return jsonify({'error': f'解散 PSI-Card 小组失败:{str(e)}'}), 500


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
            return jsonify({'error': '只支持.txt/csv/json 文件'}), 400

        # 2026-07-02 阶段 1 探测: ?probe=true 时只返回路径,不提取/不写文件
        if request.args.get('probe', '').lower() == 'true':
            if not file.filename.lower().endswith('.json'):
                return jsonify({
                    'success': True,
                    'is_probe': True,
                    'paths': [],
                    'filename': file.filename,
                    'message': '仅 .json 文件支持探测结构'
                })
            probe_content = file.read().decode('utf-8')
            try:
                probe_paths = _probe_json_paths(probe_content)
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            return jsonify({
                'success': True,
                'is_probe': True,
                'paths': probe_paths,
                'filename': file.filename,
                'message': f'探测完成,发现 {len(probe_paths)} 个潜在字段路径'
            })

        content = file.read().decode('utf-8')
        # 2026-07-01:使用 group 的 standardize_mode
        mode = group.get('standardize_mode', 'auto')
        # 2026-07-02:JSON path 协调 —— receiver 选一次 + sender 强制沿用 group.json_path
        is_json = file.filename.lower().endswith('.json')
        if username == group['creator']:
            form_path = request.form.get('path', '').strip() or None
            if is_json:
                # 2026-07-02:receiver 即使没传 form path,JSON 顶层有 path 字段也生效
                if not form_path:
                    try:
                        peek = json.loads(content)
                        if isinstance(peek, dict):
                            peek_path = peek.get('path')
                            if isinstance(peek_path, str):
                                form_path = peek_path
                    except Exception:
                        pass
                json_path = form_path
            else:
                json_path = None
        else:
            # sender: 强制从 group.json_path 读取(防两边各自选错)
            json_path = group.get('json_path')
            if is_json and not json_path:
                return jsonify({'error': '请等组长(receiver)上传并选择 JSON path'}), 400
            if not is_json:
                json_path = None
        try:
            items, original_items = extract_items_from_file(content, file.filename, mode, path=json_path)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        if not items:
            return jsonify({'error': '文件中未找到有效数据'}), 400

        # 2026-07-02 持久化 group.json_path:receiver 上传 JSON 且选了 path 时写入
        # 2026-07-02 bug fix:不能用 data 作变量名(会与下方写文件块冲突)
        if username == group['creator'] and is_json and json_path:
            all_groups = PSICardGroupManager.load_groups()
            g = next((x for x in all_groups.get('groups', []) if x['id'] == group_id), None)
            if g is not None:
                g['json_path'] = json_path
                PSICardGroupManager.save_groups(all_groups)

        # 保存到 Kunlun 目录(PSI_Card 数据)
        psi_card_data_dir = Config.KUNLUN_PSI_CARD_DATA_DIR
        group_data_dir = os.path.join(psi_card_data_dir, f"group_{group_id}")
        os.makedirs(group_data_dir, exist_ok=True)

        # 判断角色:组长是 receiver,成员是 sender
        if username == group['creator']:
            file_path = os.path.join(group_data_dir, "receiver.txt")
            role = "receiver"
        else:
            file_path = os.path.join(group_data_dir, "sender.txt")
            role = "sender"

        with open(file_path, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(f"{item}\n")

        # 2026-07-01:也保存原始 token 到 original_*.txt(给"下载我的明文"+ reverse_map 用)
        original_path = os.path.join(group_data_dir, f"original_{role}.txt")
        with open(original_path, 'w', encoding='utf-8') as f:
            for orig in original_items:
                f.write(f"{orig}\n")

        # 2026-07-02:保存原始上传字节到 uploaded_<role>.<ext>,下载时拿到和上传一样的格式
        filename_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'txt'
        if filename_ext not in ('txt', 'csv', 'json'):
            filename_ext = 'txt'
        uploaded_path = os.path.join(group_data_dir, f"uploaded_{role}.{filename_ext}")
        with open(uploaded_path, 'wb') as f:
            f.write(content.encode('utf-8'))

        print(f"[PSI-Card] {username} 已上传 {len(items)} 个元素到 {file_path} (角色: {role}, 标准化: {mode})")

        # 保存到小组数据
        PSICardGroupManager.add_upload(group_id, username, items, original_items, mode)

        # 检查双方是否都已上传(不再自动跑,改手动按 start-computation)
        group_after = PSICardGroupManager.get_group(group_id)
        uploaded_users = list(set([u['username'] for u in group_after.get('uploads', [])]))
        both_uploaded = len(uploaded_users) >= 2

        return jsonify({
            'message': '文件上传成功' + (',双方已上传,请组长点击"开始运算"按钮' if both_uploaded else ',等待对方上传'),
            'upload_count': len(items),
            'both_uploaded': both_uploaded,
            'card_completed': bool(os.path.exists(os.path.join(group_data_dir, 'cardinality.txt')))
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败:{str(e)}'}), 500


# 2026-07-02 新:组长(receiver)手动触发 PSI-Card 运算(双方都上传后才能调)
@app.route('/api/psi-card-group/<group_id>/start-computation', methods=['POST'])
@jwt_required
def api_start_psi_card_computation(group_id):
    try:
        group_id = group_id.upper()
        group = PSICardGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Card 小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        if username != group['creator']:
            return jsonify({'error': '只有 receiver(组长)可以手动触发运算'}), 403
        uploaded_users = list(set([u['username'] for u in group.get('uploads', [])]))
        if len(uploaded_users) < 2:
            return jsonify({'error': '双方未上传完成,无法运算'}), 400
        # 检测是否已完成过本轮
        group_data_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f"group_{group_id}")
        if os.path.exists(os.path.join(group_data_dir, 'cardinality.txt')):
            return jsonify({'error': '当前轮已运算完成,请先归档当前轮(finalize-round)'}), 409

        print(f"[PSI-Card] {username} 按下 [开始运算] 按钮(group={group_id})")
        result = _compute_with_timing(run_kunlun_psi_card, group_id)
        if not result['success']:
            return jsonify({'error': result.get('error', '计算失败')}), 500

        # 2026-07-02:存 pending_computation 到 group(最终 round_record 用)
        data = PSICardGroupManager.load_groups()
        for g in data['groups']:
            if g['id'] == group_id:
                g['pending_computation'] = {
                    'duration_seconds': result['duration_seconds'],
                    'duration_human': result['duration_human']
                }
                break
        PSICardGroupManager.save_groups(data)
        PSICardGroupManager.save_cardinality_result(group_id, result['cardinality'])

        return jsonify({
            'success': True,
            'cardinality': result['cardinality'],
            'duration_seconds': result['duration_seconds'],
            'duration_human': result['duration_human']
        }), 200
    except Exception as e:
        return jsonify({'error': f'运算失败:{str(e)}'}), 500


@app.route('/api/my-psi-card-groups', methods=['GET'])
@jwt_required
def api_get_my_psi_card_groups():
    try:
        groups = PSICardGroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取 PSI-Card 小组列表失败:{str(e)}'}), 500


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
        return jsonify({'error': f'删除失败:{str(e)}'}), 500


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
                if 'rounds' not in group:
                    group['rounds'] = []
                return group
        return None

    @staticmethod
    def create_group(group_name, creator, standardize_mode='auto'):
        data = PSIUnionGroupManager.load_groups()
        group_id = generate_id(4)
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'union_result': None,
            'rounds': [],
            'standardize_mode': standardize_mode,  # 2026-07-01:非数字输入标准化
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
                    return False, "小组已满(最多2人)"
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
    def add_upload(group_id, username, items, original_items=None, standardize_mode='auto'):
        data = PSIUnionGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'items': items,
                    'original_items': original_items or items,
                    'standardize_mode': standardize_mode,
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

    @staticmethod
    def finalize_round(group_id, completed_by):
        """归档当前轮次到 rounds,清空 uploads + result。"""
        data = PSIUnionGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] != group_id:
                continue
            if 'rounds' not in group:
                group['rounds'] = []
            kunlun_dir = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}")
            round_num = len(group['rounds']) + 1
            archive_dir = os.path.join(kunlun_dir, f"round{round_num}")
            os.makedirs(archive_dir, exist_ok=True)
            archive_files = {}
            # 2026-07-01:A 方案 - 归档 original_*.txt(让历史轮次能下载原始)
            for fname in ('receiver.txt', 'sender.txt', 'union.txt',
                          'receiver_ciphertext.txt', 'sender_ciphertext.txt',
                          'original_receiver.txt', 'original_sender.txt'):
                src = os.path.join(kunlun_dir, fname)
                if os.path.exists(src):
                    dst = os.path.join(archive_dir, fname)
                    shutil.copy2(src, dst)
                    archive_files[fname.replace('.txt', '')] = dst
            union_items = []
            if 'union' in archive_files:
                try:
                    with open(archive_files['union'], 'r', encoding='utf-8') as f:
                        union_items = [line.strip() for line in f if line.strip()]
                except Exception:
                    pass
            # 2026-07-01:写 union_with_original.txt(receiver 视角的 reverse map)
            if union_items:
                reverse_map = _build_reverse_map(group, group.get('standardize_mode', 'auto'))
                with_orig_path = os.path.join(archive_dir, 'union_with_original.txt')
                with open(with_orig_path, 'w', encoding='utf-8') as f:
                    for v in union_items:
                        f.write((reverse_map.get(v) or v) + '\n')
                archive_files['union_with_original'] = with_orig_path
            uploads_snapshot = {
                u['username']: u.get('numbers', [])
                for u in group.get('uploads', [])
            }
            round_record = {
                'round': round_num,
                'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'completed_by': completed_by,
                'uploads': uploads_snapshot,
                'archive_dir': archive_dir,
                'archive_files': archive_files,
                'result': {
                    'type': 'union',
                    'count': len(union_items)
                },
                'computation_seconds': (group.get('pending_computation') or {}).get('duration_seconds'),
                'computation_human': (group.get('pending_computation') or {}).get('duration_human'),
            }
            group['rounds'].append(round_record)
            group['uploads'] = []
            group['union_result'] = None
            # 2026-07-02:删顶层 stale 文件,防止下一轮看到老数据
            for stale_fname in ('union.txt',
                                'receiver_ciphertext.txt', 'sender_ciphertext.txt',
                                'sender_result.txt',
                                'original_receiver.txt', 'original_sender.txt',
                                'uploaded_receiver.json', 'uploaded_receiver.csv', 'uploaded_receiver.txt',
                                'uploaded_sender.json', 'uploaded_sender.csv', 'uploaded_sender.txt'):
                stale_path = os.path.join(kunlun_dir, stale_fname)
                if os.path.exists(stale_path):
                    os.remove(stale_path)
            PSIUnionGroupManager.save_groups(data)
            # 2026-07-02:清掉 pending_computation(round_record 已写入)
            group.pop('pending_computation', None)
            PSIUnionGroupManager.save_groups(data)
            return True, round_record
        return False, "小组不存在"

    @staticmethod
    def get_history(group_id, username):
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return None
        history = []
        for r in group.get('rounds', []):
            history.append({
                'round': r['round'],
                'completed_at': r['completed_at'],
                'completed_by': r['completed_by'],
                'my_upload_count': len(r['uploads'].get(username, [])),
                'result': r['result'],
                'is_receiver': r['uploads'].get(username, []) != [],
                # 2026-07-02:补轮次耗时
                'computation_seconds': r.get('computation_seconds'),
                'computation_human': r.get('computation_human')
            })
        return history

    @staticmethod
    def get_round_data(group_id, round_num, file_type, username):
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return None, "小组不存在"
        rounds = group.get('rounds', [])
        if round_num < 1 or round_num > len(rounds):
            return None, "轮次不存在"
        r = rounds[round_num - 1]
        archive_files = r.get('archive_files', {})
        if file_type == 'result':
            fpath = archive_files.get('union')
            if not fpath or not os.path.exists(fpath):
                return None, "结果文件不存在"
            return fpath, None
        if file_type == 'result_with_original':
            # 2026-07-01:receiver 视角的 reverse map,非数字项显示原始 token
            fpath = archive_files.get('union_with_original')
            if not fpath or not os.path.exists(fpath):
                return None, "原始版结果不存在(旧归档或尚未生成)"
            return fpath, None
        if file_type in ('my_plaintext', 'my_oprf'):
            if username not in group['members']:
                return None, "你不是该小组成员"
            is_current = (round_num == len(rounds))
            is_creator = (username == group['creator'])
            if file_type == 'my_plaintext':
                if is_current:
                    kunlun_dir = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}")
                    if is_creator:
                        orig_path = os.path.join(kunlun_dir, 'original_receiver.txt')
                        std_path = os.path.join(kunlun_dir, 'receiver.txt')
                    else:
                        orig_path = os.path.join(kunlun_dir, 'original_sender.txt')
                        std_path = os.path.join(kunlun_dir, 'sender.txt')
                    fpath = orig_path if os.path.exists(orig_path) else std_path
                else:
                    # 2026-07-01:A 方案 - 优先归档的 original,fallback 标准化
                    orig_key = 'original_receiver' if is_creator else 'original_sender'
                    std_key = 'receiver' if is_creator else 'sender'
                    fpath = archive_files.get(orig_key) or archive_files.get(std_key)
            else:  # my_oprf
                if is_current:
                    kunlun_dir = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}")
                    oprf_name = 'receiver_ciphertext.txt' if is_creator else 'sender_ciphertext.txt'
                    fpath = os.path.join(kunlun_dir, oprf_name)
                else:
                    oprf_key = 'receiver_ciphertext' if is_creator else 'sender_ciphertext'
                    fpath = archive_files.get(oprf_key)
            if not fpath or not os.path.exists(fpath):
                return None, "文件不存在"
            return fpath, None
        if file_type == 'my_original':
            # 2026-07-01:A 方案 - 归档里有 original_*.txt,这里走 archive(过去/当前都行)
            if username not in group['members']:
                return None, "你不是该小组成员"
            if is_current:
                kunlun_dir = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}")
                fname = 'original_receiver.txt' if is_creator else 'original_sender.txt'
                fpath = os.path.join(kunlun_dir, fname)
            else:
                orig_key = 'original_receiver' if is_creator else 'original_sender'
                fpath = archive_files.get(orig_key)
            if not fpath or not os.path.exists(fpath):
                return None, "原始 token 文件不存在(可能尚未上传)"
            return fpath, None
        return None, "未知文件类型"


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
        # 2026-07-01:标准化方式
        mode = data.get('standardizeMode', 'auto')
        if mode not in ('auto', 'number_only', 'text_all'):
            mode = 'auto'

        group = PSIUnionGroupManager.create_group(group_name, request.current_user['username'], mode)
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
        return jsonify({'error': f'创建 PSI-Union 小组失败:{str(e)}'}), 500


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
        return jsonify({'error': f'加入 PSI-Union 小组失败:{str(e)}'}), 500


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
            return jsonify({'error': '组长不能退出小组,请先解散小组'}), 400

        if PSIUnionGroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出 PSI-Union 小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出 PSI-Union 小组失败:{str(e)}'}), 500


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

        # ===== 修改:从文件读取并集结果,而不是从 group 对象 =====
        # 2026-07-01:finalize 后 uploads=[] 但顶层 union.txt 仍存在,不读避免老数据残留
        union_result = []
        if group.get('uploads'):
            union_result = read_union_from_file(group_id)
        # ===== 修改结束 =====
        # 2026-07-01:union_completed 标志(看 union.txt 是否存在,与并集大小无关)
        union_file = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}", "union.txt")
        union_completed = os.path.exists(union_file)

        # 2026-07-01:为 receiver 构建 reverse map,让并集中的非数字项显示原始 token
        # 优先 in-memory,退路读 kunlun_dir 顶层 original_receiver.txt
        # 重要:union_result 里的数字项可能转 int,reverse_map 的 key 是 str
        union_result_with_original = None
        if union_result:
            reverse_map = _build_reverse_map(group, group.get('standardize_mode', 'auto'))
            if not reverse_map:
                kunlun_dir = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}")
                orig_path = os.path.join(kunlun_dir, 'original_receiver.txt')
                if os.path.exists(orig_path):
                    with open(orig_path, 'r', encoding='utf-8') as f:
                        orig_items = [line.strip() for line in f if line.strip()]
                    mode = group.get('standardize_mode', 'auto')
                    reverse_map = {}
                    for o in orig_items:
                        s = _standardize_token(o, mode)
                        if s and s not in reverse_map:
                            reverse_map[s] = o
            if reverse_map:
                union_result_with_original = [
                    {'value': str(v), 'original': reverse_map.get(str(v))}
                    for v in union_result
                ]

        response_payload = {
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at'],
                'standardize_mode': group.get('standardize_mode', 'auto')
            },
            'my_upload': my_upload,
            'other_upload': other_upload,
            'is_creator': group['creator'] == username,
            'union_completed': union_completed,
            'union_count': len(union_result) if union_completed else None,
            'computation_seconds': group.get('pending_computation', {}).get('duration_seconds') if isinstance(group.get('pending_computation'), dict) else None,
            'computation_human': group.get('pending_computation', {}).get('duration_human') if isinstance(group.get('pending_computation'), dict) else None
        }
        # 2026-07-02 PSO 严格化被打破 — 双方对称显示(用户原话: sender 也要看到结果)
        role = 'receiver' if username == group['creator'] else 'sender'

        # 己方明文前 20(上传后立即显示,不等运算)
        kunlun_dir = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}")
        my_original_preview = []
        my_original_full_count = 0
        original_path = os.path.join(kunlun_dir, f"original_{role}.txt")
        if os.path.exists(original_path):
            with open(original_path, 'r', encoding='utf-8') as f:
                orig_lines = [l.strip() for l in f if l.strip()]
            my_original_preview = orig_lines[:20]
            my_original_full_count = len(orig_lines)

        # 己方密文前 20(双方对称)
        my_ciphertext_preview = []
        my_ciphertext_full_count = 0
        ct_path = os.path.join(kunlun_dir, f"{role}_ciphertext.txt")
        if os.path.exists(ct_path):
            with open(ct_path, 'r', encoding='utf-8') as f:
                ct_lines = [l.strip() for l in f if l.strip()]
            my_ciphertext_preview = ct_lines[:20]
            my_ciphertext_full_count = len(ct_lines)

        # 运算结果前 20(并集 — 2026-07-03 双方都能看到完整结果)
        # 合并 receiver + sender 两个 reverse_map(任一来源都能译码),双方视图一致
        result_preview = []
        result_full_count = len(union_result)
        if union_result:
            merged_reverse_map = {}
            mode = group.get('standardize_mode', 'auto')
            for u in group.get('uploads', []):
                for o in u.get('original_items', []):
                    s_tok = _standardize_token(o, mode)
                    if s_tok and s_tok not in merged_reverse_map:
                        merged_reverse_map[s_tok] = o
            for v in union_result[:20]:
                orig = merged_reverse_map.get(str(v)) or merged_reverse_map.get(v)
                result_preview.append({'value': str(v), 'original': orig})

        response_payload['role'] = role
        response_payload['my_original_preview'] = my_original_preview
        response_payload['my_original_full_count'] = my_original_full_count
        response_payload['my_ciphertext_preview'] = my_ciphertext_preview
        response_payload['my_ciphertext_full_count'] = my_ciphertext_full_count
        response_payload['result_preview'] = result_preview
        response_payload['result_full_count'] = result_full_count
        response_payload['download_result_url'] = f'/api/psi-union-group/{group_id}/download-result-with-original'
        return jsonify(response_payload), 200
    except Exception as e:
        return jsonify({'error': f'获取 PSI-Union 小组信息失败:{str(e)}'}), 500

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
        return jsonify({'error': f'解散 PSI-Union 小组失败:{str(e)}'}), 500


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
            return jsonify({'error': '只支持.txt/csv/json 文件'}), 400

        # 2026-07-02 阶段 1 探测: ?probe=true 时只返回路径,不提取/不写文件
        if request.args.get('probe', '').lower() == 'true':
            if not file.filename.lower().endswith('.json'):
                return jsonify({
                    'success': True,
                    'is_probe': True,
                    'paths': [],
                    'filename': file.filename,
                    'message': '仅 .json 文件支持探测结构'
                })
            probe_content = file.read().decode('utf-8')
            try:
                probe_paths = _probe_json_paths(probe_content)
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            return jsonify({
                'success': True,
                'is_probe': True,
                'paths': probe_paths,
                'filename': file.filename,
                'message': f'探测完成,发现 {len(probe_paths)} 个潜在字段路径'
            })

        content = file.read().decode('utf-8')
        # 2026-07-01:使用 group 的 standardize_mode
        mode = group.get('standardize_mode', 'auto')
        # 2026-07-02:JSON path 协调 —— receiver 选一次 + sender 强制沿用 group.json_path
        is_json = file.filename.lower().endswith('.json')
        if username == group['creator']:
            form_path = request.form.get('path', '').strip() or None
            if is_json:
                # 2026-07-02:receiver 即使没传 form path,JSON 顶层有 path 字段也生效
                if not form_path:
                    try:
                        peek = json.loads(content)
                        if isinstance(peek, dict):
                            peek_path = peek.get('path')
                            if isinstance(peek_path, str):
                                form_path = peek_path
                    except Exception:
                        pass
                json_path = form_path
            else:
                json_path = None
        else:
            # sender: 强制从 group.json_path 读取(防两边各自选错)
            json_path = group.get('json_path')
            if is_json and not json_path:
                return jsonify({'error': '请等组长(receiver)上传并选择 JSON path'}), 400
            if not is_json:
                json_path = None
        try:
            items, original_items = extract_items_from_file(content, file.filename, mode, path=json_path)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        if not items:
            return jsonify({'error': '文件中未找到有效数据'}), 400

        # 2026-07-02 持久化 group.json_path:receiver 上传 JSON 且选了 path 时写入
        # 2026-07-02 bug fix:不能用 data 作变量名(会与下方写文件块冲突)
        if username == group['creator'] and is_json and json_path:
            all_groups = PSIUnionGroupManager.load_groups()
            g = next((x for x in all_groups.get('groups', []) if x['id'] == group_id), None)
            if g is not None:
                g['json_path'] = json_path
                PSIUnionGroupManager.save_groups(all_groups)

        # ===== 保存到 Kunlun 目录(PSI_Union 数据) =====
        psi_union_data_dir = Config.KUNLUN_PSI_UNION_DATA_DIR
        group_data_dir = os.path.join(psi_union_data_dir, f"group_{group_id}")
        os.makedirs(group_data_dir, exist_ok=True)

        # 判断角色:组长是 receiver,成员是 sender
        if username == group['creator']:
            file_path = os.path.join(group_data_dir, "receiver.txt")
            role = "receiver"
        else:
            file_path = os.path.join(group_data_dir, "sender.txt")
            role = "sender"

        with open(file_path, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(f"{item}\n")

        # 2026-07-01:也保存原始 token 到 original_*.txt (给"下载我的明文"+ reverse_map 用)
        original_path = os.path.join(group_data_dir, f"original_{role}.txt")
        with open(original_path, 'w', encoding='utf-8') as f:
            for orig in original_items:
                f.write(f"{orig}\n")

        # 2026-07-02:保存原始上传字节到 uploaded_<role>.<ext>,下载时拿到和上传一样的格式
        filename_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'txt'
        if filename_ext not in ('txt', 'csv', 'json'):
            filename_ext = 'txt'
        uploaded_path = os.path.join(group_data_dir, f"uploaded_{role}.{filename_ext}")
        with open(uploaded_path, 'wb') as f:
            f.write(content.encode('utf-8'))

        print(f"[PSI-Union] {username} 已上传 {len(items)} 个元素到 {file_path} (角色: {role}, 标准化: {mode})")

        # 保存到小组数据
        PSIUnionGroupManager.add_upload(group_id, username, items, original_items, mode)

        # 检查双方是否都已上传(不再自动跑,改手动按 start-computation)
        group_after = PSIUnionGroupManager.get_group(group_id)
        uploaded_users = list(set([u['username'] for u in group_after.get('uploads', [])]))
        both_uploaded = len(uploaded_users) >= 2

        union_completed = bool(os.path.exists(os.path.join(group_data_dir, 'union.txt')))

        return jsonify({
            'message': '文件上传成功' + (',双方已上传,请组长点击"开始运算"按钮' if both_uploaded else ',等待对方上传'),
            'upload_count': len(items),
            'both_uploaded': both_uploaded,
            'union_completed': union_completed
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败:{str(e)}'}), 500

@app.route('/api/my-psi-union-groups', methods=['GET'])
@jwt_required
def api_get_my_psi_union_groups():
    try:
        groups = PSIUnionGroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取 PSI-Union 小组列表失败:{str(e)}'}), 500


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
        return jsonify({'error': f'删除失败:{str(e)}'}), 500


# ==================== 路由:静态文件服务 ====================
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
        return jsonify({'error': f'注册失败:{str(e)}'}), 500


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
        return jsonify({'error': f'登录失败:{str(e)}'}), 500


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
        # 2026-07-01:标准化方式
        mode = data.get('standardizeMode', 'auto')
        if mode not in ('auto', 'number_only', 'text_all'):
            mode = 'auto'

        group = PSIGroupManager.create_group(group_name, request.current_user['username'], mode)
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
        return jsonify({'error': f'创建隐私求交小组失败:{str(e)}'}), 500


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
        return jsonify({'error': f'加入隐私求交小组失败:{str(e)}'}), 500


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
            return jsonify({'error': '组长不能退出小组,请先解散小组'}), 400

        if PSIGroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出隐私求交小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出隐私求交小组失败:{str(e)}'}), 500


@app.route('/api/my-psi-groups', methods=['GET'])
@jwt_required
def api_get_my_psi_groups():
    try:
        groups = PSIGroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取隐私求交小组列表失败:{str(e)}'}), 500


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

        # 2026-07-01:只有当前轮有 uploads 时才读 intersection.txt
        # finalize 后 uploads=[] 但顶层 intersection.txt 仍存在(老数据),不读
        # 避免 saveAndStartNewRound 后老结果残留
        intersection = []
        if group.get('uploads'):
            intersection = read_intersection_from_file(group_id)
        # 2026-07-01:psi_completed 标志(看 intersection.txt 是否存在,与 psi_result.length 无关)
        # 修复"0 交集时按钮不显示"bug
        intersection_file = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f"group_{group_id}", "intersection.txt")
        psi_completed = os.path.exists(intersection_file)

        # 2026-07-01:为 receiver 构建 reverse map,让非数字交集项显示原始 token
        # 优先用 group['uploads'] 的 in-memory original_items(finalize 后会被清空)
        # 退路:读 kunlun_dir 顶层的 original_receiver.txt(finalize 不删,utf-8 时期有效)
        # 重要:intersection 里的数字项被 read_intersection_from_file 转成 int,reverse_map 的 key 是 str
        # 必须 str(v) 做 lookup,否则 int(10409) 查不到 str('10409')
        psi_result_with_original = None
        if intersection:
            reverse_map = _build_reverse_map(group, group.get('standardize_mode', 'auto'))
            if not reverse_map:
                # 退路:从顶层 original_receiver.txt 读(utf-8,finalize 后还在)
                kunlun_dir = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f"group_{group_id}")
                orig_path = os.path.join(kunlun_dir, 'original_receiver.txt')
                if os.path.exists(orig_path):
                    with open(orig_path, 'r', encoding='utf-8') as f:
                        orig_items = [line.strip() for line in f if line.strip()]
                    mode = group.get('standardize_mode', 'auto')
                    reverse_map = {}
                    for o in orig_items:
                        s = _standardize_token(o, mode)
                        if s and s not in reverse_map:
                            reverse_map[s] = o
            if reverse_map:
                psi_result_with_original = [
                    {'value': v, 'original': reverse_map.get(str(v))}
                    for v in intersection
                ]

        # 2026-07-02 PSO 严格化被打破 — 双方对称显示(用户原话: sender 也要看到密文/交集)
        role = 'receiver' if username == group['creator'] else 'sender'

        # 己方明文前 20(双方对称 — 上传后立即显示,不等运算)
        my_original_preview = []
        my_original_full_count = 0
        original_path = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f"group_{group_id}", f"original_{role}.txt")
        if os.path.exists(original_path):
            with open(original_path, 'r', encoding='utf-8') as f:
                orig_lines = [l.strip() for l in f if l.strip()]
            my_original_preview = orig_lines[:20]
            my_original_full_count = len(orig_lines)

        # 己方密文前 20(双方对称 — OPRF 输出)
        my_ciphertext_preview = []
        my_ciphertext_full_count = 0
        ct_path = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f"group_{group_id}", f"{role}_ciphertext.txt")
        if os.path.exists(ct_path):
            with open(ct_path, 'r', encoding='utf-8') as f:
                ct_lines = [l.strip() for l in f if l.strip()]
            my_ciphertext_preview = ct_lines[:20]
            my_ciphertext_full_count = len(ct_lines)

        # 运算结果前 20(交集 — 2026-07-03 双方都能看到完整明文)
        # 交集里双方都上传了该元素,合并两个 reverse_map 完全译码
        result_preview = []
        result_full_count = 0
        if psi_completed and intersection:
            merged_reverse_map = {}
            mode = group.get('standardize_mode', 'auto')
            for u in group.get('uploads', []):
                for o in u.get('original_items', []):
                    s_tok = _standardize_token(o, mode)
                    if s_tok and s_tok not in merged_reverse_map:
                        merged_reverse_map[s_tok] = o
            for v in intersection[:20]:
                result_preview.append({'value': str(v), 'original': merged_reverse_map.get(str(v))})
            result_full_count = len(intersection)

        response_payload = {
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at'],
                'standardize_mode': group.get('standardize_mode', 'auto'),
                'json_path': group.get('json_path')
            },
            'role': role,
            'my_upload': my_upload,
            'other_upload': other_upload,
            'is_creator': group['creator'] == username,
            'psi_completed': psi_completed,
            'intersection_count': len(intersection) if psi_completed else None,
            'computation_seconds': group.get('pending_computation', {}).get('duration_seconds') if isinstance(group.get('pending_computation'), dict) else None,
            'computation_human': group.get('pending_computation', {}).get('duration_human') if isinstance(group.get('pending_computation'), dict) else None,
            # 2026-07-02 双方对称预览(用户 4 个需求)
            'my_original_preview': my_original_preview,
            'my_original_full_count': my_original_full_count,
            'my_ciphertext_preview': my_ciphertext_preview,
            'my_ciphertext_full_count': my_ciphertext_full_count,
            'result_preview': result_preview,
            'result_full_count': result_full_count,
            # 双方都有的下载端点
            'download_result_url': f'/api/psi-group/{group_id}/download-result-with-original',
            'download_ciphertext_url': f'/api/psi-group/{group_id}/download-ciphertext/{role}',
            'download_original_url': f'/api/psi-group/{group_id}/download-original/{role}'
        }
        # receiver 还可以拿完整全集(除了 result_preview 已经覆盖)
        if group['creator'] == username:
            response_payload['psi_result'] = intersection
            response_payload['psi_result_with_original'] = psi_result_with_original
        return jsonify(response_payload), 200
    except Exception as e:
        return jsonify({'error': f'获取隐私求交小组信息失败:{str(e)}'}), 500


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
        return jsonify({'error': f'解散隐私求交小组失败:{str(e)}'}), 500


# ==================== 多轮历史记录(2026-07-01)====================
# 2026-07-02 新增:组长(receiver)手动触发的"开始运算"端点
@app.route('/api/psi-group/<group_id>/start-computation', methods=['POST'])
@jwt_required
def api_psi_group_start_computation(group_id):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404

        username = request.current_user['username']
        if username != group['creator']:
            return jsonify({'error': '只有组长(receiver)可以触发开始运算'}), 403

        uploaded_users = list(set([u['username'] for u in group.get('uploads', [])]))
        if len(uploaded_users) < 2:
            return jsonify({'error': '双方文件未全部上传'}), 400

        psi_data_dir = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f"group_{group_id}")
        intersection_file = os.path.join(psi_data_dir, 'intersection.txt')
        if os.path.exists(intersection_file):
            return jsonify({'error': '当前轮已运算完成,请先归档当前轮(finalize-round)'}), 409

        print(f"[PSI] {username} 按下 [开始运算] 按钮(group={group_id})")
        result = _compute_with_timing(run_kunlun_psi, group_id)
        if not result['success']:
            return jsonify({'error': result.get('error', '计算失败')}), 500

        # 把计时暂存到 group['pending_computation'],finalize_round 时写到 round_record
        # 2026-07-02 修复:_save() 不存在,改为重新 load + 修改 + save
        data = PSIGroupManager.load_groups()
        for g in data['groups']:
            if g['id'] == group_id:
                g['pending_computation'] = {
                    'duration_seconds': result['duration_seconds'],
                    'duration_human': result['duration_human']
                }
                break
        PSIGroupManager.save_groups(data)

        return jsonify({
            'success': True,
            'intersection': result['intersection'],
            'intersection_count': len(result['intersection']),
            'duration_seconds': result['duration_seconds'],
            'duration_human': result['duration_human']
        }), 200
    except Exception as e:
        return jsonify({'error': f'运算失败:{str(e)}'}), 500


@app.route('/api/psi-group/<group_id>/finalize-round', methods=['POST'])
@jwt_required
def api_finalize_psi_round(group_id):
    """receiver (= creator=组长) 手动保存当前结果到历史,清空 uploads,开始下一轮"""
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        # 只有 receiver (= creator=组长) 可以点保存
        if username != group['creator']:
            return jsonify({'error': '只有 receiver(组长)可以保存当前结果'}), 403
        # 校验:双方都上传 + result 已生成
        uploaded_users = [u['username'] for u in group.get('uploads', [])]
        if len(set(uploaded_users)) < 2:
            return jsonify({'error': '需要双方都上传文件后才能保存'}), 400
        result_file = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f"group_{group_id}", "intersection.txt")
        if not os.path.exists(result_file):
            return jsonify({'error': '当前结果未生成,无法保存'}), 400
        success, round_record = PSIGroupManager.finalize_round(group_id, username)
        if not success:
            return jsonify({'error': round_record}), 500
        return jsonify({
            'message': f'第 {round_record["round"]} 轮已保存到历史,双方可重新上传开始下一轮',
            'round': round_record['round'],
            'completed_at': round_record['completed_at']
        }), 200
    except Exception as e:
        return jsonify({'error': f'保存轮次失败:{str(e)}'}), 500


@app.route('/api/psi-group/<group_id>/history', methods=['GET'])
@jwt_required
def api_get_psi_history(group_id):
    """返回该小组所有 round 记录(user 视角:只暴露自己那份明文)"""
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        history = PSIGroupManager.get_history(group_id, username)
        return jsonify({
            'group_id': group_id,
            'rounds': history,
            'is_receiver': username == group['creator']
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取历史记录失败:{str(e)}'}), 500


@app.route('/api/psi-group/<group_id>/round/<int:round_num>/download', methods=['GET'])
@jwt_required
def api_download_psi_round(group_id, round_num):
    """下载某 round 的归档文件。type: my_plaintext | my_oprf | result"""
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        file_type = request.args.get('type', 'result')
        fpath, err = PSIGroupManager.get_round_data(group_id, round_num, file_type, username)
        if err:
            return jsonify({'error': err}), 404
        # send_from_directory 需要 (directory, filename) 形式
        directory = os.path.dirname(fpath)
        filename = os.path.basename(fpath)
        return send_from_directory(directory, filename, as_attachment=True,
                                   download_name=f'psi_{group_id}_round{round_num}_{file_type}.txt')
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


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
            return jsonify({'error': '只支持.txt/csv/json 文件'}), 400

        # 2026-07-02 阶段 1 探测: ?probe=true 时只返回路径,不提取/不写文件
        if request.args.get('probe', '').lower() == 'true':
            if not file.filename.lower().endswith('.json'):
                return jsonify({
                    'success': True,
                    'is_probe': True,
                    'paths': [],
                    'filename': file.filename,
                    'message': '仅 .json 文件支持探测结构'
                })
            probe_content = file.read().decode('utf-8')
            try:
                probe_paths = _probe_json_paths(probe_content)
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            return jsonify({
                'success': True,
                'is_probe': True,
                'paths': probe_paths,
                'filename': file.filename,
                'message': f'探测完成,发现 {len(probe_paths)} 个潜在字段路径'
            })

        content = file.read().decode('utf-8')
        # 2026-07-01:使用 group 的 standardize_mode
        mode = group.get('standardize_mode', 'auto')
        # 2026-07-02:JSON path 协调 —— receiver 选一次 + sender 强制沿用 group.json_path
        is_json = file.filename.lower().endswith('.json')
        if username == group['creator']:
            form_path = request.form.get('path', '').strip() or None
            if is_json:
                # 2026-07-02:receiver 即使没传 form path,JSON 顶层有 path 字段也生效
                if not form_path:
                    try:
                        peek = json.loads(content)
                        if isinstance(peek, dict):
                            peek_path = peek.get('path')
                            if isinstance(peek_path, str):
                                form_path = peek_path
                    except Exception:
                        pass
                json_path = form_path
            else:
                json_path = None
        else:
            # sender: 强制从 group.json_path 读取(防两边各自选错)
            json_path = group.get('json_path')
            if is_json and not json_path:
                return jsonify({'error': '请等组长(receiver)上传并选择 JSON path'}), 400
            if not is_json:
                json_path = None
        try:
            data, original_items = extract_items_from_file(content, file.filename, mode, path=json_path)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        if not data:
            return jsonify({'error': '文件中未找到有效数据'}), 400

        # 2026-07-02 持久化 group.json_path:receiver 上传 JSON 且选了 path 时写入
        # 2026-07-02 bug fix:不能用 data 作变量名(会与下方写文件块 for item in data 冲突)
        if username == group['creator'] and is_json and json_path:
            all_groups = PSIGroupManager.load_groups()
            g = next((x for x in all_groups.get('groups', []) if x['id'] == group_id), None)
            if g is not None:
                g['json_path'] = json_path
                PSIGroupManager.save_groups(all_groups)

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

        # 2026-07-01:也保存原始 token 到 original_*.txt (给"下载我的明文"+ reverse_map 用)
        original_path = os.path.join(group_data_dir, f"original_{role}.txt")
        with open(original_path, 'w', encoding='utf-8') as f:
            for orig in original_items:
                f.write(f"{orig}\n")

        # 2026-07-02:保存原始上传字节到 uploaded_<role>.<ext>,下载时拿到和上传一样的格式
        filename_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'txt'
        if filename_ext not in ('txt', 'csv', 'json'):
            filename_ext = 'txt'
        uploaded_path = os.path.join(group_data_dir, f"uploaded_{role}.{filename_ext}")
        with open(uploaded_path, 'wb') as f:
            f.write(content.encode('utf-8'))

        print(f"[PSI] {username} 已上传 {len(data)} 个元素到 {file_path} (角色: {role}, 标准化: {mode})")

        PSIGroupManager.add_upload(group_id, username, data, original_items, mode)

        group_after = PSIGroupManager.get_group(group_id)
        uploaded_users = list(set([u['username'] for u in group_after.get('uploads', [])]))
        both_uploaded = len(uploaded_users) >= 2
        intersection_file = os.path.join(group_data_dir, "intersection.txt")

        if both_uploaded:
            print(f"[PSI] 双方均已上传,等待 receiver 手动按 [开始运算] 按钮(group={group_id})")
        else:
            print(f"[PSI] {username} 已上传,等待对方上传 (group={group_id})")

        return jsonify({
            'message': '文件上传成功' + (',双方已上传,请组长点击"开始运算"按钮' if both_uploaded else ',等待对方上传'),
            'upload_count': len(data),
            'both_uploaded': both_uploaded,
            'psi_completed': os.path.exists(intersection_file)
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败:{str(e)}'}), 500


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
        return jsonify({'error': f'删除失败:{str(e)}'}), 500


# ==================== PSI 预览 / 下载接口 ====================
# 返回"己方密文前 20",供前端展示运算过程中要发给对方的密文
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

        # 组长是接收方(receiver),成员是发送方(sender)
        role = 'receiver' if username == group['creator'] else 'sender'
        ciphertext_file = os.path.join(
            Config.KUNLUN_PSI_DATA_DIR,
            f'group_{group_id}',
            f'{role}_ciphertext.txt'
        )

        if not os.path.exists(ciphertext_file):
            return jsonify({'error': f'密文文件不存在,请先完成计算 ({role}_ciphertext.txt)'}), 404

        with open(ciphertext_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().split('\n')[:20]

        return jsonify({
            'role': role,
            'ciphertext': lines,
            'total_count': sum(1 for _ in open(ciphertext_file, 'r', encoding='utf-8'))
        }), 200
    except Exception as e:
        return jsonify({'error': f'读取密文失败:{str(e)}'}), 500


# 2026-07-02 新:双方都能下载原文格式的完整结果(intersection hash 用己 reverse_map 翻译)
@app.route('/api/psi-group/<group_id>/download-result-with-original', methods=['GET'])
@jwt_required
def api_psi_download_result_with_original(group_id):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求交小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        result_file = os.path.join(
            Config.KUNLUN_PSI_DATA_DIR, f'group_{group_id}', 'intersection.txt'
        )
        if not os.path.exists(result_file):
            return jsonify({'error': '结果文件不存在,请先完成 PSI 计算'}), 404

        # 读 hash 形式的 intersection
        with open(result_file, 'r', encoding='utf-8') as f:
            hashes = [l.strip() for l in f if l.strip()]

        # 构建己 reverse_map(译码自己上传的 token,不能译码则保留 hash)
        mode = group.get('standardize_mode', 'auto')
        my_upload = next((u for u in group.get('uploads', []) if u['username'] == username), None)
        reverse_map = {}
        if my_upload:
            for o in my_upload.get('original_items', []):
                std = _standardize_token(o, mode)
                if std and std not in reverse_map:
                    reverse_map[std] = o

        translated = []  # 译码后的列表
        for h in hashes:
            v = reverse_map.get(h)
            if v is not None:
                translated.append(v)
            else:
                translated.append(f'# 未译码(hash): {h}')

        # 2026-07-02:下载格式 = 上传格式
        # 找 receiver 上传的原始文件后缀(.json/.csv/.txt),按对应格式输出
        group_dir = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f'group_{group_id}')
        uploaded_ext = 'txt'  # 默认
        for ext in ('json', 'csv', 'txt'):
            p = os.path.join(group_dir, f'uploaded_receiver.{ext}')
            if os.path.exists(p):
                uploaded_ext = ext
                break

        if uploaded_ext == 'json':
            # JSON 格式: {"intersection": [...], "count": N}
            import json as json_mod
            body_obj = {
                'group_id': group_id,
                'protocol': 'PSI',
                'intersection_count': len(translated),
                'intersection': translated
            }
            body = json_mod.dumps(body_obj, ensure_ascii=False, indent=2)
            mime = 'application/json'
            dl_name = f'psi_intersection_{group_id}.json'
        elif uploaded_ext == 'csv':
            # CSV 格式: intersection 列表
            lines = ['intersection']
            lines.extend(translated)
            body = '\n'.join(lines) + '\n'
            mime = 'text/csv'
            dl_name = f'psi_intersection_{group_id}.csv'
        else:
            # TXT 格式: 每行一个值
            body = '\n'.join(translated) + ('\n' if translated else '')
            mime = 'text/plain'
            dl_name = f'psi_intersection_{group_id}.txt'

        from io import BytesIO
        buf = BytesIO(body.encode('utf-8'))
        from flask import send_file
        return send_file(
            buf, as_attachment=True,
            download_name=dl_name,
            mimetype=mime
        )
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


# 2026-07-02 新:双方都能下载己密文全文
@app.route('/api/psi-group/<group_id>/download-ciphertext/<role>', methods=['GET'])
@jwt_required
def api_psi_download_ciphertext_for_role(group_id, role):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        # 2026-07-02:每方只能下载自己 role 的密文 —— receiver 不能下 sender
        is_creator = username == group['creator']
        my_role = 'receiver' if is_creator else 'sender'
        if role != my_role:
            return jsonify({'error': f'只有 {my_role} 本人能下载 {role} 密文'}), 403

        ct_file = os.path.join(
            Config.KUNLUN_PSI_DATA_DIR, f'group_{group_id}', f'{role}_ciphertext.txt'
        )
        if not os.path.exists(ct_file):
            return jsonify({'error': '密文文件不存在'}), 404
        from flask import send_file
        return send_file(
            ct_file, as_attachment=True,
            download_name=f'psi_ciphertext_{role}_{group_id}.txt',
            mimetype='text/plain'
        )
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


# 2026-07-02 新:双方都能下载己明文(原始上传字节 + 原始后缀,格式与上传一致)
@app.route('/api/psi-group/<group_id>/download-original/<role>', methods=['GET'])
@jwt_required
def api_psi_download_original_for_role(group_id, role):
    try:
        group_id = group_id.upper()
        group = PSIGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        is_creator = username == group['creator']
        # 2026-07-02:每方只能下载自己 role 的明文 —— receiver 不能下 sender,反之亦然
        my_role = 'receiver' if is_creator else 'sender'
        if role != my_role:
            return jsonify({'error': f'只有 {my_role} 本人能下载 {role} 明文(隐私)'}), 403
        # 2026-07-02:优先返 uploaded_<role>.<ext>(原始上传字节),找不到才退到 original_<role>.txt
        group_dir = os.path.join(Config.KUNLUN_PSI_DATA_DIR, f'group_{group_id}')
        uploaded = None
        for ext in ('json', 'csv', 'txt'):
            p = os.path.join(group_dir, f'uploaded_{role}.{ext}')
            if os.path.exists(p):
                uploaded = p
                chosen_ext = ext
                break
        if uploaded:
            # mimetype
            mime_map = {'json': 'application/json', 'csv': 'text/csv', 'txt': 'text/plain'}
            from flask import send_file
            return send_file(
                uploaded, as_attachment=True,
                download_name=f'psi_original_{role}_{group_id}.{chosen_ext}',
                mimetype=mime_map.get(chosen_ext, 'application/octet-stream')
            )
        # 退路:老 original_<role>.txt
        orig_file = os.path.join(group_dir, f'original_{role}.txt')
        if not os.path.exists(orig_file):
            return jsonify({'error': '明文文件不存在'}), 404
        from flask import send_file
        return send_file(
            orig_file, as_attachment=True,
            download_name=f'psi_original_{role}_{group_id}.txt',
            mimetype='text/plain'
        )
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


# 旧版(保留兼容): 直接给 hash 形式 intersection
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
            return jsonify({'error': '结果文件不存在,请先完成 PSI 计算'}), 404

        from flask import send_file
        return send_file(
            result_file,
            as_attachment=True,
            download_name=f'psi_intersection_{group_id}.txt',
            mimetype='text/plain'
        )
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


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

        # 组长是接收方(receiver),成员是发送方(sender)
        role = 'receiver' if username == group['creator'] else 'sender'
        ciphertext_file = os.path.join(
            Config.KUNLUN_PSI_UNION_DATA_DIR,
            f'group_{group_id}',
            f'{role}_ciphertext.txt'
        )

        if not os.path.exists(ciphertext_file):
            return jsonify({'error': f'密文文件不存在,请先完成计算 ({role}_ciphertext.txt)'}), 404

        with open(ciphertext_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().split('\n')[:20]

        return jsonify({
            'role': role,
            'ciphertext': lines,
            'total_count': sum(1 for _ in open(ciphertext_file, 'r', encoding='utf-8'))
        }), 200
    except Exception as e:
        return jsonify({'error': f'读取密文失败:{str(e)}'}), 500


# 下载 PSU 结果文件(并集)
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
            return jsonify({'error': '结果文件不存在,请先完成 PSU 计算'}), 404

        from flask import send_file
        return send_file(
            result_file,
            as_attachment=True,
            download_name=f'psu_union_{group_id}.txt',
            mimetype='text/plain'
        )
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


# 2026-07-02 新:下载 PSU 结果(按上传格式 .json/.csv/.txt)
@app.route('/api/psi-union-group/<group_id>/download-result-with-original', methods=['GET'])
@jwt_required
def api_psi_union_download_result_with_original(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求并小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        result_file = os.path.join(
            Config.KUNLUN_PSI_UNION_DATA_DIR, f'group_{group_id}', 'union.txt'
        )
        if not os.path.exists(result_file):
            return jsonify({'error': '结果文件不存在,请先完成 PSU 计算'}), 404

        with open(result_file, 'r', encoding='utf-8') as f:
            hashes = [l.strip() for l in f if l.strip()]

        mode = group.get('standardize_mode', 'auto')
        my_upload = next((u for u in group.get('uploads', []) if u['username'] == username), None)
        reverse_map = {}
        if my_upload:
            for o in my_upload.get('original_items', []):
                std = _standardize_token(o, mode)
                if std and std not in reverse_map:
                    reverse_map[std] = o

        translated = []
        for h in hashes:
            v = reverse_map.get(h)
            if v is not None:
                translated.append(v)
            else:
                translated.append(f'# 未译码(hash): {h}')

        # 按 receiver 上传后缀输出
        group_dir = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f'group_{group_id}')
        uploaded_ext = 'txt'
        for ext in ('json', 'csv', 'txt'):
            p = os.path.join(group_dir, f'uploaded_receiver.{ext}')
            if os.path.exists(p):
                uploaded_ext = ext
                break

        if uploaded_ext == 'json':
            import json as json_mod
            body_obj = {
                'group_id': group_id,
                'protocol': 'PSU',
                'union_count': len(translated),
                'union': translated
            }
            body = json_mod.dumps(body_obj, ensure_ascii=False, indent=2)
            mime = 'application/json'
            dl_name = f'psu_union_{group_id}.json'
        elif uploaded_ext == 'csv':
            lines = ['union']
            lines.extend(translated)
            body = '\n'.join(lines) + '\n'
            mime = 'text/csv'
            dl_name = f'psu_union_{group_id}.csv'
        else:
            body = '\n'.join(translated) + ('\n' if translated else '')
            mime = 'text/plain'
            dl_name = f'psu_union_{group_id}.txt'

        from io import BytesIO
        from flask import send_file
        buf = BytesIO(body.encode('utf-8'))
        return send_file(buf, as_attachment=True, download_name=dl_name, mimetype=mime)
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


# ==================== PSI-Union 多轮历史 API ====================

# 2026-07-02 新增:组长(receiver)手动触发的"开始运算"端点
@app.route('/api/psi-union-group/<group_id>/start-computation', methods=['POST'])
@jwt_required
def api_psi_union_group_start_computation(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求并小组不存在'}), 404

        username = request.current_user['username']
        if username != group['creator']:
            return jsonify({'error': '只有组长(receiver)可以触发开始运算'}), 403

        uploaded_users = list(set([u['username'] for u in group.get('uploads', [])]))
        if len(uploaded_users) < 2:
            return jsonify({'error': '双方文件未全部上传'}), 400

        psu_data_dir = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f"group_{group_id}")
        union_file = os.path.join(psu_data_dir, 'union.txt')
        if os.path.exists(union_file):
            return jsonify({'error': '当前轮已运算完成,请先归档当前轮(finalize-round)'}), 409

        print(f"[PSI-Union] {username} 按下 [开始运算] 按钮(group={group_id})")
        result = _compute_with_timing(run_kunlun_psu, group_id)
        if not result['success']:
            return jsonify({'error': result.get('error', '计算失败')}), 500

        # 2026-07-02 修复:_save() 不存在,改为重新 load + 修改 + save
        data = PSIUnionGroupManager.load_groups()
        for g in data['groups']:
            if g['id'] == group_id:
                g['pending_computation'] = {
                    'duration_seconds': result['duration_seconds'],
                    'duration_human': result['duration_human']
                }
                break
        PSIUnionGroupManager.save_groups(data)
        # 保存并集结果
        PSIUnionGroupManager.save_union_result(group_id, result['union'])

        return jsonify({
            'success': True,
            'union': result['union'],
            'union_count': len(result['union']),
            'duration_seconds': result['duration_seconds'],
            'duration_human': result['duration_human']
        }), 200
    except Exception as e:
        return jsonify({'error': f'运算失败:{str(e)}'}), 500


@app.route('/api/psi-union-group/<group_id>/finalize-round', methods=['POST'])
@jwt_required
def api_psi_union_finalize_round(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求并小组不存在'}), 404
        username = request.current_user['username']
        if username != group['creator']:
            return jsonify({'error': '只有 receiver(组长)可以保存当前结果'}), 403
        if len(group.get('uploads', [])) < 2:
            return jsonify({'error': '需要双方都上传文件后才能保存'}), 400
        result_file = os.path.join(Config.KUNLUN_PSI_UNION_DATA_DIR, f'group_{group_id}', 'union.txt')
        if not os.path.exists(result_file):
            return jsonify({'error': '结果文件不存在,请先完成 PSU 计算'}), 400
        ok, record = PSIUnionGroupManager.finalize_round(group_id, username)
        if not ok:
            return jsonify({'error': record}), 500
        return jsonify({
            'message': f'第 {record["round"]} 轮已保存到历史,双方可重新上传开始下一轮',
            'round': record['round'],
            'completed_at': record['completed_at']
        }), 200
    except Exception as e:
        return jsonify({'error': f'保存失败:{str(e)}'}), 500

@app.route('/api/psi-union-group/<group_id>/history', methods=['GET'])
@jwt_required
def api_psi_union_history(group_id):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求并小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        history = PSIUnionGroupManager.get_history(group_id, username)
        return jsonify({
            'group_id': group_id,
            'is_receiver': group['creator'] == username,
            'rounds': history or []
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取历史失败:{str(e)}'}), 500

@app.route('/api/psi-union-group/<group_id>/round/<int:round_num>/download', methods=['GET'])
@jwt_required
def api_psi_union_download_round(group_id, round_num):
    try:
        group_id = group_id.upper()
        group = PSIUnionGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '隐私求并小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        file_type = request.args.get('type', 'result')
        fpath, err = PSIUnionGroupManager.get_round_data(group_id, round_num, file_type, username)
        if err:
            return jsonify({'error': err}), 404
        directory = os.path.dirname(fpath)
        filename = os.path.basename(fpath)
        return send_from_directory(directory, filename, as_attachment=True,
                                   download_name=f'psu_{group_id}_round{round_num}_{file_type}.txt')
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


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
                if 'rounds' not in group:
                    group['rounds'] = []
                return group
        return None

    @staticmethod
    def create_group(group_name, creator, standardize_mode='auto'):
        data = PSIMatchGroupManager.load_groups()
        group_id = generate_id(4)
        group_data = {
            'id': group_id,
            'name': group_name,
            'creator': creator,
            'members': [creator],
            'uploads': [],
            'subset_result': None,
            'rounds': [],
            'standardize_mode': standardize_mode,  # 2026-07-01:非数字输入标准化
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
                    return False, "小组已满(最多2人)"
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
    def add_upload(group_id, username, items, original_items=None, standardize_mode='auto'):
        data = PSIMatchGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] == group_id:
                group["uploads"] = [u for u in group["uploads"] if u["username"] != username]
                group["uploads"].append({
                    'username': username,
                    'items': items,
                    'original_items': original_items or items,
                    'standardize_mode': standardize_mode,
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

    @staticmethod
    def finalize_round(group_id, completed_by):
        """归档当前轮次到 rounds,清空 uploads + result。"""
        data = PSIMatchGroupManager.load_groups()
        for group in data["groups"]:
            if group["id"] != group_id:
                continue
            if 'rounds' not in group:
                group['rounds'] = []
            kunlun_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f"group_{group_id}")
            round_num = len(group['rounds']) + 1
            archive_dir = os.path.join(kunlun_dir, f"round{round_num}")
            os.makedirs(archive_dir, exist_ok=True)
            archive_files = {}
            # 2026-07-01:A 方案 - 归档 original_*.txt(让历史轮次能下载原始)
            for fname in ('receiver.txt', 'sender.txt', 'cardinality.txt',
                          'receiver_ciphertext.txt', 'sender_ciphertext.txt',
                          'sender_result_card.txt',
                          'original_receiver.txt', 'original_sender.txt'):
                src = os.path.join(kunlun_dir, fname)
                if os.path.exists(src):
                    dst = os.path.join(archive_dir, fname)
                    shutil.copy2(src, dst)
                    archive_files[fname.replace('.txt', '')] = dst
            cardinality = 0
            if 'cardinality' in archive_files:
                try:
                    with open(archive_files['cardinality'], 'r', encoding='utf-8') as f:
                        cardinality = int(f.read().strip())
                except Exception:
                    pass
            uploads_snapshot = {
                u['username']: u.get('items', [])
                for u in group.get('uploads', [])
            }
            round_record = {
                'round': round_num,
                'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'completed_by': completed_by,
                'uploads': uploads_snapshot,
                'archive_dir': archive_dir,
                'archive_files': archive_files,
                'result': {
                    'type': 'cardinality',
                    'count': cardinality
                },
                'computation_seconds': (group.get('pending_computation') or {}).get('duration_seconds'),
                'computation_human': (group.get('pending_computation') or {}).get('duration_human'),
            }
            group['rounds'].append(round_record)
            group['uploads'] = []
            group['subset_result'] = None
            # 2026-07-02:删顶层 stale 文件,防止下一轮看到老数据
            for stale_fname in ('cardinality.txt',
                                'receiver_ciphertext.txt', 'sender_ciphertext.txt',
                                'sender_result.txt', 'sender_result_card.txt',
                                'original_receiver.txt', 'original_sender.txt'):
                stale_path = os.path.join(kunlun_dir, stale_fname)
                if os.path.exists(stale_path):
                    os.remove(stale_path)
            for role in ('receiver', 'sender'):
                for ext in ('txt', 'csv', 'json'):
                    p = os.path.join(kunlun_dir, f'uploaded_{role}.{ext}')
                    if os.path.exists(p):
                        os.remove(p)
            PSIMatchGroupManager.save_groups(data)
            # 2026-07-02:清掉 pending_computation(round_record 已写入)
            group.pop('pending_computation', None)
            PSIMatchGroupManager.save_groups(data)
            return True, round_record
        return False, "小组不存在"

    @staticmethod
    def get_history(group_id, username):
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return None
        history = []
        for r in group.get('rounds', []):
            history.append({
                'round': r['round'],
                'completed_at': r['completed_at'],
                'completed_by': r['completed_by'],
                'my_upload_count': len(r['uploads'].get(username, [])),
                'result': r['result'],
                'is_receiver': r['uploads'].get(username, []) != [],
                # 2026-07-02:补轮次耗时
                'computation_seconds': r.get('computation_seconds'),
                'computation_human': r.get('computation_human')
            })
        return history

    @staticmethod
    def get_round_data(group_id, round_num, file_type, username):
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return None, "小组不存在"
        rounds = group.get('rounds', [])
        if round_num < 1 or round_num > len(rounds):
            return None, "轮次不存在"
        r = rounds[round_num - 1]
        archive_files = r.get('archive_files', {})
        if file_type == 'result':
            fpath = archive_files.get('cardinality')
            if not fpath or not os.path.exists(fpath):
                return None, "结果文件不存在"
            return fpath, None
        if file_type == 'result_with_original':
            # PSIMatch 的 cardinality 是数字,无 list,不需要原始版
            return None, "匹配结果是 cardinality(数字),无原始版"
        if file_type in ('my_plaintext', 'my_oprf'):
            if username not in group['members']:
                return None, "你不是该小组成员"
            is_current = (round_num == len(rounds))
            is_creator = (username == group['creator'])
            if file_type == 'my_plaintext':
                if is_current:
                    kunlun_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f"group_{group_id}")
                    if is_creator:
                        orig_path = os.path.join(kunlun_dir, 'original_receiver.txt')
                        std_path = os.path.join(kunlun_dir, 'receiver.txt')
                    else:
                        orig_path = os.path.join(kunlun_dir, 'original_sender.txt')
                        std_path = os.path.join(kunlun_dir, 'sender.txt')
                    fpath = orig_path if os.path.exists(orig_path) else std_path
                else:
                    # 2026-07-01:A 方案 - 优先归档的 original,fallback 标准化
                    orig_key = 'original_receiver' if is_creator else 'original_sender'
                    std_key = 'receiver' if is_creator else 'sender'
                    fpath = archive_files.get(orig_key) or archive_files.get(std_key)
            else:  # my_oprf
                if is_current:
                    kunlun_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f"group_{group_id}")
                    oprf_name = 'receiver_ciphertext.txt' if is_creator else 'sender_ciphertext.txt'
                    fpath = os.path.join(kunlun_dir, oprf_name)
                else:
                    oprf_key = 'receiver_ciphertext' if is_creator else 'sender_ciphertext'
                    fpath = archive_files.get(oprf_key)
            if not fpath or not os.path.exists(fpath):
                return None, "文件不存在"
            return fpath, None
        if file_type == 'my_original':
            # 2026-07-01:A 方案 - 归档里有 original_*.txt
            if username not in group['members']:
                return None, "你不是该小组成员"
            if is_current:
                kunlun_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f"group_{group_id}")
                fname = 'original_receiver.txt' if is_creator else 'original_sender.txt'
                fpath = os.path.join(kunlun_dir, fname)
            else:
                orig_key = 'original_receiver' if is_creator else 'original_sender'
                fpath = archive_files.get(orig_key)
            if not fpath or not os.path.exists(fpath):
                return None, "原始 token 文件不存在(可能尚未上传)"
            return fpath, None
        return None, "未知文件类型"


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
        # 2026-07-01:标准化方式
        mode = data.get('standardizeMode', 'auto')
        if mode not in ('auto', 'number_only', 'text_all'):
            mode = 'auto'

        group = PSIMatchGroupManager.create_group(group_name, request.current_user['username'], mode)
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
        return jsonify({'error': f'创建匹配小组失败:{str(e)}'}), 500


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
        return jsonify({'error': f'加入匹配小组失败:{str(e)}'}), 500


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
            return jsonify({'error': '组长不能退出小组,请先解散小组'}), 400

        if PSIMatchGroupManager.remove_member(group_id, username):
            return jsonify({'message': '已退出匹配小组'})
        return jsonify({'error': '你不是该小组成员'}), 400
    except Exception as e:
        return jsonify({'error': f'退出匹配小组失败:{str(e)}'}), 500


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

        response_payload = {
            'group': {
                'id': group['id'],
                'name': group['name'],
                'creator': group['creator'],
                'members': group['members'],
                'created_at': group['created_at'],
                'standardize_mode': group.get('standardize_mode', 'auto')
            },
            'my_upload': my_upload,
            'other_upload': other_upload,
            'is_creator': group['creator'] == username,
            'computation_seconds': group.get('pending_computation', {}).get('duration_seconds') if isinstance(group.get('pending_computation'), dict) else None,
            'computation_human': group.get('pending_computation', {}).get('duration_human') if isinstance(group.get('pending_computation'), dict) else None
        }
        # 2026-07-02 PSO 严格化被打破 — 双方对称显示
        role = 'receiver' if username == group['creator'] else 'sender'

        # 己方明文前 20
        # 2026-07-02:PSIMatch 底层用 PSIcard 计算,共享 KUNLUN_PSI_CARD_DATA_DIR
        kunlun_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f"group_{group_id}")
        my_original_preview = []
        my_original_full_count = 0
        original_path = os.path.join(kunlun_dir, f"original_{role}.txt")
        if os.path.exists(original_path):
            with open(original_path, 'r', encoding='utf-8') as f:
                orig_lines = [l.strip() for l in f if l.strip()]
            my_original_preview = orig_lines[:20]
            my_original_full_count = len(orig_lines)

        # 己方密文前 20
        my_ciphertext_preview = []
        my_ciphertext_full_count = 0
        ct_path = os.path.join(kunlun_dir, f"{role}_ciphertext.txt")
        if os.path.exists(ct_path):
            with open(ct_path, 'r', encoding='utf-8') as f:
                ct_lines = [l.strip() for l in f if l.strip()]
            my_ciphertext_preview = ct_lines[:20]
            my_ciphertext_full_count = len(ct_lines)

        response_payload['role'] = role
        response_payload['my_original_preview'] = my_original_preview
        response_payload['my_original_full_count'] = my_original_full_count
        response_payload['my_ciphertext_preview'] = my_ciphertext_preview
        response_payload['my_ciphertext_full_count'] = my_ciphertext_full_count

        # subset_result(只含 cardinality,无交集明细)
        subset = group.get('subset_result')
        if subset:
            response_payload['subset_result'] = subset  # 透传,前端直接读
            response_payload['intersection_cardinality'] = subset.get('intersectionCardinality')
            response_payload['is_subset'] = subset.get('isSubset')
            response_payload['missing_count'] = subset.get('missingCount')
        response_payload['download_result_url'] = f'/api/psi-match-group/{group_id}/download-result-with-original'
        return jsonify(response_payload), 200
    except Exception as e:
        return jsonify({'error': f'获取匹配小组信息失败:{str(e)}'}), 500


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
        return jsonify({'error': f'解散匹配小组失败:{str(e)}'}), 500


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
            return jsonify({'error': '只支持.txt/csv/json 文件'}), 400

        # 2026-07-02 阶段 1 探测: ?probe=true 时只返回路径,不提取/不写文件
        if request.args.get('probe', '').lower() == 'true':
            if not file.filename.lower().endswith('.json'):
                return jsonify({
                    'success': True,
                    'is_probe': True,
                    'paths': [],
                    'filename': file.filename,
                    'message': '仅 .json 文件支持探测结构'
                })
            probe_content = file.read().decode('utf-8')
            try:
                probe_paths = _probe_json_paths(probe_content)
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            return jsonify({
                'success': True,
                'is_probe': True,
                'paths': probe_paths,
                'filename': file.filename,
                'message': f'探测完成,发现 {len(probe_paths)} 个潜在字段路径'
            })

        content = file.read().decode('utf-8')
        # 2026-07-01:使用 group 的 standardize_mode
        mode = group.get('standardize_mode', 'auto')
        # 2026-07-02:JSON path 协调 —— receiver 选一次 + sender 强制沿用 group.json_path
        is_json = file.filename.lower().endswith('.json')
        if username == group['creator']:
            form_path = request.form.get('path', '').strip() or None
            if is_json:
                # 2026-07-02:receiver 即使没传 form path,JSON 顶层有 path 字段也生效
                if not form_path:
                    try:
                        peek = json.loads(content)
                        if isinstance(peek, dict):
                            peek_path = peek.get('path')
                            if isinstance(peek_path, str):
                                form_path = peek_path
                    except Exception:
                        pass
                json_path = form_path
            else:
                json_path = None
        else:
            # sender: 强制从 group.json_path 读取(防两边各自选错)
            json_path = group.get('json_path')
            if is_json and not json_path:
                return jsonify({'error': '请等组长(receiver)上传并选择 JSON path'}), 400
            if not is_json:
                json_path = None
        try:
            items, original_items = extract_items_from_file(content, file.filename, mode, path=json_path)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        if not items:
            return jsonify({'error': '文件中未找到有效数据'}), 400

        # 2026-07-02 持久化 group.json_path:receiver 上传 JSON 且选了 path 时写入
        # 2026-07-02 bug fix:不能用 data 作变量名(会与下方写文件块冲突)
        if username == group['creator'] and is_json and json_path:
            all_groups = PSIMatchGroupManager.load_groups()
            g = next((x for x in all_groups.get('groups', []) if x['id'] == group_id), None)
            if g is not None:
                g['json_path'] = json_path
                PSIMatchGroupManager.save_groups(all_groups)

        # 保存上传
        PSIMatchGroupManager.add_upload(group_id, username, items, original_items, mode)

        # ===== 保存到 Kunlun PSI-Card 目录(receiver.txt / sender.txt)=====
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

        # 2026-07-01:也保存原始 token (给"下载我的明文"+ reverse_map 用)
        original_path = os.path.join(group_data_dir, f"original_{role}.txt")
        with open(original_path, 'w', encoding='utf-8') as f:
            for orig in original_items:
                f.write(f"{orig}\n")

        # 2026-07-02:保存原始上传字节到 uploaded_<role>.<ext>,下载时拿到和上传一样的格式
        filename_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'txt'
        if filename_ext not in ('txt', 'csv', 'json'):
            filename_ext = 'txt'
        uploaded_path = os.path.join(group_data_dir, f"uploaded_{role}.{filename_ext}")
        with open(uploaded_path, 'wb') as f:
            f.write(content.encode('utf-8'))

        print(f"[PSI-Match] {username} 已上传 {len(items)} 个元素到 {file_path} (角色: {role}, 标准化: {mode})")

        # 2026-07-02:PM 改为手动触发,upload 不自动跑 PSIcard(与 PSI/PSU 一致)
        # 检查双方是否都已上传,但仅返回状态,不跑计算
        group_after = PSIMatchGroupManager.get_group(group_id)
        uploaded_users = list(set([u['username'] for u in group_after.get('uploads', [])]))
        is_subset = False
        subset_completed = False
        intersection_cardinality = 0
        missing_count = 0

        return jsonify({
            'message': '文件上传成功,等待 receiver 手动触发运算',
            'upload_count': len(items),
            'both_uploaded': len(uploaded_users) >= 2,
            'subset_completed': subset_completed,
            'is_subset': is_subset if subset_completed else None,
            'intersection_cardinality': intersection_cardinality if subset_completed else None,
            'missing_count': missing_count if subset_completed else None
        }), 200

    except Exception as e:
        return jsonify({'error': f'处理失败:{str(e)}'}), 500


@app.route('/api/my-psi-match-groups', methods=['GET'])
@jwt_required
def api_get_my_psi_match_groups():
    try:
        groups = PSIMatchGroupManager.get_user_groups(request.current_user['username'])
        return jsonify({'groups': groups}), 200
    except Exception as e:
        return jsonify({'error': f'获取匹配小组列表失败:{str(e)}'}), 500


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
        return jsonify({'error': f'删除失败:{str(e)}'}), 500


# 2026-07-02 新:PSIMatch 下载结果(按上传格式 .json/.csv/.txt)
@app.route('/api/psi-match-group/<group_id>/download-result-with-original', methods=['GET'])
@jwt_required
def api_psi_match_download_result_with_original(group_id):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        subset = group.get('subset_result')
        if not subset:
            return jsonify({'error': '结果未生成,请先完成集合匹配计算'}), 404

        group_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f'group_{group_id}')
        uploaded_ext = 'txt'
        for ext in ('json', 'csv', 'txt'):
            p = os.path.join(group_dir, f'uploaded_receiver.{ext}')
            if os.path.exists(p):
                uploaded_ext = ext
                break

        if uploaded_ext == 'json':
            import json as json_mod
            body_obj = {
                'group_id': group_id,
                'protocol': 'PSIMatch',
                'intersection_cardinality': subset.get('intersectionCardinality'),
                'is_subset': subset.get('isSubset'),
                'missing_count': subset.get('missingCount'),
                'note': 'PSIMatch 不返回交集明细,仅返回基数与是否子集(隐私)'
            }
            body = json_mod.dumps(body_obj, ensure_ascii=False, indent=2)
            mime = 'application/json'
            dl_name = f'psi_match_result_{group_id}.json'
        elif uploaded_ext == 'csv':
            lines = ['field,value']
            lines.append(f"intersection_cardinality,{subset.get('intersectionCardinality')}")
            lines.append(f"is_subset,{subset.get('isSubset')}")
            lines.append(f"missing_count,{subset.get('missingCount')}")
            body = '\n'.join(lines) + '\n'
            mime = 'text/csv'
            dl_name = f'psi_match_result_{group_id}.csv'
        else:
            body = (f"intersection_cardinality: {subset.get('intersectionCardinality')}\n"
                    f"is_subset: {subset.get('isSubset')}\n"
                    f"missing_count: {subset.get('missingCount')}\n")
            mime = 'text/plain'
            dl_name = f'psi_match_result_{group_id}.txt'

        from io import BytesIO
        from flask import send_file
        buf = BytesIO(body.encode('utf-8'))
        return send_file(buf, as_attachment=True, download_name=dl_name, mimetype=mime)
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


# 2026-07-02 新:PSIcard 下载基数(按上传格式)
@app.route('/api/psi-card-group/<group_id>/download-result-with-original', methods=['GET'])
@jwt_required
def api_psi_card_download_result_with_original(group_id):
    try:
        group_id = group_id.upper()
        group = PSICardGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': 'PSI-Card 小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403

        card_file = os.path.join(
            Config.KUNLUN_PSI_CARD_DATA_DIR, f'group_{group_id}', 'cardinality.txt'
        )
        if not os.path.exists(card_file):
            return jsonify({'error': '基数文件不存在,请先完成 PSI-Card 计算'}), 404
        with open(card_file, 'r', encoding='utf-8') as f:
            cardinality = f.read().strip()

        group_dir = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f'group_{group_id}')
        uploaded_ext = 'txt'
        for ext in ('json', 'csv', 'txt'):
            p = os.path.join(group_dir, f'uploaded_receiver.{ext}')
            if os.path.exists(p):
                uploaded_ext = ext
                break

        if uploaded_ext == 'json':
            import json as json_mod
            body_obj = {
                'group_id': group_id,
                'protocol': 'PSIcard',
                'intersection_cardinality': int(cardinality) if cardinality.isdigit() else cardinality
            }
            body = json_mod.dumps(body_obj, ensure_ascii=False, indent=2)
            mime = 'application/json'
            dl_name = f'psi_card_{group_id}.json'
        elif uploaded_ext == 'csv':
            body = f"intersection_cardinality\n{cardinality}\n"
            mime = 'text/csv'
            dl_name = f'psi_card_{group_id}.csv'
        else:
            body = f"{cardinality}\n"
            mime = 'text/plain'
            dl_name = f'psi_card_{group_id}.txt'

        from io import BytesIO
        from flask import send_file
        buf = BytesIO(body.encode('utf-8'))
        return send_file(buf, as_attachment=True, download_name=dl_name, mimetype=mime)
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


# ==================== 集合匹配 密文预览 ====================
# 返回"己方密文前 20",供前端展示 PSI-Card 协议跑出来的 OPRF 密文
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

        # 组长是接收方(receiver),成员是发送方(sender)
        role = 'receiver' if username == group['creator'] else 'sender'
        ciphertext_file = os.path.join(
            Config.KUNLUN_PSI_CARD_DATA_DIR,
            f'group_{group_id}',
            f'{role}_ciphertext.txt'
        )

        if not os.path.exists(ciphertext_file):
            return jsonify({'error': f'密文文件不存在,请先完成计算 ({role}_ciphertext.txt)'}), 404

        with open(ciphertext_file, 'r', encoding='utf-8') as f:
            lines = f.read().strip().split('\n')[:20]

        return jsonify({
            'role': role,
            'ciphertext': lines,
            'total_count': sum(1 for _ in open(ciphertext_file, 'r', encoding='utf-8'))
        }), 200
    except Exception as e:
        return jsonify({'error': f'读取密文失败:{str(e)}'}), 500


# ==================== PSIMatch 多轮历史 API ====================

# 2026-07-02 新增:组长(receiver)手动触发的"开始运算"端点
@app.route('/api/psi-match-group/<group_id>/start-computation', methods=['POST'])
@jwt_required
def api_psi_match_group_start_computation(group_id):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404

        username = request.current_user['username']
        if username != group['creator']:
            return jsonify({'error': '只有组长(receiver)可以触发开始运算'}), 403

        uploaded_users = list(set([u['username'] for u in group.get('uploads', [])]))
        if len(uploaded_users) < 2:
            return jsonify({'error': '双方文件未全部上传'}), 400

        # 2026-07-02 PSIMatch: 用 subset_result 字段判断是否已跑过本轮（不用 file，因为 upload 就自动跑）
        if group.get('subset_result'):
            return jsonify({'error': '当前轮已运算完成，请先归档当前轮(finalize-round)'}), 409

        print(f"[PSI-Match] {username} 按下 [开始运算] 按钮(group={group_id})")
        result = _compute_with_timing(run_kunlun_psi_card, group_id)
        if not result['success']:
            return jsonify({'error': result.get('error', '计算失败')}), 500

        intersection_cardinality = result['cardinality']
        # 计算 is_subset + missingCount(同 upload 逻辑)
        receiver_size = next((len(u['items']) for u in group.get('uploads', [])
                              if u['username'] == group['creator']), 0)
        missing_count = max(0, receiver_size - intersection_cardinality)
        is_subset = (missing_count == 0)

        # 2026-07-02 修复:_save() 不存在,改为重新 load + 修改 + save
        data = PSIMatchGroupManager.load_groups()
        for g in data['groups']:
            if g['id'] == group_id:
                g['pending_computation'] = {
                    'duration_seconds': result['duration_seconds'],
                    'duration_human': result['duration_human']
                }
                # 2026-07-02:start-computation 也写 subset_result(与 upload 保持一致)
                g['subset_result'] = {
                    'isSubset': is_subset,
                    'intersectionCardinality': intersection_cardinality,
                    'missingCount': missing_count
                }
                break
        PSIMatchGroupManager.save_groups(data)
        # 2026-07-02:PSIMatchGroupManager 没有 save_cardinality_result(),PSIcard 才有
        # subset_result 已足够,不必再调

        return jsonify({
            'success': True,
            'cardinality': intersection_cardinality,
            'is_subset': is_subset,
            'intersection_cardinality': intersection_cardinality,
            'missing_count': missing_count,
            'duration_seconds': result['duration_seconds'],
            'duration_human': result['duration_human']
        }), 200
    except Exception as e:
        return jsonify({'error': f'运算失败:{str(e)}'}), 500


@app.route('/api/psi-match-group/<group_id>/finalize-round', methods=['POST'])
@jwt_required
def api_psi_match_finalize_round(group_id):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404
        username = request.current_user['username']
        if username != group['creator']:
            return jsonify({'error': '只有 receiver(组长)可以保存当前结果'}), 403
        if len(group.get('uploads', [])) < 2:
            return jsonify({'error': '需要双方都上传文件后才能保存'}), 400
        result_file = os.path.join(Config.KUNLUN_PSI_CARD_DATA_DIR, f'group_{group_id}', 'cardinality.txt')
        if not os.path.exists(result_file):
            return jsonify({'error': '结果文件不存在,请先完成匹配计算'}), 400
        ok, record = PSIMatchGroupManager.finalize_round(group_id, username)
        if not ok:
            return jsonify({'error': record}), 500
        return jsonify({
            'message': f'第 {record["round"]} 轮已保存到历史,双方可重新上传开始下一轮',
            'round': record['round'],
            'completed_at': record['completed_at']
        }), 200
    except Exception as e:
        return jsonify({'error': f'保存失败:{str(e)}'}), 500

@app.route('/api/psi-match-group/<group_id>/history', methods=['GET'])
@jwt_required
def api_psi_match_history(group_id):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        history = PSIMatchGroupManager.get_history(group_id, username)
        return jsonify({
            'group_id': group_id,
            'is_receiver': group['creator'] == username,
            'rounds': history or []
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取历史失败:{str(e)}'}), 500

@app.route('/api/psi-match-group/<group_id>/round/<int:round_num>/download', methods=['GET'])
@jwt_required
def api_psi_match_download_round(group_id, round_num):
    try:
        group_id = group_id.upper()
        group = PSIMatchGroupManager.get_group(group_id)
        if not group:
            return jsonify({'error': '匹配小组不存在'}), 404
        username = request.current_user['username']
        if username not in group['members']:
            return jsonify({'error': '你不是该小组成员'}), 403
        file_type = request.args.get('type', 'result')
        fpath, err = PSIMatchGroupManager.get_round_data(group_id, round_num, file_type, username)
        if err:
            return jsonify({'error': err}), 404
        directory = os.path.dirname(fpath)
        filename = os.path.basename(fpath)
        return send_from_directory(directory, filename, as_attachment=True,
                                   download_name=f'psimatch_{group_id}_round{round_num}_{file_type}.txt')
    except Exception as e:
        return jsonify({'error': f'下载失败:{str(e)}'}), 500


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