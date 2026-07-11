#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已登录的浏览器直接抽取学科网/组卷网会话 Cookie，写入 credentials.json。

为什么用 CDP（Chrome DevTools Protocol）而不是读 Cookie 数据库文件：
  新版 Edge/Chrome 对 Cookie 启用了 App-Bound Encryption（前缀 v20），
  密钥与浏览器进程绑定，纯 Python 用 Local State 主密钥解不出来（会得到乱码）。
  让浏览器自己以远程调试模式启动，再通过 CDP 的 Storage.getCookies 直接拿
  **明文** Cookie，对 v10/v11/v20 通吃，且无需管理员权限。

流程：
  1. 定位本机 Edge/Chrome 可执行文件与 User Data 目录
  2. 优先直接以 --headless + --remote-debugging-port 拉起浏览器（复用你的 User Data，
     带着已登录会话）；若真实 profile 在该环境起不来，则复制一份精简 profile 再起
  3. 连 CDP，调用 Storage.getCookies 取全部明文 Cookie
  4. 筛出 zxxk.com / zujuan.xkw.com 的，拼成 'k=v; k=v' 头
  5. 写入 credentials.json（已被 .gitignore 忽略），关闭浏览器

注意：本脚本需要在你能正常登录并使用该浏览器的机器上运行（沙箱/受限环境可能因
应用绑定加密限制而无法启动调试服务）。

用法:
    python scripts/grab_cookies.py            # 抽取并写入 credentials.json
    python scripts/grab_cookies.py --dry-run  # 仅打印抽到了什么，不写文件
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CRED_PATH = ROOT / "credentials.json"

# 项目数据源 id -> 需要抽取 Cookie 的域名关键字
# 注意：组卷网挂在 xkw.com 域名下（zujuan.xkw.com / mzujuan.xkw.com），不是 zujuan.com
DOMAIN_MAP = {
    "xueke_wang": "zxxk.com",
    "zujuan_wang": "zujuan.xkw.com",
}

CDP_PORT = 9222

# 复制 profile 时排除的大体积目录（不影响 Cookie）
_EXCLUDE_DIRS = shutil.ignore_patterns(
    "Cache", "Code Cache", "Service Worker", "Extensions", "GPUCache",
    "DawnWebGPUCache", "DawnGraphiteCache", "Local Extension Settings",
    "Extension State", "IndexedDB", "Storage", "Sessions", "Web Applications",
    "component_crx_cache", "ProvenanceData", "Edge Entity Extraction",
    "Edge Wallet", "Subresource Filter", "GrShaderCache", "Edge Shopping",
    "Safe Browsing", "BrowserMetrics-spare.pma", "Speech Recognition",
)


