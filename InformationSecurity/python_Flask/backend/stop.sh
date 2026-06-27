#!/bin/bash

# Flask Web 应用停止脚本

echo "============================================"
echo "🛑 停止 Flask Web 应用..."
echo "============================================"

# 查找并杀死所有 Flask 进程
PIDS=$(ps aux | grep "python3 app.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "✅ 没有找到运行中的 Flask 应用"
else
    echo "🔍 找到以下进程："
    ps aux | grep "python3 app.py" | grep -v grep

    # 优雅停止
    echo "📨 发送 SIGTERM 信号..."
    echo $PIDS | xargs kill -TERM

    # 等待 3 秒
    sleep 3

    # 检查是否还有进程运行
    REMAINING=$(ps aux | grep "python3 app.py" | grep -v grep | awk '{print $2}')
    if [ ! -z "$REMAINING" ]; then
        echo "⚠️  强制停止进程..."
        echo $REMAINING | xargs kill -9
    fi

    echo "✅ Flask 应用已停止"
fi

echo "============================================"