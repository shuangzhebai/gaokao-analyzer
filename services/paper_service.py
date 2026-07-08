"""
试卷业务层：封装试卷 CRUD、上传、删除、仪表盘等业务编排。
每个方法第一个参数为 db（从路由层传入），写操作后负责 db.commit()。
"""
import hashlib
import json
import os
from typing import Any, Optional

import numpy as np
from fastapi import HTTPException

from config import DOWNLOAD_DIR, MC_CONFIG, SOURCE_PRIORITY_MAP
from region_validator import RegionValidator
from repositories.paper_repo import PaperRepository
from repositories.question_repo import QuestionRepository
from repositories.analysis_repo import AnalysisRepository


class PaperService:
    """试卷业务服务"""

    def __init__(
        self,
        paper_repo: PaperRepository,
        question_repo: QuestionRepository,
        analysis_repo: AnalysisRepository,
    ):
        self.paper_repo = paper_repo
        self.question_repo = question_repo
        self.analysis_repo = analysis_repo

    async def list_papers(self, db: Any, subject: Optional[str] = None, paper_type: Optional[str] = None, year: Optional[int] = None,
                          province: Optional[str] = None, analysis_status: Optional[str] = None,
                          page: int = 1, size: int = 20,
                          tenant_id: Optional[str] = None) -> dict[str, Any]:
        """分页查询试卷列表（P2-02: 多租户隔离）"""
        return await self.paper_repo.list_papers(
            db, subject=subject, paper_type=paper_type, year=year,
            province=province, analysis_status=analysis_status,
            page=page, size=size, tenant_id=tenant_id,
        )

    async def get_paper(self, db: Any, paper_id: int) -> dict[str, Any]:
        """获取试卷详情（含题目、分析结果、来源、地区校验）"""
        paper = await self.paper_repo.get_by_id(db, paper_id)
        if not paper:
            raise HTTPException(404, "试卷不存在")

        questions = await self.question_repo.list_by_paper(db, paper_id)
        analyses = await self.analysis_repo.get_by_paper(db, paper_id)

        source = None
        if paper.get("source_id"):
            source = await self.paper_repo.get_source_by_id(db, paper["source_id"])

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

    async def delete_paper(self, db: Any, paper_id: int) -> None:
        """删除试卷"""
        paper = await self.paper_repo.get_by_id(db, paper_id)
        if not paper:
            raise HTTPException(404, "试卷不存在")
        await self.paper_repo.delete(db, paper_id)
        await db.commit()

    async def upload_paper(
        self, db: Any, file: Any, subject: str, paper_type: str, title: Optional[str], year: int, province: Optional[str],
        paper_parser: Any, kp_mapper: Any, dedup_engine: Any,
    ) -> dict[str, Any]:
        """上传并解析试卷"""
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        safe_filename = os.path.basename(file.filename or "")
        if not safe_filename:
            raise HTTPException(400, "文件名不能为空")

        ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".html", ".json", ".md"}
        ext = os.path.splitext(safe_filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                400,
                f"不允许的文件类型: {ext}，仅支持 {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        MAX_UPLOAD_SIZE = 50 * 1024 * 1024
        save_path = os.path.join(DOWNLOAD_DIR, safe_filename)
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                413,
                f"文件过大（最大 50MB），实际 {len(content) / 1024 / 1024:.1f}MB",
            )
        with open(save_path, "wb") as f:
            f.write(content)

        paper = paper_parser.parse_file(save_path, subject)
        paper_title = title or paper.title or file.filename

        region_result = RegionValidator.validate_region(
            province=province or "",
            title=paper_title,
        )
        corrected_province = region_result["province"] or province or ""

        dedup_result = await dedup_engine.check_duplicate(
            title=paper_title, subject_id=subject, year=year,
            questions=[{"content": q.content} for q in paper.questions] if paper.questions else [],
            db=db,
        )

        if dedup_result["status"] == "duplicate":
            raise HTTPException(
                409,
                f"试卷与已有试卷重复: {dedup_result['similar_papers'][0]['title']}",
            )

        content_hash = dedup_result.get("content_hash", "")
        dedup_status = dedup_result["status"]

        paper_data = {
            "title": paper_title,
            "subject_id": subject,
            "paper_type": paper_type,
            "file_path": save_path,
            "analysis_status": "parsed",
            "total_score": paper.total_score,
            "content_hash": content_hash,
            "dedup_status": dedup_status,
            "year": year,
            "question_count": len(paper.questions),
            "source_priority": "C",
            "collector": "manual",
            "province": corrected_province,
        }
        paper_id = await self.paper_repo.create(db, paper_data)

        for q in paper.questions:
            kp_codes = kp_mapper.map_question(q.content, subject)
            q_hash = hashlib.sha256((q.content or "").encode("utf-8")).hexdigest()[:32] if q.content else ""
            q_data = {
                "paper_id": paper_id,
                "q_number": q.number,
                "q_type": q.q_type,
                "content": q.content,
                "options": json.dumps(q.options, ensure_ascii=False) if q.options else None,
                "score": q.score,
                "knowledge_points": json.dumps(kp_codes),
                "content_hash": q_hash,
            }
            await self.question_repo.create(db, q_data)

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

    async def analyze_curriculum(self, db: Any, paper_id: int, curriculum_analyzer: Any) -> Any:
        """课标契合度分析"""
        paper = await self.paper_repo.get_by_id(db, paper_id)
        if not paper:
            raise HTTPException(404, "试卷不存在")

        questions = await self.question_repo.list_by_paper(db, paper_id)
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

        await self.paper_repo.update_curriculum(
            db, paper_id, result["curriculum_score"],
            json.dumps(result, ensure_ascii=False),
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
                await self.question_repo.update_cognitive(db, q["id"], cognitive, competency)

        await db.commit()
        return result

    async def analyze_quality(self, db: Any, paper_id: int, quality_scorer: Any) -> Any:
        """题目质量评估"""
        paper = await self.paper_repo.get_by_id(db, paper_id)
        if not paper:
            raise HTTPException(404, "试卷不存在")

        questions = await self.question_repo.list_by_paper(db, paper_id)
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
                await self.question_repo.update_quality(
                    db, q_id, qs["quality_rating"], 1 if qs["is_quality"] else 0,
                )

        await self.paper_repo.update_quality(
            db, paper_id, result["overall_score"],
            json.dumps(result, ensure_ascii=False),
        )

        await db.commit()
        return result

    async def get_quality_questions(self, db: Any, subject: Optional[str] = None, q_type: Optional[str] = None, limit: int = 50) -> dict[str, Any]:
        """优质题推荐"""
        rows = await self.question_repo.get_quality_questions(
            db, subject=subject, q_type=q_type, limit=limit,
        )
        return {"total": len(rows), "data": rows}

    async def estimate_irt(self, db: Any, paper_id: int, irt_model: Any, n_sim_students: int = 5000) -> dict[str, Any]:
        """单卷 IRT 参数估计"""
        questions = await self.question_repo.list_by_paper(db, paper_id)
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
            await self.question_repo.update_irt(
                db, q["id"], params["a"], params["b"], params["c"], params["a"],
            )

        await self.paper_repo.update_analysis_status(db, paper_id, "irt_estimated")
        await self.paper_repo.update_difficulty(
            db, paper_id, float(np.mean([p["b"] for p in params_list])),
        )
        await db.commit()

        return {
            "paper_id": paper_id,
            "estimated": len(params_list),
            "params": params_list,
        }

    async def batch_estimate_irt(self, db: Any, irt_model: Any, subject: Optional[str] = None, paper_type: Optional[str] = None, limit: int = 50) -> dict[str, Any]:
        """批量 IRT 参数估计"""
        paper_ids = await self.paper_repo.list_pending_irt(
            db, subject=subject, paper_type=paper_type, limit=limit,
        )

        estimated = []
        for paper_id in paper_ids:
            questions = await self.question_repo.list_by_paper(db, paper_id)
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
                await self.question_repo.update_irt(
                    db, q["id"], params["a"], params["b"], params["c"], params["a"],
                )

            await self.paper_repo.update_analysis_status(db, paper_id, "irt_estimated")
            await self.paper_repo.update_difficulty(
                db, paper_id, float(np.mean([p["b"] for p in params_list])),
            )
            estimated.append(paper_id)

        await db.commit()
        return {"estimated_count": len(estimated), "paper_ids": estimated}

    async def run_simulation(self, db: Any, paper_id: int, simulator: Any, n_students: Optional[int] = None) -> Any:
        """单卷蒙特卡洛模拟"""
        n = n_students or MC_CONFIG["n_students"]

        questions = await self.question_repo.list_by_paper(db, paper_id)
        if not questions:
            raise HTTPException(404, "该试卷没有题目")

        if questions[0]["irt_a"] is None:
            raise HTTPException(400, "请先估计 IRT 参数")

        item_params = [
            {"a": q["irt_a"], "b": q["irt_b"], "c": q["irt_c"]}
            for q in questions
        ]
        q_scores = [q["score"] for q in questions]

        subject_id = await self.paper_repo.get_subject_id(db, paper_id) or "math"

        result = simulator.simulate(item_params, q_scores, n_students=n, subject_id=subject_id)

        await self.analysis_repo.create(db, {
            "paper_id": paper_id,
            "simulation_mean": result["mean"],
            "simulation_std": result["std"],
            "simulation_median": result["median"],
            "simulation_json": json.dumps(result, ensure_ascii=False),
            "score_distribution_json": json.dumps(result["score_distribution"], ensure_ascii=False),
            "analysis_json": json.dumps(result, ensure_ascii=False),
        })
        await self.paper_repo.update_analysis_status(db, paper_id, "simulated")
        await self.paper_repo.update_simulation_json(
            db, paper_id, json.dumps(result, ensure_ascii=False),
        )
        await db.commit()

        return result

    async def batch_simulate(self, db: Any, simulator: Any, subject: Optional[str] = None, n_students: Optional[int] = None, limit: int = 10) -> dict[str, Any]:
        """批量蒙特卡洛模拟"""
        n = n_students or MC_CONFIG["n_students"]
        paper_ids = await self.paper_repo.list_by_status(
            db, "irt_estimated", subject=subject, limit=limit,
        )

        simulated = []
        for paper_id in paper_ids:
            questions = await self.question_repo.list_by_paper(db, paper_id)
            if not questions or questions[0]["irt_a"] is None:
                continue

            item_params = [
                {"a": q["irt_a"], "b": q["irt_b"], "c": q["irt_c"]}
                for q in questions
            ]
            q_scores = [q["score"] for q in questions]

            subject_id = await self.paper_repo.get_subject_id(db, paper_id) or "math"

            result = simulator.simulate(item_params, q_scores, n_students=n, subject_id=subject_id)

            await self.analysis_repo.create(db, {
                "paper_id": paper_id,
                "simulation_mean": result["mean"],
                "simulation_std": result["std"],
                "simulation_median": result["median"],
                "simulation_json": json.dumps(result, ensure_ascii=False),
                "score_distribution_json": json.dumps(result["score_distribution"], ensure_ascii=False),
                "analysis_json": json.dumps(result, ensure_ascii=False),
            })
            await self.paper_repo.update_analysis_status(db, paper_id, "simulated")
            await self.paper_repo.update_simulation_json(
                db, paper_id, json.dumps(result, ensure_ascii=False),
            )
            simulated.append(paper_id)

        await db.commit()
        return {"simulated_count": len(simulated), "n_students": n, "paper_ids": simulated}

    async def fit_analysis(
        self, db: Any, sim_paper_id: int, ref_paper_id: int, subject: str,
        fitting_analyzer: Any, simulator: Any,
    ) -> Any:
        """拟合分析（模拟卷 vs 真题）"""
        sim_qs = await self.question_repo.list_by_paper(db, sim_paper_id)
        ref_qs = await self.question_repo.list_by_paper(db, ref_paper_id)

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

        await self.analysis_repo.create(db, {
            "paper_id": sim_paper_id,
            "ref_paper_id": ref_paper_id,
            "fit_score": result["fit_score"],
            "knowledge_coverage": json.dumps(result["knowledge_coverage"], ensure_ascii=False),
            "difficulty_ks_stat": result["difficulty_fit"]["ks_stat"],
            "difficulty_ks_pvalue": result["difficulty_fit"]["ks_pvalue"],
            "question_type_match": json.dumps(result["question_type_match"], ensure_ascii=False),
            "quality_score": result["quality"],
            "analysis_json": json.dumps(result, ensure_ascii=False),
        })
        await db.commit()

        return result

    async def get_filters(self, db: Any) -> dict[str, Any]:
        """获取筛选元数据"""
        filter_data = await self.paper_repo.get_filter_options(db)
        from config import PAPER_TYPES, SOURCE_PRIORITY_MAP, SUBJECTS, REGION_HIERARCHY
        filter_data["paper_types"] = PAPER_TYPES
        filter_data["source_priorities"] = SOURCE_PRIORITY_MAP
        filter_data["subjects"] = [{"id": k, **v} for k, v in SUBJECTS.items()]
        filter_data["regions"] = REGION_HIERARCHY
        return filter_data

    async def get_dashboard(self, db: Any, auto_scraper: Any) -> dict[str, Any]:
        """仪表盘统计"""
        stats = await self.paper_repo.get_dashboard_stats(db)
        latest = await self.paper_repo.get_latest(db)

        from auth_verifier import AuthVerifier
        audit_summary_data = await AuthVerifier.get_audit_summary()

        stats["latest_papers"] = latest
        stats["audit_summary"] = audit_summary_data
        stats["auto_scraper_status"] = auto_scraper.get_status() if auto_scraper else None
        return stats

    async def batch_fix_regions(self, db: Any, limit: int = 100) -> dict[str, Any]:
        """批量纠正试卷地区信息"""
        papers = await self.paper_repo.get_papers_for_batch_fix(db, limit)
        results = RegionValidator.batch_validate(papers)
        fixed_count = 0

        for r in results:
            if r["auto_corrected"] and r["corrected_province"]:
                await self.paper_repo.update_province(db, r["paper_id"], r["corrected_province"])
                fixed_count += 1
        await db.commit()

        return {"checked": len(results), "fixed": fixed_count, "details": results}
