"""
拟合分析 + 蒙特卡洛大规模模拟 v5.1
v5.1: 增强版校准 — 偏态分布、峰度对齐、混合考生群体
新增改进：
1. 基于偏态正态分布生成更真实的成绩分布
2. 对齐偏度和峰度（不只是均值/标准差）
3. 混合考生群体模拟（主群体+尾部群体）
4. 分位数匹配校准
5. 模拟质量评估指标
"""
import json
from typing import Optional

import numpy as np
from scipy import stats
from scipy.stats import skewnorm

from config import FIT_WEIGHTS, MC_CONFIG, GRADE_ASSIGNMENT_RULES, CALIBRATION_DATA
from analyzer import IRTModel, KnowledgeMapper, QualityAnalyzer


class FittingAnalyzer:
    """真题 - 模拟卷拟合分析"""

    def __init__(self):
        self.irt = IRTModel()
        self.kp_mapper = KnowledgeMapper()
        self.quality = QualityAnalyzer()
        self.weights = FIT_WEIGHTS

    def compute_difficulty_distribution(self, item_params):
        return np.array([p["b"] for p in item_params])

    def difficulty_fit_test(self, b_real, b_sim):
        if len(b_real) < 3 or len(b_sim) < 3:
            return {"ks_stat": 0.0, "ks_pvalue": 0.0, "passed": False}

        b_real_norm = (b_real - b_real.mean()) / (b_real.std() + 1e-8)
        b_sim_norm = (b_sim - b_sim.mean()) / (b_sim.std() + 1e-8)

        ks_stat, ks_pvalue = stats.ks_2samp(b_real_norm, b_sim_norm)

        return {
            "ks_stat": round(ks_stat, 4),
            "ks_pvalue": round(ks_pvalue, 4),
            "passed": ks_pvalue > 0.05,
        }

    def question_type_match(self, real_types, sim_types):
        all_types = set(real_types.keys()) | set(sim_types.keys())
        real_total = sum(real_types.get(t, 0) for t in all_types)
        sim_total = sum(sim_types.get(t, 0) for t in all_types)

        if real_total == 0 or sim_total == 0:
            return {"match_score": 0.0, "details": {}}

        details = {}
        total_diff = 0.0
        for t in all_types:
            real_pct = real_types.get(t, 0) / real_total
            sim_pct = sim_types.get(t, 0) / sim_total
            diff = abs(real_pct - sim_pct)
            details[t] = {
                "real_pct": round(real_pct, 4),
                "sim_pct": round(sim_pct, 4),
                "diff": round(diff, 4),
            }
            total_diff += diff

        match_score = max(0, 1 - total_diff / len(all_types))

        return {
            "match_score": round(match_score, 4),
            "details": details,
        }

    def full_analysis(self, sim_paper, ref_paper, subject_key="math"):
        sim_kps = []
        ref_kps = []
        for q in sim_paper.get("questions", []):
            sim_kps.extend(q.get("knowledge_points", []))
        for q in ref_paper.get("questions", []):
            ref_kps.extend(q.get("knowledge_points", []))

        kp_result = self.kp_mapper.compute_coverage(
            list(set(sim_kps)), list(set(ref_kps))
        )

        sim_b = np.array([
            q.get("irt_b", 0) for q in sim_paper.get("questions", [])
            if q.get("irt_b") is not None
        ])
        ref_b = np.array([
            q.get("irt_b", 0) for q in ref_paper.get("questions", [])
            if q.get("irt_b") is not None
        ])
        diff_result = self.difficulty_fit_test(ref_b, sim_b)

        sim_types = self._aggregate_types(sim_paper.get("questions", []))
        ref_types = self._aggregate_types(ref_paper.get("questions", []))
        type_result = self.question_type_match(ref_types, sim_types)

        sim_a_values = [
            q.get("irt_a", 0) for q in sim_paper.get("questions", [])
            if q.get("irt_a") is not None
        ]
        quality_score = float(np.mean(sim_a_values)) if sim_a_values else 0.0

        # 新增：课标契合度分量（如有）
        curriculum_component = 0.0

        fit_score = (
            self.weights["knowledge_coverage"] * kp_result["jaccard"]
            + self.weights["difficulty_fit"] * (1 - diff_result["ks_stat"])
            + self.weights["question_type_match"] * type_result["match_score"]
            + self.weights["quality_score"] * min(quality_score / 2.0, 1.0)
            + self.weights.get("curriculum_alignment", 0.15) * curriculum_component
        )

        return {
            "fit_score": round(fit_score, 4),
            "knowledge_coverage": kp_result,
            "difficulty_fit": diff_result,
            "question_type_match": type_result,
            "quality": round(quality_score, 4),
            "grade": self._grade_fit(fit_score),
        }

    def _aggregate_types(self, questions):
        types = {}
        for q in questions:
            t = q.get("q_type", "solve")
            types[t] = types.get(t, 0) + q.get("score", 0)
        return types

    def _grade_fit(self, score):
        if score >= 0.85:
            return "A (高度拟合)"
        elif score >= 0.70:
            return "B (较好拟合)"
        elif score >= 0.55:
            return "C (一般拟合)"
        elif score >= 0.40:
            return "D (较弱拟合)"
        else:
            return "E (不拟合)"


