"""F7: 知识结构化讲解工具 — DeepSeek Prompt模板 + 降级逻辑"""
from __future__ import annotations
from typing import Any
import json

# ============================================================
# DeepSeek 结构化讲解 Prompt 模板
# ============================================================

EXPLAIN_SYSTEM_PROMPT = """你是一位资深高考备考导师。请对给定的知识点进行结构化讲解，遵循以下5步SOP：

## SOP
1. **概念回归** — 用最简洁的方式讲清"这是什么"（50字内）
2. **关键难点** — 说明最常见的卡壳点和为什么这里容易错（50字内）
3. **典型例题** — 给一道高考真题并简要分析思路（以2024/2025全国I卷为参照）
4. **变式练习** — 给一道难度相当的变式题（更改数值/情境/提问角度）
5. **延伸提问** — 提出1-2个延伸思考问题，促进深度学习

## 约束
- 输出严格的JSON格式，不要包含任何markdown标记
- 语言：接地气的中文（像在跟高中生说话，不是写论文）
- 例题出处必须真实（如果不知道确切年份，用"近年真题"）
- 变式题要明确说"第3题答案不是XX，是XX"的关键区别
- 每个步骤字数严格控制
"""

EXPLAIN_USER_TEMPLATE = """请对以下知识点进行结构化讲解：
知识点代码: {kp_code}
知识点名称: {kp_name}
学生当前掌握度: {mastery:.2f}（0-1范围，{mastery_desc}）
学生能力theta值: {theta:.2f}
所属学科: {subject_name}

高考考频: {exam_frequency}
典型题目数量: {question_count}道

额外信息: {extra_info}
"""

# ============================================================
# 降级模板（当LLM不可用时使用）
# ============================================================

FALLBACK_EXPLAIN_TEMPLATES = {
    "math": {
        "concept_summary": "这是高中数学{chapter}阶段的核心知识点，高考每年必考。",
        "key_difficulty": "常见易错点：混淆定义与性质，忽视前提条件。",
        "example": "近年高考真题中，常以选择题第{X}题或填空题形式出现。",
        "variant": "同类变式：注意条件变化时公式的适用条件。",
        "extension": "思考：这个知识点与前后章节的联系是什么？",
    },
    "general": {
        "concept_summary": "这个知识点是整个学科体系中的关键环节。",
        "key_difficulty": "需要特别注意基本概念的理解和公式的正确使用。",
        "example": "建议先复习教材中对应的例题，确保掌握基本解法。",
        "variant": "尝试调整题目条件，看看解法如何变化。",
        "extension": "思考这个知识点在实际应用中有什么意义？",
    },
}


def build_explain_payload(context: Any, kp_code: str, kp_name: str,
                          mastery: float, theta: float, subject_id: str,
                          exam_frequency: float = 0.5, question_count: int = 0,
                          extra_info: str = "") -> dict:
    """构建结构化讲解的LLM调用参数"""
    mastery_desc = "严重薄弱" if mastery < 0.2 else \
                   "薄弱" if mastery < 0.4 else \
                   "发展中" if mastery < 0.6 else \
                   "基本掌握" if mastery < 0.8 else "熟练掌握"

    subject_names = {"math": "数学", "chinese": "语文", "english": "英语",
                     "physics": "物理", "chemistry": "化学", "biology": "生物",
                     "history": "历史", "geography": "地理", "politics": "政治"}

    user_msg = EXPLAIN_USER_TEMPLATE.format(
        kp_code=kp_code, kp_name=kp_name, mastery=mastery,
        mastery_desc=mastery_desc, theta=theta,
        subject_name=subject_names.get(subject_id, subject_id),
        exam_frequency=f"{exam_frequency*100:.0f}%" if exam_frequency else "未知",
        question_count=question_count, extra_info=extra_info,
    )

    return {
        "system_prompt": EXPLAIN_SYSTEM_PROMPT,
        "user_message": user_msg,
        "response_format": {
            "type": "json_object",
        },
    }


def build_fallback_explain(subject_id: str, kp_name: str, mastery: float) -> dict:
    """LLM不可用时的降级讲解模板"""
    tmpl = FALLBACK_EXPLAIN_TEMPLATES.get(subject_id, FALLBACK_EXPLAIN_TEMPLATES["general"])
    return {
        "concept_summary": f"「{kp_name}」{tmpl['concept_summary']}",
        "key_difficulty": tmpl["key_difficulty"],
        "example": tmpl["example"],
        "variant": tmpl["variant"],
        "extension": tmpl["extension"],
        "confidence": 0.5,
        "is_fallback": True,
    }
