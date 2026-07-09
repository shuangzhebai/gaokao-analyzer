"""运行时应用上下文集中化（批次二：T-C1）。

将分散在各处的运行时元信息（版本、Python 版本、数据目录、数据库路径、DeepSeek
开关、CORS 来源、运行环境、启动时间、已注入引擎数量）集中为一个不可变数据类，
在 lifespan 启动完成后存入 ``app.state.ctx``，供依赖注入 ``get_app_context`` 与各
路由统一读取，避免重复读取环境变量 / 配置造成的不一致。
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import sys
from typing import Any

from config import VERSION, DATA_DIR, DB_PATH, get_deepseek_key, GAOKAO_ENV, CORS_ORIGINS


@dataclass(frozen=True)
class AppContext:
    """运行时应用上下文快照（不可变）。"""

    version: str
    python_version: str
    data_dir: str
    db_path: str
    deepseek_enabled: bool
    cors_origins: str
    env: str
    started_at: str
    engine_count: int


def build_app_context(app: Any) -> AppContext:
    """根据 app.state 中已注入的引擎单例构建 AppContext 快照。

    引擎属性白名单与 lifespan.create_lifespan 中 asyncio.gather 注入的 14 个引擎一致；
    排除 ``index_html``（前端缓存）与 ``ctx``（自身）以免自引用。
    """
    engine_attrs = [
        a
        for a in (
            "scraper_manager",
            "irt_model",
            "kp_mapper",
            "quality_analyzer",
            "simulator",
            "fitting_analyzer",
            "paper_parser",
            "curriculum_analyzer",
            "quality_scorer",
            "search_engine",
            "dedup_engine",
            "auto_scraper",
            "official_docs",
            "paper_analyzer",
        )
        if getattr(app.state, a, None) is not None
    ]
    return AppContext(
        version=VERSION,
        python_version=sys.version.split()[0],
        data_dir=DATA_DIR,
        db_path=DB_PATH,
        deepseek_enabled=bool(get_deepseek_key()),
        cors_origins=", ".join(CORS_ORIGINS) if CORS_ORIGINS else "(deny-all)",
        env=GAOKAO_ENV,
        started_at=datetime.now(timezone.utc).isoformat(),
        engine_count=len(engine_attrs),
    )
