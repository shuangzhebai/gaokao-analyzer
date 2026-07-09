"""题型分类引擎 — 规则引擎 + LightGBM 分类器。

P0 阶段使用规则引擎（基于题型结构特征），
P2 可扩展 LightGBM / LLM 增强。
"""

import re
from typing import Any

# 题型特征模板：每个题型的关键识别特征
_SINGLE_CHOICE_PATTERN = re.compile(
    r'^(?:[A-Z][.、．])\s*(?:[\s\S]*?)$', re.MULTILINE
)
_MULTI_CHOICE_PATTERN = re.compile(
    r'^(?:[A-Z][.、．])\s*(?:[\s\S]*?)$', re.MULTILINE
)
_FILL_PATTERN = re.compile(r'[——_]{2,}|______')
_SOLVE_PATTERN = re.compile(
    r'(?:解|证明|计算|求|解答)[：:：]'
)

# 9 大学科的题型映射表
SUBJECT_QUESTION_MAP: dict[str, dict[str, list[str]]] = {
    "math": {
        "choice": ["single_choice"],
        "fill": ["fill"],
        "solve": ["calculation", "proof", "comprehensive"],
    },
    "chinese": {
        "choice": ["single_choice"],
        "fill": ["fill"],
        "solve": ["reading_comprehension", "essay", "translation"],
    },
    "english": {
        "choice": ["single_choice", "cloze"],
        "fill": ["fill", "word_fill"],
        "solve": ["reading_comprehension", "translation", "writing"],
    },
    "physics": {"choice": ["single_choice", "multi_choice"], "fill": ["fill"], "solve": ["calculation", "experiment"]},
    "chemistry": {"choice": ["single_choice"], "fill": ["fill"], "solve": ["calculation", "experiment", "inference"]},
    "biology": {"choice": ["single_choice"], "fill": ["fill"], "solve": ["comprehensive", "experiment"]},
    "history": {"choice": ["single_choice"], "fill": ["fill"], "solve": ["material_analysis", "essay"]},
    "geography": {"choice": ["single_choice"], "fill": ["fill"], "solve": ["material_analysis", "comprehensive"]},
    "politics": {"choice": ["single_choice"], "fill": ["fill"], "solve": ["material_analysis", "essay"]},
}


class QuestionClassifier:
    """题型分类器。

    先用规则引擎基于特征分类，规则置信度不足时回退到 LightGBM（未来扩展）。
    """

    def __init__(self, model_path: str | None = None):
        self._model = None
        # 如果需要加载 LightGBM 模型，在这里初始化
        # if model_path:
        #     import lightgbm as lgb
        #     self._model = lgb.Booster(model_file=model_path)

    def extract_features(self, question: dict) -> dict[str, Any]:
        """提取题目结构特征（约 30 维）。"""
        content = question.get("content", "")
        options = question.get("options", "")
        answer = question.get("answer", "")
        has_options = bool(options and options.strip())
        option_count = len(re.findall(r'^[A-Z][.、．]', options, re.MULTILINE)) if has_options else 0
        has_fill_marker = bool(_FILL_PATTERN.search(str(content)))
        has_solve_keyword = bool(_SOLVE_PATTERN.search(str(content)))
        return {
            "has_options": has_options,
            "option_count": option_count,
            "has_fill_marker": has_fill_marker,
            "has_solve_keyword": has_solve_keyword,
            "content_length": len(str(content)),
            "answer_length": len(str(answer)),
        }

    def classify(self, question: dict) -> dict[str, Any]:
        """对单道题分类，返回 {main_type, sub_type, confidence}。"""
        features = self.extract_features(question)

        # 规则引擎分类
        if features["has_options"]:
            if features["option_count"] >= 4:
                main_type = "choice"
                sub_type = "single_choice"  # 默认单选，多选需额外判断
                confidence = 0.85
            elif features["option_count"] >= 2:
                main_type = "choice"
                sub_type = "multi_choice"
                confidence = 0.75
            else:
                main_type = "choice"
                sub_type = "single_choice"
                confidence = 0.60
        elif features["has_fill_marker"]:
            main_type = "fill"
            sub_type = "fill"
            confidence = 0.80
        elif features["has_solve_keyword"]:
            main_type = "solve"
            sub_type = "calculation"
            confidence = 0.70
        else:
            # 回退：按内容长度判断
            if features["content_length"] > 200:
                main_type = "solve"
                sub_type = "comprehensive"
                confidence = 0.50
            elif features["content_length"] > 50:
                main_type = "fill"
                sub_type = "fill"
                confidence = 0.40
            else:
                main_type = "choice"
                sub_type = "single_choice"
                confidence = 0.30

        return {
            "main_type": main_type,
            "sub_type": sub_type,
            "confidence": round(confidence, 2),
        }

    def batch_classify(self, questions: list[dict]) -> list[dict]:
        """批量分类。"""
        return [self.classify(q) for q in questions]
