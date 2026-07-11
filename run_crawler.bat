@echo off
chcp 65001 >nul
title 学科网/组卷网 真实卷子 一键爬取器
cd /d %~dp0

set "VENV=.venv\Scripts\python.exe"
if not exist "%VENV%" (
  echo [错误] 找不到虚拟环境 .venv\Scripts\python.exe
  echo         请先创建虚拟环境并安装依赖：
  echo           python -m venv .venv
  echo           .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo           .venv\Scripts\python.exe -m pip install browser_cookie3 pywin32 websocket-client pycryptodomex
  pause & exit /b 1
)

echo ============================================================
echo   学科网 / 组卷网 真实卷子 一键爬取
echo   本工具会：①从你已登录的 Edge 抽会话Cookie ②爬取并落库
echo   前提：Edge 里已登录 学科网(zxxk.com) 或 组卷网(zujuan.xkw.com)
echo ============================================================
echo.

echo [1/5] 关闭正在运行的 Edge（释放浏览器会话，稍后会自动重启）...
taskkill /F /IM msedge.exe >nul 2>&1
timeout /t 2 >nul

echo [2/5] 以调试模式启动 Edge（自动读取你已登录的会话）...
set "EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" (
  echo [错误] 找不到 Edge 可执行文件，请确认已安装 Microsoft Edge。
  pause & exit /b 1
)
start "" "%EDGE%" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="%LOCALAPPDATA%\Microsoft\Edge\User Data" --no-first-run --no-default-browser-check --disable-gpu --disable-sync --disable-extensions --disable-background-networking

set PORT_UP=0
for /l %%i in (1,1,30) do (
  curl -s --max-time 2 http://127.0.0.1:9222/json/version >nul 2>&1
  if not errorlevel 1 ( set PORT_UP=1 & goto :got )
  timeout /t 2 >nul
)
:got
if %PORT_UP%==0 (
  echo [失败] Edge 调试端口未启动。可能原因：
  echo   ① 你的 Edge 版本对 v20 应用绑定加密有额外保护；
  echo   ② 请手动退出【所有】Edge 窗口后再双击本文件重试。
  goto :cleanup
)

echo [3/5] 从 Edge 抽取会话 Cookie（写入 credentials.json，已 gitignore）...
"%VENV%" scripts\grab_cookies.py
if not exist credentials.json (
  echo [失败] 未抽到 Cookie。请确认 Edge 里已登录 学科网/组卷网，且完全退出后重试。
  goto :cleanup
)

echo [4/5] 安全探测：先 --dry-run 验证 Cookie 是否有效（不落库）...
"%VENV%" scripts\crawl_real_papers.py --dry-run --subjects math --years 2024
echo.
echo ------------------------------------------------------------
echo 如果上面显示了"发现 N 条候选"，说明 Cookie 有效、可以正式爬取。
echo 接下来将正式爬取：数学 2024 年，限量 20 份（防止被封）。
echo 按任意键开始正式爬取；若不想现在爬，直接关闭窗口即可。
echo ------------------------------------------------------------
pause

echo [5/5] 正式爬取中（数学 2024，限量 20）...
"%VENV%" scripts\crawl_real_papers.py --subjects math --years 2024 --limit 20

:cleanup
echo.
echo [收尾] 关闭调试用 Edge，重启你的正常 Edge...
taskkill /F /IM msedge.exe >nul 2>&1
start "" "%EDGE%" --user-data-dir="%LOCALAPPDATA%\Microsoft\Edge\User Data"
echo 完成。按任意键退出。
pause
