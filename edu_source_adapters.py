"""
教育站点专用数据源适配器 — 学科网 & 组卷网

设计说明：
- 所有适配器继承 BaseSourceAdapter，自动注册到 AdapterRegistry（模块导入时生效）。
- 需要登录/凭证的站点，在 DATA_SOURCES 配置中添加 cookies 或 auth_token 字段。
- 适配器注册 key：
  "xueke_wang" → 学科网 (www.zxxk.com / zujuan.xkw.com)
  "zujuan_wang" → 组卷网 (www.zujuan.com / tiku.zujuan.com)

已知限制（沙箱网络环境，端到端爬取需实测）：
1. 学科网 / 组卷网均有反爬保护（登录态 + 验证码 + 动态度数限制）。
2. 适配器需要用户提供有效 cookies / session token 才能正常工作。
3. 未对该类站点做端到端网络测试，仅验证适配器注册与框架集成正确。
"""
# mypy: disable-error-code="no-untyped-def,no-any-return,call-overload,operator,type-arg,assignment,var-annotated,misc,index,attr-defined,return-value,func-returns-value,return,has-type,unused-ignore,arg-type,no-untyped-call,type-var,call-arg"

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config import SUBJECTS
from scraper import (
    BaseSourceAdapter,
    ExtractedPaper,
    ExtractedQuestion,
    Fetcher,
    AdapterRegistry,
)
from analyzer import KnowledgeMapper

logger = logging.getLogger("gaokao.edu_adapters")


def _make_cookies_header(cfg: dict) -> dict:
    """从配置中提取 cookies 返回请求头 dict（空 dict 表示无凭据）。"""
    cookies_str = cfg.get("cookies", "").strip()
    if cookies_str:
        return {"Cookie": cookies_str}
    auth_token = cfg.get("auth_token", "").strip()
    if auth_token:
        return {"Authorization": f"Bearer {auth_token}"}
    return {}


# ===========================================================
# 学科网适配器
# ===========================================================

