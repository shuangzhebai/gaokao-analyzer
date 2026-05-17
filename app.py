"""
高考模拟卷智能分析系统 v5.0 - Web API
v5.0: 地区校验、自动采集、官方文件库、真实性审核、校准评价
"""
import asyncio
import hashlib
import json
import logging
import os
import time
import traceback
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from config import (
    SUBJECTS, PAPER_TYPES, DATA_DIR, DOWNLOAD_DIR, PROVINCES, EXAM_TAGS, MC_CONFIG,
    DEEPSEEK_CONFIG, SOURCE_PRIORITY_MAP, CALIBRATION_DATA, REGION_HIERARCHY,
    CITY_TO_PROVINCE, AUTO_SCRAPER_CONFIG, OFFICIAL_DOCS_CONFIG,
)
from models import init_db, seed_data, get_db
from scraper import ScraperManager
from parser import PaperParser
from analyzer import IRTModel, KnowledgeMapper, QualityAnalyzer
from simulator import MonteCarloSimulator, FittingAnalyzer
from curriculum import CurriculumAnalyzer
from quality import QualityScorer
from search import SearchEngine
from dedup import DedupEngine
from region_validator import RegionValidator
from auto_scraper import AutoScraper, CrossVerifier
from official_docs import OfficialDocsLibrary
from auth_verifier import AuthVerifier

app = FastAPI(title="高考模拟卷智能分析系统", version="5.0.0")
logger = logging.getLogger("gaokao")


# ============ 全局异常处理 ============

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)}"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)},
    )


# ============ 全局实例 ============

scraper_manager = None
irt_model = None
kp_mapper = None
quality_analyzer = None
simulator = None
fitting_analyzer = None
paper_parser = None
curriculum_analyzer = None
quality_scorer = None
search_engine = None
dedup_engine = None
auto_scraper = None
official_docs = None


@app.on_event("startup")
async def startup():
    global scraper_manager, irt_model, kp_mapper, quality_analyzer, simulator
    global fitting_analyzer, paper_parser, curriculum_analyzer, quality_scorer
    global search_engine, dedup_engine, auto_scraper, official_docs

    # v5.0 schema 迁移：检查是否需要重建
    db_path = os.path.join(DATA_DIR, "gaokao.db")
    needs_rebuild = False
    if os.path.exists(db_path):
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(papers)").fetchall()]
            # 检查新表是否存在
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            conn.close()
            if "content_hash" not in cols:
                needs_rebuild = True
                logger.info("v5.0 migration: old schema detected, rebuilding database")
            elif "official_docs" not in tables:
                # v5.0 新表不存在，需要追加创建（不删库）
                needs_rebuild = False
                logger.info("v5.0 migration: adding new tables")
        except Exception:
            needs_rebuild = True

    if needs_rebuild and os.path.exists(db_path):
        os.remove(db_path)
        logger.info("Removed old database for v5.0 schema migration")

    os.makedirs(DATA_DIR, exist_ok=True)
    await init_db()
    await seed_data()

    scraper_manager = ScraperManager()
    irt_model = IRTModel()
    kp_mapper = KnowledgeMapper()
    quality_analyzer = QualityAnalyzer()
    simulator = MonteCarloSimulator()
    fitting_analyzer = FittingAnalyzer()
    paper_parser = PaperParser()
    curriculum_analyzer = CurriculumAnalyzer()
    quality_scorer = QualityScorer()
    search_engine = SearchEngine()
    dedup_engine = DedupEngine(
        deepseek_api_key=DEEPSEEK_CONFIG.get("api_key") or None
    )

    # v5.0: 启动自动采集
    auto_scraper = AutoScraper(
        deepseek_api_key=DEEPSEEK_CONFIG.get("api_key") or ""
    )
    await auto_scraper.start()

    # v5.0: 初始化官方文件库
    official_docs = OfficialDocsLibrary()
    await official_docs.seed_official_docs()

    logger.info("v5.0 startup complete - region validator + auto-scraper + official docs + calibration ready")


@app.on_event("shutdown")
async def shutdown():
    if scraper_manager:
        await scraper_manager.close()
    if auto_scraper:
        await auto_scraper.stop()


# ============ 健康检查 ============

