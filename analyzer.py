"""
IRT 项目反应理论分析引擎 + 新课标知识映射
"""
import json
import math
import re
from typing import Optional

import numpy as np
from scipy import optimize, stats
from scipy.special import expit

from config import IRT_CONFIG


class IRTModel:
    """
    3PL (三参数 Logistic) IRT 模型

    P(theta) = c + (1 - c) * logistic(a * (theta - b))

    theta: 考生能力值
    a: 题目区分度 (discrimination)
    b: 题目难度 (difficulty)
    c: 猜测系数 (guessing)
    """

    def __init__(self):
        self.theta_range = IRT_CONFIG["theta_range"]
        self.quad_points = IRT_CONFIG["quad_points"]
        self.thetas = np.linspace(
            self.theta_range[0], self.theta_range[1], self.quad_points
        )

    def icc(self, theta, a, b, c=0.0):
        """题目特征曲线 (Item Characteristic Curve)"""
        return c + (1 - c) * expit(a * (theta - b))

    def icc_vectorized(self, thetas, a, b, c=0.0):
        """向量化 ICC"""
        return c + (1 - c) * expit(a * (thetas - b))

    def log_likelihood(self, params, thetas, responses):
        """对数似然函数"""
        a, b, c = params
        probs = self.icc_vectorized(thetas, a, b, c)
        probs = np.clip(probs, 1e-10, 1 - 1e-10)
        ll = np.sum(responses * np.log(probs) + (1 - responses) * np.log(1 - probs))
        return -ll  # 返回负对数似然用于最小化

    def estimate_parameters(self, thetas, responses):
        """
        估计单个题目的 IRT 参数 (a, b, c)
        thetas: 考生能力值数组
        responses: 考生作答结果 (0/1)
        """
        # 计算初始值
        p_correct = float(np.mean(responses))
        if p_correct < 0.05:
            p_correct = 0.05
        if p_correct > 0.95:
            p_correct = 0.95

        # 初始 b ≈ 对应 p_correct 的 theta
        b_init = -math.log((1 - p_correct) / p_correct)
        a_init = 1.0
        c_init = max(0.01, 1.0 / max(int(responses.sum()), 1))

        bounds = [
            (0.3, 3.0),      # a: 区分度
            (-4.0, 4.0),    # b: 难度
            (0.0, 0.35),    # c: 猜测系数
        ]

        try:
            result = optimize.minimize(
                self.log_likelihood,
                x0=[a_init, b_init, c_init],
                args=(thetas, responses),
                method="L-BFGS-B",
                bounds=bounds,
            )
            a, b, c = result.x
            # 验证合理性
            if not (0.3 <= a <= 3.0 and -4.0 <= b <= 4.0 and 0.0 <= c <= 0.35):
                raise ValueError("参数超出合理范围")
            return {"a": round(a, 4), "b": round(b, 4), "c": round(c, 4)}
        except Exception:
            return {"a": round(a_init, 4), "b": round(b_init, 4), "c": round(c_init, 4)}

    def estimate_all_questions(
        self, thetas, response_matrix
    ):
        """
        估计所有题目的 IRT 参数
        response_matrix: shape (n_students, n_questions), values 0/1
        """
        n_questions = response_matrix.shape[1]
        params_list = []
        for j in range(n_questions):
            responses = response_matrix[:, j]
            params = self.estimate_parameters(thetas, responses)
            params["question_index"] = j
            params_list.append(params)
        return params_list

    def estimate_ability(self, response_vector, item_params):
        """
        估计单个考生的能力值 theta (EAP 估计)
        """
        thetas = self.thetas
        prior = stats.norm.pdf(thetas)  # 标准正态先验

        likelihood = np.ones_like(thetas)
        for params in item_params:
            likelihood *= np.where(
                response_vector[params["question_index"]] == 1,
                self.icc_vectorized(thetas, params["a"], params["b"], params["c"]),
                1 - self.icc_vectorized(thetas, params["a"], params["b"], params["c"]),
            )

        posterior = likelihood * prior
        total = np.sum(posterior)
        if total > 0:
            eap = np.sum(thetas * posterior) / total
        else:
            eap = 0.0

        return round(eap, 4)

    def information_function(self, theta, a, b, c=0.0):
        """题目信息函数"""
        p = self.icc(theta, a, b, c)
        q = 1 - p
        if p * q * ((p - c) ** 2) == 0:
            return 0.0
        return (a ** 2) * (q / p) * ((p - c) ** 2) / ((1 - c) ** 2)

    def test_information(self, theta, item_params):
        """测验信息函数（所有题目信息函数之和）"""
        total = 0.0
        for p in item_params:
            total += self.information_function(theta, p["a"], p["b"], p["c"])
        return total

    def standard_error(self, theta, item_params):
        """测量标准误"""
        info = self.test_information(theta, item_params)
        if info > 0:
            return round(1.0 / math.sqrt(info), 4)
        return float("inf")


