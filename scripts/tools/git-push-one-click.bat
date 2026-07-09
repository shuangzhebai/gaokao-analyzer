@echo off
chcp 65001 >nul
title gaokao-analyzer Git Push
cd /d "C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer"

:: 把 WorkBuddy 自带的 PortableGit 加入 PATH，这样脚本里才能调用 git
set "GIT_BIN=C:\Users\29499\.workbuddy\vendor\PortableGit\cmd"
if not exist "%GIT_BIN%\git.exe" (
    echo [错误] 找不到 git.exe：%GIT_BIN%\git.exe
    echo 请确认 WorkBuddy 的 PortableGit 已安装。
    pause
    exit /b 1
)
set "PATH=%GIT_BIN%;%PATH%"

echo ============================================
echo    GitHub Push Helper
echo ============================================
echo.
echo 1. Open https://github.com/settings/tokens
echo 2. Generate a classic token with 'repo' scope
echo 3. Paste it below and press Enter
echo.

set /p TOKEN=GitHub Token: 

if "%TOKEN%"=="" (
    echo Token is empty. Exiting.
    pause
    exit /b 1
)

echo.
echo Pushing to GitHub...
set GIT_SSL_NO_VERIFY=true
git -c http.sslVerify=false -c http.schannelCheckRevoke=false push --force https://shuangzhebai:%TOKEN%@github.com/shuangzhebai/gaokao-analyzer.git main
set RESULT=%errorlevel%
set TOKEN=
set GIT_SSL_NO_VERIFY=

echo.
if %RESULT%==0 (
    echo ============================================
    echo    SUCCESS
    echo    https://github.com/shuangzhebai/gaokao-analyzer
    echo ============================================
) else (
    echo ============================================
    echo    FAILED. Error code: %RESULT%
    echo    Make sure your token has 'repo' permission.
    echo ============================================
)

pause
