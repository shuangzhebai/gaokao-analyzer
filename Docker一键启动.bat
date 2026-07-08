@echo off
chcp 65001 >nul
title 高考分析系统 v6.0 — Docker 一键启动
echo ============================================
echo   高考模拟卷智能分析系统
echo   Docker 一键启动版（推荐）
echo ============================================
echo.

:: 检查 Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未安装 Docker Desktop！
    echo.
    echo 请先安装 Docker Desktop：
    echo 1. 打开 https://www.docker.com/products/docker-desktop/
    echo 2. 下载并安装 Docker Desktop for Windows
    echo 3. 安装完成后重新启动本脚本
    echo.
    pause
    exit /b 1
)

echo [✓] Docker 已检测到
echo.
echo [*] 正在启动系统（首次启动约 1-3 分钟）...
echo.
echo ============================================
echo   启动完成后自动打开浏览器
echo   默认管理员账号: admin / admin123
echo   请勿关闭本窗口
echo ============================================
echo.

:: 启动 Docker Compose
docker compose up -d

if %errorlevel% neq 0 (
    echo [错误] Docker 启动失败
    pause
    exit /b 1
)

:: 等待启动完成
echo [*] 等待服务启动...
:wait_loop
timeout /t 2 /nobreak >nul
curl -s http://localhost:8000/api/health >nul 2>&1
if %errorlevel% neq 0 (
    echo   服务启动中，请稍候...
    goto wait_loop
)

:: 启动浏览器
start http://localhost:8000
echo.
echo [✓] 启动完成！
echo.
echo 浏览器已自动打开
echo 管理员账号: admin
echo 管理员密码: admin123
echo.
echo 关闭本窗口即可停止服务
echo.
pause

:: 停止服务
docker compose down
echo [✓] 服务已停止
pause
