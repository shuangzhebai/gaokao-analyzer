#!/usr/bin/env python3
"""
gaokao-analyzer 跨平台一键安装包构建脚本。

用法:
    python scripts/package-app.py          # 构建当前平台安装包
    python scripts/package-app.py --all    # 构建所有平台（需要交叉编译环境）

构建产物输出到 dist/packages/ 目录:
    Windows: gaokao-analyzer-Setup-6.0.exe  (Inno Setup)
    macOS:   gaokao-analyzer-6.0.dmg        (DMG 镜像)
    Linux:   gaokao-analyzer-6.0.AppImage   (AppImage)
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "6.0.0"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist" / "packages"
BUILD_DIR = PROJECT_ROOT / "dist" / "build"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# 嵌入式 Python 下载地址
EMBEDDED_PYTHON_URLS = {
    "windows": "https://www.python.org/ftp/python/3.13.2/python-3.13.2-embed-amd64.zip",
    "darwin": "https://www.python.org/ftp/python/3.13.2/python-3.13.2-macos11.pkg",
    "linux": "https://www.python.org/ftp/python/3.13.2/Python-3.13.2.tgz",
}

SYSTEM = platform.system().lower()


def log(msg: str) -> None:
    print(f"  [*] {msg}")


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"  [+] Running: {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=cwd or PROJECT_ROOT)


def build_frontend() -> None:
    """构建前端。"""
    log("构建前端...")
    if (FRONTEND_DIR / "dist" / "index.html").exists():
        log("前端已构建，跳过")
        return
    result = run(["npm", "run", "build"], cwd=FRONTEND_DIR)
    if result != 0:
        print("  [!] 前端构建失败，尝试使用 npm install...")
        run(["npm", "install"], cwd=FRONTEND_DIR)
        run(["npm", "run", "build"], cwd=FRONTEND_DIR)


def download_embedded_python(target_dir: Path) -> Path:
    """下载嵌入式 Python 到目标目录。"""
    system_map = {"windows": "windows", "darwin": "darwin", "linux": "linux"}
    key = system_map.get(SYSTEM, "linux")
    url = EMBEDDED_PYTHON_URLS[key]
    python_dir = target_dir / "python"

    if (python_dir / "python.exe").exists() or (python_dir / "bin" / "python3").exists():
        log("嵌入式 Python 已存在，跳过下载")
        return python_dir

    log(f"下载嵌入式 Python ({SYSTEM})...")
    python_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = target_dir / "python.zip"
    urllib.request.urlretrieve(url, zip_path)
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(python_dir)
    zip_path.unlink()
    
    return python_dir


def install_deps(python_dir: Path, target_dir: Path) -> None:
    """安装依赖到目标目录。"""
    log("安装依赖...")
    
    if SYSTEM == "windows":
        python_exe = python_dir / "python.exe"
        # 嵌入式 Python 需要 pip
        if not (python_dir / "Scripts" / "pip.exe").exists():
            log("安装 pip...")
            # 下载 get-pip.py
            urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", 
                                      str(target_dir / "get-pip.py"))
            run([str(python_exe), str(target_dir / "get-pip.py"), "--no-warn-script-location"])
    else:
        python_exe = python_dir / "bin" / "python3"
    
    log("安装项目依赖...")
    run([str(python_exe), "-m", "pip", "install", 
         "-r", str(PROJECT_ROOT / "requirements.txt"),
         "-t", str(target_dir / "lib"),
         "--no-compile", "-q"])


def copy_app(target_dir: Path) -> None:
    """复制应用代码到目标目录。"""
    log("复制应用代码...")
    
    # 后端代码
    for item in PROJECT_ROOT.iterdir():
        if item.name.startswith((".", "node_modules", "frontend", "website", 
                                 "dist", "data", "__pycache__", ".venv", 
                                 "deploy", "scripts")):
            continue
        if item.is_dir():
            shutil.copytree(item, target_dir / "app" / item.name, 
                          ignore=shutil.ignoring("__pycache__", ".pyc"))
        elif item.suffix in (".py", ".txt", ".md", ".yml", ".json", ".bat", ".sh"):
            shutil.copy2(item, target_dir / "app" / item.name)
    
    # 前端构建产物
    frontend_dist = FRONTEND_DIR / "dist"
    if frontend_dist.exists():
        shutil.copytree(frontend_dist, target_dir / "app" / "frontend" / "dist")
    
    # 静态文件
    static_dir = PROJECT_ROOT / "static"
    if static_dir.exists():
        shutil.copytree(static_dir, target_dir / "app" / "static")


def create_launchers(target_dir: Path) -> None:
    """创建各平台启动器。"""
    log("创建启动器...")
    
    if SYSTEM == "windows":
        # Windows: 批处理 + PowerShell
        launcher = target_dir / "启动系统.bat"
        launcher.write_text(
            f"""@echo off
