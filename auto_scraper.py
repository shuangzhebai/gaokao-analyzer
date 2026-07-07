"""
v5.0 智能自动采集调度器
功能：定时自动搜索试卷、多平台交叉验证、DeepSeek辅助判断真实性
"""
import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Optional
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from config import (
    DOWNLOAD_DIR, SCRAPER_CONFIG, SOURCES, SUBJECTS,
    AUTO_SCRAPER_CONFIG, DEEPSEEK_CONFIG, CITY_TO_PROVINCE,
)
from models import get_db
from dedup import DedupEngine

logger = logging.getLogger("gaokao")


class CrossVerifier:
    """多平台交叉验证器"""

    @staticmethod
    async def verify_paper(title: str, subject_id: str, year: int,
                           province: str = "", deepseek_key: str = "") -> dict:
        """
        交叉验证试卷真实性
        在多个平台搜索同一试卷，确认是否存在一致性

        Returns:
            {
                "verified": bool,
                "confidence": float,  # 0.0-1.0
                "sources_found": int,  # 多少个平台确认了
                "details": [{source, found, title_match, url}],
                "deepseek_result": dict or None,
            }
        """
        results = []
        sources_confirmed = 0

        # 从标题提取关键词
        keywords = CrossVerifier._extract_search_keywords(title, subject_id, year)
        search_query = " ".join(keywords)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(SCRAPER_CONFIG["timeout"]),
            headers={"User-Agent": SCRAPER_CONFIG["user_agent"]},
            follow_redirects=True,
        ) as client:
            # 在每个平台搜索
            for source_id, source_config in SOURCES.items():
                if not source_config.get("enabled", True):
                    continue
                try:
                    found, match_detail = await CrossVerifier._search_on_platform(
                        client, source_id, source_config, search_query, title
                    )
                    results.append({
                        "source": source_config["name"],
                        "source_id": source_id,
                        "found": found,
                        "title_match": match_detail,
                    })
                    if found:
                        sources_confirmed += 1
                except Exception as e:
                    results.append({
                        "source": source_config["name"],
                        "source_id": source_id,
                        "found": False,
                        "error": str(e),
                    })

        # 计算置信度
        min_sources = AUTO_SCRAPER_CONFIG.get("cross_verify_sources", 2)
        confidence = min(sources_confirmed / max(min_sources, 1), 1.0)
        verified = sources_confirmed >= min_sources

        # DeepSeek 辅助验证
        deepseek_result = None
        if deepseek_key and not verified:
            deepseek_result = await CrossVerifier._deepseek_verify(
                title, subject_id, year, results, deepseek_key
            )
            if deepseek_result and deepseek_result.get("is_real"):
                confidence = max(confidence, 0.7)
                verified = True

        return {
            "verified": verified,
            "confidence": round(confidence, 3),
            "sources_found": sources_confirmed,
            "details": results,
            "deepseek_result": deepseek_result,
        }

    @staticmethod
    async def _search_on_platform(client, source_id, source_config,
                                   search_query, original_title) -> tuple:
        """在单个平台搜索"""
        base_url = source_config.get("base_url", "")
        search_path = source_config.get("search_path", "/search")

        if source_id == "moe":
            # 教育部考试院：直接检查已知页面
            return False, ""

        url = f"{base_url}{search_path}?q={quote(search_query)}"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return False, ""
            text = resp.text
            # 简单标题匹配
            # 从原标题提取核心关键词
            core_words = [w for w in original_title.split() if len(w) >= 2]
            if not core_words:
                # 中文标题按字符拆分
                core_words = [original_title[i:i+4] for i in range(0, min(len(original_title), 20), 4)]

            match_count = sum(1 for w in core_words if w in text)
            found = match_count >= max(len(core_words) * 0.4, 2)
            return found, f"匹配{match_count}/{len(core_words)}个关键词"
        except Exception:
            return False, ""

    @staticmethod
    async def _deepseek_verify(title, subject_id, year, platform_results,
                                api_key) -> Optional[dict]:
        """使用 DeepSeek 验证试卷真实性"""
        subject_name = SUBJECTS.get(subject_id, {}).get("name", subject_id)
        platform_info = "\n".join(
            f"  - {r['source']}: {'找到' if r.get('found') else '未找到'}"
            for r in platform_results
        )

        prompt = f"""你是一个高考信息验证专家。请判断以下试卷是否真实存在。

试卷标题: {title}
科目: {subject_name}
年份: {year}

多平台搜索结果:
{platform_info}

请判断这份试卷是否真实存在，以JSON格式返回:
{{"is_real": true/false, "confidence": 0.0-1.0, "reason": "判断理由"}}

只返回JSON。"""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    DEEPSEEK_CONFIG["api_url"],
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": DEEPSEEK_CONFIG["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 200,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    content = content.replace("```json", "").replace("```", "").strip()
                    return json.loads(content)
        except Exception as e:
            logger.error(f"DeepSeek verify failed: {e}")
        return None

    @staticmethod
    def _extract_search_keywords(title, subject_id, year) -> list:
        """从标题提取搜索关键词"""
        keywords = [str(year)]
        subject_name = SUBJECTS.get(subject_id, {}).get("name", "")
        if subject_name:
            keywords.append(subject_name)

        # 提取地区
        for city, province in CITY_TO_PROVINCE.items():
            if city in title:
                keywords.append(city)
                break
        for province in CITY_TO_PROVINCE.values():
            if province in title and province not in keywords:
                keywords.append(province)
                break

        # 提取考试类型
        for tag in ["一模", "二模", "三模", "省质检", "联考", "适应性考试"]:
            if tag in title:
                keywords.append(tag)
                break

        # 提取核心内容词
        if "高考" in title:
            keywords.append("高考")
        if "模拟" in title:
            keywords.append("模拟")

        return keywords[:6]


