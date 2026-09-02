#!/usr/bin/env bash
# 酒店客诉分析流水线 —— Linux / macOS 启动入口
set -u

cd "$(dirname "$0")" || exit 1
export PYTHONUTF8=1

if [ -x ".venv/bin/python" ]; then
    echo "[提示] 使用虚拟环境 .venv/bin/python 启动流水线..."
    ".venv/bin/python" src/main.py
    code=$?
elif command -v python3 >/dev/null 2>&1; then
    echo "[提示] 未找到 .venv 虚拟环境，改用系统 python3 运行（首次使用请先安装依赖）。"
    python3 src/main.py
    code=$?
else
    echo "[错误] 找不到可用的 Python。"
    echo "首次使用请先执行："
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/python -m pip install -r requirements.txt"
    exit 1
fi

echo
echo "运行结束（退出码 ${code}）。"
exit "${code}"
