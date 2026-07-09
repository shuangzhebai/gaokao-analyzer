"""
采集进度与统计服务层
提供采集统计、目标进度、手动触发等业务编排。
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from engines.question_classifier import QuestionClassifier

logger = logging.getLogger("gaokao")


class CollectionService:
    """采集进度与统计服务"""

    COLLECTION_TARGET = {
        "mock_papers": 1000,
        "real_exams_years": 5,
    }

    def __init__(self):
        self.classifier = QuestionClassifier()

    async def get_collection_stats(self, db: Any) -> dict[str, Any]:
        """获取采集统计：总题目数 / 各来源占比 / 各学科占比 / 近期趋势

        Args:
            db: 数据库连接

        Returns:
            采集统计数据字典
        """
        # 总题目数
        total_questions_row = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM questions"
        )
        total_questions = total_questions_row["cnt"] if total_questions_row else 0

        # 总试卷数
        total_papers_row = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers"
        )
        total_papers = total_papers_row["cnt"] if total_papers_row else 0

        # 各来源占比 (papers)
        by_source = await db.execute_fetchall(
            "SELECT COALESCE(source_id, 'unknown') as source, COUNT(*) as cnt "
            "FROM papers GROUP BY source_id ORDER BY cnt DESC"
        )
        source_distribution: dict[str, int] = {
            r["source"]: r["cnt"] for r in by_source
        }

        # 各学科占比 (papers)
        by_subject = await db.execute_fetchall(
            "SELECT subject_id, COUNT(*) as cnt "
            "FROM papers GROUP BY subject_id ORDER BY cnt DESC"
        )
        subject_distribution: dict[str, int] = {
            r["subject_id"]: r["cnt"] for r in by_subject
        }

        # 各学科题目数
        questions_by_subject = await db.execute_fetchall(
            """SELECT p.subject_id, COUNT(q.id) as cnt
               FROM questions q
               JOIN papers p ON q.paper_id = p.id
               GROUP BY p.subject_id ORDER BY cnt DESC"""
        )
        questions_by_subject_dict: dict[str, int] = {
            r["subject_id"]: r["cnt"] for r in questions_by_subject
        }

        # 近期趋势（按天统计最近30天新增试卷数）
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        daily_trend = await db.execute_fetchall(
            """SELECT DATE(collected_at) as day, COUNT(*) as cnt
               FROM papers
               WHERE collected_at >= ?
               GROUP BY DATE(collected_at)
               ORDER BY day ASC""",
            (thirty_days_ago,),
        )
        trend_data = [
            {"date": r["day"], "count": r["cnt"]} for r in daily_trend
        ]

        return {
            "total_questions": total_questions,
            "total_papers": total_papers,
            "source_distribution": source_distribution,
            "subject_distribution": subject_distribution,
            "questions_by_subject": questions_by_subject_dict,
            "daily_trend": trend_data,
        }

    async def get_target_progress(self, db: Any) -> dict[str, Any]:
        """获取目标进度

        Args:
            db: 数据库连接

        Returns:
            目标进度数据
        """
        # 模拟卷数量（paper_type != 'real' 的试卷）
        mock_papers_row = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE paper_type != 'real'"
        )
        collected_mock_papers = mock_papers_row["cnt"] if mock_papers_row else 0

        # 高考真题（paper_type = 'real'）
        real_exams_row = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE paper_type = 'real'"
        )
        collected_real_exams = real_exams_row["cnt"] if real_exams_row else 0

        # 近5年真题覆盖情况
        current_year = datetime.now().year
        target_years = list(range(current_year - 4, current_year + 1))
        real_exams_by_year = await db.execute_fetchall(
            "SELECT year, COUNT(*) as cnt FROM papers "
            "WHERE paper_type = 'real' AND year >= ? AND year <= ? "
            "GROUP BY year ORDER BY year",
            (target_years[0], target_years[-1]),
        )
        year_coverage = {
            str(y): 0 for y in target_years
        }
        for r in real_exams_by_year:
            year_coverage[str(r["year"])] = r["cnt"]

        # 进度百分比
        mock_pct = min(collected_mock_papers / self.COLLECTION_TARGET["mock_papers"] * 100, 100)
        # 真题进度：按年份覆盖度计算，每覆盖一年为 20%
        covered_years = sum(1 for v in year_coverage.values() if v > 0)
        real_pct = min(covered_years / self.COLLECTION_TARGET["real_exams_years"] * 100, 100)

        return {
            "target": {
                "mock_papers": self.COLLECTION_TARGET["mock_papers"],
                "real_exams_years": self.COLLECTION_TARGET["real_exams_years"],
            },
            "collected_mock_papers": collected_mock_papers,
            "collected_real_exams": collected_real_exams,
            "mock_progress_pct": round(mock_pct, 1),
            "real_progress_pct": round(real_pct, 1),
            "overall_progress_pct": round((mock_pct + real_pct) / 2, 1),
            "year_coverage": year_coverage,
        }

    async def get_collection_logs(
        self, db: Any, limit: int = 50, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """获取采集任务记录列表

        Args:
            db: 数据库连接
            limit: 返回记录数上限
            offset: 分页偏移

        Returns:
            采集日志记录列表
        """
        rows = await db.execute_fetchall(
            """SELECT * FROM collection_logs
               ORDER BY started_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        # 反序列化 errors 字段
        result = []
        for r in rows:
            entry = dict(r)
            try:
                entry["errors"] = json.loads(r["errors"]) if isinstance(r["errors"], str) else r["errors"]
            except (json.JSONDecodeError, TypeError):
                entry["errors"] = []
            result.append(entry)
        return result

    async def trigger_manual_collection(
        self, db: Any, auto_scraper: Any,
    ) -> dict[str, Any]:
        """手动触发一次采集任务

        Args:
            db: 数据库连接
            auto_scraper: AutoScraper 实例

        Returns:
            触发结果
        """
        if not auto_scraper:
            return {"triggered": False, "error": "Auto-scraper not initialized"}

        # 创建采集日志记录
        started_at = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO collection_logs
               (source, task_type, started_at, status)
               VALUES (?, 'manual', ?, 'running')""",
            ("manual_trigger", started_at),
        )
        log_id = cursor.lastrowid
        await db.commit()

        try:
            # 执行单次采集（同步执行，调用者应使用 BackgroundTasks）
            await auto_scraper._run_once()

            # 更新采集日志为完成状态
            completed_at = datetime.now().isoformat()
            await db.execute(
                """UPDATE collection_logs SET
                   completed_at = ?, status = 'completed'
                   WHERE id = ?""",
                (completed_at, log_id),
            )
            await db.commit()

            return {"triggered": True, "log_id": log_id}

        except Exception as e:
            logger.exception("Manual collection failed")
            # 标记为失败
            completed_at = datetime.now().isoformat()
            await db.execute(
                """UPDATE collection_logs SET
                   completed_at = ?, status = 'failed',
                   errors = ? WHERE id = ?""",
                (completed_at, json.dumps([str(e)], ensure_ascii=False), log_id),
            )
            await db.commit()
            return {"triggered": False, "error": str(e), "log_id": log_id}
