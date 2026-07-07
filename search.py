"""
全文搜索引擎 v5.1 - 基于 SQLite FTS5
支持：关键词搜索、多维度筛选、相关度排序、搜索建议
v5.1: 增强中文分词搜索、多关键词 AND/OR、模糊匹配；统一分词器(tokenizer)；
      修复相关度排序(B-1)；导出 search_similar_titles 供查重复用降级策略(B-3)
"""
import logging
from typing import Optional

from models import get_db
from tokenizer import tokenize

logger = logging.getLogger("gaokao")


class SearchEngine:
    """FTS5 全文搜索引擎"""

    def __init__(self):
        self._subject_names = {
            "chinese": "语文", "math": "数学", "english": "英语",
            "physics": "物理", "chemistry": "化学", "biology": "生物",
            "history": "历史", "geography": "地理", "politics": "政治",
        }

    async def search(
        self,
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
        page: int = 1,
        size: int = 20,
    ) -> dict:
        """
        全文搜索试卷

        Args:
            q: 搜索关键词
            subject: 科目 ID
            paper_type: 试卷类型
            year: 年份
            province: 省份
            exam_tag: 考试标签
            source_priority: 来源可信度
            verified: 是否已验证
            analysis_status: 分析状态
            sort: 排序方式 (relevance/time/priority)
            page: 页码
            size: 每页数量

        Returns:
            { total, page, size, query, data }
        """
        async for db in get_db():
            conditions = []
            params = []
            fts_snippets = None
            matched_ids = None  # 初始化，防止 q 为空格时 NameError

            # FTS5 全文搜索
            if q and q.strip():
                # v5.1: 中文分词 + 多关键词 AND 搜索（统一使用 tokenizer 模块）
                tokens = tokenize(q.strip())
                if not tokens:
                    return {"total": 0, "page": page, "size": size, "query": q, "data": []}

                # 尝试完整短语搜索
                clean_q = q.strip().replace('"', '""')
                fts_match = f'"{clean_q}"'

                fts_sql = f"""
                    SELECT rowid, rank, snippet(papers_fts, '<em>', '</em>', '...', 1, 32) as snippet
                    FROM papers_fts
                    WHERE papers_fts MATCH ?
                    ORDER BY rank
                """
                fts_results = await db.execute_fetchall(fts_sql, [fts_match])

                # 如果短语搜索无结果，尝试多关键词 AND 搜索
                if not fts_results and len(tokens) > 1:
                    and_query = ' AND '.join(f'"{t}"' for t in tokens if len(t) >= 2)
                    if and_query:
                        fts_results = await db.execute_fetchall(
                            fts_sql, [and_query]
                        )

                # 如果 AND 搜索也无结果，尝试 OR 搜索
                if not fts_results and len(tokens) > 1:
                    or_query = ' OR '.join(f'"{t}"' for t in tokens if len(t) >= 2)
                    if or_query:
                        fts_results = await db.execute_fetchall(
                            fts_sql, [or_query]
                        )

                if not fts_results:
                    # FTS 都没结果，降级到 LIKE（逐个 token）
                    like_conditions = []
                    for t in tokens:
                        kw = f"%{t}%"
                        like_conditions.append("(p.title LIKE ? OR p.province LIKE ? OR p.school LIKE ? OR p.exam_tag LIKE ?)")
                        params.extend([kw, kw, kw, kw])
                    conditions.append("(" + " AND ".join(like_conditions) + ")")
                else:
                    matched_ids = [r["rowid"] for r in fts_results]
                    fts_snippets = {r["rowid"]: r["snippet"] for r in fts_results}
                    if matched_ids:
                        placeholders = ",".join("?" * len(matched_ids))
                        conditions.append(f"p.id IN ({placeholders})")
                        params.extend(matched_ids)
                    else:
                        # FTS 返回空结果，直接返回空
                        return {"total": 0, "page": page, "size": size, "query": q, "data": []}

            # 筛选条件
            if subject:
                conditions.append("p.subject_id = ?")
                params.append(subject)
            if paper_type:
                conditions.append("p.paper_type = ?")
                params.append(paper_type)
            if year:
                conditions.append("p.year = ?")
                params.append(year)
            if province:
                conditions.append("p.province LIKE ?")
                params.append(f"%{province}%")
            if exam_tag:
                conditions.append("p.exam_tag LIKE ?")
                params.append(f"%{exam_tag}%")
            if source_priority:
                conditions.append("p.source_priority = ?")
                params.append(source_priority)
            if verified is not None:
                conditions.append("p.verified = ?")
                params.append(1 if verified else 0)
            if analysis_status:
                conditions.append("p.analysis_status = ?")
                params.append(analysis_status)

            # 排除已标记为重复的试卷
            conditions.append("(p.dedup_status != 'duplicate' OR p.dedup_status IS NULL)")

            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            offset = (page - 1) * size

            # 排序
            if sort == "time":
                order = "p.created_at DESC"
            elif sort == "priority":
                order = """
                    CASE p.source_priority
                        WHEN 'S' THEN 0
                        WHEN 'A' THEN 1
                        WHEN 'B' THEN 2
                        ELSE 3
                    END, p.created_at DESC
                """
            else:
                # relevance: 按 FTS 命中顺序（即 rank 顺序）排序，未被命中的排在之后
                if matched_ids:
                    # 为命中 id 分配递增权重(0,1,2,...)，保持 FTS 相关度顺序；
                    # 非命中 id 用比最大位置更大的值，确保全部排在命中集之后。
                    when_clauses = " ".join(
                        f"WHEN {mid} THEN {i}" for i, mid in enumerate(matched_ids)
                    )
                    sentinel = len(matched_ids) + 1
                    order = f"CASE p.id {when_clauses} ELSE {sentinel} END"
                else:
                    order = "p.created_at DESC"

            # 计数
            count_sql = f"SELECT COUNT(*) as cnt FROM papers p {where}"
            total_row = await db.execute_fetchone(count_sql, params)
            total = total_row["cnt"] if total_row else 0

            # 查询
            data_sql = f"""
                SELECT p.id, p.title, p.subject_id, p.paper_type, p.year,
                       p.province, p.school, p.exam_tag,
                       p.source_id, p.source_url, p.source_priority,
                       p.verified, p.question_count, p.difficulty,
                       p.quality_score, p.curriculum_score, p.analysis_status,
                       p.total_score, p.created_at,
                       s.name as source_name
                FROM papers p
                LEFT JOIN sources s ON p.source_id = s.id
                {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?
            """
            rows = await db.execute_fetchall(data_sql, params + [size, offset])

            # 附加 snippet
            data = []
            for row in rows:
                item = dict(row)
                if fts_snippets and row["id"] in fts_snippets:
                    item["snippet"] = fts_snippets[row["id"]]
                else:
                    # 生成简单 snippet
                    title = item.get("title", "")
                    item["snippet"] = title[:80] + "..." if len(title) > 80 else title
                data.append(item)

            return {
                "total": total,
                "page": page,
                "size": size,
                "query": q,
                "data": data,
            }

    async def suggest(self, q: str, limit: int = 10) -> list:
        """搜索建议：返回匹配的试卷标题"""
        if not q or len(q.strip()) < 1:
            return []

        async for db in get_db():
            clean_q = q.strip().replace('"', '""')
            try:
                # 先尝试短语匹配
                rows = await db.execute_fetchall(
                    """SELECT DISTINCT title FROM papers_fts
                       WHERE papers_fts MATCH ?
                       LIMIT ?""",
                    [f'"{clean_q}"', limit],
                )
                if rows:
                    return [r["title"] for r in rows]

                # 短语无结果，尝试分词 AND 匹配（统一使用 tokenizer 模块）
                tokens = tokenize(clean_q)
                if len(tokens) >= 2:
                    and_query = ' AND '.join(f'"{t}"' for t in tokens if len(t) >= 2)
                    if and_query:
                        rows = await db.execute_fetchall(
                            """SELECT DISTINCT title FROM papers_fts
                               WHERE papers_fts MATCH ?
                               LIMIT ?""",
                            [and_query, limit],
                        )
                        if rows:
                            return [r["title"] for r in rows]

                # 降级到 LIKE
                rows = await db.execute_fetchall(
                    "SELECT DISTINCT title FROM papers WHERE title LIKE ? LIMIT ?",
                    [f"%{q.strip()}%", limit],
                )
                return [r["title"] for r in rows]
            except Exception:  # noqa: BLE001
                rows = await db.execute_fetchall(
                    "SELECT DISTINCT title FROM papers WHERE title LIKE ? LIMIT ?",
                    [f"%{q.strip()}%", limit],
                )
                return [r["title"] for r in rows]

    async def search_questions(
        self,
        q: str,
        subject: Optional[str] = None,
        q_type: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> dict:
        """题目全文搜索"""
        async for db in get_db():
            conditions = []
            params = []

            if q and q.strip():
                clean_q = q.strip().replace('"', '""')
                conditions.append("qf.content MATCH ?")
                params.append(f'"{clean_q}"')

            if subject:
                conditions.append("p.subject_id = ?")
                params.append(subject)
            if q_type:
                conditions.append("q.q_type = ?")
                params.append(q_type)

            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            offset = (page - 1) * size

            count_sql = f"""
                SELECT COUNT(*) as cnt
                FROM questions_fts qf
                JOIN questions q ON qf.rowid = q.id
                JOIN papers p ON q.paper_id = p.id
                {where}
            """
            total_row = await db.execute_fetchone(count_sql, params)
            total = total_row["cnt"] if total_row else 0

            data_sql = f"""
                SELECT q.id, q.q_number, q.q_type, q.content, q.score,
                       q.knowledge_points, q.difficulty_tag,
                       p.id as paper_id, p.title as paper_title,
                       p.subject_id, p.year, p.province,
                       snippet(questions_fts, '<em>', '</em>', '...', 0, 64) as snippet
                FROM questions_fts qf
                JOIN questions q ON qf.rowid = q.id
                JOIN papers p ON q.paper_id = p.id
                {where}
                ORDER BY qf.rank
                LIMIT ? OFFSET ?
            """
            rows = await db.execute_fetchall(data_sql, params + [size, offset])

            return {
                "total": total,
                "page": page,
                "size": size,
                "query": q,
                "data": rows,
            }


async def search_similar_titles(db, title: str, subject_id: str, limit: int = 5) -> list:
    """共享：基于中文分词 + AND→OR→LIKE 降级，查询相似标题（供搜索与查重复用，B-3）。

    Args:
        db: aiosqlite 连接
        title: 待查重标题
        subject_id: 科目 ID（限定同科目，避免跨科误判）
        limit: 返回候选数量

    Returns:
        [{"id": int, "title": str, "year": int}, ...]（已按相关度排序）
    """
    tokens = tokenize(title)
    if not tokens:
        return []

    clean_title = title.strip().replace('"', '""')
    sql = """
        SELECT p.id, p.title, p.year
        FROM papers_fts pf
        JOIN papers p ON pf.rowid = p.id
        WHERE papers_fts MATCH ? AND p.subject_id = ?
        ORDER BY pf.rank
        LIMIT ?
    """

    rows = []
    # 1) 短语匹配
    try:
        rows = await db.execute_fetchall(sql, [f'"{clean_title}"', subject_id, limit])
    except Exception:  # noqa: BLE001
        rows = []
    # 2) 多关键词 AND
    if not rows and len(tokens) > 1:
        and_query = ' AND '.join(f'"{t}"' for t in tokens if len(t) >= 2)
        if and_query:
            try:
                rows = await db.execute_fetchall(sql, [and_query, subject_id, limit])
            except Exception:  # noqa: BLE001
                rows = []
    # 3) 多关键词 OR
    if not rows and len(tokens) > 1:
        or_query = ' OR '.join(f'"{t}"' for t in tokens if len(t) >= 2)
        if or_query:
            try:
                rows = await db.execute_fetchall(sql, [or_query, subject_id, limit])
            except Exception:  # noqa: BLE001
                rows = []
    # 4) LIKE 降级（逐 token）
    if not rows:
        conditions = []
        params: list = [subject_id]
        for t in tokens:
            conditions.append("p.title LIKE ?")
            params.append(f"%{t}%")
        like_sql = (
            "SELECT p.id, p.title, p.year FROM papers p "
            f"WHERE p.subject_id = ? AND {' AND '.join(conditions)} LIMIT ?"
        )
        params.append(limit)
        try:
            rows = await db.execute_fetchall(like_sql, params)
        except Exception:  # noqa: BLE001
            rows = []

    return [{"id": r["id"], "title": r["title"], "year": r["year"]} for r in rows]
