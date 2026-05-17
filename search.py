"""
全文搜索引擎 v5.1 - 基于 SQLite FTS5
支持：关键词搜索、多维度筛选、相关度排序、搜索建议
v5.1: 增强中文分词搜索、多关键词 AND/OR、模糊匹配
"""
import re
import logging
from typing import Optional

from models import get_db

logger = logging.getLogger("gaokao")


class SearchEngine:
    """FTS5 全文搜索引擎"""

    def __init__(self):
        self._subject_names = {
            "chinese": "语文", "math": "数学", "english": "英语",
            "physics": "物理", "chemistry": "化学", "biology": "生物",
            "history": "历史", "geography": "地理", "politics": "政治",
        }

    @staticmethod
    def _tokenize_chinese(q: str) -> list:
        """
        中文智能分词：按空格/标点分割，并自动切分连续中文字符为 2-4 字词组
        例: "深圳二模数学" → ["深圳", "二模", "数学"]
        """
        # 先按空格/标点切分
        raw_tokens = re.split(r'[\s,，。、；;：:！!？?（）()（）【】\[\]{}]+', q.strip())
        tokens = []
        for t in raw_tokens:
            if not t:
                continue
            # 英文/数字直接保留
            if re.match(r'^[\w\d]+$', t) and not re.search(r'[\u4e00-\u9fff]', t):
                tokens.append(t)
                continue
            # 中文: 按常见考试关键词模式切分
            # 匹配 "XX一模/二模/三模/省质检/联考" 等模式
            exam_patterns = [
                r'深圳', '广州', '南京', '杭州', '长沙', '武汉', '成都',
                '北京', '上海', '天津', '重庆', '福州', '厦门', '济南', '青岛',
                '郑州', '合肥', '西安', '南昌',
                '一模', '二模', '三模', '四模',
                '省质检', '省统考', '联考', '月考', '期末', '期中',
                '适应性', '模拟', '真题',
                '数学', '语文', '英语', '物理', '化学', '生物', '历史', '地理', '政治',
                '附中', '中学', '一中', '二中', '三中', '外国语', '实验',
                '百校', '名校', '九校', '八校', '十校',
                'T8', '华大', '天一', '衡水', '黄冈', '镇海',
                '学军', '长郡', '雅礼', '南外', '人大',
                '高考', '中考', '期末', '入学',
            ]
            remaining = t
            for pattern in exam_patterns:
                if pattern in remaining:
                    tokens.append(pattern)
                    remaining = remaining.replace(pattern, '', 1)
            # 剩余部分: 切分为 2-4 字词组
            if remaining:
                if len(remaining) <= 4:
                    tokens.append(remaining)
                else:
                    # 按 2 字切分（中文常用词长度）
                    for i in range(0, len(remaining), 2):
                        chunk = remaining[i:i+2]
                        if chunk:
                            tokens.append(chunk)
        return [t for t in tokens if len(t) >= 1]

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
                # v5.1: 中文分词 + 多关键词 AND 搜索
                tokens = self._tokenize_chinese(q.strip())
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
                # relevance: 使用 FTS rank 排序或默认时间排序
                if matched_ids:
                    # 按 FTS 匹配的 ID 顺序排序（FTS 已经按 rank 排好）
                    id_order = ",".join(str(mid) for mid in matched_ids)
                    order = f"CASE p.id WHEN {id_order} THEN 0 ELSE 1 END, p.created_at DESC"
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

                # 短语无结果，尝试分词 AND 匹配
                tokens = self._tokenize_chinese(clean_q)
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
            except Exception:
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
