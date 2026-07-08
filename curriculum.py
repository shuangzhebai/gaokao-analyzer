"""
新课标课程标准契合度分析引擎 v3.0
核心功能：
1. 课程标准知识点覆盖度量化
2. 能力层次（识记/理解/应用/分析/综合/评价）分析
3. 核心素养匹配度评分
4. 课标契合度综合评分
5. 考试大纲偏差诊断
"""
# mypy: disable-error-code="no-untyped-def,no-any-return,call-overload,operator,type-arg,assignment,var-annotated,misc,index,attr-defined,return-value,func-returns-value,return,has-type,unused-ignore,arg-type"

import json
from typing import Any, Optional

import numpy as np

from config import CURRICULUM_LEVELS, CORE_COMPETENCIES


class CurriculumAnalyzer:
    """
    新课标课程标准契合度分析器
    基于教育部《普通高中课程方案和课程标准(2017年版2020年修订)》
    """

    # 各科各知识点的能力层次要求映射
    COGNITIVE_MAP = {
        "math": {
            "2.1.1": "识记", "2.1.2": "理解",
            "2.2.1": "理解", "2.2.2": "应用", "2.2.3": "分析",
            "2.3.1": "应用", "2.3.2": "综合", "2.3.3": "综合",
            "2.4.1": "理解", "2.4.2": "应用", "2.4.3": "应用",
            "2.5.1": "理解", "2.5.2": "综合", "2.5.3": "综合",
            "2.6.1": "应用", "2.6.2": "应用",
            "2.7.1": "理解", "2.7.2": "分析", "2.7.3": "综合",
            "2.8.1": "应用", "2.8.2": "综合", "2.8.3": "应用",
            "2.9.1": "理解", "2.9.2": "应用", "2.9.3": "应用", "2.9.4": "分析",
            "2.10.1": "应用", "2.10.2": "识记",
        },
        "physics": {
            "4.1.1": "理解", "4.1.2": "应用", "4.1.3": "分析",
            "4.1.4": "分析", "4.1.5": "综合", "4.1.6": "综合",
            "4.2.1": "理解", "4.2.2": "应用", "4.2.3": "分析",
            "4.2.4": "综合", "4.2.5": "理解",
            "4.3.1": "识记", "4.3.2": "应用", "4.3.3": "理解",
            "4.4": "理解",
            "4.5.1": "识记", "4.5.2": "理解", "4.5.3": "理解",
            "4.6": "综合",
        },
        "chinese": {
            "1.1.1": "识记", "1.1.2": "识记", "1.1.3": "应用",
            "1.1.4": "分析", "1.1.5": "理解", "1.1.6": "应用",
            "1.2.1": "分析", "1.2.2": "评价", "1.2.3": "识记",
            "1.3.1": "分析", "1.3.2": "评价", "1.3.3": "分析",
            "1.4.1": "综合", "1.4.2": "综合", "1.4.3": "综合",
        },
        "english": {
            "3.1.1": "理解", "3.1.2": "理解", "3.1.3": "理解",
            "3.2.1": "理解", "3.2.2": "分析", "3.2.3": "分析", "3.2.4": "应用",
            "3.3": "应用",
            "3.4.1": "应用", "3.4.2": "应用", "3.4.3": "理解",
            "3.4.4": "理解", "3.4.5": "理解", "3.4.6": "应用",
            "3.5.1": "综合", "3.5.2": "综合", "3.5.3": "综合",
        },
    }

    # 各科各知识点的核心素养关联
    COMPETENCY_MAP = {
        "math": {
            "2.1": ["数学抽象"], "2.2": ["数学抽象", "数学运算"],
            "2.3": ["数学运算", "逻辑推理"], "2.4": ["数学运算", "直观想象"],
            "2.5": ["逻辑推理", "数学运算"], "2.6": ["逻辑推理", "数学运算"],
            "2.7": ["直观想象", "逻辑推理"], "2.8": ["数学运算", "直观想象"],
            "2.9": ["数据分析", "数学建模"], "2.10": ["数学运算"],
        },
        "physics": {
            "4.1": ["物理观念", "科学思维"], "4.2": ["物理观念", "科学思维"],
            "4.3": ["物理观念"], "4.4": ["科学思维"],
            "4.5": ["物理观念", "科学思维"], "4.6": ["科学探究"],
        },
        "chinese": {
            "1.1": ["语言建构与运用"], "1.2": ["文化传承与理解", "思维发展与提升"],
            "1.3": ["思维发展与提升", "审美鉴赏与创造"],
            "1.4": ["思维发展与提升", "审美鉴赏与创造"],
        },
        "english": {
            "3.1": ["语言能力"], "3.2": ["语言能力", "思维品质"],
            "3.3": ["语言能力", "思维品质"], "3.4": ["语言能力"],
            "3.5": ["语言能力", "思维品质"],
        },
    }

    def analyze_paper(self, questions, subject_key, ref_kps=None) -> Any:
        """
        全面分析试卷的课程标准契合度

        questions: [{"knowledge_points": [...], "content": str, "q_type": str, "score": float, ...}]
        subject_key: 科目代码
        ref_kps: 课标要求的知识点列表（None则使用完整课标）

        返回：{
            "curriculum_score": float,        # 课标契合度总分(0-100)
            "knowledge_coverage": {...},       # 知识点覆盖度
            "cognitive_distribution": {...},   # 能力层次分布
            "competency_coverage": {...},      # 核心素养覆盖
            "bias_diagnosis": {...},           # 偏差诊断
            "grade": str,                      # 等级
        }
        """
        # 1. 知识点覆盖度分析
        kp_result = self._analyze_knowledge_coverage(questions, subject_key, ref_kps)

        # 2. 能力层次分析
        cognitive_result = self._analyze_cognitive_levels(questions, subject_key)

        # 3. 核心素养覆盖度
        competency_result = self._analyze_competency_coverage(questions, subject_key)

        # 4. 偏差诊断
        bias_result = self._diagnose_bias(kp_result, cognitive_result, subject_key)

        # 5. 综合评分
        curriculum_score = self._compute_curriculum_score(
            kp_result, cognitive_result, competency_result
        )

        return {
            "curriculum_score": round(curriculum_score, 2),
            "knowledge_coverage": kp_result,
            "cognitive_distribution": cognitive_result,
            "competency_coverage": competency_result,
            "bias_diagnosis": bias_result,
            "grade": self._grade_score(curriculum_score),
        }

    def _analyze_knowledge_coverage(self, questions, subject_key, ref_kps=None) -> Any:
        """知识点覆盖度量化分析"""
        # 收集试卷涉及的知识点
        paper_kps = set()
        kp_score_map = {}
        for q in questions:
            for kp in (q.get("knowledge_points") or []):
                paper_kps.add(kp)
                kp_score_map[kp] = kp_score_map.get(kp, 0) + q.get("score", 0)

        # 获取课标知识点
        from models import KNOWLEDGE_SEED
        curriculum_kps = set()
        for code, _name, _parent, _level in KNOWLEDGE_SEED.get(subject_key, []):
            curriculum_kps.add(code)

        if ref_kps:
            curriculum_kps = set(ref_kps)

        if not curriculum_kps:
            return {"coverage_rate": 0, "jaccard": 0, "missing": [], "extra": [], "distribution": {}}

        covered = paper_kps & curriculum_kps
        missing = curriculum_kps - paper_kps
        extra = paper_kps - curriculum_kps
        union = paper_kps | curriculum_kps

        coverage_rate = len(covered) / len(curriculum_kps) if curriculum_kps else 0
        jaccard = len(covered) / len(union) if union else 0

        # 按一级知识点统计分布
        distribution = {}
        for kp in covered:
            parent = kp.rsplit(".", 1)[0] if "." in kp else kp
            distribution[parent] = distribution.get(parent, 0) + kp_score_map.get(kp, 0)

        return {
            "coverage_rate": round(coverage_rate, 4),
            "jaccard": round(jaccard, 4),
            "covered_count": len(covered),
            "total_curriculum_kps": len(curriculum_kps),
            "missing": sorted(missing),
            "extra": sorted(extra),
            "distribution": distribution,
        }

    def _analyze_cognitive_levels(self, questions, subject_key) -> None:
        """能力层次分布分析"""
        cognitive_map = self.COGNITIVE_MAP.get(subject_key, {})
        level_weights = {name: info["weight"] for name, info in CURRICULUM_LEVELS.items()}

        # 统计试卷中各能力层次的分值分布
        paper_levels = {name: 0.0 for name in CURRICULUM_LEVELS}
        total_score = 0

        for q in questions:
            q_kps = q.get("knowledge_points") or []
            q_score = q.get("score", 0)
            total_score += q_score

            # 根据知识点映射能力层次
            levels_found = set()
            for kp in q_kps:
                level = cognitive_map.get(kp)
                if level:
                    levels_found.add(level)

            # 如果没找到映射，根据题型推断
            if not levels_found:
                q_type = q.get("q_type", "solve")
                if q_type == "choice":
                    levels_found.add("理解")
                elif q_type == "fill":
                    levels_found.add("应用")
                else:
                    levels_found.add("综合")

            for level in levels_found:
                paper_levels[level] += q_score / len(levels_found)

        # 课标理想分布
        ideal_levels = level_weights

        # 计算实际比例
        if total_score > 0:
            actual_pcts = {k: round(v / total_score, 4) for k, v in paper_levels.items()}
        else:
            actual_pcts = {k: 0 for k in CURRICULUM_LEVELS}

        # 计算偏差
        deviations = {}
        for level in CURRICULUM_LEVELS:
            actual = actual_pcts.get(level, 0)
            ideal = ideal_levels.get(level, 0)
            deviations[level] = round(actual - ideal, 4)

        return {
            "actual": actual_pcts,
            "ideal": ideal_levels,
            "deviations": deviations,
            "total_score": total_score,
        }

    def _analyze_competency_coverage(self, questions, subject_key) -> Any:
        """核心素养覆盖度分析"""
        competency_map = self.COMPETENCY_MAP.get(subject_key, {})
        core_competencies = CORE_COMPETENCIES.get(subject_key, [])

        if not core_competencies:
            return {"coverage": 0, "details": {}}

        # 统计各核心素养的分值
        competency_scores = {c: 0.0 for c in core_competencies}
        total_score = 0

        for q in questions:
            q_kps = q.get("knowledge_points") or []
            q_score = q.get("score", 0)
            total_score += q_score

            matched = set()
            for kp in q_kps:
                parent = kp.rsplit(".", 1)[0] if "." in kp else kp
                for comp in competency_map.get(parent, []):
                    matched.add(comp)

            for comp in matched:
                if comp in competency_scores:
                    competency_scores[comp] += q_score

        # 计算覆盖度
        covered = sum(1 for s in competency_scores.values() if s > 0)
        coverage = covered / len(core_competencies) if core_competencies else 0

        details = {}
        for comp in core_competencies:
            score = competency_scores.get(comp, 0)
            pct = round(score / total_score * 100, 1) if total_score > 0 else 0
            details[comp] = {
                "score": round(score, 1),
                "percentage": pct,
                "covered": score > 0,
            }

        return {
            "coverage": round(coverage, 4),
            "covered_count": covered,
            "total_count": len(core_competencies),
            "details": details,
        }

    def _diagnose_bias(self, kp_result, cognitive_result, subject_key) -> Any:
        """偏差诊断 - 识别试卷与课标的偏差"""
        warnings = []

        # 知识点缺失过多
        if kp_result["coverage_rate"] < 0.5:
            warnings.append({
                "type": "knowledge_gap",
                "severity": "high",
                "message": f"知识点覆盖率仅 {kp_result['coverage_rate']*100:.1f}%，远低于课标要求",
                "detail": f"缺失 {len(kp_result['missing'])} 个课标知识点",
            })
        elif kp_result["coverage_rate"] < 0.7:
            warnings.append({
                "type": "knowledge_gap",
                "severity": "medium",
                "message": f"知识点覆盖率 {kp_result['coverage_rate']*100:.1f}%，仍有提升空间",
            })

        # 能力层次偏差
        deviations = cognitive_result.get("deviations", {})
        for level, dev in deviations.items():
            if abs(dev) > 0.15:
                severity = "high" if abs(dev) > 0.25 else "medium"
                direction = "偏多" if dev > 0 else "偏少"
                warnings.append({
                    "type": "cognitive_bias",
                    "severity": severity,
                    "message": f"'{level}'层次题目{direction}（偏差 {dev*100:+.1f}%）",
                })

        return {
            "warnings": warnings,
            "warning_count": len(warnings),
            "high_severity_count": sum(1 for w in warnings if w["severity"] == "high"),
        }

    def _compute_curriculum_score(self, kp_result, cognitive_result, competency_result) -> Any:
        """计算课标契合度综合评分(0-100)"""
        # 知识点覆盖度评分(0-40)
        kp_score = kp_result["coverage_rate"] * 40

        # 能力层次合理性评分(0-30)
        deviations = cognitive_result.get("deviations", {})
        total_deviation = sum(abs(d) for d in deviations.values())
        max_possible_deviation = 2.0  # 理论最大偏差
        cognitive_score = max(0, (1 - total_deviation / max_possible_deviation)) * 30

        # 核心素养覆盖评分(0-30)
        competency_score = competency_result["coverage"] * 30

        return kp_score + cognitive_score + competency_score

    def _grade_score(self, score) -> Any:
        if score >= 90:
            return "A (高度契合)"
        elif score >= 75:
            return "B (较好契合)"
        elif score >= 60:
            return "C (一般契合)"
        elif score >= 45:
            return "D (较弱契合)"
        else:
            return "E (不契合)"
