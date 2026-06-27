#!/bin/bash

# Flask Web 应用启动脚本

echo "============================================"
echo "🚀 启动 Flask Web 应用..."
echo "============================================"

# 检查是否在正确的目录
if [ ! -f "app.py" ]; then
    echo "❌ 错误：请在 backend 目录下运行此脚本"
    exit 1
fi

# 检查 Python3 是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：Python3 未安装"
    echo "请先安装 Python3: sudo apt install python3"
    exit 1
fi

# 检查虚拟环境（可选）
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate 2>/dev/null || echo "⚠️  虚拟环境激活失败，继续使用系统 Python"

# 安装依赖
echo "📦 安装依赖包..."
pip install -r requirements.txt

# 创建必要的目录
mkdir -p uploads

echo "✅ 准备完成，启动服务器..."
echo "============================================"
echo "🌐 访问地址: http://localhost:5000/login.html"
echo "🌐 访问地址: http://127.0.0.1:5000/login.html"
echo "============================================"
echo "按 Ctrl+C 停止服务器"
echo "============================================"

# 启动 Flask 应用
echo "正在启动 Flask 应用..."
python3 app.py