"""P2: 作业批改系统 API 路由 — v7.2 新增"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..deps import get_current_user
from ..helpers import db_one, db_all, db_exec, db_insert
import json

router = APIRouter(prefix="/api/v1/assignments", tags=["作业系统"])


class AssignmentCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    course_id: Optional[int] = None
    subject_id: str = "math"
    questions: list[dict] = []  # [{q_type, content, answer, score}]
    due_at: Optional[str] = None


class SubmissionCreate(BaseModel):
    answers: list[dict]  # [{question_id, answer_text}]


@router.post("")
async def create_assignment(
    assignment: AssignmentCreate,
    user: dict = Depends(get_current_user),
):
    """创建作业（教师端）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        questions_json = json.dumps(assignment.questions, ensure_ascii=False)
        cursor = await db.execute(
            """INSERT INTO assignments
               (title, description, course_id, subject_id, questions, due_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (assignment.title, assignment.description, assignment.course_id,
             assignment.subject_id, questions_json, assignment.due_at, user["id"])
        )
        await db.commit()
        return {"id": cursor.lastrowid, "status": "created"}
    finally:
        await db.close()


@router.get("")
async def list_assignments(
    course_id: Optional[int] = Query(None),
    user: dict = Depends(get_current_user),
):
    """获取作业列表"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        if course_id:
            cursor = await db.execute(
                "SELECT * FROM assignments WHERE course_id=? ORDER BY created_at DESC",
                (course_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM assignments ORDER BY created_at DESC"
            )
        rows = await cursor.fetchall()
        return {"assignments": [dict(r) for r in rows]}
    finally:
        await db.close()


@router.get("/{assignment_id}")
async def get_assignment(
    assignment_id: int,
    user: dict = Depends(get_current_user),
):
    """获取作业详情"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute(
            "SELECT * FROM assignments WHERE id=?", (assignment_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Assignment not found")
        return dict(row)
    finally:
        await db.close()


@router.post("/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    submission: SubmissionCreate,
    user: dict = Depends(get_current_user),
):
    """提交作业（自动批改客观题）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        # 获取作业
        cursor = await db.execute(
            "SELECT * FROM assignments WHERE id=?", (assignment_id,)
        )
        assignment = await cursor.fetchone()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        questions = json.loads(assignment["questions"])
        total_score = 0
        earned_score = 0
        results = []

        for i, q in enumerate(questions):
            q_score = q.get("score", 1)
            total_score += q_score
            user_ans = submission.answers[i]["answer_text"] if i < len(submission.answers) else ""
            correct_ans = q.get("answer", "")

            # 客观题自动批改
            if q.get("q_type") in ("choice", "fill"):
                is_correct = user_ans.strip() == correct_ans.strip()
            else:
                is_correct = None  # 主观题需教师批改

            if is_correct:
                earned_score += q_score
            results.append({
                "question_index": i,
                "user_answer": user_ans,
                "correct_answer": correct_ans,
                "is_correct": is_correct,
                "score": q_score if is_correct else 0,
            })

        # 保存提交记录
        results_json = json.dumps(results, ensure_ascii=False)
        cursor = await db.execute(
            """INSERT INTO assignment_submissions
               (assignment_id, user_id, answers, score, total_score, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (assignment_id, user["id"], results_json,
             earned_score, total_score,
             "auto_graded" if all(r.get("is_correct") is not None for r in results) else "pending_review")
        )
        await db.commit()

        return {
            "submission_id": cursor.lastrowid,
            "score": earned_score,
            "total_score": total_score,
            "percentage": round(earned_score / total_score * 100, 1) if total_score > 0 else 0,
            "results": results,
            "status": "auto_graded" if all(r.get("is_correct") is not None for r in results) else "pending_review",
        }
    finally:
        await db.close()


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: int,
    user: dict = Depends(get_current_user),
):
    """获取提交结果"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute(
            "SELECT * FROM assignment_submissions WHERE id=? AND user_id=?",
            (submission_id, user["id"])
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")
        result = dict(row)
        result["answers"] = json.loads(result["answers"])
        return result
    finally:
        await db.close()