class XueKeWangAdapter(BaseSourceAdapter):
    """学科网 (zxxk.com / zujuan.xkw.com) 专用适配器。

    学科网是 K12 教育资源平台，需要登录态访问试卷详情。
    配置示例:
    ```json
    {
      "id": "xueke_wang",
      "name": "学科网试卷",
      "adapter_type": "xueke_wang",
      "enabled": false,
      "priority": "A",
      "base_url": "https://www.zxxk.com",
      "zujuan_base": "https://zujuan.xkw.com",
      "search_path": "/soft/search.aspx?keyword={keyword}",
      "selectors": {
         "list_item": "a.resource-item, .paper-list a, .search-result a",
         "question_block": ".question-item, .exam-question, .q-box",
         "options": ".option, .options li",
         "answer": ".answer, .correct-answer",
         "score": ".score, .fraction"
      },
      "cookies": "",
      "rate_limit": 5,
      "auth_required": true
    }
    ```
    """

    def __init__(self, source_config: dict,
                 fetcher: Optional[Fetcher] = None,
                 kp_mapper: Optional[KnowledgeMapper] = None):
        super().__init__(source_config, fetcher, kp_mapper)
        self.auth_headers = _make_cookies_header(source_config)

    def _build_headers(self) -> dict:
        """合并 UA + 认证头。"""
        h = dict(self.auth_headers)
        # Fetcher 自动轮换 UA，这里只添加上下文相关的 Referer
        if "zujuan" in self.config.get("base_url", ""):
            h.setdefault("Referer", "https://zujuan.xkw.com/")
        else:
            h.setdefault("Referer", "https://www.zxxk.com/")
        h.setdefault("Accept", "text/html,application/xhtml+xml")
        return h

    def discover(self, subject_key: str, year: int = 2026,
                 keyword: str = "") -> List[Dict[str, Any]]:
        """在学科网发现试卷，返回元数据列表。"""
        subject_name = SUBJECTS.get(subject_key, {}).get("name", subject_key)
        base_url = self.config.get("base_url", "https://www.zxxk.com")
        search_path = self.config.get("search_path", "/soft/search.aspx")

        search_key = keyword or f"{year}年{subject_name}试卷"
        url = f"{base_url}{search_path}?keyword={search_key}"

        # 可选：使用组卷子站 zujuan.xkw.com 更精准
        zujuan_base = self.config.get("zujuan_base", "")
        if zujuan_base:
            search_key2 = keyword or f"{subject_name}"
            url = f"{zujuan_base}/search?keyword={search_key2}&grade=year{year}"

        html = self.fetcher.fetch_text(url, extra_headers=self._build_headers())
        if not html:
            logger.warning("学科网发现失败: %s", url)
            return []

        soup = BeautifulSoup(html, "lxml")
        sel = self.config.get("selectors", {})
        list_sel = sel.get("list_item", "a")
        items = soup.select(list_sel)

        results: List[Dict[str, Any]] = []
        seen_urls: set = set()
        for link in items[:30]:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not href or not title or len(title) < 4:
                continue
            full_url = urljoin(url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # 按关键词过滤
            keywords = [subject_name, "试卷", "试题", "模拟", "高考", str(year)]
            if any(kw in title for kw in keywords):
                results.append({
                    "title": title,
                    "url": full_url,
                    "source": "学科网",
                    "source_id": self.source_id,
                    "priority": self.config.get("priority", "A"),
                    "subject": subject_key,
                    "year": year,
                    "type": "web",
                    "province": None,
                    "metadata": {"referer": base_url},
                })
        logger.info("学科网发现 %s(%s): %d 条", subject_name, year, len(results))
        return results

    def fetch_and_parse(self, item: Dict[str, Any],
                        metadata_only: bool = False) -> Optional[ExtractedPaper]:
        url = item.get("url", "")
        if not url:
            return None
        if metadata_only:
            return ExtractedPaper(
                title=item.get("title", ""),
                subject=item.get("subject", "math"),
                year=item.get("year", 2026),
                source_id=self.source_id,
                source_url=url,
                file_path=None,
                metadata=item.get("metadata", {}),
            )

        html = self.fetcher.fetch_text(url, extra_headers=self._build_headers())
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            title = soup.title.string if soup.title else item.get("title", "")
            title = title.strip()[:200] if title else ""

            questions = self._parse_questions(soup, item.get("subject", "math"))
        except Exception as exc:  # noqa: BLE001
            logger.error("学科网解析失败 %s: %s", url, exc)
            return None

        total = sum(q.score for q in questions)
        if total == 0 and questions:
            total = 150.0

        return ExtractedPaper(
            title=title or item.get("title", ""),
            subject=item.get("subject", "math"),
            year=item.get("year", 2026),
            source_id=self.source_id,
            source_url=url,
            questions=questions,
            total_score=total,
            file_path=None,
            metadata=item.get("metadata", {}),
        )

    def _parse_questions(self, soup: BeautifulSoup,
                         subject: str) -> List[ExtractedQuestion]:
        """从学科网页面中解析题目列表。"""
        sel = self.config.get("selectors", {})
        q_sel = sel.get("question_block", ".question-item, .exam-question")
        nodes = soup.select(q_sel)

        questions: List[ExtractedQuestion] = []
        for node in nodes:
            text = node.get_text(" ", strip=True)
            if not text or len(text) < 5:
                continue

            q_type = self._classify_q_type(text)

            # 选项解析
            options: List[Dict[str, str]] = []
            opt_sel = sel.get("options", ".option, .options li")
            for om in node.select(opt_sel):
                t = om.get_text(strip=True)
                m = re.match(r"^([A-D])[\.、．\)]\s*(.*)", t)
                if m:
                    options.append({"label": m.group(1), "text": m.group(2)})

            # 答案解析
            answer = ""
            ans_sel = sel.get("answer", ".answer, .correct-answer")
            ans_node = node.select_one(ans_sel)
            if ans_node:
                answer = ans_node.get_text(strip=True)

            # 分值推断
            score_sel = sel.get("score", ".score, .fraction")
            score_node = node.select_one(score_sel)
            score = 12.0
            if score_node:
                try:
                    score = float(re.sub(r"[^\d.]", "", score_node.get_text()))
                except (ValueError, TypeError):
                    score = self._guess_score(q_type)
            else:
                score = self._guess_score(q_type)

            kps = self._map_knowledge(text, subject)

            questions.append(ExtractedQuestion(
                q_type=q_type,
                content=text[:2000],  # 限制单题长度
                options=options,
                answer=answer[:200],
                score=score,
                knowledge_points=kps,
            ))
        return questions


# ===========================================================
# 组卷网适配器
# ===========================================================

class ZuJuanWangAdapter(BaseSourceAdapter):
    """组卷网 (zujuan.com / chujuan.cn / 21cnjy.com) 专用适配器。

    组卷网拥有海量中小学题库，支持按知识点/教材版本筛选。
    配置示例:
    ```json
    {
      "id": "zujuan_wang",
      "name": "组卷网试卷",
      "adapter_type": "zujuan_wang",
      "enabled": false,
      "priority": "A",
      "base_url": "https://www.zujuan.com",
      "search_path": "/search?q={keyword}&page=1",
      "subject_mapping": {
         "math": "math",
         "chinese": "chinese",
         "english": "english"
      },
      "selectors": {
         "list_item": ".paper-item, .exam-item, .resource-card, a[href*='paper']",
         "question_block": ".question, .exam-question, .q-container",
         "options": ".option-item, .option",
         "answer": "span.answer, .correct, .key",
         "score": ".score, .fraction, .mark"
      },
      "cookies": "",
      "rate_limit": 5,
      "auth_required": true
    }
    ```
    """

    def __init__(self, source_config: dict,
                 fetcher: Optional[Fetcher] = None,
                 kp_mapper: Optional[KnowledgeMapper] = None):
        super().__init__(source_config, fetcher, kp_mapper)
        self.auth_headers = _make_cookies_header(source_config)
        self.subject_map = source_config.get("subject_mapping", {})

    def _build_headers(self) -> dict:
        h = dict(self.auth_headers)
        h.setdefault("Referer", "https://www.zujuan.com/")
        h.setdefault("Accept", "text/html,application/xhtml+xml")
        return h

    def _map_subject(self, subject_key: str) -> str:
        """将内部 subject key 映射为站点路径片段（支持覆盖）。"""
        return self.subject_map.get(subject_key, subject_key)

    def discover(self, subject_key: str, year: int = 2026,
                 keyword: str = "") -> List[Dict[str, Any]]:
        subject_name = SUBJECTS.get(subject_key, {}).get("name", subject_key)
        site_subject = self._map_subject(subject_key)
        base_url = self.config.get("base_url", "https://www.zujuan.com")
        search_path = self.config.get("search_path", "/search")

        search_key = keyword or f"{year}年{subject_name}试卷"
        if "{year}" in search_path:
            search_path = search_path.replace("{year}", str(year))
        url = f"{base_url}{search_path}".replace("{keyword}", search_key)

        # 对组卷网，也可尝试按科目二级域
        if site_subject and site_subject != subject_key:
            alt_url = f"{base_url}/{site_subject}/paper"
        else:
            alt_url = url

        html = self.fetcher.fetch_text(alt_url, extra_headers=self._build_headers())
        if not html:
            html = self.fetcher.fetch_text(url, extra_headers=self._build_headers())
        if not html:
            logger.warning("组卷网发现失败: %s / %s", url, alt_url)
            return []

        soup = BeautifulSoup(html, "lxml")
        sel = self.config.get("selectors", {})
        list_sel = sel.get("list_item", "a")
        items = soup.select(list_sel)

        results: List[Dict[str, Any]] = []
        seen_urls: set = set()
        for link in items[:30]:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not href or not title or len(title) < 4:
                continue
            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            keywords = [subject_name, "试卷", "试题", "模拟", "高考", str(year)]
            if any(kw in title for kw in keywords):
                results.append({
                    "title": title,
                    "url": full_url,
                    "source": "组卷网",
                    "source_id": self.source_id,
                    "priority": self.config.get("priority", "A"),
                    "subject": subject_key,
                    "year": year,
                    "type": "web",
                    "province": None,
                    "metadata": {"referer": base_url},
                })
        logger.info("组卷网发现 %s(%s): %d 条", subject_name, year, len(results))
        return results

    def fetch_and_parse(self, item: Dict[str, Any],
                        metadata_only: bool = False) -> Optional[ExtractedPaper]:
        url = item.get("url", "")
        if not url:
            return None
        if metadata_only:
            return ExtractedPaper(
                title=item.get("title", ""),
                subject=item.get("subject", "math"),
                year=item.get("year", 2026),
                source_id=self.source_id,
                source_url=url,
                file_path=None,
                metadata=item.get("metadata", {}),
            )

        html = self.fetcher.fetch_text(url, extra_headers=self._build_headers())
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            title = soup.title.string if soup.title else item.get("title", "")
            title = title.strip()[:200] if title else ""

            questions = self._parse_questions(soup, item.get("subject", "math"))
        except Exception as exc:  # noqa: BLE001
            logger.error("组卷网解析失败 %s: %s", url, exc)
            return None

        total = sum(q.score for q in questions)
        if total == 0 and questions:
            total = 150.0

        return ExtractedPaper(
            title=title or item.get("title", ""),
            subject=item.get("subject", "math"),
            year=item.get("year", 2026),
            source_id=self.source_id,
            source_url=url,
            questions=questions,
            total_score=total,
            file_path=None,
            metadata=item.get("metadata", {}),
        )

    def _parse_questions(self, soup: BeautifulSoup,
                         subject: str) -> List[ExtractedQuestion]:
        """从组卷网页面中解析题目列表。"""
        sel = self.config.get("selectors", {})
        q_sel = sel.get("question_block", ".question, .exam-question, .q-container")
        nodes = soup.select(q_sel)

        questions: List[ExtractedQuestion] = []
        for node in nodes:
            text = node.get_text(" ", strip=True)
            if not text or len(text) < 5:
                continue

            q_type = self._classify_q_type(text)

            # 选项解析
            options: List[Dict[str, str]] = []
            opt_sel = sel.get("options", ".option-item, .option")
            for om in node.select(opt_sel):
                t = om.get_text(strip=True)
                m = re.match(r"^([A-D])[\.、．\)]\s*(.*)", t)
                if m:
                    options.append({"label": m.group(1), "text": m.group(2)})

            # 答案解析
            answer = ""
            ans_sel = sel.get("answer", "span.answer, .correct, .key")
            ans_node = node.select_one(ans_sel)
            if ans_node:
                answer = ans_node.get_text(strip=True)

            # 分值
            score_sel = sel.get("score", ".score, .fraction, .mark")
            score_node = node.select_one(score_sel)
            score = 12.0
            if score_node:
                try:
                    score = float(re.sub(r"[^\d.]", "", score_node.get_text()))
                except (ValueError, TypeError):
                    score = self._guess_score(q_type)
            else:
                score = self._guess_score(q_type)

            kps = self._map_knowledge(text, subject)

            questions.append(ExtractedQuestion(
                q_type=q_type,
                content=text[:2000],
                options=options,
                answer=answer[:200],
                score=score,
                knowledge_points=kps,
            ))
        return questions


# ===========================================================
# 自动注册到 AdapterRegistry
# ===========================================================

AdapterRegistry.register("xueke_wang", XueKeWangAdapter)
AdapterRegistry.register("zujuan_wang", ZuJuanWangAdapter)

logger.info("教育站点适配器已注册: xueke_wang, zujuan_wang")
