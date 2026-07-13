"""规划Agent FC工具：考频排名查询 — 内置默认数据"""
from __future__ import annotations
from typing import Any

# 默认高频考点排名（数学）
DEFAULT_FREQUENCY = {
    "math": {
        "2.3.2": {"frequency": 0.92, "rank": "高", "name": "导数在函数中的应用"},
        "2.4.3": {"frequency": 0.88, "rank": "高", "name": "解三角形"},
        "2.7.3": {"frequency": 0.85, "rank": "高", "name": "空间向量与立体几何"},
        "2.5.1": {"frequency": 0.82, "rank": "高", "name": "等差数列与等比数列"},
        "2.8.2": {"frequency": 0.80, "rank": "高", "name": "圆锥曲线"},
        "2.2.2": {"frequency": 0.75, "rank": "高", "name": "基本初等函数"},
        "2.4.1": {"frequency": 0.72, "rank": "高", "name": "三角函数的概念与图像"},
        "2.9.4": {"frequency": 0.68, "rank": "中", "name": "随机变量及其分布"},
        "2.7.1": {"frequency": 0.60, "rank": "中", "name": "空间几何体"},
        "2.6.1": {"frequency": 0.55, "rank": "中", "name": "基本不等式"},
    }
}


async def get_exam_frequency(context: Any, kp_codes: list[str]) -> list[dict]:
    """获取知识点的考频排名"""
    if not kp_codes:
        return []

    subject_freq = DEFAULT_FREQUENCY.get("math", {})
    results = []
    for code in kp_codes:
        freq_info = subject_freq.get(code)
        if freq_info:
            results.append({
                "kp_code": code,
                "kp_name": freq_info["name"],
                "frequency": freq_info["frequency"],
                "rank": freq_info["rank"],
            })
        else:
            results.append({
                "kp_code": code,
                "kp_name": None,
                "frequency": 0.3,
                "rank": "低（暂无数据）",
            })
    # 按考频降序排序
    results.sort(key=lambda x: -x["frequency"])
    return results


async def get_hot_topics(subject_id: str, year: int = 2026) -> list[dict]:
    """获取某科高频考点TOP20"""
    subject_freq = DEFAULT_FREQUENCY.get(subject_id, DEFAULT_FREQUENCY.get("math", {}))
    sorted_items = sorted(subject_freq.items(), key=lambda x: -x[1]["frequency"])
    return [
        {"kp_code": code, "kp_name": info["name"],
         "frequency": info["frequency"], "rank": info["rank"]}
        for code, info in sorted_items[:20]
    ]


async def get_syllabus_changes(subject_id: str,
                                from_year: int = 2025,
                                to_year: int = 2026) -> dict:
    """获取考纲变化"""
    return {
        "subject_id": subject_id,
        "from_year": from_year,
        "to_year": to_year,
        "added": ["数学建模与数据分析（新增）"],
        "removed": [],
        "adjusted": ["立体几何要求降低（直观感知为主）"],
    }