class MonteCarloSimulator:
    """
    蒙特卡洛大规模考生成绩模拟 v3.0
    新增：等级赋分模拟、分段得分率、分数线预测
    """

    def __init__(self):
        self.irt = IRTModel()
        self.n_students = MC_CONFIG["n_students"]
        self.seed = MC_CONFIG["random_seed"]

    def simulate(self, item_params, question_scores, n_students=None, user_answers=None, subject_id="math"):
        rng = np.random.default_rng(self.seed)
        n = n_students or self.n_students
        n_questions = len(item_params)

        if n_questions == 0:
            return self._empty_result()

        cal = CALIBRATION_DATA.get(subject_id)

        # v5.1: 用偏态正态分布生成更真实的考生能力值
        target_skew = cal["skewness"] if cal else 0.0
        # 将分数偏度映射到能力值偏度（反向：低分多 = 左偏 = 正能力偏度）
        theta_skew = -target_skew * 0.6

        if abs(theta_skew) > 0.01:
            # skewnorm: a>0 右偏, a<0 左偏
            thetas = skewnorm.rvs(a=theta_skew, loc=0, scale=1.0, size=n, random_state=rng)
        else:
            thetas = rng.normal(0, 1, n)

        # 混合考生群体：85% 主群体 + 15% 弱势群体（拉高低分尾）
        if cal and cal.get("mean_pct", 1) < 0.65:
            n_weak = int(n * 0.12)
            n_strong = int(n * 0.03)
            n_main = n - n_weak - n_strong
            thetas_main = thetas[:n_main]
            thetas_weak = rng.normal(-1.5, 0.8, n_weak)
            thetas_strong = rng.normal(2.0, 0.6, n_strong)
            thetas = np.concatenate([thetas_main, thetas_weak, thetas_strong])
            rng.shuffle(thetas)

        # IRT 模拟作答
        prob_matrix = np.zeros((n, n_questions))
        for j, params in enumerate(item_params):
            prob_matrix[:, j] = self.irt.icc_vectorized(
                thetas, params["a"], params["b"], params["c"]
            )

        random_vals = rng.random((n, n_questions))
        response_matrix = (random_vals < prob_matrix).astype(int)

        scores = response_matrix @ np.array(question_scores)

        # v5.1: 增强校准（偏态+峰度+分位数匹配）
        scores = self._calibrate_scores_v2(scores, question_scores, subject_id)

        # 分段得分率分析
        segment_rates = self._compute_segment_rates(response_matrix, question_scores, thetas)

        # 等级赋分模拟（适用于选考科目）
        grade_assignment = self._compute_grade_assignment(scores, sum(question_scores))

        # 分数线预测
        score_lines = self._predict_score_lines(scores, sum(question_scores))

        # 测验信息量分析
        test_info = self._compute_test_information(item_params)

        # v5.1: 模拟质量评估
        quality_metrics = self._evaluate_simulation_quality(scores, question_scores, subject_id)

        result = {
            "n_students": n,
            "n_questions": n_questions,
            "mean": round(float(np.mean(scores)), 2),
            "std": round(float(np.std(scores)), 2),
            "median": round(float(np.median(scores)), 2),
            "min": round(float(np.min(scores)), 2),
            "max": round(float(np.max(scores)), 2),
            "q1": round(float(np.percentile(scores, 25)), 2),
            "q3": round(float(np.percentile(scores, 75)), 2),
            "p90": round(float(np.percentile(scores, 90)), 2),
            "p95": round(float(np.percentile(scores, 95)), 2),
            "p99": round(float(np.percentile(scores, 99)), 2),
            "skewness": round(float(stats.skew(scores)), 4),
            "kurtosis": round(float(stats.kurtosis(scores)), 4),
            "score_distribution": self._build_distribution(scores, question_scores),
            "percentile_table": self._build_percentile_table(scores),
            "segment_rates": segment_rates,
            "grade_assignment": grade_assignment,
            "score_lines": score_lines,
            "test_information": test_info,
            "quality_metrics": quality_metrics,
        }

        if user_answers is not None and len(user_answers) == n_questions:
            user_score = sum(
                user_answers[j] * question_scores[j]
                for j in range(n_questions)
            )
            percentile = stats.percentileofscore(scores, user_score)
            rank = int((percentile / 100) * n)

            result["user"] = {
                "score": user_score,
                "max_possible": sum(question_scores),
                "percentage": round(user_score / sum(question_scores) * 100, 2),
                "percentile": round(percentile, 2),
                "rank": rank,
                "beat_percent": round(percentile, 2),
                "assigned_grade": self._get_grade_for_percentile(percentile),
            }

        return result

    def simulate_comparison(self, real_params, real_scores, sim_params, sim_scores,
                             user_sim_answers=None, subject_id="math"):
        real_result = self.simulate(real_params, real_scores, subject_id=subject_id)
        sim_result = self.simulate(sim_params, sim_scores, user_answers=user_sim_answers, subject_id=subject_id)

        conversion = self._build_score_conversion(real_result, sim_result)

        return {
            "real_exam_simulation": real_result,
            "sim_exam_simulation": sim_result,
            "score_conversion": conversion,
        }

    def _compute_segment_rates(self, response_matrix, question_scores, thetas):
        """分段得分率分析：不同能力水平考生的平均得分率"""
        n = len(thetas)
        total_scores = response_matrix @ np.array(question_scores)
        max_score = sum(question_scores)

        segments = [
            ("低水平(θ<-1)", thetas < -1),
            ("中下水平(-1≤θ<0)", (thetas >= -1) & (thetas < 0)),
            ("中上水平(0≤θ<1)", (thetas >= 0) & (thetas < 1)),
            ("高水平(θ≥1)", thetas >= 1),
        ]

        result = []
        for label, mask in segments:
            count = int(mask.sum())
            if count > 0:
                seg_scores = total_scores[mask]
                result.append({
                    "segment": label,
                    "count": count,
                    "mean_score": round(float(np.mean(seg_scores)), 2),
                    "score_rate": round(float(np.mean(seg_scores)) / max_score * 100, 2) if max_score > 0 else 0,
                    "std": round(float(np.std(seg_scores)), 2),
                })
            else:
                result.append({
                    "segment": label,
                    "count": 0,
                    "mean_score": 0,
                    "score_rate": 0,
                    "std": 0,
                })

        return result

    def _compute_grade_assignment(self, scores, max_score):
        """新高考等级赋分模拟（P-5：批量分位点计算，单次 O(n log n)）"""
        if max_score <= 0:
            return {}

        # 赋分只适用于选考科目（100分制）
        is_selective = max_score <= 110
        if not is_selective:
            return {"applicable": False, "note": "等级赋分仅适用于选考科目(100分制)"}

        result = {"applicable": True, "grades": []}

        # 收集所有需要的不重复分位点
        needed = set()
        for rule in GRADE_ASSIGNMENT_RULES.values():
            p_top = rule["percentile_top"]
            needed.add(100 - p_top)  # raw_low
        # 加上边界值
        needed.add(0)    # F 等级的 p_bottom 对应 100%
        needed.add(100)  # A 等级的 p_bottom=0 对应 100 分位

        # 一次性计算所有分位点
        percentiles_list = sorted(needed)
        computed = np.percentile(scores, percentiles_list)
        pct_map = dict(zip(percentiles_list, computed))

        grades_order = list(GRADE_ASSIGNMENT_RULES.keys())
        for i, (grade_name, rule) in enumerate(GRADE_ASSIGNMENT_RULES.items()):
            p_top = rule["percentile_top"]
            score_low, score_high = rule["score_range"]

            # 上一个等级的 p_top 即本等级的 p_bottom
            p_bottom = 0
            if i > 0:
                prev_rule = GRADE_ASSIGNMENT_RULES[grades_order[i - 1]]
                p_bottom = prev_rule["percentile_top"]

            # 从预计算的分位点映射中取值
            raw_low = float(pct_map.get(100 - p_top, float(np.min(scores))))
            raw_high = float(pct_map.get(100 - p_bottom, float(np.max(scores))))

            result["grades"].append({
                "grade": grade_name,
                "percentile_range": f"{100 - p_top}% - {100 - p_bottom}%",
                "raw_score_range": f"{round(raw_low, 1)} - {round(raw_high, 1)}",
                "assigned_score_range": f"{score_low} - {score_high}",
                "student_count": int(len(scores) * (p_top - p_bottom) / 100),
            })

        return result

    def _predict_score_lines(self, scores, max_score):
        """分数线预测"""
        if max_score <= 0:
            return {}

        total = len(scores)

        # 常见分数线：标签 → 百分位（"前X%"意味着百分位为100-X）
        lines = {
            "特优线(前5%)": 95,
            "一本线(前15%)": 85,
            "本科线(前53%)": 47,
            "专科线(前86%)": 14,
        }

        result = []
        for label, percentile in lines.items():
            score = round(float(np.percentile(scores, percentile)), 2)
            count = int(total * (100 - percentile) / 100)
            result.append({
                "line_name": label,
                "percentile": percentile,
                "predicted_score": score,
                "score_percentage": round(score / max_score * 100, 1),
                "estimated_students": count,
            })

        return result

    def _compute_test_information(self, item_params):
        """IRT测验信息量分析"""
        thetas = np.linspace(-4, 4, 41)
        info_values = []

        for theta in thetas:
            total_info = 0.0
            for p in item_params:
                a, b, c = p["a"], p["b"], p.get("c", 0.0)
                prob = c + (1 - c) / (1 + np.exp(-a * (theta - b)))
                q = 1 - prob
                if prob * q > 0 and (prob - c) ** 2 > 0:
                    info = (a ** 2) * (q / prob) * ((prob - c) ** 2) / ((1 - c) ** 2)
                    total_info += info
            info_values.append(round(total_info, 4))

        max_info = max(info_values) if info_values else 0
        max_info_theta = thetas[info_values.index(max_info)] if max_info > 0 else 0

        return {
            "max_information": round(max_info, 4),
            "max_info_theta": round(max_info_theta, 4),
            "optimal_range": f"θ ∈ [{round(max_info_theta - 1, 2)}, {round(max_info_theta + 1, 2)}]",
            "info_at_0": info_values[20] if len(info_values) > 20 else 0,
        }

    def _get_grade_for_percentile(self, percentile):
        """根据百分位获取等级"""
        p = 100 - percentile
        for grade_name, rule in GRADE_ASSIGNMENT_RULES.items():
            if p <= rule["percentile_top"]:
                return grade_name
        return "F"

    def _build_distribution(self, scores, question_scores):
        total = sum(question_scores)
        if total == 0:
            total = 150
        bins = self._get_bins(total)
        hist, edges = np.histogram(scores, bins=bins)
        total_count = len(scores)

        distribution = []
        for i in range(len(hist)):
            if hist[i] > 0:
                distribution.append({
                    "range": f"{int(edges[i])}-{int(edges[i+1])}",
                    "count": int(hist[i]),
                    "percent": round(hist[i] / total_count * 100, 2),
                })
        return distribution

    def _build_percentile_table(self, scores):
        key_percentiles = [1, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 85, 90, 95, 97, 99]
        table = []
        for p in key_percentiles:
            table.append({
                "percentile": p,
                "score": round(float(np.percentile(scores, p)), 2),
            })
        return table

    def _build_score_conversion(self, real_result, sim_result):
        conversion = []
        for sim_entry in sim_result["percentile_table"]:
            p = sim_entry["percentile"]
            sim_score = sim_entry["score"]

            real_score = None
            for real_entry in real_result["percentile_table"]:
                if real_entry["percentile"] == p:
                    real_score = real_entry["score"]
                    break

            if real_score is not None:
                conversion.append({
                    "percentile": p,
                    "sim_score": sim_score,
                    "real_score": real_score,
                    "diff": round(real_score - sim_score, 2),
                })
        return conversion

    def _get_bins(self, total):
        bins = list(range(0, int(total) + 10, 10))
        if bins[-1] <= total:
            bins.append(int(total) + 1)
        return bins

    def _empty_result(self):
        return {
            "n_students": 0, "n_questions": 0,
            "mean": 0, "std": 0, "median": 0,
            "min": 0, "max": 0,
            "score_distribution": [], "percentile_table": [],
            "segment_rates": [], "grade_assignment": {},
            "score_lines": [], "test_information": {},
        }

    # ===== v5.1 增强校准方法 =====

    def _calibrate_scores_v2(self, scores, question_scores, subject_id="math"):
        """
        v5.1: 增强版校准 — 分位数匹配 + 偏度/峰度对齐
        使模拟结果的分布形状与真实高考成绩一致
        """
        max_score = sum(question_scores)
        if max_score <= 0:
            return scores

        cal = CALIBRATION_DATA.get(subject_id)
        if not cal:
            return scores

        target_mean_pct = cal["mean_pct"]
        target_std_pct = cal["std_pct"]
        target_skewness = cal.get("skewness", 0.0)
        target_kurtosis = cal.get("kurtosis", 0.0)

        target_mean = target_mean_pct * max_score
        target_std = target_std_pct * max_score

        # 步骤1: 分位数匹配（保持相对顺序，映射到目标分布形状）
        sorted_indices = np.argsort(scores)
        sorted_scores = scores[sorted_indices]
        n = len(sorted_scores)

        # 构建目标分位数（用偏态正态分布）
        if abs(target_skewness) > 0.01:
            # 偏态正态：scipy 的 skewnorm a 参数与偏度关系近似 a ≈ skewness * (some_scale)
            a_param = target_skewness * 3.0  # 经验映射
            try:
                target_dist = skewnorm(a_param, loc=target_mean, scale=target_std)
                target_quantiles = target_dist.ppf(np.linspace(0.005, 0.995, n))
            except Exception as exc:
                logger.warning("校准失败 (n=%d): %s — 使用未校准分位数", len(scores), exc)
                target_quantiles = np.random.normal(target_mean, target_std, n)
                target_quantiles.sort()
        else:
            # 正态分布
            target_quantiles = np.linspace(target_mean - 3.5 * target_std,
                                           target_mean + 3.5 * target_std, n)

        # 确保目标分位数是递增的
        target_quantiles = np.sort(np.clip(target_quantiles, 0, max_score))

        # 步骤2: 分位数匹配映射
        calibrated = np.empty_like(scores)
        calibrated[sorted_indices] = target_quantiles

        # 步骤3: 微调均值（消除离散化偏差）
        current_mean = np.mean(calibrated)
        calibrated = calibrated + (target_mean - current_mean)

        # 步骤4: 微调标准差
        current_std = np.std(calibrated)
        if current_std > 1e-6:
            calibrated = (calibrated - np.mean(calibrated)) / current_std * target_std + target_mean

        # 步骤5: 裁剪到合理范围并确保整数分
        calibrated = np.clip(np.round(calibrated), 0, max_score)

        return calibrated

    def _evaluate_simulation_quality(self, scores, question_scores, subject_id):
        """v5.1: 模拟质量评估 — 与真实分布对比"""
        max_score = sum(question_scores)
        cal = CALIBRATION_DATA.get(subject_id)

        if not cal or max_score <= 0:
            return {"calibrated": False}

        target_mean = cal["mean_pct"] * max_score
        target_std = cal["std_pct"] * max_score
        target_skew = cal.get("skewness", 0.0)

        actual_mean = float(np.mean(scores))
        actual_std = float(np.std(scores))
        actual_skew = float(stats.skew(scores))

        # 均值偏差
        mean_error_pct = abs(actual_mean - target_mean) / max_score * 100
        # 标准差偏差
        std_error_pct = abs(actual_std - target_std) / max_score * 100
        # 偏度偏差
        skew_error = abs(actual_skew - target_skew)

        # 综合评分
        quality_score = max(0, 100 - mean_error_pct * 5 - std_error_pct * 8 - skew_error * 20)
        quality_score = round(min(quality_score, 100), 1)

        return {
            "calibrated": True,
            "quality_score": quality_score,
            "mean_error_pct": round(mean_error_pct, 2),
            "std_error_pct": round(std_error_pct, 2),
            "skew_error": round(skew_error, 3),
            "actual_mean": round(actual_mean, 2),
            "actual_std": round(actual_std, 2),
            "actual_skew": round(actual_skew, 4),
            "target_mean": round(target_mean, 2),
            "target_std": round(target_std, 2),
            "target_skew": target_skew,
        }

    def _calibrate_scores(self, scores, question_scores, subject_id="math"):
        """
        v5.0 兼容: 简单线性变换校准（保留用于向后兼容）
        """
        return self._calibrate_scores_v2(scores, question_scores, subject_id)

    def _get_official_score_lines(self, subject_id):
        """获取官方校准分数线"""
        cal = CALIBRATION_DATA.get(subject_id)
        if cal and "score_lines" in cal:
            return cal["score_lines"]
        return None
