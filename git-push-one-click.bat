@echo off
chcp 65001 >nul
title gaokao-analyzer Git Push
cd /d "C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer"

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

echo.
if %RESULT%==0 (
    echo SUCCESS
    echo https://github.com/shuangzhebai/gaokao-analyzer
) else (
    echo FAILED. Error code: %RESULT%
    echo Make sure your token has 'repo' permission.
)

pause
