"""P1: 学习报告生成 API 路由 — v7.2 新增"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Optional
from datetime import datetime

from ..deps import get_current_user
from ..helpers import db_one, db_all, db_exec, db_insert
import json

router = APIRouter(prefix="/api/v1/reports", tags=["学习报告"])


@router.get("/learning-summary")
async def get_learning_summary(
    user: dict = Depends(get_current_user),
):
    """获取学习总结数据"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        # 综合统计
        cursor = await db.execute(
            "SELECT theta, knowledge_mastery FROM student_profiles WHERE user_id=?",
            (user["id"],)
        )
        profile = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM error_records WHERE user_id=?",
            (user["id"],)
        )
        error_count = (await cursor.fetchone())["count"]

        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM agent_execution_logs WHERE user_id=?",
            (user["id"],)
        )
        diagnosis_count = (await cursor.fetchone())["count"]

        cursor = await db.execute(
            "SELECT current_streak, longest_streak, total_study_days "
            "FROM user_streaks WHERE user_id=?",
            (user["id"],)
        )
        streak = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM user_achievements WHERE user_id=?",
            (user["id"],)
        )
        achievement_count = (await cursor.fetchone())["count"]

        theta = profile["theta"] if profile else 0
        knowledge_mastery = {}
        if profile and profile["knowledge_mastery"]:
            try:
                knowledge_mastery = json.loads(profile["knowledge_mastery"])
            except (TypeError, json.JSONDecodeError):
                knowledge_mastery = {}

        weak_points = sorted(
            [{"kp": k, "mastery": v} for k, v in knowledge_mastery.items() if v < 0.6],
            key=lambda x: x["mastery"]
        )[:5]

        return {
            "theta": round(float(theta), 2),
            "total_errors": error_count,
            "total_diagnoses": diagnosis_count,
            "streak": {
                "current": streak["current_streak"] if streak else 0,
                "longest": streak["longest_streak"] if streak else 0,
                "total_days": streak["total_study_days"] if streak else 0,
            } if streak else {"current": 0, "longest": 0, "total_days": 0},
            "achievements": achievement_count,
            "top_weak_points": weak_points,
            "generated_at": datetime.now().isoformat(),
        }
    finally:
        await db.close()


@router.get("/learning-summary/html", response_class=HTMLResponse)
async def get_learning_summary_html(
    user: dict = Depends(get_current_user),
):
    """获取学习总结HTML报告（可打印/导出PDF）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        summary = await get_learning_summary(user)
    finally:
        await db.close()

    weak_html = ""
    for w in summary["top_weak_points"]:
        mastery_pct = int(w["mastery"] * 100)
        color = "#EF4444" if mastery_pct < 30 else "#F97316" if mastery_pct < 50 else "#F59E0B"
        weak_html += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{w['kp']}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                <div style="background:#f0f0f0;border-radius:10px;overflow:hidden;">
                    <div style="background:{color};width:{mastery_pct}%;height:20px;
                         border-radius:10px;text-align:center;color:white;font-size:12px;
                         line-height:20px;">{mastery_pct}%</div>
                </div>
            </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ margin: 2cm; }}
  body {{ font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; color: #333; }}
  .header {{ text-align: center; padding: 30px 0; border-bottom: 3px solid #2563EB; }}
  .header h1 {{ color: #2563EB; margin: 0; }}
  .header p {{ color: #666; margin: 5px 0 0; }}
  .stats {{ display: flex; justify-content: space-around; margin: 30px 0; }}
  .stat-card {{ text-align: center; padding: 20px; background: #f8fafc;
               border-radius: 12px; flex: 1; margin: 0 8px; }}
  .stat-card .value {{ font-size: 32px; font-weight: bold; color: #2563EB; }}
  .stat-card .label {{ font-size: 14px; color: #666; margin-top: 5px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
  th {{ background: #2563EB; color: white; padding: 10px; text-align: left; }}
  .footer {{ text-align: center; margin-top: 40px; padding-top: 20px;
             border-top: 1px solid #ddd; font-size: 12px; color: #999; }}
</style></head><body>
<div class="header">
  <h1>📚 学习总结报告</h1>
  <p>生成时间: {summary['generated_at'][:10]}</p>
</div>
<div class="stats">
  <div class="stat-card"><div class="value">{summary['theta']}</div>
    <div class="label">能力值 (θ)</div></div>
  <div class="stat-card"><div class="value">{summary['streak']['current']}</div>
    <div class="label">连续学习天数</div></div>
  <div class="stat-card"><div class="value">{summary['achievements']}</div>
    <div class="label">已获成就</div></div>
  <div class="stat-card"><div class="value">{summary['total_diagnoses']}</div>
    <div class="label">诊断次数</div></div>
</div>
<h2 style="color:#2563EB;">📊 薄弱知识点</h2>
<table><tr><th>知识点</th><th>掌握度</th></tr>
{weak_html if weak_html else '<tr><td colspan="2" style="text-align:center;padding:20px;">暂无薄弱知识点</td></tr>'}</table>
<h2 style="color:#2563EB;">💡 学习建议</h2>
<ul>
  <li>重点关注掌握度低于 <strong>50%</strong> 的知识点，建议从最薄弱的知识点开始突破</li>
  <li>每天坚持学习 <strong>至少30分钟</strong>，保持连续学习记录</li>
  <li>完成一次学习诊断，获取精准的个性化学习路径</li>
  <li>利用错题本定期复习，巩固薄弱环节</li>
</ul>
<div class="footer">
  <p>gaokao-analyzer · AI-powered learning system</p>
</div>
</body></html>"""

    return HTMLResponse(content=html)