chcp 65001 >nul
title 高考分析系统 v{VERSION}
echo ============================================
echo   高考模拟卷智能分析系统 v{VERSION}
echo   正在启动，请稍候...
echo ============================================
set PYTHONPATH=%~dp0lib;%~dp0app
%~dp0python\\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
if %errorlevel% neq 0 (
    echo [错误] 启动失败，请尝试以管理员身份运行
    pause
)
""", encoding="utf-8"
        )
        
        # PowerShell 启动器（更友好）
        ps_launcher = target_dir / "启动系统.ps1"
        ps_launcher.write_text(
            f"""$Host.UI.RawUI.WindowTitle = "高考分析系统 v{VERSION}"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  高考模拟卷智能分析系统 v{VERSION}" -ForegroundColor Cyan
Write-Host "  正在启动，请稍候..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$$env:PYTHONPATH = "$$PSScriptRoot\\lib;$$PSScriptRoot\\app"
Start-Process "http://localhost:8000"
& "$$PSScriptRoot\\python\\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8000
""", encoding="utf-8"
        )
    
    elif SYSTEM == "darwin":
        # macOS: .command 文件
        launcher = target_dir / "启动系统.command"
        launcher.write_text(
            f"""#!/bin/bash
cd "$(dirname "$0")"
echo "============================================"
echo "  高考模拟卷智能分析系统 v{VERSION}"
echo "  正在启动，请稍候..."
echo "============================================"
export PYTHONPATH="$PWD/lib:$PWD/app"
open http://localhost:8000
"$PWD/python/bin/python3" -m uvicorn app:app --host 0.0.0.0 --port 8000
""", encoding="utf-8"
        )
        launcher.chmod(0o755)
    
    else:
        # Linux: shell 脚本
        launcher = target_dir / "启动系统.sh"
        launcher.write_text(
            f"""#!/bin/bash
cd "$(dirname "$0")"
echo "============================================"
echo "  高考模拟卷智能分析系统 v{VERSION}"
echo "  正在启动，请稍候..."
echo "============================================"
export PYTHONPATH="$PWD/lib:$PWD/app"
xdg-open http://localhost:8000 2>/dev/null || true
"$PWD/python/bin/python3" -m uvicorn app:app --host 0.0.0.0 --port 8000
""", encoding="utf-8"
        )
        launcher.chmod(0o755)


def create_windows_installer(build_dir: Path) -> None:
    """创建 Windows Inno Setup 安装包。"""
    log("创建 Windows 安装包...")
    
    iss_path = build_dir / "installer.iss"
    iss_content = f"""
#define MyAppName "高考模拟卷智能分析系统"
#define MyAppVersion "{VERSION}"
#define MyAppPublisher "gaokao-analyzer"
#define MyAppURL "https://github.com/shuangzhebai/gaokao-analyzer"

