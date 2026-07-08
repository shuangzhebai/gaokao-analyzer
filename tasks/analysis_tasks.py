"""分析/模拟/采集的 Celery 异步任务定义。在 Celery worker 中独立运行。"""

import logging
import os

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(bind=True, name="analyze_paper", max_retries=2, default_retry_delay=30)
    def analyze_paper(self, paper_id: int) -> dict:
        """对指定试卷执行 IRT 估计 + 模拟 + 质量分析全流程。"""
        import asyncio
        import aiosqlite

        from config import DB_PATH
        from services.paper_service import PaperService
        from repositories.paper_repo import PaperRepository
        from repositories.question_repo import QuestionRepository
        from repositories.analysis_repo import AnalysisRepository

        async def _run():
            db = await aiosqlite.connect(DB_PATH)
            db.row_factory = aiosqlite.Row
            try:
                repo_paper = PaperRepository()
                repo_question = QuestionRepository()
                repo_analysis = AnalysisRepository()
                service = PaperService(repo_paper, repo_question, repo_analysis)
                result = await service.full_analyze(db, paper_id)
                return {"status": "success", "paper_id": paper_id, "result": result}
            except Exception as e:
                logger.exception("analyze_paper(%s) failed", paper_id)
                return {"status": "error", "paper_id": paper_id, "error": str(e)}
            finally:
                await db.close()

        return asyncio.run(_run())

    @shared_task(bind=True, name="simulate_paper", max_retries=2, default_retry_delay=30)
    def simulate_paper(self, paper_id: int, n_students: int = 50000) -> dict:
        """对已 IRT 估计的试卷执行成绩模拟。"""
        import asyncio
        import aiosqlite

        from config import DB_PATH
        from services.paper_service import PaperService
        from repositories.paper_repo import PaperRepository
        from repositories.question_repo import QuestionRepository
        from repositories.analysis_repo import AnalysisRepository

        async def _run():
            db = await aiosqlite.connect(DB_PATH)
            db.row_factory = aiosqlite.Row
            try:
                repo_paper = PaperRepository()
                repo_question = QuestionRepository()
                repo_analysis = AnalysisRepository()
                service = PaperService(repo_paper, repo_question, repo_analysis)
                result = await service.run_simulation(db, paper_id, n_students)
                return {"status": "success", "paper_id": paper_id, "result": result}
            except Exception as e:
                logger.exception("simulate_paper(%s) failed", paper_id)
                return {"status": "error", "paper_id": paper_id, "error": str(e)}
            finally:
                await db.close()

        return asyncio.run(_run())

    @shared_task(bind=True, name="collect_papers", max_retries=2, default_retry_delay=30)
    def collect_papers(self, sources: list[str] | None = None) -> dict:
        """从指定或默认数据源采集试卷。"""
        import asyncio
        import aiosqlite

        from config import DB_PATH
        from services.scrape_service import ScrapeService
        from repositories.paper_repo import PaperRepository
        from repositories.question_repo import QuestionRepository

        async def _run():
            db = await aiosqlite.connect(DB_PATH)
            db.row_factory = aiosqlite.Row
            try:
                repo_paper = PaperRepository()
                repo_question = QuestionRepository()
                service = ScrapeService()
                result = await service.collect_papers(
                    db, sources or [], repo_paper, repo_question
                )
                return {"status": "success", "result": result}
            except Exception as e:
                logger.exception("collect_papers failed")
                return {"status": "error", "error": str(e)}
            finally:
                await db.close()

        return asyncio.run(_run())

    logger.info("Celery 任务已注册: analyze_paper, simulate_paper, collect_papers")

except ImportError:
    logger.info("Celery 未安装 — 异步任务以同步方式运行（降级模式）")

    # 占位函数供路由调用（降级时用）
    def analyze_paper(paper_id: int) -> dict:
        return {"status": "UNAVAILABLE", "message": "Celery 未启用"}

    def simulate_paper(paper_id: int, n_students: int = 50000) -> dict:
        return {"status": "UNAVAILABLE", "message": "Celery 未启用"}

    def collect_papers(sources: list[str] | None = None) -> dict:
        return {"status": "UNAVAILABLE", "message": "Celery 未启用"}
