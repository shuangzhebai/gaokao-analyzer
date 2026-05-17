"""
v5.0 官方文件库
收录高考政策文件、考试大纲、评分标准等
来源必须是教育部/省级教育考试院等权威官方平台
"""
import asyncio
import hashlib
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config import OFFICIAL_DOCS_CONFIG, SCRAPER_CONFIG
from models import get_db

logger = logging.getLogger("gaokao")


class OfficialDocsLibrary:
    """官方文件库管理器"""

    # 预置的权威文件种子数据
    SEED_DOCS = [
        {
            "title": "普通高中课程方案（2017年版2020年修订）",
            "category": "curriculum",
            "source": "教育部",
            "source_url": "http://www.moe.gov.cn/srcsite/A26/s8001/202006/t20200609.html",
            "priority": "S",
            "year": 2020,
            "summary": "教育部发布的普通高中课程方案修订版，规定高中各学科课程设置和学分要求。",
        },
        {
            "title": "普通高中数学课程标准（2017年版2020年修订）",
            "category": "curriculum",
            "source": "教育部",
            "source_url": "http://www.moe.gov.cn/",
            "priority": "S",
            "year": 2020,
            "summary": "高中数学课程标准，含必修和选择性必修课程内容要求。",
        },
        {
            "title": "普通高中语文课程标准（2017年版2020年修订）",
            "category": "curriculum",
            "source": "教育部",
            "source_url": "http://www.moe.gov.cn/",
            "priority": "S",
            "year": 2020,
            "summary": "高中语文课程标准，含学习任务群和学业质量水平。",
        },
        {
            "title": "普通高中英语课程标准（2017年版2020年修订）",
            "category": "curriculum",
            "source": "教育部",
            "source_url": "http://www.moe.gov.cn/",
            "priority": "S",
            "year": 2020,
            "summary": "高中英语课程标准，含语言能力、文化意识等核心素养要求。",
        },
        {
            "title": "关于深化考试招生制度改革的实施意见",
            "category": "reform",
            "source": "国务院",
            "source_url": "http://www.gov.cn/",
            "priority": "S",
            "year": 2014,
            "summary": "国务院发布的考试招生制度改革纲领性文件，启动新高考改革。",
        },
        {
            "title": "2025年普通高等学校招生全国统一考试大纲",
            "category": "scoring",
            "source": "教育部考试院",
            "source_url": "https://www.neea.edu.cn/",
            "priority": "S",
            "year": 2025,
            "summary": "2025年高考考试大纲，含各科考试范围、题型、分值分配。",
        },
        {
            "title": "第三批高考综合改革省份实施方案",
            "category": "reform",
            "source": "教育部",
            "source_url": "http://www.moe.gov.cn/",
            "priority": "S",
            "year": 2021,
            "summary": "河北、辽宁、江苏、福建、湖北、湖南、广东、重庆8省市新高考改革方案。",
        },
        {
            "title": "2024年普通高等学校招生全国统一考试命题指导意见",
            "category": "exam_notice",
            "source": "教育部考试院",
            "source_url": "https://www.neea.edu.cn/",
            "priority": "S",
            "year": 2024,
            "summary": "2024年高考命题指导思想，强调素养导向、情境创设。",
        },
        {
            "title": "关于普通高中学业水平考试的实施意见",
            "category": "policy",
            "source": "教育部",
            "source_url": "http://www.moe.gov.cn/",
            "priority": "S",
            "year": 2014,
            "summary": "学业水平考试实施办法，规定合格性考试和等级性考试。",
        },
        {
            "title": "普通高校本科招生专业选考科目要求指引",
            "category": "reform",
            "source": "教育部",
            "source_url": "http://www.moe.gov.cn/",
            "priority": "S",
            "year": 2021,
            "summary": "各高校专业选考科目要求指引，影响等级赋分规则。",
        },
    ]

    async def seed_official_docs(self):
        """初始化官方文件种子数据"""
        async for db in get_db():
            for doc in self.SEED_DOCS:
                existing = await db.execute_fetchone(
                    "SELECT id FROM official_docs WHERE title = ?",
                    (doc["title"],),
                )
                if existing:
                    continue

                content_hash = hashlib.sha256(
                    f"{doc['title']}|{doc['source']}|{doc['year']}".encode()
                ).hexdigest()[:32]

                await db.execute(
                    """INSERT INTO official_docs
                       (title, category, source, source_url, priority, year, summary, content_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (doc["title"], doc["category"], doc["source"], doc["source_url"],
                     doc["priority"], doc["year"], doc["summary"], content_hash),
                )
            await db.commit()
            logger.info(f"Official docs seeded: {len(self.SEED_DOCS)} documents")

    async def search_docs(self, keyword: str = "", category: str = "",
                          year: Optional[int] = None, page: int = 1,
                          size: int = 20) -> dict:
        """搜索官方文件"""
        async for db in get_db():
            conditions = []
            params = []

            if keyword:
                conditions.append("(title LIKE ? OR summary LIKE ?)")
                kw = f"%{keyword}%"
                params.extend([kw, kw])
            if category:
                conditions.append("category = ?")
                params.append(category)
            if year:
                conditions.append("year = ?")
                params.append(year)

            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            offset = (page - 1) * size

            total = await db.execute_fetchone(
                f"SELECT COUNT(*) as cnt FROM official_docs {where}", params
            )
            rows = await db.execute_fetchall(
                f"""SELECT * FROM official_docs {where}
                    ORDER BY priority ASC, year DESC, created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [size, offset],
            )

            return {
                "total": total["cnt"] if total else 0,
                "page": page,
                "size": size,
                "data": rows,
            }

    async def get_categories(self) -> list:
        """获取文件分类列表"""
        return OFFICIAL_DOCS_CONFIG.get("categories", [])

    async def refresh_from_official_sources(self) -> dict:
        """从官方源刷新文件库"""
        found = 0
        added = 0

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30),
            headers={"User-Agent": SCRAPER_CONFIG["user_agent"]},
            follow_redirects=True,
        ) as client:
            for source in OFFICIAL_DOCS_CONFIG.get("sources", []):
                try:
                    resp = await client.get(source["base_url"])
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "lxml")
                    keywords = OFFICIAL_DOCS_CONFIG.get("keywords", [])

                    links = soup.find_all("a", href=True)
                    new_docs = []
                    for link in links:
                        title = link.get_text(strip=True)
                        if not title or len(title) < 6:
                            continue
                        # 检查是否包含高考相关关键词
                        if not any(kw in title for kw in keywords):
                            continue

                        found += 1
                        href = link.get("href", "")
                        from urllib.parse import urljoin
                        full_url = urljoin(source["base_url"], href)

                        content_hash = hashlib.sha256(
                            f"{title}|{source['name']}|".encode()
                        ).hexdigest()[:32]

                        new_docs.append({
                            "title": title,
                            "category": source["category"],
                            "source": source["name"],
                            "source_url": full_url,
                            "priority": source["priority"],
                            "summary": title[:100],
                            "content_hash": content_hash,
                        })

                    # 批量写入数据库
                    if new_docs:
                        async for db in get_db():
                            for doc in new_docs:
                                existing = await db.execute_fetchone(
                                    "SELECT id FROM official_docs WHERE source_url = ?",
                                    (doc["source_url"],),
                                )
                                if existing:
                                    continue

                                await db.execute(
                                    """INSERT INTO official_docs
                                       (title, category, source, source_url, priority, summary, content_hash)
                                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                    (doc["title"], doc["category"], doc["source"], doc["source_url"],
                                     doc["priority"], doc["summary"], doc["content_hash"]),
                                )
                                added += 1
                            await db.commit()

                except Exception as e:
                    logger.error(f"Refresh from {source['name']} failed: {e}")

        return {"found": found, "added": added}
