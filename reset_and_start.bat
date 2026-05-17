@echo off
chcp 65001 >nul
echo ==========================================
echo 高考分析系统 v4.0 - 强制重建数据库
echo ==========================================
echo.

cd /d "%~dp0"

echo [1/3] 删除旧数据库...
if exist "data\gaokao.db" (
    del /f "data\gaokao.db"
    echo 已删除旧数据库
) else (
    echo 无旧数据库，跳过
)

echo.
echo [2/3] 安装依赖...
python -m pip install -q -r requirements.txt
echo 依赖就绪

echo.
echo [3/3] 启动系统（将自动生成1000份试卷数据）...
echo 首次启动约需1-3分钟，请耐心等待
echo.
python start.py
