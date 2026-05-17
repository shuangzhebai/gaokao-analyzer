"""
高考模拟卷智能分析系统 v5.0 - 一键启动脚本
支持 --reset 强制重建数据库
v5.0: 地区校验 + 自动采集 + 官方文件库 + 真实性审核 + 校准评价
"""
import asyncio
import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 导入配置以获取 DB_PATH
from config import DB_PATH


def install_deps():
    """安装依赖"""
    print("=" * 60)
    print("检查/安装依赖包...")
    print("=" * 60)
    req_file = os.path.join(BASE_DIR, "requirements.txt")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "-r", req_file],
        cwd=BASE_DIR,
    )
    print("依赖就绪!\n")


def generate_sample(force=False):
    """生成1000份试卷数据

    Args:
        force: 强制重建数据库（忽略已有数据）
    """
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("强制重建：已删除旧数据库")

    if not force and os.path.exists(DB_PATH):
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "papers" in tables:
                count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
                cols = [r[1] for r in conn.execute("PRAGMA table_info(papers)").fetchall()]
                needs_migration = "content_hash" not in cols
                if needs_migration:
                    print("检测到旧版数据库，需要升级 schema...")
                    conn.close()
                    os.remove(DB_PATH)
                    print("已删除旧数据库，将重新创建...")
                # v5.0: 检查新表是否存在
                elif "official_docs" not in tables or "verification_audit" not in tables:
                    print("检测到 v4.x 数据库，需要升级到 v5.0 schema...")
                    conn.close()
                    # 不删库，仅追加新表（init_db 使用 CREATE IF NOT EXISTS）
                    print("将追加 v5.0 新表（official_docs, verification_audit）...")
                    # 不需要重新生成数据，直接返回
                    return
                elif count >= 1000:
                    conn.close()
                    print(f"数据库已有 {count} 份试卷，跳过生成。")
                    return
            conn.close()
        except Exception as e:
            print(f"数据库检查异常: {e}，将重新生成...")
            try:
                os.remove(DB_PATH)
            except Exception:
                pass

    print("=" * 60)
    print("生成1000份试卷数据库 (800模拟+200真题)...")
    print("首次生成约需 1-3 分钟，请耐心等待...")
    print("=" * 60)
    from sample_data import generate_all_papers
    asyncio.run(generate_all_papers())
    print()


def start_server():
    """启动 Web 服务"""
    print("=" * 60)
    print("启动高考模拟卷智能分析系统 v5.0")
    print("=" * 60)
    print("访问地址: http://127.0.0.1:8899")
    print("v5.0 新特性: 地区校验 | 自动采集 | 官方文件库 | 真实性审核 | 校准评价")
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    print()

    import uvicorn
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8899,
        log_level="info",
    )


if __name__ == "__main__":
    # 支持 --reset 参数强制重建数据库
    force_reset = "--reset" in sys.argv
    install_deps()
    generate_sample(force=force_reset)
    start_server()
