"""
阶段二（后端核心）：试卷质量分析引擎（整合 analyze_paper 入口，覆盖 6 维度）

设计原则：
- 弃用任何 LLM：纯确定性数值方法，复用现有 IRTModel / MonteCarloSimulator /
  QualityAnalyzer / KnowledgeMapper（不重写数值方法，避免回归）。
- 单一入口 analyze_paper(paper) -> AnalysisReport（dict，可 JSON 序列化）。
- 6 个评价维度，每维度给出 0-100 分值 + 文字结论，量化方法均有依据：
    1) 难度评估：题型权重 / 知识点覆盖深度 / 模拟答题正确率 → 整体难度系数 + 分题难度系数
    2) 知识点覆盖分析：广度（去重知识点数 / 总知识点池）+ 深度（频次均衡度）
    3) 题型分布分析：各类题型占比、分值分配合理性（与预设权重对比偏离度）
    4) 区分度评价：高/低能力组通过率差 + 点二列相关近似（IRT a 辅助）
    5) 信度评估：Cronbach α + 分半信度（Spearman-Brown 校正）
    6) 效度评估：内容效度比 CVR（对照知识点大纲覆盖率）+ 效度依据说明
- 质量综合评分：6 维度加权 → 综合分(0-100) + 等级(优秀/良好/合格/待改进) + 结论。
- 性能：analyze_papers_batch 异步并行（asyncio + ThreadPoolExecutor，numpy 释放 GIL）；
  缓存 IRT 拟合与知识点映射，避免重复计算。
"""
import asyncio
import logging
import threading
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import numpy as np

from analyzer import IRTModel, KnowledgeMapper, QualityAnalyzer
from config import (get_analysis_config, get_analysis_weights,
                     get_question_type_preset, normalize_subject)
from models import KNOWLEDGE_SEED
from simulator import MonteCarloSimulator

logger = logging.getLogger("gaokao")


class LRUCache:
    """有上限的 LRU 缓存，线程安全（maxsize=256）。"""
    def __init__(self, maxsize: int = 256):
        self.maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key, value):
        with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            if len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    def __contains__(self, key):
        with self._lock:
            return key in self._cache

    def __len__(self):
        with self._lock:
            return len(self._cache)


