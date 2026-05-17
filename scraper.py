"""
多源试卷爬取引擎 v3.0
修复：resp.text() → resp.text (httpx属性而非方法)
增强：更多数据源、关键词精准搜索、智能试卷内容识别
"""
import asyncio
import hashlib
import os
import random
import re
import time
from urllib.parse import urljoin, urlparse, quote

import httpx
from bs4 import BeautifulSoup

from config import (
    DOWNLOAD_DIR,
    PAPER_TYPES,
    SCRAPER_CONFIG,
    SOURCES,
    SUBJECTS,
)
from models import get_db


class BaseScraper:
    """爬虫基类"""

    def __init__(self, source_config):
        self.config = source_config
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(SCRAPER_CONFIG["timeout"]),
            headers={"User-Agent": SCRAPER_CONFIG["user_agent"]},
            follow_redirects=True,
        )
        self.seen_urls = set()

    async def close(self):
        await self.client.aclose()

    async def fetch(self, url, **kwargs):
        """带重试的请求"""
        for attempt in range(SCRAPER_CONFIG["retry_times"]):
            try:
                resp = await self.client.get(url, **kwargs)
                if resp.status_code == 200:
                    return resp
            except Exception:
                pass
            await asyncio.sleep(SCRAPER_CONFIG["request_delay"] * (attempt + 1))
        return None

    async def search(self, subject_key, year=2026, keyword=""):
        raise NotImplementedError

    async def download(self, url, save_path):
        resp = await self.fetch(url)
        if resp:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True
        return False

    def _url_hash(self, url):
        return hashlib.md5(url.encode()).hexdigest()[:12]


class MOEScraper(BaseScraper):
    """教育部考试院爬虫"""

    async def search(self, subject_key, year=2026, keyword=""):
        subject_name = SUBJECTS[subject_key]["name"]
        results = []

        base = self.config["base_url"]
        urls_to_check = [
            f"{base}/html1/report/{year}/index.shtml",
            f"{base}/html1/category/{year}/index.shtml",
        ]

        for url in urls_to_check:
            resp = await self.fetch(url)
            if not resp:
                continue
            # 修复：resp.text 是属性，不是方法
            soup = BeautifulSoup(resp.text, "lxml")
            links = soup.find_all("a", href=True)
            for link in links:
                title = link.get_text(strip=True)
                if subject_name in title and any(
                    k in title for k in ["高考", "真题", "考试"]
                ):
                    if keyword and keyword not in title:
                        continue
                    href = urljoin(url, link["href"])
                    results.append({
                        "title": title,
                        "url": href,
                        "source": self.config["name"],
                        "priority": self.config["priority"],
                        "subject": subject_key,
                        "year": year,
                        "type": "real",
                    })
            await asyncio.sleep(SCRAPER_CONFIG["request_delay"])

        return results


class ZXXKScraper(BaseScraper):
    """学科网爬虫"""

    async def search(self, subject_key, year=2026, keyword=""):
        subject_name = SUBJECTS[subject_key]["name"]
        results = []
        search_key = keyword or f"{year}届{subject_name}高考模拟"

        for page in range(1, 4):
            search_url = f"https://www.zxxk.com/soft/search.aspx?keyword={quote(search_key)}&page={page}"
            resp = await self.fetch(search_url)
            if not resp:
                continue

            # 修复：resp.text 是属性
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select(".list-item, .resource-item, li[class*=res]")
            for item in items:
                title_el = item.select_one("a.title, a[href*='soft']")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                if not href:
                    continue
                full_url = urljoin(search_url, href)

                paper_type = self._classify_paper_type(title)
                province = self._extract_province(title)

                results.append({
                    "title": title,
                    "url": full_url,
                    "source": self.config["name"],
                    "priority": self.config["priority"],
                    "subject": subject_key,
                    "year": year,
                    "type": paper_type,
                    "province": province,
                })

            await asyncio.sleep(SCRAPER_CONFIG["request_delay"])

        return results

    def _classify_paper_type(self, title):
        for kw, ptype in [
            ("省质检", "provincial"), ("省模拟", "provincial"),
            ("省联考", "provincial"), ("省统考", "provincial"),
            ("月考", "monthly"), ("周考", "monthly"),
            ("专项", "special"), ("专题", "special"),
        ]:
            if kw in title:
                return ptype
        return "school"

    def _extract_province(self, title):
        provinces = [
            "北京", "上海", "天津", "重庆", "广东", "深圳", "广州", "江苏", "浙江",
            "山东", "福建", "湖南", "湖北", "河南", "河北", "四川", "成都", "安徽",
            "江西", "陕西", "辽宁", "吉林", "黑龙江", "山西", "云南", "贵州",
            "广西", "海南", "甘肃", "青海", "宁夏", "新疆", "内蒙古", "西藏",
        ]
        for p in provinces:
            if p in title:
                return p
        return None