class AutoScraper:
    """定时自动采集调度器"""

    def __init__(self, deepseek_api_key: str = ""):
        self.config = AUTO_SCRAPER_CONFIG
        self.api_key = deepseek_api_key

    def __repr__(self):
        masked = self.api_key[:4] + "****" if self.api_key else "None"
        return f"AutoScraper(api_key={masked})"
        self._running = False
        self._task = None
        self._last_run = None
        self._run_count = 0
        self._results_log = []

    async def start(self):
        """启动定时采集"""
        if not self.config.get("enabled", True):
            logger.info("Auto-scraper disabled by config")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Auto-scraper started, interval={self.config['interval_minutes']}min")

    async def stop(self):
        """停止定时采集"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Auto-scraper stopped")

    async def _run_loop(self):
        """主循环"""
        interval = self.config.get("interval_minutes", 30) * 60
        while self._running:
            try:
                await self._run_once()
            except Exception as e:
                logger.error(f"Auto-scraper run error: {e}")
            self._last_run = datetime.now()
            self._run_count += 1
            await asyncio.sleep(interval)

    async def _run_once(self):
        """执行一次采集"""
        logger.info("Auto-scraper: starting collection run...")

        subjects = self.config.get("subjects", list(SUBJECTS.keys()))
        year_range = self.config.get("year_range", [2025, 2026])
        max_papers = self.config.get("max_papers_per_run", 20)

        dedup_engine = DedupEngine(
            deepseek_api_key=self.api_key or None
        )

        total_found = 0
        total_saved = 0
        total_skipped = 0

        async for db in get_db():
            for year in range(year_range[0], year_range[1] + 1):
                for subject_id in subjects:
                    if total_saved >= max_papers:
                        break

                    try:
                        items = await self._search_subject_year(
                            subject_id, year
                        )
                    except Exception as e:
                        logger.error(f"Auto-search {subject_id}/{year} failed: {e}")
                        continue

                    for item in items:
                        if total_saved >= max_papers:
                            break
                        total_found += 1

                        # 查重
                        dedup_result = await dedup_engine.check_duplicate(
                            title=item.get("title", ""),
                            subject_id=subject_id,
                            year=year,
                            source_url=item.get("url", ""),
                        )

                        if dedup_result["status"] == "duplicate":
                            total_skipped += 1
                            continue

                        # 交叉验证
                        if self.config.get("cross_verify_sources", 0) > 1:
                            verify = await CrossVerifier.verify_paper(
                                title=item.get("title", ""),
                                subject_id=subject_id,
                                year=year,
                                province=item.get("province", ""),
                                deepseek_key=self.api_key,
                            )
                            item["cross_verify"] = verify
                            if not verify["verified"]:
                                logger.info(f"Auto-scraper: skipped unverified '{item.get('title', '')}' "
                                          f"(confidence={verify['confidence']})")
                                total_skipped += 1
                                continue

                        # 保存
                        existing = await db.execute_fetchone(
                            "SELECT id FROM papers WHERE source_url = ?",
                            (item.get("url", ""),),
                        )
                        if existing:
                            total_skipped += 1
                            continue

                        cursor = await db.execute(
                            """INSERT INTO papers
                               (title, subject_id, paper_type, source_id, source_url, year, province,
                                file_path, analysis_status, content_hash, dedup_status, source_priority,
                                collected_at, collector, verified)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, datetime('now'), 'auto-scraper', ?)""",
                            (
                                item.get("title", ""),
                                subject_id,
                                item.get("type", "school"),
                                item.get("source_id", ""),
                                item.get("url", ""),
                                year,
                                item.get("province"),
                                None,
                                dedup_result.get("content_hash", ""),
                                dedup_result["status"],
                                item.get("priority", "B"),
                                1 if item.get("cross_verify", {}).get("verified", False) else 0,
                            ),
                        )
                        paper_id = cursor.lastrowid
                        total_saved += 1

                        # 记录采集日志
                        await db.execute(
                            """INSERT INTO scrape_logs
                               (source_id, url, status, paper_id, dedup_result, response_time_ms)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (item.get("source_id"), item.get("url"), "auto_collected",
                             paper_id, dedup_result["status"], 0),
                        )

                if total_saved >= max_papers:
                    break

            await db.commit()

        log_entry = {
            "time": datetime.now().isoformat(),
            "found": total_found,
            "saved": total_saved,
            "skipped": total_skipped,
            "run_number": self._run_count + 1,
        }
        self._results_log.append(log_entry)
        logger.info(f"Auto-scraper run complete: found={total_found}, saved={total_saved}, skipped={total_skipped}")

    async def _search_subject_year(self, subject_id: str, year: int) -> list:
        """搜索特定科目和年份的试卷"""
        subject_name = SUBJECTS.get(subject_id, {}).get("name", "")
        results = []

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(SCRAPER_CONFIG["timeout"]),
            headers={"User-Agent": SCRAPER_CONFIG["user_agent"]},
            follow_redirects=True,
        ) as client:
            # 在各平台搜索
            for source_id, source_config in SOURCES.items():
                if not source_config.get("enabled", True):
                    continue

                search_key = f"{year}届{subject_name}高考模拟"
                base_url = source_config.get("base_url", "")
                search_path = source_config.get("search_path", "/search")

                if source_id == "moe":
                    continue  # 教育部不搜模拟题

                url = f"{base_url}{search_path}?q={quote(search_key)}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "lxml")
                    links = soup.select(source_config.get("result_selector", "a"))

                    for link in links[:5]:
                        title = link.get_text(strip=True)
                        href = link.get("href", "")
                        if not href or not title:
                            continue

                        full_url = urljoin(url, href)

                        if subject_name not in title and "高考" not in title:
                            continue

                        # 提取省份
                        province = self._extract_province(title)

                        results.append({
                            "title": title,
                            "url": full_url,
                            "source_id": source_id,
                            "source": source_config["name"],
                            "priority": source_config["priority"],
                            "subject": subject_id,
                            "year": year,
                            "type": "school",
                            "province": province,
                        })

                except Exception as e:
                    logger.error(f"Auto-search on {source_id} failed: {e}")

                await asyncio.sleep(SCRAPER_CONFIG.get("request_delay", 2.0))

        # URL 去重
        seen = set()
        unique = []
        for r in results:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        return unique

    def _extract_province(self, title: str) -> str:
        """从标题提取省份"""
        for city, province in CITY_TO_PROVINCE.items():
            if city in title:
                return province
        for province in CITY_TO_PROVINCE.values():
            if province in title:
                return province
        return ""

    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "run_count": self._run_count,
            "interval_minutes": self.config.get("interval_minutes", 30),
            "recent_results": self._results_log[-10:],
        }
