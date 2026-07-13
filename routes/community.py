"""P3: 社区/问答系统 API 路由 — v7.2 新增"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..deps import get_current_user
from ..helpers import db_one, db_all, db_exec, db_insert
import json

router = APIRouter(prefix="/api/v1/community", tags=["社区"])


class QuestionCreate(BaseModel):
    title: str
    content: str
    subject_id: str = "math"
    tags: list[str] = []
    kp_code: Optional[str] = None


class AnswerCreate(BaseModel):
    content: str


@router.post("/questions")
async def create_question(
    question: QuestionCreate,
    user: dict = Depends(get_current_user),
):
    """发布提问"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        tags_json = json.dumps(question.tags, ensure_ascii=False)
        cursor = await db.execute(
            """INSERT INTO forum_questions
               (title, content, subject_id, tags, kp_code, user_id, author_name)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (question.title, question.content, question.subject_id,
             tags_json, question.kp_code, user["id"], user.get("username", ""))
        )
        await db.commit()
        return {"id": cursor.lastrowid, "status": "created"}
    finally:
        await db.close()


@router.get("/questions")
async def list_questions(
    subject_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """获取问题列表（分页）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        offset = (page - 1) * page_size
        if subject_id:
            cursor = await db.execute(
                """SELECT q.*, COUNT(a.id) as answer_count
                   FROM forum_questions q
                   LEFT JOIN forum_answers a ON q.id = a.question_id
                   WHERE q.subject_id=?
                   GROUP BY q.id
                   ORDER BY q.created_at DESC LIMIT ? OFFSET ?""",
                (subject_id, page_size, offset)
            )
            count_cursor = await db.execute(
                "SELECT COUNT(*) as count FROM forum_questions WHERE subject_id=?",
                (subject_id,)
            )
        else:
            cursor = await db.execute(
                """SELECT q.*, COUNT(a.id) as answer_count
                   FROM forum_questions q
                   LEFT JOIN forum_answers a ON q.id = a.question_id
                   GROUP BY q.id
                   ORDER BY q.created_at DESC LIMIT ? OFFSET ?""",
                (page_size, offset)
            )
            count_cursor = await db.execute("SELECT COUNT(*) as count FROM forum_questions")

        rows = await cursor.fetchall()
        total = (await count_cursor.fetchone())["count"]
        return {
            "questions": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    finally:
        await db.close()


@router.get("/questions/{question_id}")
async def get_question(
    question_id: int,
    user: dict = Depends(get_current_user),
):
    """获取问题详情（含回答）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute(
            "SELECT * FROM forum_questions WHERE id=?", (question_id,)
        )
        question = await cursor.fetchone()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        answers_cursor = await db.execute(
            "SELECT * FROM forum_answers WHERE question_id=? ORDER BY votes DESC, created_at",
            (question_id,)
        )
        answers = await answers_cursor.fetchall()

        return {
            "question": dict(question),
            "answers": [dict(a) for a in answers],
        }
    finally:
        await db.close()


@router.post("/questions/{question_id}/answers")
async def create_answer(
    question_id: int,
    answer: AnswerCreate,
    user: dict = Depends(get_current_user),
):
    """回答问题"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute(
            """INSERT INTO forum_answers
               (question_id, content, user_id, author_name)
               VALUES (?, ?, ?, ?)""",
            (question_id, answer.content, user["id"], user.get("username", ""))
        )
        await db.execute(
            "UPDATE forum_questions SET answer_count = answer_count + 1 WHERE id=?",
            (question_id,)
        )
        await db.commit()
        return {"id": cursor.lastrowid, "status": "created"}
    finally:
        await db.close()


@router.post("/answers/{answer_id}/vote")
async def vote_answer(
    answer_id: int,
    vote: int = Query(1, description="1=upvote, -1=downvote"),
    user: dict = Depends(get_current_user),
):
    """回答投票"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        await db.execute(
            "UPDATE forum_answers SET votes = votes + ? WHERE id=?",
            (vote, answer_id)
        )
        await db.commit()
        return {"status": "voted"}
    finally:
        await db.close()


@router.get("/hot")
async def get_hot_topics(
    limit: int = Query(10, le=50),
    user: dict = Depends(get_current_user),
):
    """获取热门问题"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute(
            """SELECT * FROM forum_questions
               ORDER BY answer_count DESC, created_at DESC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return {"hot_topics": [dict(r) for r in rows]}
    finally:
        await db.close()
