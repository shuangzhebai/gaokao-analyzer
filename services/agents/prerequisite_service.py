"""规划Agent FC工具：前置知识点DAG查询"""
from __future__ import annotations
from typing import Any


async def get_prerequisites(context: Any, kp_codes: list[str]) -> list[dict]:
    """
    查询知识点前置依赖（DAG）
    返回 [{"code": "...", "name": "...", "prereq_code": "...", "prereq_name": "..."}]
    """
    if not kp_codes:
        return []

    # 从已缓存的 knowledge_tree 中查询
    tree = context.knowledge_tree or {}
    results = []
    for kp in kp_codes:
        node = tree.get(kp, {})
        prereqs = node.get("prerequisites", [])
        for p in prereqs:
            p_node = tree.get(p, {})
            results.append({
                "kp_code": kp,
                "prerequisite_code": p,
                "prerequisite_name": p_node.get("name", p),
            })
    return results


async def get_dependency_graph(context: Any, subject_id: str) -> dict:
    """
    获取整个知识点的DAG依赖图
    从 knowledge_points 表查询
    """
    # TODO: 从数据库查询所有知识点及其依赖关系
    # 当前返回空，实际部署时从 knowledge_points 表读取
    return {
        "subject_id": subject_id,
        "nodes": [],
        "edges": [],
    }