class GenericWebScraper(BaseScraper):
    """通用网页爬虫"""

    def __init__(self, source_config):
        super().__init__(source_config)
        self.search_path = source_config.get("search_path", "/search")
        self.result_selector = source_config.get("result_selector", "a")
        self.title_selector = source_config.get("title_selector", None)

    async def search(self, subject_key, year=2026, keyword=""):
        subject_name = SUBJECTS[subject_key]["name"]
        results = []
        search_key = keyword or f"{year}届{subject_name}高考模拟"

        base = self.config["base_url"]
        for page in range(1, 3):
            url = f"{base}{self.search_path}?q={quote(search_key)}&page={page}"
            resp = await self.fetch(url)
            if not resp:
                continue

            # 修复：resp.text 是属性，不是方法
            soup = BeautifulSoup(resp.text, "lxml")
            links = soup.select(self.result_selector)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not href:
                    continue
                full_url = urljoin(url, href)

                if subject_name in title or "高考" in title or "模拟" in title or keyword in title:
                    results.append({
                        "title": title,
                        "url": full_url,
                        "source": self.config["name"],
                        "priority": self.config["priority"],
                        "subject": subject_key,
                        "year": year,
                        "type": "school",
                    })

            await asyncio.sleep(SCRAPER_CONFIG["request_delay"])

        return results


class ScraperManager:
    """爬虫管理器 - 统一调度"""

    SCRAPERS = {
        "moe": MOEScraper,
        "zxxk": ZXXKScraper,
        "zujuan": GenericWebScraper,  # v5.0: 组卷网
        "jyeoo": GenericWebScraper,
        "gaosan": GenericWebScraper,
        "paperpass": GenericWebScraper,
        "21cnjy": GenericWebScraper,  # v5.0: 21世纪教育网
    }

    def __init__(self):
        self.scrapers = {}
        self._init_scrapers()

    def _init_scrapers(self):
        for source_id, source_config in SOURCES.items():
            if not source_config.get("enabled", True):
                continue
            scraper_cls = self.SCRAPERS.get(source_id, GenericWebScraper)
            self.scrapers[source_id] = scraper_cls(source_config)

    async def close(self):
        for s in self.scrapers.values():
            await s.close()

    async def collect_all(self, year=2026, subjects=None, keyword=""):
        if subjects is None:
            subjects = list(SUBJECTS.keys())

        all_results = []
        semaphore = asyncio.Semaphore(SCRAPER_CONFIG["max_concurrent"])

        async def _collect_one(source_id, subject_key):
            async with semaphore:
                scraper = self.scrapers.get(source_id)
                if not scraper:
                    return []
                try:
                    results = await scraper.search(subject_key, year, keyword=keyword)
                    for r in results:
                        r["source_id"] = source_id
                    return results
                except Exception as e:
                    return [{"error": str(e), "source_id": source_id}]

        tasks = []
        for source_id in self.scrapers:
            for subject_key in subjects:
                tasks.append(_collect_one(source_id, subject_key))

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results_list:
            if isinstance(res, list):
                all_results.extend(res)

        # 去重
        seen = set()
        unique = []
        for item in all_results:
            url = item.get("url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(item)

        return unique

    async def save_results(self, results):
        saved = []
        async for db in get_db():
            for item in results:
                if "error" in item:
                    continue

                existing = await db.execute_fetchone(
                    "SELECT id FROM papers WHERE source_url = ?", (item.get("url"),)
                )
                if existing:
                    continue

                file_path = None
                if item.get("url"):
                    ext = self._guess_extension(item["url"])
                    filename = f"{item.get('title', 'unknown')[:50]}_{hashlib.md5(item['url'].encode()).hexdigest()[:8]}{ext}"
                    file_path = os.path.join(DOWNLOAD_DIR, filename)

                cursor = await db.execute(
                    """INSERT INTO papers
                       (title, subject_id, paper_type, source_id, source_url, year, province, file_path, analysis_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (
                        item.get("title", ""),
                        item.get("subject", "math"),
                        item.get("type", "school"),
                        item.get("source_id", ""),
                        item.get("url", ""),
                        item.get("year", 2026),
                        item.get("province"),
                        file_path,
                    ),
                )
                paper_id = cursor.lastrowid
                saved.append(paper_id)

                await db.execute(
                    "INSERT INTO scrape_logs (source_id, url, status, paper_id) VALUES (?,?,?,?)",
                    (item.get("source_id"), item.get("url"), "success", paper_id),
                )

            await db.commit()
        return saved

    def _guess_extension(self, url):
        parsed = urlparse(url)
        path = parsed.path.lower()
        for ext in [".pdf", ".docx", ".doc", ".wps"]:
            if path.endswith(ext):
                return ext
        return ".html"
