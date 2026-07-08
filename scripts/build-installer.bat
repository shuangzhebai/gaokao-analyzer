@echo off
chcp 65001 >nul
title 高考分析系统 — 安装包构建工具

echo ============================================
echo   高考模拟卷智能分析系统 v6.0
echo   一键安装包构建工具
echo ============================================
echo.
echo 选择构建目标：
echo   1. Windows 安装包 (.exe) — 需要 Inno Setup
echo   2. ZIP 便携版 — 无需额外工具
echo   3. 全部构建
echo.

set /p CHOICE="请输入选项 (1/2/3): "

if "%CHOICE%"=="1" goto build_exe
if "%CHOICE%"=="2" goto build_zip
if "%CHOICE%"=="3" goto build_all
echo 无效选项
pause
exit /b

:build_zip
echo.
echo [*] 构建 ZIP 便携版...
cd /d %~dp0..
python scripts\package-app.py
echo.
echo [✓] ZIP 便携版构建完成
echo 输出文件: dist\packages\gaokao-analyzer-6.0.0-win64.zip
echo 解压后双击「启动系统.bat」即可运行
pause
exit /b

:build_exe
echo.
echo [*] 构建 EXE 安装包...
echo 需要 Inno Setup 6+ (https://jrsoftware.org/isdl.php)
cd /d %~dp0
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup-windows.iss
if %errorlevel% neq 0 (
    echo [错误] Inno Setup 编译失败
    pause
    exit /b
)
echo.
echo [✓] EXE 安装包构建完成
echo 输出文件: ..\dist\packages\gaokao-analyzer-Setup-6.0.0.exe
pause
exit /b

:build_all
echo.
echo [*] 构建全部安装包...
call :build_zip
call :build_exe
echo [✓] 全部构建完成
pause
