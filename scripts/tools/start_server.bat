@echo off
chcp 65001 >nul 2>&1
echo ============================================================
echo   Gaokao Analyzer v3.0 - Starting...
echo ============================================================
echo.

REM Kill any process on port 8899
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :8899 ^| findstr LISTENING') do (
    echo Killing old process on port 8899: PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

cd /d "C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer"

echo Step 1: Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.12+
    pause
    exit /b 1
)

echo.
echo Step 2: Quick syntax check...
python -c "import py_compile; [py_compile.compile(f, doraise=True) for f in ['config.py','models.py','analyzer.py','simulator.py','curriculum.py','quality.py','parser.py','scraper.py','app.py','sample_data.py','start.py']]"
if errorlevel 1 (
    echo.
    echo ERROR: Syntax check failed! See errors above.
    echo.
    pause
    exit /b 1
)

echo.
echo Step 3: Testing imports...
python -c "from app import app; print('All imports OK!')"
if errorlevel 1 (
    echo.
    echo ERROR: Import failed! See errors above.
    echo.
    pause
    exit /b 1
)

echo.
echo Step 4: Starting server...
echo   URL: http://127.0.0.1:8899
echo   Press Ctrl+C to stop
echo.
python start.py
echo.
echo Server stopped.
pause
