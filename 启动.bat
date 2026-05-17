@echo off
chcp 65001 >nul 2>&1
title 高考模拟卷智能分析系统 v3.0
echo ============================================================
echo   高考模拟卷智能分析系统 v3.0 - 一键启动
echo ============================================================
echo.
echo 正在检查旧进程...
taskkill /F /FI "WINDOWTITLE eq 高考模拟卷智能分析系统*" >nul 2>&1
echo.
cd /d "C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer"
python start.py
echo.
echo 服务已停止。按任意键退出...
pause >nul
