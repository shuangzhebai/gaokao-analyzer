"""
试卷 DAO：封装 papers 表的所有 SQL 操作（aiosqlite，不引入 ORM）。
"""
from typing import Any, Optional


class PaperRepository:
    """试卷数据访问对象"""

    async def list_papers(
        self, db: Any,
        subject: Optional[str] = None,
        paper_type: Optional[str] = None,
        year: Optional[int] = None,
        province: Optional[str] = None,
        analysis_status: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """分页查询试卷列表，排除 duplicate 状态的试卷。
        
        P2-02: tenant_id 参数实现多租户数据隔离。
        """
        conditions: list[str] = []
        params: list[Any] = []
        # 多租户隔离
        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
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

    async def get_by_id(self, db: Any, paper_id: int) -> Any:
        """根据主键获取试卷"""
        return await db.execute_fetchone("SELECT * FROM papers WHERE id = ?", (paper_id,))

    async def get_source_by_id(self, db: Any, source_id: str) -> Any:
        """获取数据源信息"""
        return await db.execute_fetchone("SELECT * FROM sources WHERE id = ?", (source_id,))

    async def create(self, db: Any, data: dict[str, Any]) -> Any:
        """插入一条试卷记录，返回自增 id。"""
        cursor = await db.execute(
            """INSERT INTO papers
               (title, subject_id, paper_type, file_path, analysis_status, total_score,
                content_hash, dedup_status, year, question_count, source_priority, collector,
                province, source_id, source_url, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("title", ""),
                data.get("subject_id", "math"),
                data.get("paper_type", "school"),
                data.get("file_path"),
                data.get("analysis_status", "pending"),
                data.get("total_score", 150),
                data.get("content_hash", ""),
                data.get("dedup_status", "unique"),
                data.get("year", 2026),
                data.get("question_count", 0),
                data.get("source_priority", "C"),
                data.get("collector", "manual"),
                data.get("province", ""),
                data.get("source_id"),
                data.get("source_url"),
                data.get("collected_at"),
            ),
        )
        return cursor.lastrowid

    async def delete(self, db: Any, paper_id: int) -> None:
        """删除试卷及其关联数据。事务包裹防部分删除。"""
        await db.execute("BEGIN")
        try:
            await db.execute("DELETE FROM questions WHERE paper_id = ?", (paper_id,))
            await db.execute("DELETE FROM analysis_results WHERE paper_id = ?", (paper_id,))
            await db.execute(
                "DELETE FROM dedup_records WHERE paper_id_1 = ? OR paper_id_2 = ?",
                (paper_id, paper_id),
            )
            await db.execute("DELETE FROM verification_audit WHERE paper_id = ?", (paper_id,))
            await db.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
            await db.execute("COMMIT")
        except Exception:
            await db.execute("ROLLBACK")
            raise

    async def update_analysis_status(self, db: Any, paper_id: int, status: str) -> None:
        """更新分析状态"""
        await db.execute(
            "UPDATE papers SET analysis_status = ? WHERE id = ?",
            (status, paper_id),
        )

    async def update_difficulty(self, db: Any, paper_id: int, difficulty: float) -> None:
        """更新试卷难度"""
        await db.execute(
            "UPDATE papers SET difficulty = ? WHERE id = ?",
            (difficulty, paper_id),
        )

    async def update_curriculum(self, db: Any, paper_id: int, score: float, json_data: str) -> None:
        """更新课标契合度分析结果"""
        await db.execute(
            "UPDATE papers SET curriculum_score=?, curriculum_json=? WHERE id=?",
            (score, json_data, paper_id),
        )

    async def update_quality(self, db: Any, paper_id: int, score: float, json_data: str) -> None:
        """更新质量评估结果"""
        await db.execute(
            "UPDATE papers SET quality_score=?, quality_json=? WHERE id=?",
            (score, json_data, paper_id),
        )

    async def update_simulation_json(self, db: Any, paper_id: int, json_data: str) -> None:
        """更新模拟结果 JSON"""
        await db.execute(
            "UPDATE papers SET simulation_json=? WHERE id=?",
            (json_data, paper_id),
        )

    async def update_verified(self, db: Any, paper_id: int, verified: int) -> None:
        """更新验证状态"""
        await db.execute(
            "UPDATE papers SET verified = ? WHERE id = ?",
            (verified, paper_id),
        )

    async def update_province(self, db: Any, paper_id: int, province: str) -> None:
        """更新省份信息"""
        await db.execute(
            "UPDATE papers SET province = ? WHERE id = ?",
            (province, paper_id),
        )

    async def get_dashboard_stats(self, db: Any) -> dict[str, Any]:
        """聚合仪表盘统计数据"""
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
        }

    async def get_filter_options(self, db: Any) -> dict[str, Any]:
        """获取筛选元数据（省份、考试标签、学校、年份）"""
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
        }

    async def get_latest(self, db: Any, limit: int = 10) -> Any:
        """获取最新试卷列表"""
        return await db.execute_fetchall(
            """SELECT id, title, subject_id, paper_type, year, province,
                      analysis_status, curriculum_score, quality_score,
                      source_priority, verified, dedup_status
               FROM papers
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        )

    async def list_pending_irt(
        self, db: Any,
        subject: Optional[str] = None,
        paper_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[int]:
        """列出待 IRT 估算的试卷 ID"""
        conditions = ["id IN (SELECT DISTINCT paper_id FROM questions WHERE irt_a IS NULL)"]
        params = []
        if subject:
            conditions.append("subject_id = ?")
            params.append(subject)
        if paper_type:
            conditions.append("paper_type = ?")
            params.append(paper_type)

        where = "WHERE " + " AND ".join(conditions)
        rows = await db.execute_fetchall(
            f"SELECT id FROM papers {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )
        return [r["id"] for r in rows]

    async def list_by_status(
        self, db: Any,
        status: str,
        subject: Optional[str] = None,
        limit: int = 10,
    ) -> list[int]:
        """按分析状态列出试卷 ID"""
        conditions = ["analysis_status = ?"]
        params = [status]
        if subject:
            conditions.append("subject_id = ?")
            params.append(subject)

        where = "WHERE " + " AND ".join(conditions)
        rows = await db.execute_fetchall(
            f"SELECT id FROM papers {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        )
        return [r["id"] for r in rows]

    async def get_subject_id(self, db: Any, paper_id: int) -> Optional[str]:
        """获取试卷的科目 ID"""
        row = await db.execute_fetchone(
            "SELECT subject_id FROM papers WHERE id = ?", (paper_id,)
        )
        return row["subject_id"] if row else None

    async def exists_by_source_url(self, db: Any, source_url: str) -> bool:
        """检查 source_url 是否已存在"""
        row = await db.execute_fetchone(
            "SELECT id FROM papers WHERE source_url = ?", (source_url,)
        )
        return row is not None

    async def get_papers_for_batch_fix(self, db: Any, limit: int = 100) -> Any:
        """获取待批量纠正地区的试卷（limit 1-1000）。"""
        limit = max(1, min(limit, 1000))
        return await db.execute_fetchall(
            "SELECT id, title, province, school FROM papers LIMIT ?", (limit,)
        )
