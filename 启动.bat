@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
title 酒店客诉分析流水线

if exist ".venv\Scripts\python.exe" goto :run_venv

where python >nul 2>&1
if errorlevel 1 goto :no_python

echo [提示] 未找到 .venv 虚拟环境，改用系统 python 运行（首次使用请先安装依赖）。
python src\main.py
set "EXIT_CODE=%ERRORLEVEL%"
goto :finished

:run_venv
echo [提示] 使用虚拟环境 .venv\Scripts\python.exe 启动流水线...
".venv\Scripts\python.exe" src\main.py
set "EXIT_CODE=%ERRORLEVEL%"
goto :finished

:no_python
echo.
echo [错误] 找不到可用的 Python。
echo 既没有 .venv 虚拟环境，系统中也找不到 python 命令。
echo.
echo 首次使用请先打开 PowerShell 执行下面两行：
echo   python -m venv .venv
echo   .venv\Scripts\python -m pip install -r requirements.txt
echo 安装完成后重新双击本文件即可。
echo.
pause
exit /b 1

:finished
echo.
echo 运行结束（退出码 %EXIT_CODE%）。按任意键关闭窗口...
pause >nul
exit /b %EXIT_CODE%
