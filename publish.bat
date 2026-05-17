@echo off
title gaokao-analyzer Publisher
cd /d "%~dp0"

set REPO_NAME=gaokao-analyzer
set GITHUB_USER=shuangzhebai
set REMOTE_URL=https://github.com/%GITHUB_USER%/%REPO_NAME%.git

echo ========================================
echo   gaokao-analyzer Publisher
echo ========================================
echo.

:: Check git
where git >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git not found
    echo Please install: https://git-scm.com
    pause
    exit /b 1
)
git --version
echo.

:: Init git
if not exist ".git" (
    echo [1/4] Initializing git repository...
    git init
    git branch -M main
) else (
    echo [1/4] Git repository already exists
)

:: Add remote
echo [2/4] Setting remote URL...
git remote remove origin >nul 2>&1
git remote add origin %REMOTE_URL%
echo Remote: %REMOTE_URL%

:: Add files
echo [3/4] Adding files...
git add .
git status --short

:: Commit
echo [4/4] Committing...
git commit -m "feat: v5.1 skewnorm simulation + search + region validator"

:: Push
echo.
echo ========================================
echo Pushing to GitHub...
echo.
echo IMPORTANT: Use Personal Access Token
echo Generate at: github.com/settings/tokens
echo Required scope: repo
echo ========================================
echo.
git push -u origin main --force

if errorlevel 1 (
    echo.
    echo FAILED!
    echo 1. Create repo at: https://github.com/new
    echo 2. Repository name: gaokao-analyzer
    echo 3. Use Token (not password)
) else (
    echo.
    echo SUCCESS!
    echo URL: https://github.com/%GITHUB_USER%/%REPO_NAME%
)

pause
