"""P2: 课程管理系统 API 路由 — v7.2 新增"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..deps import get_current_user
from ..helpers import db_one, db_all, db_exec, db_insert
import json

router = APIRouter(prefix="/api/v1/courses", tags=["课程管理"])


class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    subject_id: str = "math"
    difficulty: str = "medium"
    estimated_hours: float = 0
    cover_url: Optional[str] = None


class ChapterCreate(BaseModel):
    course_id: int
    title: str
    content_type: str = "video"
    content_url: Optional[str] = None
    duration_minutes: int = 0
    order_index: int = 0
    kp_codes: list[str] = []


@router.post("")
async def create_course(
    course: CourseCreate,
    user: dict = Depends(get_current_user),
):
    """创建课程"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute(
            """INSERT INTO courses (title, description, subject_id, difficulty,
               estimated_hours, cover_url, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (course.title, course.description, course.subject_id,
             course.difficulty, course.estimated_hours,
             course.cover_url, user["id"])
        )
        await db.commit()
        return {"id": cursor.lastrowid, "status": "created"}
    finally:
        await db.close()


@router.get("")
async def list_courses(
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """获取课程列表"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        if subject_id:
            cursor = await db.execute(
                "SELECT * FROM courses WHERE subject_id=? ORDER BY created_at DESC",
                (subject_id,)
            )
        else:
            cursor = await db.execute("SELECT * FROM courses ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return {"courses": [dict(r) for r in rows]}
    finally:
        await db.close()


@router.get("/{course_id}")
async def get_course(
    course_id: int,
    user: dict = Depends(get_current_user),
):
    """获取课程详情（含章节）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute("SELECT * FROM courses WHERE id=?", (course_id,))
        course = await cursor.fetchone()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        chapters_cursor = await db.execute(
            "SELECT * FROM course_chapters WHERE course_id=? ORDER BY order_index",
            (course_id,)
        )
        chapters = await chapters_cursor.fetchall()
        return {
            "course": dict(course),
            "chapters": [dict(c) for c in chapters],
        }
    finally:
        await db.close()


@router.post("/chapters")
async def add_chapter(
    chapter: ChapterCreate,
    user: dict = Depends(get_current_user),
):
    """添加课程章节"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        kp_json = json.dumps(chapter.kp_codes)
        cursor = await db.execute(
            """INSERT INTO course_chapters
               (course_id, title, content_type, content_url, duration_minutes,
                order_index, kp_codes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chapter.course_id, chapter.title, chapter.content_type,
             chapter.content_url, chapter.duration_minutes,
             chapter.order_index, kp_json)
        )
        await db.commit()
        return {"id": cursor.lastrowid, "status": "created"}
    finally:
        await db.close()


@router.post("/{course_id}/enroll")
async def enroll_course(
    course_id: int,
    user: dict = Depends(get_current_user),
):
    """报名课程"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO course_enrollments (user_id, course_id) VALUES (?, ?)",
            (user["id"], course_id)
        )
        await db.commit()
        return {"status": "enrolled"}
    finally:
        await db.close()


@router.get("/my/enrollments")
async def my_enrollments(user: dict = Depends(get_current_user)):
    """获取我的课程"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute(
            """SELECT c.*, ce.progress_pct, ce.enrolled_at
               FROM courses c
               JOIN course_enrollments ce ON c.id = ce.course_id
               WHERE ce.user_id=?
               ORDER BY ce.enrolled_at DESC""",
            (user["id"],)
        )
        rows = await cursor.fetchall()
        return {"enrollments": [dict(r) for r in rows]}
    finally:
        await db.close()
