"""规划Agent FC工具：教材章节查询 — 内置默认数据"""
from __future__ import annotations
from typing import Any, Optional

# 默认教材章节数据（数学人教版）
DEFAULT_CHAPTERS = {
    "math": {
        "人教版必修一": [
            {"chapter_code": "B1-C1", "chapter_name": "集合与函数概念",
             "kp_codes": ["2.1", "2.1.1", "2.2.1"]},
            {"chapter_code": "B1-C2", "chapter_name": "基本初等函数",
             "kp_codes": ["2.2.2"]},
        ],
        "人教版必修二": [
            {"chapter_code": "B2-C1", "chapter_name": "空间几何体",
             "kp_codes": ["2.7.1"]},
            {"chapter_code": "B2-C2", "chapter_name": "点线面位置关系",
             "kp_codes": ["2.7.2"]},
        ],
    }
}


async def get_chapter_for_kp(context: Any, kp_code: str) -> dict:
    """查询知识点对应的教材章节信息"""
    # 遍历默认数据查找
    for subject_id, textbooks in DEFAULT_CHAPTERS.items():
        for textbook_name, chapters in textbooks.items():
            for ch in chapters:
                if kp_code in ch.get("kp_codes", []):
                    return {
                        "kp_code": kp_code,
                        "textbook_name": textbook_name,
                        "chapter_code": ch["chapter_code"],
                        "chapter_name": ch["chapter_name"],
                    }
    return {
        "kp_code": kp_code,
        "textbook_name": "教材映射待扩展",
        "chapter_name": "请先导入教材映射数据",
        "section_name": None,
    }


async def get_chapters_for_subject(subject_id: str) -> list[dict]:
    """获取某科所有教材章节树"""
    chapters = []
    for textbook_name, sections in DEFAULT_CHAPTERS.get(subject_id, {}).items():
        for ch in sections:
            chapters.append({
                "textbook_name": textbook_name,
                "chapter_code": ch["chapter_code"],
                "chapter_name": ch["chapter_name"],
                "kp_count": len(ch.get("kp_codes", [])),
            })
    return chapters


async def search_kp_by_chapter(subject_id: str, textbook_name: Optional[str] = None,
                                 chapter_code: Optional[str] = None) -> list[dict]:
    """按教材/章节搜索知识点"""
    textbooks = DEFAULT_CHAPTERS.get(subject_id, {})
    if textbook_name:
        textbooks = {k: v for k, v in textbooks.items() if k == textbook_name}
    results = []
    for tb, chapters in textbooks.items():
        for ch in chapters:
            if chapter_code and ch["chapter_code"] != chapter_code:
                continue
            results.append({
                "textbook_name": tb,
                "chapter_code": ch["chapter_code"],
                "chapter_name": ch["chapter_name"],
                "kp_codes": ch.get("kp_codes", []),
            })
    return results