class KnowledgeMapper:
    """
    新课标知识点映射引擎
    将试题内容映射到《普通高中课程方案和课程标准》知识图谱
    """

    # 科目关键词映射
    SUBJECT_KEYWORDS = {
        "math": {
            "导数": ["2.3.1", "2.3.2", "2.3.3"],
            "函数": ["2.2.1", "2.2.2", "2.2.3"],
            "三角": ["2.4.1", "2.4.2", "2.4.3"],
            "数列": ["2.5.1", "2.5.2", "2.5.3"],
            "立体几何": ["2.7.1", "2.7.2", "2.7.3"],
            "圆锥曲线": ["2.8.2"],
            "概率": ["2.9.1", "2.9.4"],
            "统计": ["2.9.2"],
            "向量": ["2.10.1"],
            "复数": ["2.10.2"],
            "不等式": ["2.6.1", "2.6.2"],
            "集合": ["2.1.1"],
            "充要": ["2.1.2"],
            "极限": ["2.3.3"],
            "积分": ["2.3.3"],
            "椭圆": ["2.8.2"],
            "抛物线": ["2.8.2"],
            "双曲线": ["2.8.2"],
            "排列组合": ["2.9.3"],
            "二项式": ["2.9.3"],
            "随机变量": ["2.9.4"],
            "正态分布": ["2.9.4"],
            "直线": ["2.8.1"],
            "圆": ["2.8.1"],
            "参数方程": ["2.8.3"],
            "极坐标": ["2.8.3"],
            "解三角形": ["2.4.3"],
            "恒等变换": ["2.4.2"],
            "正弦": ["2.4.1", "2.4.2", "2.4.3"],
            "余弦": ["2.4.1", "2.4.2", "2.4.3"],
            "函数方程": ["2.2.3"],
            "零点": ["2.2.3"],
            "指数": ["2.2.2"],
            "对数": ["2.2.2"],
            "幂函数": ["2.2.2"],
            "空间向量": ["2.7.3"],
            "空间几何": ["2.7.1"],
            "点线面": ["2.7.2"],
            "方差": ["2.9.2"],
            "回归": ["2.9.2"],
            "独立性检验": ["2.9.2"],
        },
        "physics": {
            "牛顿": ["4.1.2"],
            "匀变速": ["4.1.1"],
            "动量": ["4.1.6"],
            "动能": ["4.1.5"],
            "万有引力": ["4.1.4"],
            "电场": ["4.2.1"],
            "电路": ["4.2.2"],
            "磁场": ["4.2.3"],
            "电磁感应": ["4.2.4"],
            "交变电流": ["4.2.5"],
            "原子": ["4.5.1"],
            "核": ["4.5.2"],
            "波粒二象": ["4.5.3"],
            "热力学": ["4.3.3"],
            "理想气体": ["4.3.2"],
            "光学": ["4.4"],
            "实验": ["4.6"],
            "平抛": ["4.1.3"],
            "圆周运动": ["4.1.3"],
        },
    }

    def map_question(self, question_content, subject_key):
        """
        将题目内容映射到知识点列表
        返回知识点代码列表
        """
        if subject_key not in self.SUBJECT_KEYWORDS:
            return []

        keyword_map = self.SUBJECT_KEYWORDS[subject_key]
        matched_codes = set()

        for keyword, codes in keyword_map.items():
            if keyword in question_content:
                for code in codes:
                    matched_codes.add(code)

        return sorted(matched_codes)

    def compute_coverage(self, paper_kps, ref_kps):
        """
        计算知识点覆盖率
        paper_kps: 模拟卷的知识点代码列表
        ref_kps: 真题的知识点代码列表
        """
        paper_set = set(paper_kps)
        ref_set = set(ref_kps)

        if not ref_set:
            return {"jaccard": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

        intersection = paper_set & ref_set
        union = paper_set | ref_set

        jaccard = len(intersection) / len(union) if union else 0
        precision = len(intersection) / len(paper_set) if paper_set else 0
        recall = len(intersection) / len(ref_set) if ref_set else 0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0
        )

        missing = ref_set - paper_set  # 模拟卷缺失的知识点
        extra = paper_set - ref_set  # 模拟卷多余的知识点

        return {
            "jaccard": round(jaccard, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "intersection": sorted(intersection),
            "missing": sorted(missing),
            "extra": sorted(extra),
        }


class QualityAnalyzer:
    """试题质量分析器"""

    @staticmethod
    def discrimination(item_params):
        """基于 IRT 区分度参数"""
        return round(item_params.get("a", 0), 4)

    @staticmethod
    def difficulty_index(p_correct):
        """经典测验理论的难度指数"""
        return round(p_correct, 4)

    @staticmethod
    def point_biserial(score_array, item_scores):
        """点二列相关（区分度的经典指标）"""
        if len(score_array) != len(item_scores):
            return 0.0
        if len(set(item_scores)) < 2:
            return 0.0
        corr, _ = stats.pointbiserialr(item_scores, score_array)
        return round(corr, 4)

    @staticmethod
    def cronbach_alpha(response_matrix):
        """Cronbach Alpha 信度系数"""
        n_items = response_matrix.shape[1]
        if n_items < 2:
            return 0.0
        item_vars = np.var(response_matrix, axis=0, ddof=1)
        total_var = np.var(np.sum(response_matrix, axis=1), ddof=1)
        if total_var == 0:
            return 0.0
        alpha = (n_items / (n_items - 1)) * (1 - np.sum(item_vars) / total_var)
        return round(alpha, 4)

    @staticmethod
    def quality_score(discrimination, alpha, difficulty):
        """
        综合质量评分 (0-100)
        """
        # 区分度评分 (0-40)
        disc_score = min(40, discrimination * 30)

        # 信度评分 (0-30)
        alpha_score = min(30, alpha * 30)

        # 难度适当性评分 (0-30) - 难度在 0.3-0.7 最优
        if 0.3 <= difficulty <= 0.7:
            diff_score = 30
        elif 0.2 <= difficulty <= 0.8:
            diff_score = 20
        elif 0.1 <= difficulty <= 0.9:
            diff_score = 10
        else:
            diff_score = 0

        return round(disc_score + alpha_score + diff_score, 2)
