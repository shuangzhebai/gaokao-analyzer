"""
题目质量评估与优质题识别引擎 v3.0
核心功能：
1. 单题质量评估（区分度、难度适当性、认知层次）
2. 优质题识别算法（多维度加权评分）
3. 整卷质量分析（信度、效度、难度梯度）
4. 题目推荐（按质量排序，识别优秀题目）
"""
# mypy: disable-error-code="no-untyped-def,no-any-return,call-overload,operator,type-arg,assignment,var-annotated,misc,index,attr-defined,return-value,func-returns-value,return,has-type,unused-ignore,arg-type,no-untyped-call,type-var,call-arg"

import json
from typing import Any, Optional

import numpy as np
from scipy import stats

from config import IRT_CONFIG, CURRICULUM_LEVELS
from analyzer import IRTModel, KnowledgeMapper


class QualityScorer:
    """
    题目质量评估器
    综合IRT参数、经典测量理论、认知层次进行多维度评估
    """

    # 质量等级阈值
    QUALITY_THRESHOLDS = {
        "excellent": 85,  # 优质题
        "good": 70,       # 良好题
        "fair": 55,       # 合格题
        "poor": 40,       # 较差题
    }

    def score_question(self, q_data, all_questions=None, responses=None) -> None:
        """
        评估单个题目的质量

        q_data: {
            "irt_a": float, "irt_b": float, "irt_c": float,
            "q_type": str, "score": float, "content": str,
            "knowledge_points": list, "cognitive_level": str,
        }
        all_questions: 同卷其他题目(用于相对评估)
        responses: 考生作答数据(可选)

        返回: {
            "quality_score": float,      # 综合质量分(0-100)
            "discrimination_score": float, # 区分度分(0-100)
            "difficulty_score": float,    # 难度适当性分(0-100)
            "cognitive_score": float,     # 认知层次分(0-100)
            "quality_rating": str,        # 评级 excellent/good/fair/poor
            "is_quality": bool,           # 是否优质题
            "highlights": list,           # 亮点
            "issues": list,               # 问题
        }
        """
        scores = {}
        highlights = []
        issues = []

        # 1. 区分度评分 (权重40%)
        irt_a = q_data.get("irt_a") or 0
        disc_score = self._score_discrimination(irt_a)
        scores["discrimination"] = disc_score
        if irt_a >= 1.5:
            highlights.append(f"区分度优秀(a={irt_a:.2f})，能有效区分不同水平考生")
        elif irt_a < 0.5:
            issues.append(f"区分度不足(a={irt_a:.2f})，无法有效区分考生水平")

        # 2. 难度适当性评分 (权重25%)
        irt_b = q_data.get("irt_b") or 0
        irt_c = q_data.get("irt_c") or 0
        diff_score = self._score_difficulty(irt_b, irt_c, q_data.get("q_type", "solve"))
        scores["difficulty"] = diff_score
        if -1.0 <= irt_b <= 1.0:
            highlights.append(f"难度适中(b={irt_b:.2f})，适合大多数考生")
        elif irt_b > 2.0:
            issues.append(f"难度偏大(b={irt_b:.2f})，可能过于困难")
        elif irt_b < -2.0:
            issues.append(f"难度偏小(b={irt_b:.2f})，区分度受限")

        # 3. 猜测系数评估 (权重15%)
        guess_score = self._score_guessing(irt_c, q_data.get("q_type", "solve"))
        scores["guessing"] = guess_score
        if irt_c > 0.25 and q_data.get("q_type") != "choice":
            issues.append(f"非选择题猜测系数偏高(c={irt_c:.2f})")

        # 4. 认知层次评分 (权重20%)
        cognitive_score = self._score_cognitive(q_data)
        scores["cognitive"] = cognitive_score

        # 加权总分
        weights = {"discrimination": 0.40, "difficulty": 0.25, "guessing": 0.15, "cognitive": 0.20}
        quality_score = sum(scores[k] * weights[k] for k in weights)

        # 评级
        rating = self._rate_quality(quality_score)
        is_quality = quality_score >= self.QUALITY_THRESHOLDS["excellent"]

        if is_quality:
            highlights.insert(0, "★ 优质题目：综合质量评分达到优秀标准")

        return {
            "quality_score": round(quality_score, 2),
            "detail_scores": {k: round(v, 2) for k, v in scores.items()},
            "quality_rating": rating,
            "is_quality": is_quality,
            "highlights": highlights,
            "issues": issues,
        }

    def score_paper(self, questions_data) -> Any:
        """
        评估整卷质量

        questions_data: 题目列表，每项含 irt_a/irt_b/irt_c/q_type/score/knowledge_points 等

        返回: {
            "overall_score": float,
            "reliability": float,           # 信度估计
            "difficulty_gradient": {...},   # 难度梯度分析
            "discrimination_summary": {...},# 区分度统计
            "quality_distribution": {...},  # 质量分布
            "quality_questions": [...],     # 优质题列表
            "weak_questions": [...],        # 较差题列表
            "suggestions": [...],           # 改进建议
        }
        """
        if not questions_data:
            return self._empty_paper_result()

        # 逐题评估
        question_scores = []
        quality_questions = []
        weak_questions = []

        for i, q in enumerate(questions_data):
            score_result = self.score_question(q, questions_data)
            score_result["question_index"] = i
            score_result["q_number"] = q.get("q_number", i + 1)
            question_scores.append(score_result)

            if score_result["is_quality"]:
                quality_questions.append({
                    "index": i,
                    "q_number": q.get("q_number", i + 1),
                    "quality_score": score_result["quality_score"],
                    "highlights": score_result["highlights"],
                })
            elif score_result["quality_rating"] == "poor":
                weak_questions.append({
                    "index": i,
                    "q_number": q.get("q_number", i + 1),
                    "quality_score": score_result["quality_score"],
                    "issues": score_result["issues"],
                })

        # 整卷统计
        a_values = [q.get("irt_a", 0) for q in questions_data if q.get("irt_a")]
        b_values = [q.get("irt_b", 0) for q in questions_data if q.get("irt_b")]

        # 区分度统计
        disc_summary = {
            "mean": round(float(np.mean(a_values)), 4) if a_values else 0,
            "std": round(float(np.std(a_values)), 4) if a_values else 0,
            "min": round(float(np.min(a_values)), 4) if a_values else 0,
            "max": round(float(np.max(a_values)), 4) if a_values else 0,
            "excellent_count": sum(1 for a in a_values if a >= 1.5),
            "poor_count": sum(1 for a in a_values if a < 0.5),
        }

        # 难度梯度分析
        gradient = self._analyze_difficulty_gradient(b_values, questions_data)

        # 信度估计（基于IRT）
        reliability = self._estimate_reliability(questions_data)

        # 质量分布
        quality_dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
        for qs in question_scores:
            quality_dist[qs["quality_rating"]] = quality_dist.get(qs["quality_rating"], 0) + 1

        # 总分
        overall_score = float(np.mean([qs["quality_score"] for qs in question_scores]))

        # 改进建议
        suggestions = self._generate_suggestions(
            disc_summary, gradient, quality_dist, quality_questions, weak_questions
        )

        return {
            "overall_score": round(overall_score, 2),
            "reliability": round(reliability, 4),
            "difficulty_gradient": gradient,
            "discrimination_summary": disc_summary,
            "quality_distribution": quality_dist,
            "quality_questions": quality_questions,
            "weak_questions": weak_questions,
            "question_scores": question_scores,
            "suggestions": suggestions,
        }

    def _score_discrimination(self, a) -> Any:
        """区分度评分 (0-100)"""
        if a >= 2.0:
            return 100
        elif a >= 1.5:
            return 80 + (a - 1.5) / 0.5 * 20
        elif a >= 1.0:
            return 55 + (a - 1.0) / 0.5 * 25
        elif a >= 0.5:
            return 25 + (a - 0.5) / 0.5 * 30
        else:
            return max(0, a / 0.5 * 25)

    def _score_difficulty(self, b, c, q_type) -> Any:
        """难度适当性评分 (0-100)"""
        # 不同题型的最优难度范围不同
        optimal_ranges = {
            "choice": (-1.0, 1.0),
            "fill": (-0.5, 1.5),
            "solve": (-0.5, 2.0),
        }
        low, high = optimal_ranges.get(q_type, (-0.5, 1.5))

        if low <= b <= high:
            # 在最优范围内，越居中越高分
            center = (low + high) / 2
            half_range = (high - low) / 2
            score = 80 + 20 * (1 - abs(b - center) / half_range)
            return round(score, 2)
        elif b < low:
            # 偏易
            distance = low - b
            return max(0, 80 - distance * 25)
        else:
            # 偏难
            distance = b - high
            return max(0, 80 - distance * 15)

    def _score_guessing(self, c, q_type) -> Any:
        """猜测系数评分 (0-100)"""
        if q_type == "choice":
            # 选择题允许一定猜测
            if c <= 0.2:
                return 90
            elif c <= 0.25:
                return 75
            elif c <= 0.33:
                return 50
            else:
                return max(0, 50 - (c - 0.33) * 300)
        else:
            # 非选择题猜测系数应接近0
            if c <= 0.05:
                return 100
            elif c <= 0.1:
                return 80
            elif c <= 0.2:
                return 50
            else:
                return max(0, 50 - (c - 0.2) * 200)

    def _score_cognitive(self, q_data) -> Any:
        """认知层次评分 (0-100)"""
        q_type = q_data.get("q_type", "solve")
        # 题型默认对应认知层次
        type_cognitive = {
            "choice": "理解",
            "fill": "应用",
            "solve": "综合",
        }
        expected = type_cognitive.get(q_type, "应用")

        # 如果有显式认知层次标记
        actual = q_data.get("cognitive_level") or expected

        # 层次匹配度
        levels = list(CURRICULUM_LEVELS.keys())
        if actual in levels and expected in levels:
            distance = abs(levels.index(actual) - levels.index(expected))
            if distance == 0:
                return 100
            elif distance == 1:
                return 75
            elif distance == 2:
                return 50
            else:
                return 30

        return 70  # 默认

    def _rate_quality(self, score) -> Any:
        if score >= self.QUALITY_THRESHOLDS["excellent"]:
            return "excellent"
        elif score >= self.QUALITY_THRESHOLDS["good"]:
            return "good"
        elif score >= self.QUALITY_THRESHOLDS["fair"]:
            return "fair"
        else:
            return "poor"

    def _analyze_difficulty_gradient(self, b_values, questions_data) -> Any:
        """分析难度梯度是否合理"""
        if not b_values:
            return {"is_reasonable": False, "description": "无难度数据"}

        # 理想梯度：从易到难递增
        n = len(b_values)
        sorted_b = sorted(b_values)

        # 检查是否大致递增
        increases = sum(1 for i in range(1, n) if sorted_b[i] > sorted_b[i-1])
        gradient_ratio = increases / (n - 1) if n > 1 else 1

        # 难度范围
        b_range = max(b_values) - min(b_values) if b_values else 0

        # 分段难度
        n_segments = min(3, n)
        segment_size = n // n_segments
        segments = []
        for i in range(n_segments):
            start = i * segment_size
            end = start + segment_size if i < n_segments - 1 else n
            seg_b = sorted_b[start:end]
            segments.append({
                "segment": f"第{i+1}部分",
                "mean_difficulty": round(float(np.mean(seg_b)), 4) if seg_b else 0,
                "count": len(seg_b),
            })

        is_reasonable = gradient_ratio >= 0.5 and b_range >= 1.0

        return {
            "is_reasonable": is_reasonable,
            "gradient_ratio": round(gradient_ratio, 4),
            "difficulty_range": round(b_range, 4),
            "min_b": round(float(np.min(b_values)), 4),
            "max_b": round(float(np.max(b_values)), 4),
            "segments": segments,
        }

    def _estimate_reliability(self, questions_data) -> Any:
        """基于IRT参数估计信度（测验信息函数法）"""
        a_values = [q.get("irt_a", 0) for q in questions_data if q.get("irt_a")]
        if not a_values:
            return 0.0

        # 简化信度估计：基于平均区分度和题目数量
        n = len(a_values)
        mean_a = float(np.mean(a_values))

        # 使用Spearman-Brown公式
        reliability = (n * mean_a ** 2) / (1 + (n - 1) * mean_a ** 2) * 0.8
        return min(reliability, 0.99)

    def _generate_suggestions(self, disc_summary, gradient, quality_dist,
                               quality_questions, weak_questions):
        """生成改进建议"""
        suggestions = []

        # 区分度建议
        if disc_summary["poor_count"] > 0:
            suggestions.append(
                f"有 {disc_summary['poor_count']} 道题区分度不足(a<0.5)，建议替换或修改这些题目"
            )
        if disc_summary["excellent_count"] == 0:
            suggestions.append("试卷缺少高区分度题目(a>=1.5)，建议增加区分优秀考生的题目")

        # 难度梯度建议
        if not gradient.get("is_reasonable", True):
            suggestions.append("难度梯度不够合理，建议调整为从易到难的递进结构")
        if gradient.get("difficulty_range", 0) < 1.0:
            suggestions.append("题目难度区分不够，建议增加难度跨度")

        # 质量分布建议
        poor_pct = quality_dist.get("poor", 0) / max(sum(quality_dist.values()), 1)
        if poor_pct > 0.3:
            suggestions.append(f"较差题目占比 {poor_pct*100:.0f}%，建议重点优化这些题目")

        if not quality_questions:
            suggestions.append("整卷缺少优质题(评分>=85)，建议精选高质量题目")

        if not suggestions:
            suggestions.append("试卷整体质量良好，建议继续保持当前水平")

        return suggestions

    def _empty_paper_result(self) -> Any:
        return {
            "overall_score": 0,
            "reliability": 0,
            "difficulty_gradient": {},
            "discrimination_summary": {},
            "quality_distribution": {},
            "quality_questions": [],
            "weak_questions": [],
            "question_scores": [],
            "suggestions": ["无题目数据"],
        }