@app.get("/api/health")
async def health_check():
    try:
        async for db in get_db():
            count = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM papers")
            docs_count = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM official_docs")
            return {
                "status": "ok",
                "papers_count": count["cnt"] if count else 0,
                "official_docs_count": docs_count["cnt"] if docs_count else 0,
                "version": "5.0.0",
                "features": ["fts5_search", "deepseek_dedup", "source_tracking",
                             "region_validator", "auto_scraper", "cross_verify",
                             "official_docs", "calibrated_simulation", "auth_audit"],
                "auto_scraper_status": auto_scraper.get_status() if auto_scraper else None,
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============ 页面路由 ============

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# ============ 科目相关 ============

@app.get("/api/subjects")
async def list_subjects():
    return [{"id": k, **v} for k, v in SUBJECTS.items()]


# ============ 地区校验 API (v5.0) ============

@app.get("/api/regions")
async def get_regions():
    """获取地区层级映射"""
    return REGION_HIERARCHY


@app.get("/api/regions/validate")
async def validate_region(province: str = "", city: str = "", title: str = ""):
    """校验地区信息"""
    return RegionValidator.validate_region(province=province, city=city, title=title)


@app.post("/api/regions/batch-fix")
async def batch_fix_regions(limit: int = 100):
    """批量纠正试卷地区信息"""
    async for db in get_db():
        rows = await db.execute_fetchall(
            "SELECT id, title, province, school FROM papers LIMIT ?", (limit,)
        )
        papers = [dict(r) for r in rows]

    results = RegionValidator.batch_validate(papers)
    fixed_count = 0

    async for db in get_db():
        for r in results:
            if r["auto_corrected"] and r["corrected_province"]:
                await db.execute(
                    "UPDATE papers SET province = ? WHERE id = ?",
                    (r["corrected_province"], r["paper_id"]),
                )
                fixed_count += 1
        await db.commit()

    return {"checked": len(results), "fixed": fixed_count, "details": results}


# ============ 全文搜索 API ============

@app.get("/api/search")
async def search_papers(
    q: str = "",
    subject: Optional[str] = None,
    paper_type: Optional[str] = None,
    year: Optional[int] = None,
    province: Optional[str] = None,
    exam_tag: Optional[str] = None,
    source_priority: Optional[str] = None,
    verified: Optional[bool] = None,
    analysis_status: Optional[str] = None,
    sort: str = "relevance",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    return await search_engine.search(
        q=q, subject=subject, paper_type=paper_type, year=year,
        province=province, exam_tag=exam_tag, source_priority=source_priority,
        verified=verified, analysis_status=analysis_status,
        sort=sort, page=page, size=size,
    )


@app.get("/api/search/suggest")
async def search_suggest(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=20)):
    suggestions = await search_engine.suggest(q, limit)
    return {"query": q, "suggestions": suggestions}


@app.get("/api/search/questions")
async def search_questions(
    q: str = Query(..., min_length=1),
    subject: Optional[str] = None,
    q_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    return await search_engine.search_questions(q=q, subject=subject, q_type=q_type, page=page, size=size)


# ============ 试卷管理 ============

@app.get("/api/papers")
async def list_papers(
    subject: Optional[str] = None,
    paper_type: Optional[str] = None,
    year: Optional[int] = None,
    province: Optional[str] = None,
    analysis_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    async for db in get_db():
        conditions = []
        params = []
        if subject:
            conditions.append("subject_id = ?")
            params.append(subject)
        if paper_type:
            conditions.append("paper_type = ?")
            params.append(paper_type)
        if year:
            conditions.append("year = ?")
            params.append(year)
        if province:
            conditions.append("(province LIKE ? OR school LIKE ?)")
            pv = f"%{province}%"
            params.extend([pv, pv])
        if analysis_status:
            conditions.append("analysis_status = ?")
            params.append(analysis_status)

        conditions.append("(dedup_status != 'duplicate' OR dedup_status IS NULL)")

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * size

        total = await db.execute_fetchone(f"SELECT COUNT(*) as cnt FROM papers {where}", params)
        rows = await db.execute_fetchall(
            f"SELECT * FROM papers {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [size, offset],
        )
        return {
            "total": total["cnt"] if total else 0,
            "page": page,
            "size": size,
            "data": rows,
        }


@app.get("/api/papers/{paper_id}")
async def get_paper(paper_id: int):
    async for db in get_db():
        paper = await db.execute_fetchone("SELECT * FROM papers WHERE id = ?", (paper_id,))
        if not paper:
            raise HTTPException(404, "试卷不存在")

        questions = await db.execute_fetchall(
            "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
        )
        analyses = await db.execute_fetchall(
            "SELECT * FROM analysis_results WHERE paper_id = ?", (paper_id,)
        )

        source = None
        if paper.get("source_id"):
            source = await db.execute_fetchone(
                "SELECT * FROM sources WHERE id = ?", (paper["source_id"],)
            )

        # v5.0: 地区校验
        region_check = RegionValidator.validate_region(
            province=paper.get("province", ""),
            city=paper.get("school", ""),
            title=paper.get("title", ""),
        )

        return {
            "paper": paper,
            "questions": questions,
            "analyses": analyses,
            "source": source,
            "source_priority_label": SOURCE_PRIORITY_MAP.get(paper.get("source_priority", ""), ""),
            "region_check": region_check,
        }


@app.delete("/api/papers/{paper_id}")
async def delete_paper(paper_id: int):
    async for db in get_db():
        paper = await db.execute_fetchone("SELECT id FROM papers WHERE id = ?", (paper_id,))
        if not paper:
            raise HTTPException(404, "试卷不存在")

        await db.execute("DELETE FROM questions WHERE paper_id = ?", (paper_id,))
        await db.execute("DELETE FROM analysis_results WHERE paper_id = ?", (paper_id,))
        await db.execute("DELETE FROM dedup_records WHERE paper_id_1 = ? OR paper_id_2 = ?", (paper_id, paper_id))
        await db.execute("DELETE FROM verification_audit WHERE paper_id = ?", (paper_id,))
        await db.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        await db.commit()
    return {"ok": True}


# ============ 查重 API ============

@app.post("/api/papers/dedup")
async def check_dedup(
    title: str = Query(..., min_length=1),
    subject_id: str = Query(...),
    year: int = Query(...),
    source_url: str = "",
):
    result = await dedup_engine.check_duplicate(
        title=title, subject_id=subject_id, year=year, source_url=source_url,
    )
    return result


# ============ 试卷上传（增加查重+地区校验） ============

@app.post("/api/papers/upload")
async def upload_paper(
    file: UploadFile = File(...),
    subject: str = Form("math"),
    paper_type: str = Form("school"),
    title: Optional[str] = Form(None),
    year: int = Form(2026),
    province: Optional[str] = Form(None),
):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    save_path = os.path.join(DOWNLOAD_DIR, file.filename)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    paper = paper_parser.parse_file(save_path, subject)
    paper_title = title or paper.title or file.filename

    # v5.0: 地区校验
    region_result = RegionValidator.validate_region(
        province=province or "",
        title=paper_title,
    )
    corrected_province = region_result["province"] or province or ""

    # 查重检测
    dedup_result = await dedup_engine.check_duplicate(
        title=paper_title, subject_id=subject, year=year,
        questions=[{"content": q.content} for q in paper.questions] if paper.questions else [],
    )

    if dedup_result["status"] == "duplicate":
        raise HTTPException(409, f"试卷与已有试卷重复: {dedup_result['similar_papers'][0]['title']}")

    content_hash = dedup_result.get("content_hash", "")
    dedup_status = dedup_result["status"]

    async for db in get_db():
        cursor = await db.execute(
            """INSERT INTO papers
               (title, subject_id, paper_type, file_path, analysis_status, total_score,
                content_hash, dedup_status, year, question_count, source_priority, collector, province)
               VALUES (?, ?, ?, ?, 'parsed', ?, ?, ?, ?, ?, 'C', 'manual', ?)""",
            (paper_title, subject, paper_type, save_path, paper.total_score,
             content_hash, dedup_status, year, len(paper.questions), corrected_province),
        )
        paper_id = cursor.lastrowid

        for q in paper.questions:
            kp_codes = kp_mapper.map_question(q.content, subject)
            q_hash = hashlib.sha256((q.content or "").encode("utf-8")).hexdigest()[:32] if q.content else ""
            await db.execute(
                """INSERT INTO questions
                   (paper_id, q_number, q_type, content, options, score, knowledge_points, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (paper_id, q.number, q.q_type, q.content,
                 json.dumps(q.options, ensure_ascii=False) if q.options else None,
                 q.score, json.dumps(kp_codes), q_hash),
            )

        for sp in dedup_result.get("similar_papers", []):
            await db.execute(
                """INSERT INTO dedup_records (paper_id_1, paper_id_2, similarity, method, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (paper_id, sp["paper_id"], sp["similarity"], sp["method"], "pending"),
            )

        await db.commit()
        return {
            "paper_id": paper_id,
            "title": paper_title,
            "question_count": len(paper.questions),
            "dedup_status": dedup_status,
            "region_check": region_result,
            "similar_papers": dedup_result.get("similar_papers", []),
        }


# ============ 课标契合度分析 ============

@app.post("/api/papers/{paper_id}/curriculum-analysis")
async def analyze_curriculum(paper_id: int):
    async for db in get_db():
        paper = await db.execute_fetchone("SELECT * FROM papers WHERE id = ?", (paper_id,))
        if not paper:
            raise HTTPException(404, "试卷不存在")

        questions = await db.execute_fetchall(
            "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
        )
        if not questions:
            raise HTTPException(400, "该试卷没有题目，无法分析")

        q_data = []
        for q in questions:
            kps = json.loads(q["knowledge_points"]) if q["knowledge_points"] else []
            q_data.append({
                "knowledge_points": kps,
                "content": q["content"] or "",
                "q_type": q["q_type"],
                "score": q["score"],
            })

        result = curriculum_analyzer.analyze_paper(q_data, paper["subject_id"])

        await db.execute(
            "UPDATE papers SET curriculum_score=?, curriculum_json=? WHERE id=?",
            (result["curriculum_score"], json.dumps(result, ensure_ascii=False), paper_id),
        )

        cognitive_map = curriculum_analyzer.COGNITIVE_MAP.get(paper["subject_id"], {})
        competency_map = curriculum_analyzer.COMPETENCY_MAP.get(paper["subject_id"], {})

        for q in questions:
            kps = json.loads(q["knowledge_points"]) if q["knowledge_points"] else []
            levels = set()
            for kp in kps:
                level = cognitive_map.get(kp)
                if level:
                    levels.add(level)
            cognitive = ",".join(sorted(levels)) if levels else None

            comps = set()
            for kp in kps:
                parent = kp.rsplit(".", 1)[0] if "." in kp else kp
                for comp in competency_map.get(parent, []):
                    comps.add(comp)
            competency = ",".join(sorted(comps)) if comps else None

            if cognitive or competency:
                await db.execute(
                    "UPDATE questions SET cognitive_level=?, core_competency=? WHERE id=?",
                    (cognitive, competency, q["id"]),
                )

        await db.commit()
        return result


# ============ 题目质量评估 ============

@app.post("/api/papers/{paper_id}/quality-analysis")
async def analyze_quality(paper_id: int):
    async for db in get_db():
        paper = await db.execute_fetchone("SELECT * FROM papers WHERE id = ?", (paper_id,))
        if not paper:
            raise HTTPException(404, "试卷不存在")

        questions = await db.execute_fetchall(
            "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
        )
        if not questions:
            raise HTTPException(400, "该试卷没有题目")

        q_data = []
        for q in questions:
            kps = json.loads(q["knowledge_points"]) if q["knowledge_points"] else []
            q_data.append({
                "irt_a": q["irt_a"],
                "irt_b": q["irt_b"],
                "irt_c": q["irt_c"],
                "q_type": q["q_type"],
                "score": q["score"],
                "content": q["content"] or "",
                "knowledge_points": kps,
                "cognitive_level": q.get("cognitive_level"),
                "q_number": q["q_number"],
            })

        result = quality_scorer.score_paper(q_data)

        for qs in result.get("question_scores", []):
            q_idx = qs["question_index"]
            if q_idx < len(questions):
                q_id = questions[q_idx]["id"]
                await db.execute(
                    "UPDATE questions SET quality_rating=?, is_quality=? WHERE id=?",
                    (qs["quality_rating"], 1 if qs["is_quality"] else 0, q_id),
                )

        await db.execute(
            "UPDATE papers SET quality_score=?, quality_json=? WHERE id=?",
            (result["overall_score"], json.dumps(result, ensure_ascii=False), paper_id),
        )

        await db.commit()
        return result


# ============ 优质题推荐 ============

@app.get("/api/quality-questions")
async def get_quality_questions(
    subject: Optional[str] = None,
    q_type: Optional[str] = None,
    min_score: float = 85,
    limit: int = 50,
):
    async for db in get_db():
        conditions = ["q.is_quality = 1"]
        params = []
        if subject:
            conditions.append("p.subject_id = ?")
            params.append(subject)
        if q_type:
            conditions.append("q.q_type = ?")
            params.append(q_type)

        where = "WHERE " + " AND ".join(conditions)
        rows = await db.execute_fetchall(
            f"""SELECT q.*, p.title as paper_title, p.subject_id, p.year, p.province
                FROM questions q JOIN papers p ON q.paper_id = p.id
                {where}
                ORDER BY q.discrimination DESC
                LIMIT ?""",
            params + [limit],
        )
        return {"total": len(rows), "data": rows}


# ============ 批量操作 ============

@app.post("/api/papers/batch/estimate-irt")
async def batch_estimate_irt(
    subject: Optional[str] = None,
    paper_type: Optional[str] = None,
    limit: int = 50,
):
    async for db in get_db():
        conditions = []
        params = []
        base_where = "id IN (SELECT DISTINCT paper_id FROM questions WHERE irt_a IS NULL)"

        if subject:
            conditions.append("subject_id = ?")
            params.append(subject)
        if paper_type:
            conditions.append("paper_type = ?")
            params.append(paper_type)

        where = f"WHERE {base_where}"
        if conditions:
            where += " AND " + " AND ".join(conditions)

        rows = await db.execute_fetchall(
            f"SELECT id FROM papers {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )

        estimated = []
        for row in rows:
            paper_id = row["id"]
            questions = await db.execute_fetchall(
                "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
            )
            if not questions:
                continue
            if questions[0].get("irt_a") is not None:
                continue

            n_q = len(questions)
            rng = np.random.default_rng(42)
            thetas = rng.normal(0, 1, 5000)

            response_matrix = np.zeros((5000, n_q), dtype=int)
            for j, q in enumerate(questions):
                q_type = q["q_type"]
                if q_type == "choice":
                    p_correct = rng.uniform(0.50, 0.85)
                elif q_type == "fill":
                    p_correct = rng.uniform(0.25, 0.60)
                else:
                    p_correct = rng.uniform(0.10, 0.50)
                difficulty_ramp = min(j / max(n_q - 1, 1) * 0.3, 0.3)
                p_correct = max(0.05, p_correct - difficulty_ramp)
                response_matrix[:, j] = rng.binomial(1, p_correct, 5000)
            params_list = irt_model.estimate_all_questions(thetas, response_matrix)

            for j, params in enumerate(params_list):
                q = questions[j]
                await db.execute(
                    "UPDATE questions SET irt_a=?, irt_b=?, irt_c=?, discrimination=? WHERE id=?",
                    (params["a"], params["b"], params["c"], params["a"], q["id"]),
                )

            await db.execute(
                "UPDATE papers SET analysis_status='irt_estimated', difficulty=? WHERE id=?",
                (float(np.mean([p["b"] for p in params_list])), paper_id),
            )
            estimated.append(paper_id)

        await db.commit()
        return {"estimated_count": len(estimated), "paper_ids": estimated}


@app.post("/api/papers/batch/simulate")
async def batch_simulate(
    subject: Optional[str] = None,
    n_students: Optional[int] = None,
    limit: int = 10,
):
    n = n_students or MC_CONFIG["n_students"]
    async for db in get_db():
        conditions = ["analysis_status = 'irt_estimated'"]
        params = []
        if subject:
            conditions.append("subject_id = ?")
            params.append(subject)

        where = "WHERE " + " AND ".join(conditions)
        rows = await db.execute_fetchall(
            f"SELECT id FROM papers {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )

        simulated = []
        for row in rows:
            paper_id = row["id"]
            questions = await db.execute_fetchall(
                "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
            )
            if not questions or questions[0]["irt_a"] is None:
                continue

            item_params = [
                {"a": q["irt_a"], "b": q["irt_b"], "c": q["irt_c"]}
                for q in questions
            ]
            q_scores = [q["score"] for q in questions]

            # v5.0: 传入 subject_id 用于校准
            paper_info = await db.execute_fetchone("SELECT subject_id FROM papers WHERE id = ?", (paper_id,))
            subject_id = paper_info["subject_id"] if paper_info else "math"

            result = simulator.simulate(item_params, q_scores, n_students=n, subject_id=subject_id)

            await db.execute(
                """INSERT INTO analysis_results
                   (paper_id, simulation_mean, simulation_std, simulation_median, simulation_json,
                    score_distribution_json, analysis_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (paper_id, result["mean"], result["std"], result["median"],
                 json.dumps(result, ensure_ascii=False),
                 json.dumps(result["score_distribution"], ensure_ascii=False),
                 json.dumps(result, ensure_ascii=False)),
            )
            await db.execute(
                "UPDATE papers SET analysis_status='simulated', simulation_json=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False), paper_id),
            )
            simulated.append(paper_id)

        await db.commit()
        return {"simulated_count": len(simulated), "n_students": n, "paper_ids": simulated}


# ============ IRT 参数估计 ============

@app.post("/api/papers/{paper_id}/estimate-irt")
async def estimate_irt(paper_id: int, n_sim_students: int = 5000):
    async for db in get_db():
        questions = await db.execute_fetchall(
            "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
        )
        if not questions:
            raise HTTPException(404, "该试卷没有题目")

        n_q = len(questions)
        rng = np.random.default_rng(42)
        thetas = rng.normal(0, 1, n_sim_students)

        response_matrix = np.zeros((n_sim_students, n_q), dtype=int)
        for j, q in enumerate(questions):
            q_type = q["q_type"]
            if q_type == "choice":
                p_correct = rng.uniform(0.50, 0.85)
            elif q_type == "fill":
                p_correct = rng.uniform(0.25, 0.60)
            else:
                p_correct = rng.uniform(0.10, 0.50)
            difficulty_ramp = min(j / max(n_q - 1, 1) * 0.3, 0.3)
            p_correct = max(0.05, p_correct - difficulty_ramp)
            response_matrix[:, j] = rng.binomial(1, p_correct, n_sim_students)

        params_list = irt_model.estimate_all_questions(thetas, response_matrix)

        for j, params in enumerate(params_list):
            q = questions[j]
            await db.execute(
                "UPDATE questions SET irt_a=?, irt_b=?, irt_c=?, discrimination=? WHERE id=?",
                (params["a"], params["b"], params["c"], params["a"], q["id"]),
            )

        await db.execute(
            "UPDATE papers SET analysis_status='irt_estimated', difficulty=? WHERE id=?",
            (float(np.mean([p["b"] for p in params_list])), paper_id),
        )
        await db.commit()

        return {
            "paper_id": paper_id,
            "estimated": len(params_list),
            "params": params_list,
        }


# ============ 蒙特卡洛模拟 ============

@app.post("/api/papers/{paper_id}/simulate")
async def run_simulation(paper_id: int, n_students: Optional[int] = None):
    n = n_students or MC_CONFIG["n_students"]

    item_params = None
    q_scores = None
    subject_id = "math"

    async for db in get_db():
        questions = await db.execute_fetchall(
            "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
        )
        if not questions:
            raise HTTPException(404, "该试卷没有题目")

        if questions[0]["irt_a"] is None:
            raise HTTPException(400, "请先估计 IRT 参数")

        item_params = [
            {"a": q["irt_a"], "b": q["irt_b"], "c": q["irt_c"]}
            for q in questions
        ]
        q_scores = [q["score"] for q in questions]

        # v5.0: 获取 subject_id 用于校准
        paper = await db.execute_fetchone("SELECT subject_id FROM papers WHERE id = ?", (paper_id,))
        if paper:
            subject_id = paper["subject_id"]

    result = simulator.simulate(item_params, q_scores, n_students=n, subject_id=subject_id)

    async for db in get_db():
        await db.execute(
            """INSERT INTO analysis_results
               (paper_id, simulation_mean, simulation_std, simulation_median, simulation_json, score_distribution_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (paper_id, result["mean"], result["std"], result["median"],
             json.dumps(result, ensure_ascii=False),
             json.dumps(result["score_distribution"], ensure_ascii=False)),
        )
        await db.execute(
            "UPDATE papers SET analysis_status='simulated', simulation_json=? WHERE id=?",
            (json.dumps(result, ensure_ascii=False), paper_id),
        )
        await db.commit()

    return result


# ============ 拟合分析 ============

@app.post("/api/analysis/fit")
async def fit_analysis(
    sim_paper_id: int = Query(..., description="模拟卷 ID"),
    ref_paper_id: int = Query(..., description="真题 ID"),
    subject: str = Query("math"),
):
    sim_qs = None
    ref_qs = None

    async for db in get_db():
        sim_rows = await db.execute_fetchall(
            "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (sim_paper_id,)
        )
        ref_rows = await db.execute_fetchall(
            "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (ref_paper_id,)
        )
        sim_qs = sim_rows
        ref_qs = ref_rows

    if not sim_qs or not ref_qs:
        raise HTTPException(404, "试卷或题目不存在")

    sim_paper = {
        "questions": [
            {
                "q_type": q["q_type"], "score": q["score"],
                "irt_a": q["irt_a"] or 1.0, "irt_b": q["irt_b"] or 0.0, "irt_c": q["irt_c"] or 0.0,
                "knowledge_points": json.loads(q["knowledge_points"]) if q["knowledge_points"] else [],
            }
            for q in sim_qs
        ]
    }
    ref_paper = {
        "questions": [
            {
                "q_type": q["q_type"], "score": q["score"],
                "irt_a": q["irt_a"] or 1.0, "irt_b": q["irt_b"] or 0.0, "irt_c": q["irt_c"] or 0.0,
                "knowledge_points": json.loads(q["knowledge_points"]) if q["knowledge_points"] else [],
            }
            for q in ref_qs
        ]
    }

    result = fitting_analyzer.full_analysis(sim_paper, ref_paper, subject)

    sim_params = [{"a": q["irt_a"], "b": q["irt_b"], "c": q["irt_c"]} for q in sim_paper["questions"]]
    sim_scores = [q["score"] for q in sim_paper["questions"]]
    ref_params = [{"a": q["irt_a"], "b": q["irt_b"], "c": q["irt_c"]} for q in ref_paper["questions"]]
    ref_scores = [q["score"] for q in ref_paper["questions"]]

    comp = simulator.simulate_comparison(ref_params, ref_scores, sim_params, sim_scores, subject_id=subject)
    result["comparison"] = comp

    async for db in get_db():
        await db.execute(
            """INSERT INTO analysis_results
               (paper_id, ref_paper_id, fit_score, knowledge_coverage, difficulty_ks_stat,
                difficulty_ks_pvalue, question_type_match, quality_score, analysis_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sim_paper_id, ref_paper_id, result["fit_score"],
             json.dumps(result["knowledge_coverage"], ensure_ascii=False),
             result["difficulty_fit"]["ks_stat"], result["difficulty_fit"]["ks_pvalue"],
             json.dumps(result["question_type_match"], ensure_ascii=False),
             result["quality"],
             json.dumps(result, ensure_ascii=False)),
        )
        await db.commit()

    return result


# ============ 爬取相关 ============

@app.get("/api/scrape/status")
async def scrape_status():
    async for db in get_db():
        total = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM papers")
        by_type = await db.execute_fetchall(
            "SELECT paper_type, COUNT(*) as cnt FROM papers GROUP BY paper_type"
        )
        by_subject = await db.execute_fetchall(
            "SELECT subject_id, COUNT(*) as cnt FROM papers GROUP BY subject_id"
        )
        by_year = await db.execute_fetchall(
            "SELECT year, COUNT(*) as cnt FROM papers GROUP BY year ORDER BY year"
        )
        by_province = await db.execute_fetchall(
            "SELECT province, COUNT(*) as cnt FROM papers WHERE province IS NOT NULL GROUP BY province ORDER BY cnt DESC LIMIT 20"
        )
        by_priority = await db.execute_fetchall(
            "SELECT source_priority, COUNT(*) as cnt FROM papers GROUP BY source_priority"
        )
        dedup_stats = await db.execute_fetchall(
            "SELECT dedup_status, COUNT(*) as cnt FROM papers GROUP BY dedup_status"
        )
        recent_logs = await db.execute_fetchall(
            "SELECT * FROM scrape_logs ORDER BY created_at DESC LIMIT 20"
        )
        return {
            "total_papers": total["cnt"] if total else 0,
            "by_type": {r["paper_type"]: r["cnt"] for r in by_type},
            "by_subject": {r["subject_id"]: r["cnt"] for r in by_subject},
            "by_year": {str(r["year"]): r["cnt"] for r in by_year},
            "top_provinces": {r["province"]: r["cnt"] for r in by_province},
            "by_priority": {r["source_priority"]: r["cnt"] for r in by_priority},
            "dedup_stats": {r["dedup_status"]: r["cnt"] for r in dedup_stats},
            "recent_logs": recent_logs,
            "auto_scraper_status": auto_scraper.get_status() if auto_scraper else None,
        }


@app.post("/api/scrape/collect")
async def collect_papers(
    year: int = 2026,
    subjects: Optional[str] = None,
    keyword: Optional[str] = None,
):
    sub_list = subjects.split(",") if subjects else None
    results = await scraper_manager.collect_all(year, sub_list, keyword=keyword or "")

    saved = []
    skipped = []
    async for db in get_db():
        for item in results:
            if "error" in item:
                await db.execute(
                    "INSERT INTO scrape_logs (source_id, url, status, error_msg) VALUES (?,?,?,?)",
                    (item.get("source_id"), "", "error", item.get("error", "")),
                )
                continue

            dedup_result = await dedup_engine.check_duplicate(
                title=item.get("title", ""),
                subject_id=item.get("subject", "math"),
                year=item.get("year", year),
                source_url=item.get("url", ""),
            )

            if dedup_result["status"] == "duplicate":
                await db.execute(
                    "INSERT INTO scrape_logs (source_id, url, status, dedup_result) VALUES (?,?,?,?)",
                    (item.get("source_id"), item.get("url"), "skipped", "duplicate"),
                )
                skipped.append(item.get("title"))
                continue

            existing = await db.execute_fetchone(
                "SELECT id FROM papers WHERE source_url = ?", (item.get("url"),)
            )
            if existing:
                continue

            file_path = None
            if item.get("url"):
                ext = scraper_manager._guess_extension(item["url"])
                filename = f"{item.get('title', 'unknown')[:50]}_{hashlib.md5(item['url'].encode()).hexdigest()[:8]}{ext}"
                file_path = os.path.join(DOWNLOAD_DIR, filename)

            content_hash = dedup_result.get("content_hash", "")
            dedup_status = dedup_result["status"]

            # v5.0: 地区校验
            region_result = RegionValidator.validate_region(
                province=item.get("province", ""),
                title=item.get("title", ""),
            )
            corrected_province = region_result["province"] or item.get("province")

            cursor = await db.execute(
                """INSERT INTO papers
                   (title, subject_id, paper_type, source_id, source_url, year, province,
                    file_path, analysis_status, content_hash, dedup_status, source_priority,
                    collected_at, collector)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, datetime('now'), 'system')""",
                (
                    item.get("title", ""),
                    item.get("subject", "math"),
                    item.get("type", "school"),
                    item.get("source_id", ""),
                    item.get("url", ""),
                    item.get("year", year),
                    corrected_province,
                    file_path,
                    content_hash,
                    dedup_status,
                    item.get("priority", "B"),
                ),
            )
            paper_id = cursor.lastrowid
            saved.append(paper_id)

            for sp in dedup_result.get("similar_papers", []):
                await db.execute(
                    """INSERT INTO dedup_records (paper_id_1, paper_id_2, similarity, method, status)
                       VALUES (?, ?, ?, ?, ?)""",
                    (paper_id, sp["paper_id"], sp["similarity"], sp["method"], "pending"),
                )

            await db.execute(
                "INSERT INTO scrape_logs (source_id, url, status, paper_id, dedup_result) VALUES (?,?,?,?,?)",
                (item.get("source_id"), item.get("url"), "success", paper_id, dedup_status),
            )

        await db.commit()
    return {
        "found": len(results),
        "saved": len(saved),
        "skipped_duplicates": len(skipped),
        "paper_ids": saved,
    }


# ============ v5.0: 自动采集状态 ============

@app.get("/api/auto-scraper/status")
async def auto_scraper_status():
    if not auto_scraper:
        return {"running": False, "error": "Auto-scraper not initialized"}
    return auto_scraper.get_status()


@app.post("/api/auto-scraper/trigger")
async def trigger_auto_scrape():
    """手动触发一次自动采集"""
    if not auto_scraper:
        raise HTTPException(500, "Auto-scraper not initialized")
    asyncio.create_task(auto_scraper._run_once())
    return {"triggered": True}


# ============ v5.0: 官方文件库 API ============

@app.get("/api/official-docs")
async def list_official_docs(
    keyword: str = "",
    category: str = "",
    year: Optional[int] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    return await official_docs.search_docs(
        keyword=keyword, category=category, year=year, page=page, size=size,
    )


@app.get("/api/official-docs/categories")
async def list_doc_categories():
    return await official_docs.get_categories()


@app.post("/api/official-docs/refresh")
async def refresh_official_docs():
    result = await official_docs.refresh_from_official_sources()
    return result


# ============ v5.0: 真实性审核 API ============

@app.post("/api/audit/paper/{paper_id}")
async def audit_paper(paper_id: int):
    result = await AuthVerifier.audit_paper(
        paper_id, deepseek_key=DEEPSEEK_CONFIG.get("api_key", "")
    )
    return result


@app.post("/api/audit/batch")
async def batch_audit(limit: int = 100, unverified_only: bool = True):
    result = await AuthVerifier.batch_audit(limit=limit, unverified_only=unverified_only)
    return result


@app.get("/api/audit/summary")
async def audit_summary():
    return await AuthVerifier.get_audit_summary()


# ============ v5.0: 交叉验证 API ============

@app.post("/api/verify/paper")
async def verify_paper_authenticity(
    title: str = Query(...),
    subject_id: str = Query(...),
    year: int = Query(...),
    province: str = "",
):
    result = await CrossVerifier.verify_paper(
        title=title, subject_id=subject_id, year=year, province=province,
        deepseek_key=DEEPSEEK_CONFIG.get("api_key", ""),
    )
    return result


# ============ v5.0: 校准数据 API ============

@app.get("/api/calibration")
async def get_calibration_data():
    return CALIBRATION_DATA


# ============ 知识点 ============

@app.get("/api/knowledge-points/{subject_id}")
async def list_knowledge_points(subject_id: str):
    async for db in get_db():
        rows = await db.execute_fetchall(
            "SELECT * FROM knowledge_points WHERE subject_id = ? ORDER BY code", (subject_id,)
        )
        return rows


# ============ 筛选元数据 ============

@app.get("/api/filters")
async def get_filter_options():
    async for db in get_db():
        provinces = await db.execute_fetchall(
            "SELECT DISTINCT province FROM papers WHERE province IS NOT NULL AND province != '' ORDER BY province"
        )
        exam_tags = await db.execute_fetchall(
            "SELECT DISTINCT exam_tag FROM papers WHERE exam_tag IS NOT NULL AND exam_tag != '' ORDER BY exam_tag"
        )
        schools = await db.execute_fetchall(
            "SELECT DISTINCT school FROM papers WHERE school IS NOT NULL AND school != '' ORDER BY school LIMIT 30"
        )
        years = await db.execute_fetchall(
            "SELECT DISTINCT year FROM papers WHERE year IS NOT NULL ORDER BY year DESC"
        )
        return {
            "provinces": [r["province"] for r in provinces if r["province"]],
            "exam_tags": [r["exam_tag"] for r in exam_tags if r["exam_tag"]],
            "schools": [r["school"] for r in schools if r["school"]],
            "years": [r["year"] for r in years if r["year"]],
            "paper_types": PAPER_TYPES,
            "source_priorities": SOURCE_PRIORITY_MAP,
            "subjects": [{"id": k, **v} for k, v in SUBJECTS.items()],
            "regions": REGION_HIERARCHY,
        }


# ============ 仪表盘统计 ============

@app.get("/api/dashboard")
async def dashboard_stats():
    async for db in get_db():
        total_papers = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM papers")
        analyzed = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE analysis_status IN ('irt_estimated', 'simulated')"
        )
        simulated = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE analysis_status = 'simulated'"
        )
        real_count = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE paper_type = 'real'"
        )
        mock_count = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE paper_type != 'real'"
        )
        quality_count = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM questions WHERE is_quality = 1"
        )
        verified_count = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE verified = 1"
        )
        dedup_unique = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE dedup_status = 'unique' OR dedup_status IS NULL"
        )
        dedup_suspected = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM papers WHERE dedup_status = 'suspected'"
        )
        docs_count = await db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM official_docs"
        )

        by_subject = await db.execute_fetchall(
            "SELECT subject_id, COUNT(*) as cnt FROM papers GROUP BY subject_id"
        )
        by_year = await db.execute_fetchall(
            "SELECT year, COUNT(*) as cnt FROM papers GROUP BY year ORDER BY year"
        )
        by_type = await db.execute_fetchall(
            "SELECT paper_type, COUNT(*) as cnt FROM papers GROUP BY paper_type"
        )

        latest = await db.execute_fetchall(
            """SELECT id, title, subject_id, paper_type, year, province,
                      analysis_status, curriculum_score, quality_score,
                      source_priority, verified, dedup_status
               FROM papers
               ORDER BY created_at DESC LIMIT 10"""
        )

        # v5.0: 审核概况
        audit_summary_data = await AuthVerifier.get_audit_summary()

        return {
            "total_papers": total_papers["cnt"] if total_papers else 0,
            "analyzed_papers": analyzed["cnt"] if analyzed else 0,
            "simulated_papers": simulated["cnt"] if simulated else 0,
            "real_count": real_count["cnt"] if real_count else 0,
            "mock_count": mock_count["cnt"] if mock_count else 0,
            "quality_questions": quality_count["cnt"] if quality_count else 0,
            "verified_count": verified_count["cnt"] if verified_count else 0,
            "dedup_unique": dedup_unique["cnt"] if dedup_unique else 0,
            "dedup_suspected": dedup_suspected["cnt"] if dedup_suspected else 0,
            "official_docs_count": docs_count["cnt"] if docs_count else 0,
            "by_subject": {r["subject_id"]: r["cnt"] for r in by_subject},
            "by_year": {str(r["year"]): r["cnt"] for r in by_year},
            "by_type": {r["paper_type"]: r["cnt"] for r in by_type},
            "latest_papers": latest,
            "audit_summary": audit_summary_data,
            "auto_scraper_status": auto_scraper.get_status() if auto_scraper else None,
        }
