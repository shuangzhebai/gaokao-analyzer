"""
高考模拟卷智能分析系统 v5.1 - 一键启动脚本
支持 --reset 强制重建数据库（显式删库，用户意图）
支持 --install-deps 显式安装依赖（默认不再每次启动都 pip install，R-5）
v5.1: schema 升级改为版本化迁移（见 models.run_migrations），绝不自动删库（T01）
"""
import asyncio
import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 导入配置以获取 DB_PATH
from config import DB_PATH


def install_deps() -> None:
    """安装依赖（仅在显式 --install-deps 时调用，R-5）"""
    print("=" * 60)
    print("安装依赖包...")
    print("=" * 60)
    req_file = os.path.join(BASE_DIR, "requirements.txt")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "-r", req_file],
        cwd=BASE_DIR,
    )
    print("依赖就绪!\n")


def generate_sample(force: bool = False) -> None:
    """生成1000份试卷数据

    Args:
        force: 强制重建数据库（--reset，显式删库；仅此情形删库）
    """
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("强制重建(--reset)：已删除旧数据库")

    if not force and os.path.exists(DB_PATH):
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "papers" in tables:
                count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
                # v5.1(T01): 不再因 schema 差异删库，交由 init_db 的版本化迁移处理
                if count >= 1000:
                    conn.close()
                    print(f"数据库已有 {count} 份试卷，跳过生成。")
                    return
                conn.close()
                print(f"数据库现有 {count} 份试卷，将执行版本化迁移并补生成数据（不删库）。")
            else:
                conn.close()
        except Exception as e:
            print(f"数据库检查异常: {e}，将尝试迁移/重建")

    print("=" * 60)
    print("生成1000份试卷数据库 (800模拟+200真题)...")
    print("首次生成约需 1-3 分钟，请耐心等待...")
    print("=" * 60)
    from sample_data import generate_all_papers
    asyncio.run(generate_all_papers())
    print()


def start_server() -> None:
    """启动 Web 服务"""
    print("=" * 60)
    print("启动高考模拟卷智能分析系统 v5.1")
    print("=" * 60)
    print("访问地址: http://127.0.0.1:8899")
    print("v5.1 新特性: 版本化迁移(防清空) | 地区校验 | 自动采集(默认关闭) | "
          "官方文件库 | 真实性审核 | 校准评价 | 中文搜索相关度修复")
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
    # 支持 --reset 强制重建数据库；--install-deps 显式安装依赖
    force_reset = "--reset" in sys.argv
    install_deps_flag = "--install-deps" in sys.argv
    if install_deps_flag:
        install_deps()
    generate_sample(force=force_reset)
    start_server()
