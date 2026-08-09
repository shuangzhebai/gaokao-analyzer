@echo off
chcp 65001 >nul
title 高考分析系统 v6.0 — 一键启动
echo ============================================
echo   高考模拟卷智能分析系统 - 一键启动
echo   Version 6.0
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python 环境！
    echo.
    echo 请先安装 Python 3.13+：
    echo 1. 打开 https://www.python.org/downloads/
    echo 2. 下载最新版 Python 安装包
    echo 3. 安装时勾选 "Add Python to PATH"
    echo 4. 安装完成后重新运行本脚本
    echo.
    pause
    exit /b 1
)

:: 检查 Python 版本
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [✓] Python %PY_VER% 已检测到

:: 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [*] 首次运行，正在创建虚拟环境...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [✓] 虚拟环境已创建
) else (
    echo [✓] 虚拟环境已存在
)

:: 安装依赖（首次或依赖更新时）
if not exist ".venv\Installed" (
    echo [*] 首次运行，正在安装依赖（约 2-5 分钟）...
    call .venv\Scripts\pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo [警告] 部分依赖安装失败，尝试继续...
    )
    echo. > ".venv\Installed"
    echo [✓] 依赖安装完成
)

:: 启动服务
echo.
echo [*] 正在启动系统...
echo.
echo ============================================
echo   启动完成后会自动打开浏览器
echo   首次使用请注册管理员账号
echo ============================================
echo.

:: 启动 FastAPI + 自动打开浏览器
start http://localhost:8000
call .venv\Scripts\uvicorn app:app --host 0.0.0.0 --port 8000

if %errorlevel% neq 0 (
    echo [错误] 启动失败
    echo 请尝试以管理员身份运行本脚本
    pause
)

pause
