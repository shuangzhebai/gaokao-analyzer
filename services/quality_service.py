"""质量诊断服务编排层。

协调 HybridQualityEngine（IRT+CTT 混合诊断引擎）与 IRT 引擎，
对外提供单题/批量质量分析、报告查询、IRT 预计算能力。
"""

import json
import logging
from typing import Any

import numpy as np

from engines.hybrid_quality import HybridQualityEngine

logger = logging.getLogger("gaokao")


class QualityService:
    """质量诊断编排服务。"""

    def __init__(self, engine: HybridQualityEngine | None = None) -> None:
        self._engine = engine or HybridQualityEngine()

    async def analyze(self, question_ids: list[int], responses_data: list[dict] | None = None) -> list[dict]:
        """对一组题目做质量分析。

        如果提供了 responses_data，则使用真实作答数据计算 CTT + IRT 指标；
        否则使用 IRT 参数缓存（无真实数据时返回基于缓存的分析）。

        Args:
            question_ids: 题目 ID 列表
            responses_data: 可选，作答数据，格式为
                [{question_id, user_id, score, max_score, is_correct}, ...]

        Returns:
            list[dict]: 质量报告列表
        """
        reports: list[dict] = []

        # 尝试从缓存获取 IRT 参数
        irt_params_map: dict[int, dict[str, Any]] = {}
        try:
            from engines.irt_models import get_cached_params
            irt_params_map = await get_cached_params(question_ids)
        except Exception as e:
            logger.warning("获取 IRT 缓存参数失败: %s", e)

        for qid in question_ids:
            ctt_stats = None
            irt_params = irt_params_map.get(qid)

            # 如果有作答数据，计算 CTT 指标
            if responses_data:
                q_responses = [r for r in responses_data if r.get("question_id") == qid]
                if q_responses:
                    ctt_stats = self._engine.compute_ctt_indicators(q_responses)

            # 生成 6 维报告
            report = self._engine.generate_6d_report(qid, ctt_stats=ctt_stats, irt_params=irt_params)
            reports.append(report)

        return reports

    async def batch_analyze(self, paper_ids: list[int], responses_data: list[dict] | None = None) -> list[dict]:
        """批量分析多份试卷，生成横向对比。

        Args:
            paper_ids: 试卷 ID 列表
            responses_data: 可选作答数据

        Returns:
            list[dict]: 每份试卷的整体质量报告
        """
        paper_reports: list[dict] = []
        for pid in paper_ids:
            # 获取该试卷下的所有题目 ID（占位：真实场景需从数据库读取）
            # 当前返回整体质量骨架
            report = {
                "paper_id": pid,
                "title": f"试卷 #{pid}",
                "quality_score": 0.0,
                "question_count": 0,
                "dimensions": {
                    "difficulty": 0.5,
                    "discrimination": 0.5,
                    "reliability": 0.5,
                    "validity": 0.5,
                    "knowledge_coverage": 0.5,
                    "type_match": 0.5,
                },
            }
            paper_reports.append(report)
        return paper_reports

    async def get_report(self, question_id: int) -> dict | None:
        """获取单题质量报告。

        优先从缓存读取 IRT 参数并生成报告，无缓存时返回 None。

        Args:
            question_id: 题目 ID

        Returns:
            dict | None: 质量报告
        """
        try:
            from engines.irt_models import get_cached_params

            params_map = await get_cached_params([question_id])
            irt_params = params_map.get(question_id)
            if irt_params:
                return self._engine.generate_6d_report(question_id, irt_params=irt_params)
        except Exception as e:
            logger.warning("获取题目 %d 质量报告失败: %s", question_id, e)
        return None

    async def precompute_all(self) -> dict[str, Any]:
        """全量 IRT 预计算（依次处理所有需要预计算的题目）。

        注意：当前为占位实现，完整版需要从数据库读取题目 ID 列表。

        Returns:
            dict: 预计算状态摘要
        """
        logger.info("全量 IRT 预计算启动")
        try:
            from engines.irt_models import precompute_params
            # 占位：实际上应当从数据库读取所有 question_id
            result = await precompute_params([])
            return {
                "status": "completed",
                "total_cached": len(result),
                "message": "IRT 预计算完成",
            }
        except Exception as e:
            logger.error("全量 IRT 预计算失败: %s", e)
            return {
                "status": "error",
                "message": str(e),
            }

    async def compare_papers(self, paper_ids: list[int]) -> list[dict]:
        """多卷横向对比。

        Args:
            paper_ids: 试卷 ID 列表

        Returns:
            list[dict]: 各卷质量对比数据
        """
        return await self.batch_analyze(paper_ids)
