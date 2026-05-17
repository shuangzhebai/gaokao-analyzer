"""
查重引擎 v4.0 - 三级查重策略
Level 1: content_hash 快速比对 (O(1))
Level 2: FTS5 标题相似搜索 (O(log n))
Level 3: DeepSeek API 语义相似度 (按需调用)
"""
import hashlib
import json
import logging
import time
from typing import Optional

import httpx

from models import get_db

logger = logging.getLogger("gaokao")


class DedupEngine:
    """三级查重引擎"""

    def __init__(self, deepseek_api_key: Optional[str] = None):
        self.api_key = deepseek_api_key
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.api_model = "deepseek-chat"
        self._rate_limit_remaining = 10
        self._rate_limit_reset = 0

    @staticmethod
    def compute_content_hash(title: str, subject_id: str, year: int,
                             questions: list = None) -> str:
        """计算内容哈希，用于快速去重"""
        parts = [title, subject_id, str(year)]
        if questions:
            for q in questions[:5]:  # 只取前5道题
                content = q.get("content", "") or ""
                parts.append(content[:100])
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    async def check_duplicate(self, title: str, subject_id: str, year: int,
                              questions: list = None, source_url: str = "",
                              content_hash: str = "") -> dict:
        """
        三级查重检测

        Returns:
            {
                "status": "unique" | "suspected" | "duplicate",
                "similar_papers": [{"paper_id", "title", "similarity", "method"}],
                "content_hash": str
            }
        """
        # 计算哈希
        if not content_hash:
            content_hash = self.compute_content_hash(title, subject_id, year, questions)

        # Level 1: Hash 比对
        hash_result = await self._hash_check(content_hash, source_url)
        if hash_result["status"] == "duplicate":
            return hash_result

        # Level 2: FTS5 标题搜索
        fts_result = await self._fts_check(title, subject_id, year)
        if not fts_result["similar_papers"]:
            return {"status": "unique", "similar_papers": [], "content_hash": content_hash}

        # Level 3: DeepSeek 语义分析（按需）
        if self.api_key and self._can_call_api():
            return await self._deepseek_check(
                title, questions, fts_result["similar_papers"], content_hash
            )

        # 无 DeepSeek 时，用标题相似度作为判断
        return fts_result

    async def _hash_check(self, content_hash: str, source_url: str) -> dict:
        """Level 1: 哈希快速比对"""
        async for db in get_db():
            # 检查内容哈希
            if content_hash:
                row = await db.execute_fetchone(
                    "SELECT id, title FROM papers WHERE content_hash = ? LIMIT 1",
                    (content_hash,),
                )
                if row:
                    return {
                        "status": "duplicate",
                        "similar_papers": [{
                            "paper_id": row["id"],
                            "title": row["title"],
                            "similarity": 1.0,
                            "method": "hash",
                        }],
                        "content_hash": content_hash,
                    }

            # 检查 source_url
            if source_url:
                row = await db.execute_fetchone(
                    "SELECT id, title FROM papers WHERE source_url = ? LIMIT 1",
                    (source_url,),
                )
                if row:
                    return {
                        "status": "duplicate",
                        "similar_papers": [{
                            "paper_id": row["id"],
                            "title": row["title"],
                            "similarity": 1.0,
                            "method": "url",
                        }],
                        "content_hash": content_hash,
                    }

            return {"status": "unique", "similar_papers": [], "content_hash": content_hash}

    async def _fts_check(self, title: str, subject_id: str, year: int) -> dict:
        """Level 2: FTS5 标题相似搜索"""
        async for db in get_db():
            # 提取标题关键词
            keywords = self._extract_keywords(title)
            if not keywords:
                return {"status": "unique", "similar_papers": [], "content_hash": ""}

            # 用关键词搜索相似标题
            clean_kw = " ".join(keywords).replace('"', '""')
            try:
                rows = await db.execute_fetchall(
                    """SELECT p.id, p.title, p.year
                       FROM papers_fts pf
                       JOIN papers p ON pf.rowid = p.id
                       WHERE papers_fts MATCH ? AND p.subject_id = ?
                       ORDER BY pf.rank
                       LIMIT 5""",
                    [f'"{clean_kw}"', subject_id],
                )
            except Exception:
                # FTS5 查询失败，降级到 LIKE
                kw_like = f"%{'%'.join(keywords)}%"
                rows = await db.execute_fetchall(
                    """SELECT id, title, year FROM papers
                       WHERE title LIKE ? AND subject_id = ?
                       LIMIT 5""",
                    [kw_like, subject_id],
                )

            similar = []
            for row in rows:
                sim = self._title_similarity(title, row["title"])
                if sim > 0.5:
                    similar.append({
                        "paper_id": row["id"],
                        "title": row["title"],
                        "similarity": round(sim, 3),
                        "method": "fts",
                    })

            # 按相似度排序
            similar.sort(key=lambda x: x["similarity"], reverse=True)

            if similar and similar[0]["similarity"] >= 0.9:
                status = "duplicate"
            elif similar and similar[0]["similarity"] >= 0.7:
                status = "suspected"
            else:
                status = "unique"

            return {
                "status": status,
                "similar_papers": similar,
                "content_hash": "",
            }

    async def _deepseek_check(
        self, title: str, questions: list,
        candidates: list, content_hash: str
    ) -> dict:
        """Level 3: DeepSeek API 语义相似度检测"""
        if not self._can_call_api():
            return {
                "status": "suspected" if candidates else "unique",
                "similar_papers": candidates,
                "content_hash": content_hash,
            }

        # 构造提示词
        candidate_info = "\n".join(
            f"  ID={c['paper_id']}, 标题: {c['title']}, 初步相似度: {c['similarity']}"
            for c in candidates[:3]
        )

        questions_summary = ""
        if questions:
            q_contents = [q.get("content", "")[:50] for q in questions[:5]]
            questions_summary = "新试卷前5题: " + "; ".join(q_contents)

        prompt = f"""你是一个试卷查重专家。请判断以下试卷是否与已有试卷重复。

新试卷标题: {title}
{questions_summary}

已有相似试卷:
{candidate_info}

请以 JSON 格式返回判断结果:
{{"is_duplicate": true/false, "similarity": 0.0-1.0, "reason": "判断理由"}}

只返回 JSON，不要其他内容。"""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.api_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 200,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    # 解析 JSON
                    content = content.replace("```json", "").replace("```", "").strip()
                    result = json.loads(content)

                    similarity = result.get("similarity", 0.5)
                    is_dup = result.get("is_duplicate", False)

                    # 更新 candidates 的相似度
                    if candidates:
                        candidates[0]["similarity"] = round(similarity, 3)
                        candidates[0]["method"] = "deepseek"
                        candidates[0]["reason"] = result.get("reason", "")

                    if is_dup or similarity >= 0.9:
                        status = "duplicate"
                    elif similarity >= 0.7:
                        status = "suspected"
                    else:
                        status = "unique"

                    return {
                        "status": status,
                        "similar_papers": candidates,
                        "content_hash": content_hash,
                    }
                else:
                    logger.warning(f"DeepSeek API error: {resp.status_code}")
                    self._rate_limit_remaining = 0
                    self._rate_limit_reset = time.time() + 60

        except Exception as e:
            logger.error(f"DeepSeek API call failed: {e}")
            self._rate_limit_remaining = 0
            self._rate_limit_reset = time.time() + 60

        # API 调用失败，回退到 FTS 结果
        return {
            "status": "suspected" if candidates else "unique",
            "similar_papers": candidates,
            "content_hash": content_hash,
        }

    def _can_call_api(self) -> bool:
        """检查是否可以调用 DeepSeek API（频率控制）"""
        now = time.time()
        if now > self._rate_limit_reset:
            self._rate_limit_remaining = 10
            self._rate_limit_reset = now + 60
        return self._rate_limit_remaining > 0 and self.api_key is not None

    @staticmethod
    def _extract_keywords(title: str) -> list:
        """从标题中提取关键词"""
        # 停用词
        stopwords = {"的", "与", "及", "和", "在", "为", "了", "是", "有", "年",
                     "届", "第", "次", "次模拟", "考试", "试卷", "高三", "高考"}

        # 简单分词：按常见分隔符拆分
        parts = []
        for sep in [" ", "·", "—", "—", "—"]:
            title = title.replace(sep, "|")
        for part in title.split("|"):
            part = part.strip()
            if part and part not in stopwords and len(part) >= 2:
                parts.append(part)

        # 如果没有拆出有效关键词，取标题前8个字
        if not parts and len(title) >= 4:
            parts.append(title[:8])

        return parts[:5]  # 最多5个关键词

    @staticmethod
    def _title_similarity(title1: str, title2: str) -> float:
        """计算标题相似度（基于字符级 Jaccard）"""
        if not title1 or not title2:
            return 0.0

        # 使用2-gram
        def ngrams(s, n=2):
            return set(s[i:i+n] for i in range(len(s)-n+1))

        ng1 = ngrams(title1)
        ng2 = ngrams(title2)

        if not ng1 or not ng2:
            return 0.0

        intersection = ng1 & ng2
        union = ng1 | ng2
        return len(intersection) / len(union)