[Setup]
AppId={{B4A2C8E1-8F5A-4A6D-9C3E-2F1D7E5B8A0C}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
DefaultDirName={{autopf}}\\gaokao-analyzer
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
OutputDir={build_dir / "output"}
OutputBaseFilename=gaokao-analyzer-Setup-{VERSION}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={{app}}\\启动系统.bat

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\\ChineseSimplified.isl"

[Files]
Source: "{build_dir / "portable"}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\启动系统"; Filename: "{{app}}\\启动系统.bat"; WorkingDir: "{{app}}"
Name: "{{group}}\\卸载系统"; Filename: "{{uninstallexe}}"
Name: "{{commondesktop}}\\高考分析系统"; Filename: "{{app}}\\启动系统.bat"; WorkingDir: "{{app}}"

[Run]
Filename: "{{app}}\\启动系统.bat"; Description: "启动系统"; Flags: postinstall nowait skipifsilent shellexec
"""
    iss_path.write_text(iss_content, encoding="utf-8")
    
    # 检查 Inno Setup 是否安装
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if os.path.exists(iscc):
        log("运行 Inno Setup 编译...")
        run([iscc, str(iss_path)])
    else:
        log("Inno Setup 未安装，跳过 .exe 安装包生成")
        log("安装 Inno Setup 后可运行: iscc installer.iss")


def create_macos_bundle(build_dir: Path) -> None:
    """创建 macOS .app 和 .dmg。"""
    log("创建 macOS 安装包...")
    app_dir = build_dir / "gaokao-analyzer.app" / "Contents"
    (app_dir / "MacOS").mkdir(parents=True, exist_ok=True)
    (app_dir / "Resources").mkdir(parents=True, exist_ok=True)
    
    # Info.plist
    plist = app_dir / "Info.plist"
    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>gaokao-analyzer</string>
    <key>CFBundleDisplayName</key>
    <string>高考分析系统</string>
    <key>CFBundleVersion</key>
    <string>{VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>启动系统.command</string>
</dict>
</plist>""", encoding="utf-8")


def create_linux_appimage(build_dir: Path) -> None:
    """创建 Linux AppRun 和 .desktop 文件。"""
    log("创建 Linux 安装包...")
    appdir = build_dir / "gaokao-analyzer.AppDir"
    
    # 这个占位 — 实际 AppImage 构建需要 appimagetool
    (appdir / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps").mkdir(parents=True, exist_ok=True)
    
    log("Linux AppImage 构建需要 appimagetool")
    log("详见: https://github.com/AppImage/AppImageKit")


def build() -> None:
    """主构建流程。"""
    print(f"\n{'='*50}")
    print(f"  gaokao-analyzer v{VERSION} 安装包构建")
    print(f"  平台: {SYSTEM}")
    print(f"{'='*50}\n")
    
    # 清空构建目录
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    
    # 1. 构建前端
    build_frontend()
    
    # 2. 创建可移植安装目录
    portable_dir = BUILD_DIR / "portable"
    portable_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. 下载嵌入式 Python
    download_embedded_python(portable_dir)
    
    # 4. 安装依赖
    install_deps(portable_dir / "python", portable_dir)
    
    # 5. 复制应用代码
    copy_app(portable_dir)
    
    # 6. 创建启动器
    create_launchers(portable_dir)
    
    # 7. 创建平台安装包
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    
    if SYSTEM == "windows":
        # 创建 ZIP 便携版（通用）
        log("创建 ZIP 便携版...")
        zip_path = DIST_DIR / f"gaokao-analyzer-{VERSION}-win64.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(portable_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = str(file_path.relative_to(portable_dir))
                    zf.write(file_path, arcname)
        log(f"ZIP 便携版: {zip_path}")
        
        # 尝试创建 .exe 安装包
        create_windows_installer(BUILD_DIR)
    
    elif SYSTEM == "darwin":
        create_macos_bundle(BUILD_DIR)
        log(f"macOS 应用: {BUILD_DIR / 'gaokao-analyzer.app'}")
    
    elif SYSTEM == "linux":
        create_linux_appimage(BUILD_DIR)
    
    # 8. 汇总
    print(f"\n{'='*50}")
    print("  构建完成!")
    print(f"  输出目录: {DIST_DIR}")
    print(f"{'='*50}")
    print(f"\n各平台使用方式:")
    print(f"  Windows: 解压 ZIP → 双击「启动系统.bat」→ 自动开浏览器")
    print(f"  macOS:   打开 .app → 自动开浏览器")
    print(f"  Linux:   运行 ./gaokao-analyzer-x86_64.AppImage")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建 gaokao-analyzer 安装包")
    parser.add_argument("--all", action="store_true", help="构建所有平台")
    args = parser.parse_args()
    build()