def _find_browsers() -> list[tuple[str, Path]]:
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        ("Edge", Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")),
        ("Edge", Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")),
        ("Edge", Path(local) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
        ("Chrome", Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")),
        ("Chrome", Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")),
        ("Chrome", Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe"),
        ("Chromium", Path(local) / "Chromium" / "Application" / "chrome.exe"),
        ("Brave", Path(local) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe"),
    ]
    seen, found = set(), []
    for name, p in candidates:
        try:
            if p.exists() and p not in seen:
                found.append((name, p)); seen.add(p)
        except Exception:
            pass
    return found


def _user_data_dir(browser_name: str) -> Path | None:
    local = os.environ.get("LOCALAPPDATA", "")
    table = {
        "Edge": Path(local) / "Microsoft" / "Edge" / "User Data",
        "Chrome": Path(local) / "Google" / "Chrome" / "User Data",
        "Chromium": Path(local) / "Chromium" / "User Data",
        "Brave": Path(local) / "BraveSoftware" / "Brave-Browser" / "User Data",
    }
    d = table.get(browser_name)
    return d if d and d.exists() else None


def _launch_cdp(browser_exe: Path, user_data_dir: Path, timeout: int = 45) -> tuple:
    """以远程调试模式拉起浏览器，返回 (proc, version_dict)。失败返回 (None, None)。

    先尝试 --headless；若调试服务起不来（部分环境下 v20 应用绑定加密会导致无头模式
    卡死在 cookie 初始化），自动回退到普通窗口模式（真实窗口进程能正常做 App-Bound 解密）。
    """
    for lock in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        lk = user_data_dir / lock
        try:
            if lk.exists():
                lk.unlink()
        except Exception:
            pass
    base = [
        str(browser_exe), f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data_dir}", "--remote-allow-origins=*",
        "--no-first-run", "--no-default-browser-check", "--disable-gpu",
        "--disable-sync", "--disable-extensions", "--disable-background-networking",
    ]
    modes = [base + ["--headless", "--no-sandbox"], base]  # 先无头，失败回退普通窗口
    for args in modes:
        try:
            proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            print(f"[--] 启动浏览器失败: {exc}")
            continue
        for _ in range(timeout):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version",
                                            timeout=2) as r:
                    return proc, json.loads(r.read())
            except Exception:
                if proc.poll() is not None:
                    break
                time.sleep(1)
        # 超时：杀掉，尝试下一种模式
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    return None, None


def _kill(proc) -> None:
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def _ws_get(ws_url: str, method: str, params: dict | None = None, req_id: int = 1) -> dict | None:
    import websocket  # 延迟导入
    ws = websocket.create_connection(ws_url, timeout=15)
    try:
        ws.send(json.dumps({"id": req_id, "method": method, "params": params or {}}))
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                msg = json.loads(ws.recv())
            except Exception:
                break
            if msg.get("id") == req_id:
                return msg.get("result")
    finally:
        try:
            ws.close()
        except Exception:
            pass
    return None


def _get_cookies_via_cdp(ws_url: str) -> list | None:
    res = _ws_get(ws_url, "Storage.getCookies", {})
    if res and "cookies" in res:
        return res["cookies"]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3) as r:
            targets = json.loads(r.read())
        page = next((t for t in targets if t.get("type") == "page"
                     and t.get("webSocketDebuggerUrl")), None)
        if page:
            purl = page["webSocketDebuggerUrl"]
            _ws_get(purl, "Network.enable", {}, req_id=1)
            res2 = _ws_get(purl, "Network.getAllCookies", {}, req_id=2)
            if res2 and "cookies" in res2:
                return res2["cookies"]
    except Exception:
        pass
    return None


def _match_source(domain: str) -> str | None:
    d = (domain or "").lower()
    if "zxxk.com" in d:
        return "xueke_wang"
    if "zujuan" in d or "xkw.com" in d:  # 组卷网在 xkw.com 域下，sso 等共享域也算
        return "zujuan_wang"
    return None


def _extract_from(browser_exe: Path, user_data_dir: Path) -> dict:
    """在给定 User Data 目录上起 CDP 并抽取，返回 {source_id: cookie头}。"""
    proc, version = _launch_cdp(browser_exe, user_data_dir)
    if proc is None or version is None:
        return {}
    try:
        ws_url = version.get("webSocketDebuggerUrl")
        cookies = _get_cookies_via_cdp(ws_url) if ws_url else None
    finally:
        _kill(proc)
    if not cookies:
        return {}
    by_src: dict = {}
    for c in cookies:
        sid = _match_source(c.get("domain", ""))
        if sid:
            by_src.setdefault(sid, []).append(f"{c['name']}={c['value']}")
    return {s: "; ".join(v) for s, v in by_src.items() if v}


def _connect_existing() -> dict:
    """若本机已有浏览器以 --remote-debugging-port 运行，直接连上去抽明文 Cookie。
    用于配合 run_crawler.bat：由 .bat 负责拉起带调试端口的浏览器，本函数只连接。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version",
                                    timeout=3) as r:
            version = json.loads(r.read())
    except Exception:
        return {}
    ws_url = version.get("webSocketDebuggerUrl")
    if not ws_url:
        return {}
    cookies = _get_cookies_via_cdp(ws_url)
    if not cookies:
        return {}
    by_src: dict = {}
    for c in cookies:
        sid = _match_source(c.get("domain", ""))
        if sid:
            by_src.setdefault(sid, []).append(f"{c['name']}={c['value']}")
    return {s: "; ".join(v) for s, v in by_src.items() if v}


def grab_all(dry_run: bool = False) -> dict:
    """抽取全部源 Cookie，返回 {source_id: {'cookies': str}}。"""
    result: dict = {}
    # 优先连接已运行的调试实例（如 run_crawler.bat 已拉起），避免重复启动浏览器
    existing = _connect_existing()
    if existing:
        print("[*] 检测到已运行的浏览器调试实例，直接抽取...")
        for sid, hdr in existing.items():
            result[sid] = {"cookies": hdr}
            print(f"[OK] {sid}: 抽到 {hdr.count('=')} 个 cookie（来自已运行实例）")
        if not dry_run:
            CRED_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK] 已写入 {CRED_PATH}")
        return result
    for name, exe in _find_browsers():
        ud = _user_data_dir(name)
        if not ud:
            continue
        print(f"[*] 尝试 {name} 真实 profile（CDP 模式）...")
        res = _extract_from(exe, ud)
        if not res:
            # 回退：复制一份精简 profile（排除大缓存）再起，避开真实 profile 卡死
            print(f"[*] 真实 profile 起不来，复制精简 profile 重试...")
            try:
                tmp = Path(tempfile.gettempdir()) / f"edge_cdp_{os.getpid()}"
                if tmp.exists():
                    shutil.rmtree(tmp)
                shutil.copytree(ud, tmp, ignore=_EXCLUDE_DIRS)
                res = _extract_from(exe, tmp)
                shutil.rmtree(tmp, ignore_errors=True)
            except Exception as exc:
                print(f"[--] 复制 profile 失败: {exc}")
        if res:
            for sid, hdr in res.items():
                if sid not in result:
                    result[sid] = {"cookies": hdr}
                    print(f"[OK] {sid}: 抽到 {hdr.count('=')} 个 cookie（来自 {name}）")
    if result and not dry_run:
        CRED_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] 已写入 {CRED_PATH}")
    elif not result:
        print("[提示] 未抽到任何 Cookie。可能原因：①浏览器未登录学科网/组卷网；"
              "②当前环境（如受限沙箱）禁止浏览器启动调试服务（应用绑定加密限制）。"
              "请在你能正常使用该浏览器的机器上运行本脚本。")
    return result


def main() -> None:
    dry = "--dry-run" in sys.argv
    grab_all(dry_run=dry)


if __name__ == "__main__":
    main()