class PaperAnalyzer:
    """整卷质量分析器：整合 IRT / 蒙特卡洛 / 知识点映射，输出 6 维度报告。"""

    def __init__(self, subject_id: str = "math", n_students: Optional[int] = None,
                 simulator: Optional[MonteCarloSimulator] = None,
                 kp_mapper: Optional[KnowledgeMapper] = None,
                 irt_model: Optional[IRTModel] = None,
                 quality_analyzer: Optional[QualityAnalyzer] = None,
                 use_cache: Optional[bool] = None):
        cfg = get_analysis_config()
        self.subject_id = subject_id
        self.n_students = n_students or cfg["n_simulation_students"]
        self.irt_students = cfg["irt_virtual_students"]
        self.seed = cfg["seed"]
        self.use_cache = cfg["use_cache"] if use_cache is None else use_cache
        self.weights = get_analysis_weights()
        self.irt = irt_model or IRTModel()
        self.kp_mapper = kp_mapper or KnowledgeMapper()
        self.quality = quality_analyzer or QualityAnalyzer()
        self.simulator = simulator or MonteCarloSimulator()
        # 缓存（LRU，有上限防无限增长）
        self._fit_cache: LRUCache = LRUCache(maxsize=256)
        self._kp_cache: LRUCache = LRUCache(maxsize=256)

    # ===================== 主入口 =====================

    def analyze(self, paper: Any) -> Dict[str, Any]:
        """分析单份试卷，返回结构化报告（dict，可 JSON 序列化）。

        线程安全：不修改任何共享可变状态（subject 用局部变量）。
        """
        questions = self._normalize_questions(paper)
        if not questions:
            return self._empty_report(paper)

        # 以试卷自身声明的科目为准（覆盖初始化时的 subject_id，保证线程安全）
        subject = self._paper_subject(paper)

        # 1) IRT 参数（缺失则估计），并重建作答矩阵
        item_params, responses, _thetas = self._ensure_irt(questions, subject)

        # 2) 模拟作答正确率 / 能力分布（复用蒙特卡洛引擎）
        q_scores = [q.get("score", 0.0) for q in questions]
        sim = self.simulator.simulate(
            item_params, q_scores, n_students=self.n_students, subject_id=subject
        )

        # 3) 各维度
        difficulty = self._eval_difficulty(questions, item_params, responses, sim)
        coverage = self._eval_knowledge_coverage(questions, subject)
        type_dist = self._eval_type_distribution(questions, q_scores, subject)
        discrimination = self._eval_discrimination(questions, item_params, responses)
        reliability = self._eval_reliability(responses)
        validity = self._eval_validity(questions, subject)

        dims = {
            "difficulty": difficulty,
            "knowledge_coverage": coverage,
            "type_distribution": type_dist,
            "discrimination": discrimination,
            "reliability": reliability,
            "validity": validity,
        }
        composite = self._composite(dims)
        viz = self._visualization(dims, coverage, type_dist, difficulty)

        metrics = {
            "overall_difficulty": difficulty["overall_difficulty"],
            "knowledge_breadth": coverage["breadth"],
            "type_preset_deviation": type_dist.get("preset_deviation"),
            "mean_discrimination": discrimination["mean_high_low_diff"],
            "mean_irt_a": discrimination["mean_irt_a"],
            "cronbach_alpha": reliability["cronbach_alpha"],
            "split_half_reliability": reliability["split_half"],
            "content_validity_cvr": validity["cvr"],
            "sim_mean": sim.get("mean"),
            "sim_std": sim.get("std"),
            "sim_median": sim.get("median"),
        }

        return {
            "paper_title": self._paper_title(paper),
            "subject": subject,
            "year": self._paper_year(paper),
            "question_count": len(questions),
            "total_score": float(sum(q_scores)),
            "dimensions": dims,
            "composite": composite,
            "visualization": viz,
            "metrics": metrics,
            "simulation": {
                "n_students": sim.get("n_students"),
                "mean": sim.get("mean"),
                "std": sim.get("std"),
                "median": sim.get("median"),
                "score_distribution": sim.get("score_distribution"),
                "segment_rates": sim.get("segment_rates"),
                "percentile_table": sim.get("percentile_table"),
            },
        }

    # ===================== 题目归一化与 IRT =====================

    def _normalize_questions(self, paper: Any) -> List[Dict[str, Any]]:
        """将 ExtractedPaper / dict / 各种 Question 对象规范为统一 dict 列表。"""
        if hasattr(paper, "questions"):
            qs = paper.questions
        elif isinstance(paper, dict):
            qs = paper.get("questions", [])
        else:
            qs = []
        out: List[Dict[str, Any]] = []
        for q in qs:
            if hasattr(q, "__dict__") and not isinstance(q, dict):
                d = {
                    "q_type": getattr(q, "q_type", "solve"),
                    "content": getattr(q, "content", ""),
                    "score": float(getattr(q, "score", 0) or 0),
                    "knowledge_points": list(getattr(q, "knowledge_points", []) or []),
                    "options": getattr(q, "options", []) or [],
                    "answer": getattr(q, "answer", ""),
                    "irt_a": getattr(q, "irt_a", None),
                    "irt_b": getattr(q, "irt_b", None),
                    "irt_c": getattr(q, "irt_c", None),
                }
            else:
                d = {
                    "q_type": q.get("q_type", "solve"),
                    "content": q.get("content", ""),
                    "score": float(q.get("score", 0) or 0),
                    "knowledge_points": list(q.get("knowledge_points", []) or []),
                    "options": q.get("options", []) or [],
                    "answer": q.get("answer", ""),
                    "irt_a": q.get("irt_a"),
                    "irt_b": q.get("irt_b"),
                    "irt_c": q.get("irt_c"),
                }
            out.append(d)
        return out

    def _map_kp(self, content: str, subject: str) -> List[str]:
        """知识点映射（带 LRU 缓存，防止内存泄漏）。"""
        key = (subject, content)
        if self.use_cache:
            cached = self._kp_cache.get(key)
            if cached is not None:
                return cached
        kps = self.kp_mapper.map_question(content or "", normalize_subject(subject))
        if self.use_cache:
            self._kp_cache.put(key, kps)
        return kps

    def _ensure_knowledge(self, questions: List[Dict[str, Any]], subject: str) -> None:
        """为空知识点补映射（就地修改）。"""
        for q in questions:
            kps = q.get("knowledge_points") or []
            if not kps and q.get("content"):
                q["knowledge_points"] = self._map_kp(q["content"], subject)

    def _ensure_irt(self, questions, subject):
        """确保每题有 IRT 参数（a,b,c）与作答矩阵。

        - 若题目已带完整 IRT 参数：直接使用，跳过估计（快路径）。
        - 否则：用虚拟考生生成作答矩阵，逐题 L-BFGS-B 估计 IRT 参数。
        - 始终基于 ICC 重建 response_matrix，供正确率/区分度/信度计算（一致口径）。
        - 缓存 IRT 拟合结果（LRU），避免重复计算。
        """
        n_q = len(questions)
        rng = np.random.default_rng(self.seed)
        thetas = rng.normal(0, 1, self.irt_students)

        have_irt = all(
            q.get("irt_a") is not None and q.get("irt_b") is not None for q in questions
        )
        if have_irt:
            item_params = [
                {"a": float(q["irt_a"]), "b": float(q["irt_b"]),
                 "c": float(q.get("irt_c") or 0.0)}
                for q in questions
            ]
        else:
            # 尝试从缓存读取
            cache_key = (subject, n_q, self.irt_students, self.seed)
            if self.use_cache:
                cached = self._fit_cache.get(cache_key)
                if cached is not None:
                    item_params = cached
                else:
                    item_params = None
                if item_params is not None:
                    resp_rng = np.random.default_rng(self.seed)
                    response_matrix = self._build_response(thetas, item_params, resp_rng)
                    return item_params, response_matrix, thetas

            response_matrix = np.zeros((self.irt_students, n_q), dtype=int)
            for j, q in enumerate(questions):
                q_type = q.get("q_type", "solve")
                if q_type == "choice":
                    p = rng.uniform(0.50, 0.85)
                elif q_type == "fill":
                    p = rng.uniform(0.25, 0.60)
                else:
                    p = rng.uniform(0.10, 0.50)
                ramp = min(j / max(n_q - 1, 1) * 0.3, 0.3)
                p = max(0.05, p - ramp)
                response_matrix[:, j] = rng.binomial(1, p, self.irt_students)
            item_params = self.irt.estimate_all_questions(thetas, response_matrix)
            for j, p in enumerate(item_params):
                questions[j]["irt_a"] = p["a"]
                questions[j]["irt_b"] = p["b"]
                questions[j]["irt_c"] = p["c"]

            # 写入缓存（LRU）
            if self.use_cache:
                self._fit_cache.put(cache_key, item_params)

        resp_rng = np.random.default_rng(self.seed)
        response_matrix = self._build_response(thetas, item_params, resp_rng)
        return item_params, response_matrix, thetas

    @staticmethod
    def _build_response(thetas: np.ndarray, item_params: List[dict],
                        rng: np.random.Generator) -> np.ndarray:
        """基于 IRT 3PL 特征曲线重建作答矩阵（0/1）。"""
        n = len(thetas)
        n_q = len(item_params)
        resp = np.zeros((n, n_q), dtype=int)
        for j, p in enumerate(item_params):
            prob = p["c"] + (1 - p["c"]) * 1.0 / (1.0 + np.exp(-p["a"] * (thetas - p["b"])))
            resp[:, j] = (rng.random(n) < prob).astype(int)
        return resp

    # ===================== 维度 1：难度评估 =====================

    def _eval_difficulty(self, questions, item_params, responses, sim) -> Dict[str, Any]:
        n_q = len(questions)
        per_question = []
        p_corrects = []
        for j in range(n_q):
            p_c = float(np.mean(responses[:, j]))
            p_corrects.append(p_c)
            b = item_params[j].get("b", 0.0)
            tag = "易" if p_c >= 0.7 else ("中" if p_c >= 0.4 else "难")
            per_question.append({
                "q_index": j,
                "q_type": questions[j].get("q_type", "solve"),
                "p_correct": round(p_c, 4),
                "difficulty_coefficient": round(p_c, 4),
                "irt_b": round(float(b), 4),
                "difficulty_tag": tag,
            })
        overall = float(np.mean(p_corrects)) if p_corrects else 0.0
        target = get_analysis_config().get("target_difficulty", 0.65)
        # 难度适宜度：越接近目标值越高分
        appropriateness = max(0.0, 1 - abs(overall - target) / max(target, 1e-6))
        # 难度梯度：题间正确率标准差（适中跨度更好，0.25 视为理想）
        std = float(np.std(p_corrects)) if len(p_corrects) > 1 else 0.0
        gradient_score = min(1.0, std / 0.25)
        score = round(100 * (0.7 * appropriateness + 0.3 * gradient_score), 2)
        level = "易" if overall >= 0.7 else ("中" if overall >= 0.4 else "难")
        conclusion = (
            f"整卷难度系数≈{overall:.2f}（难度水平：{level}），理想目标≈{target:.2f}，"
            f"{'难度适宜' if appropriateness >= 0.8 else '难度偏离理想区间'}；"
            f"题间难度跨度 std={std:.2f}，{'合理' if gradient_score >= 0.6 else '偏小'}。"
        )
        return {
            "score": score,
            "conclusion": conclusion,
            "overall_difficulty": round(overall, 4),
            "difficulty_level": level,
            "target_difficulty": target,
            "gradient_std": round(std, 4),
            "per_question": per_question,
        }

    # ===================== 维度 2：知识点覆盖 =====================

    def _eval_knowledge_coverage(self, questions, subject) -> Dict[str, Any]:
        pool = [code for code, _n, _p, _l in KNOWLEDGE_SEED.get(normalize_subject(subject), [])]
        pool_set = set(pool)
        pool_size = len(pool_set)
        self._ensure_knowledge(questions, subject)

        covered = set()
        freq: Dict[str, int] = {}
        for q in questions:
            for kp in (q.get("knowledge_points") or []):
                covered.add(kp)
                freq[kp] = freq.get(kp, 0) + 1
        covered_in_pool = covered & pool_set
        breadth = len(covered_in_pool) / pool_size if pool_size else 0.0

        # 深度均衡度：频次变异系数越低越均衡
        counts = np.array([freq.get(k, 0) for k in covered_in_pool], dtype=float)
        if len(counts) > 1 and counts.mean() > 0:
            cv = counts.std() / counts.mean()
            depth_balance = max(0.0, 1 - cv)
        else:
            depth_balance = 1.0 if len(counts) > 0 else 0.0

        score = round(100 * (0.6 * breadth + 0.4 * depth_balance), 2)

        dist: Dict[str, int] = {}
        for kp, c in freq.items():
            parent = kp.rsplit(".", 1)[0] if "." in kp else kp
            dist[parent] = dist.get(parent, 0) + c

        conclusion = (
            f"覆盖课标知识点 {len(covered_in_pool)}/{pool_size}（广度 {breadth*100:.0f}%），"
            f"覆盖深度均衡度 {depth_balance*100:.0f}%。"
            f"{'覆盖较全面。' if breadth >= 0.6 else '知识点覆盖广度有待加强。'}"
        )
        return {
            "score": score,
            "conclusion": conclusion,
            "distinct_count": len(covered_in_pool),
            "pool_size": pool_size,
            "breadth": round(breadth, 4),
            "depth_balance": round(depth_balance, 4),
            "distribution": {k: int(v) for k, v in sorted(dist.items())},
            "covered": sorted(covered_in_pool),
            "missing_top": sorted(pool_set - covered_in_pool)[:20],
        }

    # ===================== 维度 3：题型分布 =====================

    def _eval_type_distribution(self, questions, q_scores, subject) -> Dict[str, Any]:
        n = len(questions)
        type_count: Dict[str, int] = {}
        type_score: Dict[str, float] = {}
        for i, q in enumerate(questions):
            t = q.get("q_type", "solve")
            type_count[t] = type_count.get(t, 0) + 1
            type_score[t] = type_score.get(t, 0.0) + q_scores[i]

        total_score = sum(q_scores) or 1.0
        type_ratios = {t: round(c / n, 4) for t, c in type_count.items()}
        score_ratios = {t: round(type_score[t] / total_score, 4) for t in type_score}

        preset = get_question_type_preset(normalize_subject(subject))
        if preset:
            dev = sum(abs(score_ratios.get(t, 0.0) - w) for t, w in preset.items())
            for t in preset:
                if t not in score_ratios:
                    dev += preset[t]
            score = round(max(0.0, 100 * (1 - dev)), 2)
            has_preset = True
        else:
            mixed = sum(1 for t in ("choice", "fill", "solve") if t in type_count)
            score = round(60 + 13 * (mixed - 1), 2) if mixed >= 1 else 40.0
            dev = None
            has_preset = False

        if has_preset:
            conclusion = (
                f"题型题数占比：{type_ratios}；分值占比：{score_ratios}；"
                f"与标准卷预设偏离度 {round(dev, 3)}。"
                f"{'分值分配较合理。' if dev <= 0.2 else '分值分配偏离预设，建议调整。'}"
            )
        else:
            conclusion = (
                f"题型题数占比：{type_ratios}；分值占比：{score_ratios}。"
                f"无标准预设，按题型多样性评分。"
            )
        return {
            "score": score,
            "conclusion": conclusion,
            "type_count": type_count,
            "type_ratios": type_ratios,
            "score_ratios": score_ratios,
            "preset": preset,
            "preset_deviation": round(dev, 4) if dev is not None else None,
        }

    # ===================== 维度 4：区分度 =====================

    def _eval_discrimination(self, questions, item_params, responses) -> Dict[str, Any]:
        n_q = len(questions)
        # 以作答矩阵行（考生）的总分作为能力代理，用于高/低分组排序
        ability = responses.sum(axis=1)
        order = np.argsort(ability)
        n = len(ability)
        low_n = max(1, int(n * 0.27))
        high_n = max(1, int(n * 0.27))
        low_idx = order[:low_n]
        high_idx = order[-high_n:]

        disc_list = []
        weak = []
        for j in range(n_q):
            p_low = float(np.mean(responses[low_idx, j]))
            p_high = float(np.mean(responses[high_idx, j]))
            d = p_high - p_low
            pb = self.quality.point_biserial(ability, responses[:, j])
            a = item_params[j].get("a", 0.0)
            disc_list.append({
                "q_index": j,
                "high_low_diff": round(d, 4),
                "point_biserial": pb,
                "irt_a": round(float(a), 4),
            })
            if d < 0.2 or a < 0.5:
                weak.append(j)

        mean_d = float(np.mean([x["high_low_diff"] for x in disc_list])) if disc_list else 0.0
        mean_a = float(np.mean([x["irt_a"] for x in disc_list])) if disc_list else 0.0
        # 评分：高低组差 >=0.4 为优；IRT a >=1.5 为优（各占 50%）
        score = round(100 * (0.5 * min(1.0, mean_d / 0.4) + 0.5 * min(1.0, mean_a / 1.5)), 2)

        conclusion = (
            f"平均高/低分组通过率差≈{mean_d:.2f}，平均 IRT 区分度 a≈{mean_a:.2f}；"
            f"区分度不足的题目 {len(weak)} 道。"
            f"{'整体区分度良好。' if mean_d >= 0.3 else '区分度偏弱，建议优化。'}"
        )
        return {
            "score": score,
            "conclusion": conclusion,
            "mean_high_low_diff": round(mean_d, 4),
            "mean_irt_a": round(mean_a, 4),
            "weak_items": weak,
            "per_question": disc_list,
        }

    # ===================== 维度 5：信度 =====================

    def _eval_reliability(self, responses) -> Dict[str, Any]:
        n_q = responses.shape[1]
        if n_q < 2:
            return {
                "score": 0.0,
                "conclusion": "题目数不足，无法评估信度。",
                "cronbach_alpha": 0.0,
                "split_half": 0.0,
            }
        alpha = self.quality.cronbach_alpha(responses)
        # 分半信度（奇偶分半 + Spearman-Brown 校正）
        half = n_q // 2
        if half >= 1:
            odd = responses[:, 0::2].sum(axis=1)
            even = responses[:, 1::2].sum(axis=1)
            if odd.std() > 0 and even.std() > 0 and np.std(odd + even) > 0:
                r = float(np.corrcoef(odd, even)[0, 1])
                split = (2 * r) / (1 + r) if (not np.isnan(r) and abs(r) < 1) else 1.0
            else:
                split = 0.0
        else:
            split = 0.0

        score = round(100 * min(1.0, max(0.0, (alpha - 0.3) / 0.6)), 2)
        if alpha >= 0.8:
            verdict = "信度优秀。"
        elif alpha >= 0.6:
            verdict = "信度可接受。"
        else:
            verdict = "信度偏低，题量或同质性不足。"
        conclusion = (
            f"Cronbach α≈{alpha:.2f}，分半信度(校正)≈{split:.2f}。{verdict}"
        )
        return {
            "score": score,
            "conclusion": conclusion,
            "cronbach_alpha": alpha,
            "split_half": round(float(split), 4),
        }

    # ===================== 维度 6：效度 =====================

    def _eval_validity(self, questions, subject) -> Dict[str, Any]:
        pool = [code for code, _n, _p, _l in KNOWLEDGE_SEED.get(normalize_subject(subject), [])]
        pool_set = set(pool)
        pool_size = len(pool_set)
        self._ensure_knowledge(questions, subject)

        covered = set()
        for q in questions:
            for kp in (q.get("knowledge_points") or []):
                covered.add(kp)
        covered_in_pool = covered & pool_set
        cvr = len(covered_in_pool) / pool_size if pool_size else 0.0
        score = round(100 * cvr, 2)
        if cvr >= 0.6:
            verdict = "内容效度良好。"
        else:
            verdict = "内容效度不足，建议补充缺失知识点。"
        conclusion = (
            f"内容效度（对照 {subject} 知识点大纲覆盖）CVR≈{cvr:.2f}："
            f"覆盖 {len(covered_in_pool)}/{pool_size} 个大纲知识点。"
            f"效度依据：试卷内容与课标知识点大纲的匹配程度（覆盖率越高，内容效度越高）。"
            f"{verdict}"
        )
        return {
            "score": score,
            "conclusion": conclusion,
            "cvr": round(cvr, 4),
            "covered_outline": len(covered_in_pool),
            "outline_size": pool_size,
            "missing_outline": sorted(pool_set - covered_in_pool)[:20],
            "basis": "对照知识点大纲覆盖率（CVR / content validity index 近似）",
        }

    # ===================== 综合评分 =====================

    def _composite(self, dims: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        score = 0.0
        for name, w in self.weights.items():
            score += dims[name]["score"] * w
        score = round(score, 2)
        if score >= 85:
            grade = "优秀"
        elif score >= 70:
            grade = "良好"
        elif score >= 60:
            grade = "合格"
        else:
            grade = "待改进"
        strongest = max(self.weights.keys(), key=lambda k: dims[k]["score"])
        weakest = min(self.weights.keys(), key=lambda k: dims[k]["score"])
        conclusion = (
            f"综合质量分 {score}（{grade}）。最强维度：{strongest}；"
            f"最弱维度：{weakest}（{dims[weakest]['score']}分），"
            f"建议：{self._suggest(weakest)}"
        )
        return {
            "score": score,
            "grade": grade,
            "conclusion": conclusion,
            "weights": dict(self.weights),
        }

    @staticmethod
    def _suggest(dim: str) -> str:
        tips = {
            "difficulty": "调整题目难度梯度，使整卷难度接近目标值。",
            "knowledge_coverage": "补充缺失课标知识点，提升覆盖广度与深度。",
            "type_distribution": "调整各题型分值占比，贴近标准卷结构。",
            "discrimination": "替换区分度不足的题目，增强高/低分组差异。",
            "reliability": "增加同质题目数量，提升测量一致性。",
            "validity": "强化与课标大纲的对应，提升内容效度。",
        }
        return tips.get(dim, "持续优化试卷质量。")

    # ===================== 可视化数据 =====================

    def _visualization(self, dims, coverage, type_dist, difficulty) -> Dict[str, Any]:
        radar = [{"dimension": k, "score": round(dims[k]["score"], 2)}
                 for k in ("difficulty", "knowledge_coverage", "type_distribution",
                           "discrimination", "reliability", "validity")]
        type_bar = [{"type": t, "ratio": r} for t, r in type_dist["type_ratios"].items()]
        kp_bar = [{"code": k, "frequency": v}
                  for k, v in sorted(coverage["distribution"].items(),
                                     key=lambda x: -x[1])[:15]]
        diff_curve = [{"q_index": d["q_index"], "difficulty": d["difficulty_coefficient"]}
                      for d in difficulty["per_question"]]
        return {
            "radar": radar,
            "type_distribution_bar": type_bar,
            "knowledge_bar": kp_bar,
            "difficulty_curve": diff_curve,
        }

    # ===================== 工具 =====================

    @staticmethod
    def _paper_title(paper) -> str:
        if hasattr(paper, "title"):
            return paper.title
        if isinstance(paper, dict):
            return paper.get("title", "")
        return ""

    @staticmethod
    def _paper_subject(paper) -> str:
        if hasattr(paper, "subject"):
            return paper.subject
        if isinstance(paper, dict):
            return paper.get("subject", "math")
        return "math"

    @staticmethod
    def _paper_year(paper) -> int:
        if hasattr(paper, "year"):
            return paper.year
        if isinstance(paper, dict):
            return paper.get("year", 2026)
        return 2026

    def _empty_report(self, paper) -> Dict[str, Any]:
        dims = {k: {"score": 0, "conclusion": "无题目数据"}
                for k in ("difficulty", "knowledge_coverage", "type_distribution",
                          "discrimination", "reliability", "validity")}
        return {
            "paper_title": self._paper_title(paper),
            "subject": self._paper_subject(paper),
            "year": self._paper_year(paper),
            "question_count": 0,
            "total_score": 0.0,
            "dimensions": dims,
            "composite": {"score": 0, "grade": "待改进",
                          "conclusion": "试卷无题目，无法评估", "weights": dict(self.weights)},
            "visualization": {"radar": [], "type_distribution_bar": [],
                              "knowledge_bar": [], "difficulty_curve": []},
            "metrics": {},
            "simulation": {},
        }


# ===================== 模块级便捷入口 =====================

def analyze_paper(paper: Any, subject_id: str = "math",
                  n_students: Optional[int] = None) -> Dict[str, Any]:
    """便捷入口：单卷分析。"""
    analyzer = PaperAnalyzer(subject_id=subject_id, n_students=n_students)
    return analyzer.analyze(paper)


async def analyze_papers_batch(papers: List[Any], max_workers: Optional[int] = None,
                               subject_id: str = "math",
                               n_students: Optional[int] = None,
                               analyzer: Optional[PaperAnalyzer] = None
                               ) -> List[Dict[str, Any]]:
    """批量并行分析：asyncio + 线程池（CPU 密集的 numpy/IRT 放线程池）。

    返回与 papers 等长的报告列表；单卷异常时返回带 error 的报告（不中断整体）。
    共享同一 analyzer 实例以复用 IRT/知识点缓存（线程安全）。

    Args:
        papers: 试卷列表（ExtractedPaper / dict）。
        max_workers: 并行 worker 数（默认取 ANALYSIS_CONFIG.max_workers）。
        subject_id: 默认科目（每卷会以其自身声明科目覆盖）。
        n_students: 模拟考生数（覆盖配置）。
        analyzer: 可选共享分析器实例；不传则内部新建。
    Returns:
        报告列表（与输入顺序一致）。
    """
    cfg = get_analysis_config()
    max_workers = max_workers or cfg["max_workers"]
    if analyzer is None:
        analyzer = PaperAnalyzer(subject_id=subject_id, n_students=n_students)

    n = len(papers)
    if n == 0:
        return []
    if n == 1:
        try:
            return [analyzer.analyze(papers[0])]
        except Exception as exc:  # noqa: BLE001
            logger.error("批量分析单卷失败: %s", exc)
            return [{"error": str(exc)}]

    def _run(p):
        try:
            return analyzer.analyze(p)
        except Exception as exc:  # noqa: BLE001
            logger.error("批量分析单卷失败: %s", exc)
            return {"error": str(exc), "paper_title": getattr(p, "title", None)}

    loop = asyncio.get_event_loop()
    # 默认线程池：numpy 运算释放 GIL，可获得近似线性加速；
    # ProcessPoolExecutor 亦可（executor="process"），但需保证对象可 pickle。
    if cfg.get("executor") == "process":
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            tasks = [loop.run_in_executor(pool, _run, p) for p in papers]
            return list(await asyncio.gather(*tasks, return_exceptions=True))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        tasks = [loop.run_in_executor(pool, _run, p) for p in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    out: List[Dict[str, Any]] = []
    for r in results:
        if isinstance(r, Exception):
            out.append({"error": str(r)})
        else:
            out.append(r)
    return out


__all__ = ["PaperAnalyzer", "analyze_paper", "analyze_papers_batch"]
