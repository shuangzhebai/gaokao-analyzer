"""
阶段二（后端核心）：试卷质量分析 API
- POST /api/papers/{id}/analyze      单卷分析（结构化报告，落库 paper_reports）
- POST /api/papers/analyze/batch     批量并行分析（接收 paper id 列表，返回报告数组）
- GET  /api/papers/{id}/report       取已存报告

约束：保持既有 routes/*.py 路由不变，仅新增本模块端点；报告落库到独立表 paper_reports。
"""
import json
import logging
from typing import List, Optional

import numpy as np
from aiosqlite import Connection
from fastapi import APIRouter, Body, Depends, HTTPException

from config import SUBJECTS
from deps import get_paper_analyzer
from models import get_db
from paper_analysis import PaperAnalyzer, analyze_papers_batch

logger = logging.getLogger("gaokao")
router = APIRouter()


# ===================== 内部工具 =====================

async def _load_paper_for_analysis(paper_id: int, db: Connection):
    """从 DB 读取试卷与题目，构建可分析的 paper dict。"""
    paper = await db.execute_fetchone("SELECT * FROM papers WHERE id = ?", (paper_id,))
    if not paper:
        return None, None
    rows = await db.execute_fetchall(
        "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
    )
    questions = []
    for q in rows:
        kps = json.loads(q["knowledge_points"]) if q["knowledge_points"] else []
        options = json.loads(q["options"]) if q["options"] else []
        questions.append({
            "q_type": q["q_type"],
            "content": q["content"] or "",
            "score": q["score"] or 0.0,
            "knowledge_points": kps,
            "options": options,
            "answer": q.get("answer") or "",
            "irt_a": q.get("irt_a"),
            "irt_b": q.get("irt_b"),
            "irt_c": q.get("irt_c"),
        })
    paper_dict = {
        "title": paper.get("title", ""),
        "subject": paper.get("subject_id", "math"),
        "year": paper.get("year", 2026),
        "questions": questions,
    }
    return paper, paper_dict


def _json_default(obj):
    """numpy 类型序列化兜底。"""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


async def _store_report(db: Connection, paper_id: int, report: dict) -> None:
    """将报告落库到 paper_reports，并标记试卷 analysis_status='analyzed'。"""
    composite = report.get("composite", {})
    await db.execute(
        """INSERT INTO paper_reports (paper_id, report_json, composite_score, grade)
           VALUES (?, ?, ?, ?)""",
        (paper_id, json.dumps(report, ensure_ascii=False, default=_json_default),
         composite.get("score"), composite.get("grade")),
    )
    await db.execute(
        "UPDATE papers SET analysis_status='analyzed' WHERE id=?", (paper_id,)
    )
    await db.commit()


# ===================== 端点 =====================

@router.post("/api/papers/{paper_id}/analyze")
async def analyze_paper_endpoint(
    paper_id: int,
    db: Connection = Depends(get_db),
    analyzer: PaperAnalyzer = Depends(get_paper_analyzer),
):
    """分析单份试卷，返回结构化报告并落库。"""
    paper, paper_dict = await _load_paper_for_analysis(paper_id, db)
    if paper is None:
        raise HTTPException(404, "试卷不存在")
    if not paper_dict["questions"]:
        raise HTTPException(400, "该试卷没有题目，无法分析")
    report = analyzer.analyze(paper_dict)
    await _store_report(db, paper_id, report)
    return report


@router.post("/api/papers/analyze/batch")
async def analyze_papers_batch_endpoint(
    paper_ids: List[int] = Body(..., embed=True),
    max_workers: Optional[int] = None,
    db: Connection = Depends(get_db),
    analyzer: PaperAnalyzer = Depends(get_paper_analyzer),
):
    """批量并行分析多份试卷（接收 paper id 列表），返回与输入顺序一致的报告数组。"""
    if not paper_ids:
        raise HTTPException(400, "paper_ids 不能为空")

    # 读取所有试卷（保持输入顺序）
    loaded = []
    for pid in paper_ids:
        paper, paper_dict = await _load_paper_for_analysis(pid, db)
        loaded.append((pid, paper_dict))

    # 仅对有题目的试卷做并行分析
    to_analyze = [(pid, pd) for pid, pd in loaded if pd and pd["questions"]]
    result_map = {}
    if to_analyze:
        papers = [pd for _pid, pd in to_analyze]
        subject = papers[0]["subject"] if papers else "math"
        reports = await analyze_papers_batch(
            papers, max_workers=max_workers, subject_id=subject, analyzer=analyzer
        )
        for (pid, _pd), rep in zip(to_analyze, reports):
            if "error" not in rep:
                await _store_report(db, pid, rep)
            result_map[pid] = rep

    results = []
    for pid, pd in loaded:
        if pd is None:
            results.append({"paper_id": pid, "error": "试卷不存在"})
        elif not pd["questions"]:
            results.append({"paper_id": pid, "error": "该试卷没有题目，无法分析"})
        else:
            results.append({"paper_id": pid, "report": result_map.get(pid)})

    return {"count": len(results), "results": results}


@router.get("/api/papers/{paper_id}/report")
async def get_paper_report(paper_id: int, db: Connection = Depends(get_db)):
    """获取某试卷最新一次分析报告。"""
    row = await db.execute_fetchone(
        "SELECT * FROM paper_reports WHERE paper_id = ? ORDER BY id DESC LIMIT 1", (paper_id,)
    )
    if not row:
        raise HTTPException(404, "该试卷暂无分析报告")
    report = json.loads(row["report_json"]) if row["report_json"] else None
    return {
        "paper_id": paper_id,
        "composite_score": row.get("composite_score"),
        "grade": row.get("grade"),
        "created_at": row.get("created_at"),
        "report": report,
    }
