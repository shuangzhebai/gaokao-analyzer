"""
阶段二（后端核心）：可插拔数据源适配器爬虫框架（弃用 DeepSeek / 任何 LLM 做解析）

设计要点：
- 统一的试卷结构：ExtractedPaper / ExtractedQuestion（dict / dataclass，可 JSON 序列化）。
- 统一网络请求器 Fetcher：UA 池随机轮换、随机延迟、指数退避重试、可选代理钩子、
  超时与异常兜底（所有网络请求唯一出口）。
- 可插拔适配器：BaseSourceAdapter 抽象基类 + AdapterRegistry 注册表。
  * LocalFixtureAdapter：解析本地 HTML / JSON / Markdown 样例卷为结构化字段（无网络、无 LLM）。
  * GenericWebAdapter：BeautifulSoup + 可配置选择器（config 驱动），用于真实站点。
- ScraperManager：据 config 构建适配器；兼容旧 collect_all API（返回元数据 dict 列表）；
  新增 fetch_paper 做结构化抽取，并在落库前调用 DedupEngine 标记 dedup_status。
- 容错：单源失败不影响其他源；解析异常记录日志并返回「部分成功」；支持「仅元数据」模式
  （metadata_only=True，不下载大文件，file_path=None）。

注意：本模块完全不依赖任何 LLM / DeepSeek，结构化抽取由规则 + BeautifulSoup 完成。
"""
# mypy: disable-error-code="no-untyped-def,no-any-return,call-overload,operator,type-arg,assignment,var-annotated,misc,index,attr-defined,return-value,func-returns-value,return,has-type,unused-ignore,arg-type"
import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from analyzer import KnowledgeMapper
from config import (
    DATA_SOURCES,
    DOWNLOAD_DIR,
    SUBJECTS,
    get_data_sources_config,
    get_scraper_network_config,
)
from dedup import DedupEngine
from models import get_db

logger = logging.getLogger("gaokao")

# 项目根目录（用于解析相对 base_dir）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class ExtractedQuestion:
    """统一抽取的题目结构。"""

    q_type: str = "solve"                 # choice / fill / solve
    content: str = ""
    options: List[Dict[str, str]] = field(default_factory=list)
    answer: str = ""
    score: float = 0.0
    knowledge_points: List[str] = field(default_factory=list)
    difficulty_tag: str = ""              # 易 / 中 / 难


@dataclass
class ExtractedPaper:
    """统一抽取的试卷结构（dict / dataclass，可 JSON 序列化）。"""

    title: str = ""
    subject: str = "math"
    year: int = 2026
    source_id: str = ""
    source_url: str = ""
    questions: List[ExtractedQuestion] = field(default_factory=list)
    total_score: float = 0.0
    difficulty_tag: str = ""
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    dedup_status: str = "unique"
    content_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转为可 JSON 序列化的 dict。"""
        return {
            "title": self.title,
            "subject": self.subject,
            "year": self.year,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "questions": [vars(q) for q in self.questions],
            "total_score": self.total_score,
            "difficulty_tag": self.difficulty_tag,
            "file_path": self.file_path,
            "metadata": self.metadata,
            "dedup_status": self.dedup_status,
            "content_hash": self.content_hash,
        }


class Fetcher:
    """统一网络请求器：UA 池随机轮换、随机延迟、指数退避重试、可选代理、超时与异常兜底。

    所有对外网络请求都经过本类，避免散落各处导致反爬策略不一致。
    """

    def __init__(self, network_config: Optional[dict] = None) -> Any:
        self.cfg = network_config or get_scraper_network_config()
        self._ua_pool = self.cfg.get("user_agent_pool") or ["Mozilla/5.0"]
        client_kwargs: Dict[str, Any] = dict(
            timeout=httpx.Timeout(self.cfg.get("timeout", 20)),
            follow_redirects=True,
            verify=self.cfg.get("verify_ssl", True),
            headers={"User-Agent": random.choice(self._ua_pool)},
        )
        proxy = self.cfg.get("proxy")
        if proxy:
            # 兼容不同 httpx 版本：优先 proxies，失败回退 proxy
            try:
                client_kwargs["proxies"] = proxy
            except TypeError:  # pragma: no cover - 旧版 httpx
                client_kwargs["proxy"] = proxy
        self._client = httpx.Client(**client_kwargs)

    def _rotate_ua(self) -> None:
        """随机轮换 User-Agent。"""
        self._client.headers["User-Agent"] = random.choice(self._ua_pool)

    def _random_delay(self) -> None:
        """请求间随机延迟（反爬限频）。"""
        lo = self.cfg.get("min_delay", 1.0)
        hi = self.cfg.get("max_delay", 3.0)
        time.sleep(random.uniform(lo, hi))

    def fetch_text(self, url: str, extra_headers: Optional[dict] = None,
                   **kwargs) -> Optional[str]:
        """带指数退避重试的 GET，返回文本内容；失败返回 None 并记录日志。

        任何异常都被兜底捕获，调用方据此走「部分成功」逻辑，不会整体崩溃。
        extra_headers：适配器传入的认证/上下文头（如 Cookie/Referer），合并为 headers。
        """
        max_retries = self.cfg.get("max_retries", 3)
        base = self.cfg.get("backoff_base", 2.0)
        cap = self.cfg.get("backoff_max", 30.0)
        last_err: Optional[str] = None
        req_kwargs: Dict[str, Any] = dict(kwargs)
        if extra_headers:
            req_kwargs["headers"] = extra_headers
        for attempt in range(max_retries):
            try:
                self._rotate_ua()
                resp = self._client.get(url, **req_kwargs)
                if resp.status_code == 200:
                    return resp.text
                last_err = f"HTTP {resp.status_code}"
                logger.warning("Fetcher %s 返回 %s（尝试 %d/%d）",
                               url, resp.status_code, attempt + 1, max_retries)
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                logger.warning("Fetcher 请求 %s 失败: %s（尝试 %d/%d）",
                               url, exc, attempt + 1, max_retries)
            # 指数退避（最后一次不等待）
            if attempt < max_retries - 1:
                time.sleep(min(cap, base ** (attempt + 1)))
        logger.error("Fetcher 放弃 %s：%s", url, last_err)
        return None

    def fetch_bytes(self, url: str, extra_headers: Optional[dict] = None,
                   **kwargs) -> Optional[bytes]:
        """带指数退避重试的 GET，返回二进制内容（用于下载大文件）。"""
        max_retries = self.cfg.get("max_retries", 3)
        base = self.cfg.get("backoff_base", 2.0)
        cap = self.cfg.get("backoff_max", 30.0)
        req_kwargs: Dict[str, Any] = dict(kwargs)
        if extra_headers:
            req_kwargs["headers"] = extra_headers
        for attempt in range(max_retries):
            try:
                self._rotate_ua()
                resp = self._client.get(url, **req_kwargs)
                if resp.status_code == 200:
                    return resp.content
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fetcher 下载 %s 失败: %s（尝试 %d/%d）",
                               url, exc, attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(min(cap, base ** (attempt + 1)))
        return None

    def close(self) -> None:
        """关闭底层 httpx 客户端。"""
        try:
            self._client.close()
        except Exception:  # noqa: BLE001
            pass


class BaseSourceAdapter(ABC):
    """数据源适配器抽象基类。

    子类需实现两个核心方法：
    - discover：在数据源中发现候选试卷，返回元数据 dict 列表（字段兼容旧 collect_all：
      title / url / source / source_id / priority / subject / year / type / province）。
    - fetch_and_parse：下载并结构化抽取为 ExtractedPaper。
    """

    # 题型默认分值（当样例未给出分值时回退）
    Q_TYPE_DEFAULT_SCORE = {"choice": 5.0, "fill": 5.0, "solve": 12.0}

    def __init__(self, source_config: dict,
                 fetcher: Optional[Fetcher] = None,
                 kp_mapper: Optional[KnowledgeMapper] = None):
        self.config = source_config
        self.source_id = source_config.get("id", "unknown")
        self.fetcher = fetcher or Fetcher()
        self.kp_mapper = kp_mapper or KnowledgeMapper()

    @abstractmethod
    def discover(self, subject_key: str, year: int = 2026,
                 keyword: str = "") -> List[Dict[str, Any]]:
        """发现候选试卷，返回元数据 dict 列表。"""
        ...

    @abstractmethod
    def fetch_and_parse(self, item: Dict[str, Any],
                        metadata_only: bool = False) -> Optional[ExtractedPaper]:
        """下载并结构化抽取为 ExtractedPaper。

        metadata_only=True 时不下载大文件，file_path=None（仅元数据模式）。
        """
        ...

    # ---------- 通用工具方法（供子类复用） ----------

    def _classify_q_type(self, text: str, default: str = "solve") -> str:
        """根据文本关键词推断题型。"""
        t = text or ""
        if any(k in t for k in ["选择", "下列", "不正确", "正确", "选项", "选项"]):
            return "choice"
        if any(k in t for k in ["填空", "填入"]):
            return "fill"
        return default

    def _guess_score(self, q_type: str, fallback: Optional[float] = None) -> float:
        """分值推断：优先使用显式分值。"""
        if fallback is not None:
            return float(fallback)
        return float(self.Q_TYPE_DEFAULT_SCORE.get(q_type, 12.0))

    def _map_knowledge(self, content: str, subject: str) -> List[str]:
        """知识点映射（容错：失败返回空列表）。"""
        try:
            return self.kp_mapper.map_question(content or "", subject)
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _difficulty_tag(p_correct: Optional[float]) -> str:
        """由正确率推断难度标签。"""
        if p_correct is None:
            return ""
        if p_correct >= 0.7:
            return "易"
        if p_correct >= 0.4:
            return "中"
        return "难"


class LocalFixtureAdapter(BaseSourceAdapter):
    """解析本地 HTML / JSON / Markdown 样例卷为结构化字段（无网络、无 LLM）。"""

    def discover(self, subject_key: str, year: int = 2026, keyword: str = "") -> List[Dict[str, Any]]:
        base_dir = self.config.get("base_dir", "tests/fixtures/papers")
        if not os.path.isabs(base_dir):
            base_dir = os.path.join(BASE_DIR, base_dir)
        if not os.path.isdir(base_dir):
            logger.warning("fixture 目录不存在: %s", base_dir)
            return []
        results: List[Dict[str, Any]] = []
        recursive = self.config.get("recursive", True)
        if recursive:
            walker = os.walk(base_dir)
        else:
            files = [f for f in os.listdir(base_dir) if os.path.isfile(os.path.join(base_dir, f))]
            walker = [(base_dir, [], files)]  # type: ignore[list-item]

        for root, _dirs, files in walker:
            for fname in sorted(files):
                if fname.startswith("."):
                    continue
                path = os.path.join(root, fname)
                title = os.path.splitext(fname)[0]
                results.append({
                    "title": title,
                    "url": path,                       # 本地路径作为 url（fixture 场景）
                    "source": self.config.get("name", "本地样例"),
                    "source_id": self.source_id,
                    "priority": self.config.get("priority", "S"),
                    "subject": subject_key,
                    "year": year,
                    "type": "fixture",
                    "province": None,
                    "file_path": path,
                    "format": self.config.get("format", "auto"),
                })
        return results

    def fetch_and_parse(self, item: Dict[str, Any],
                        metadata_only: bool = False) -> Optional[ExtractedPaper]:
        path = item.get("url") or item.get("file_path")
        if not path or not os.path.isfile(path):
            logger.warning("fixture 文件缺失: %s", path)
            return None
        fmt = item.get("format") or self.config.get("format", "auto")
        subject = item.get("subject", "math")
        try:
            if fmt == "auto":
                ext = os.path.splitext(path)[1].lower()
                if ext == ".json":
                    fmt = "json"
                elif ext in (".html", ".htm"):
                    fmt = "html"
                elif ext in (".md", ".markdown"):
                    fmt = "markdown"
                else:
                    fmt = "html"
            if fmt == "json":
                paper = self._parse_json(path, subject)
            elif fmt == "markdown":
                paper = self._parse_markdown(path, subject)
            else:
                paper = self._parse_html(path, subject)
        except Exception as exc:  # noqa: BLE001
            logger.error("解析 fixture 失败 %s: %s", path, exc)
            return None

        paper.source_id = self.source_id
        paper.source_url = item.get("url", "")
        paper.year = item.get("year", 2026)
        paper.file_path = None if metadata_only else path
        paper.metadata = {**item.get("metadata", {}), "format": fmt, "fixture": True}
        return paper

    # ---------- 各格式解析 ----------

    def _parse_json(self, path: str, subject: str) -> ExtractedPaper:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        questions: List[ExtractedQuestion] = []
        for q in data.get("questions", []):
            q_type = q.get("q_type") or self._classify_q_type(q.get("content", ""))
            content = q.get("content", "")
            kps = q.get("knowledge_points") or self._map_knowledge(content, subject)
            questions.append(ExtractedQuestion(
                q_type=q_type,
                content=content,
                options=q.get("options", []),
                answer=str(q.get("answer", "")),
                score=self._guess_score(q_type, q.get("score")),
                knowledge_points=kps,
                difficulty_tag=q.get("difficulty_tag", ""),
            ))
        return ExtractedPaper(
            title=data.get("title", os.path.basename(path)),
            subject=subject,
            year=data.get("year", 2026),
            questions=questions,
            total_score=float(sum(q.score for q in questions) or data.get("total_score", 0)),
        )

    def _parse_html(self, path: str, subject: str) -> ExtractedPaper:
        with open(path, "r", encoding="utf-8") as fh:
            soup = BeautifulSoup(fh.read(), "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        title = soup.title.string if soup.title else os.path.basename(path)
        questions = self._extract_questions(soup.get_text("\n"), subject)
        return ExtractedPaper(
            title=title or os.path.basename(path),
            subject=subject,
            questions=questions,
            total_score=float(sum(q.score for q in questions)),
        )

    def _parse_markdown(self, path: str, subject: str) -> ExtractedPaper:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        # 去掉 YAML front-matter（若存在）
        if text.startswith("---"):
            parts = text.split("---", 2)
            text = parts[-1] if len(parts) >= 3 else text
        title = os.path.basename(path)
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if m:
            title = m.group(1).strip()
        questions = self._extract_questions(text, subject)
        return ExtractedPaper(
            title=title,
            subject=subject,
            questions=questions,
            total_score=float(sum(q.score for q in questions)),
        )

    def _extract_questions(self, text: str, subject: str) -> List[ExtractedQuestion]:
        """通用文本题目抽取：按题号切分，抽取选项与答案。"""
        questions: List[ExtractedQuestion] = []
        # 以「数字.」作为题号边界切分；capturing group 会把题号保留在结果中
        blocks = re.split(r"\n\s*(\d{1,2})[\.、．\)]\s+", text)
        idx = 1
        while idx + 1 < len(blocks):
            _num = blocks[idx]
            body = blocks[idx + 1]
            idx += 2
            q_type = self._classify_q_type(body)
            options: List[Dict[str, str]] = []
            for om in re.finditer(r"\n\s*([A-D])[\.、．\)]\s*(.+)", body):
                options.append({"label": om.group(1), "text": om.group(2).strip()})
            ans_match = re.search(r"答案[：:]\s*([A-D\d\.\u4e00-\u9fa5]+)", body)
            answer = ans_match.group(1).strip() if ans_match else ""
            score = self._guess_score(q_type)
            content = body.strip()
            kps = self._map_knowledge(content, subject)
            questions.append(ExtractedQuestion(
                q_type=q_type,
                content=content,
                options=options,
                answer=answer,
                score=score,
                knowledge_points=kps,
                difficulty_tag="",
            ))
        return questions


class GenericWebAdapter(BaseSourceAdapter):
    """通用网页适配器：BeautifulSoup + 可配置选择器（config 驱动），用于真实站点。

    所有网络请求统一经 Fetcher（UA 池 / 延迟 / 退避 / 超时兜底）。依据 config 的
    selectors 抽取列表项与题目字段；选择器为空时退化为通用启发式解析。
    """

    def discover(self, subject_key: str, year: int = 2026, keyword: str = "") -> List[Dict[str, Any]]:
        subject_name = SUBJECTS.get(subject_key, {}).get("name", subject_key)
        base_url = self.config.get("base_url", "")
        search_path = self.config.get("search_path", "/search")
        if "{" in search_path:                       # 支持 {year} 占位符
            url = base_url + search_path.format(year=year)
        else:
            search_key = keyword or f"{year}届{subject_name}高考模拟"
            url = f"{base_url}{search_path}?q={quote(search_key)}"

        html = self.fetcher.fetch_text(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        sel = self.config.get("selectors", {})
        items = soup.select(sel.get("list_item", "a"))
        results: List[Dict[str, Any]] = []
        for link in items[:20]:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not href or not title:
                continue
            full_url = urljoin(url, href)
            if subject_name in title or "高考" in title or "模拟" in title or keyword in title:
                results.append({
                    "title": title,
                    "url": full_url,
                    "source": self.config.get("name", "网页源"),
                    "source_id": self.source_id,
                    "priority": self.config.get("priority", "B"),
                    "subject": subject_key,
                    "year": year,
                    "type": "web",
                    "province": None,
                })
        return results

    def fetch_and_parse(self, item: Dict[str, Any],
                        metadata_only: bool = False) -> Optional[ExtractedPaper]:
        subject = item.get("subject", "math")
        # 仅元数据模式：不下载正文，返回带元数据的空题卷
        if metadata_only:
            return ExtractedPaper(
                title=item.get("title", ""),
                subject=subject,
                year=item.get("year", 2026),
                source_id=self.source_id,
                source_url=item.get("url", ""),
                file_path=None,
                metadata=item.get("metadata", {}),
            )
        url = item.get("url", "")
        html = self.fetcher.fetch_text(url)
        if not html:
            return None
        sel = self.config.get("selectors", {})
        try:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style"]):
                tag.decompose()
            title = soup.title.string if soup.title else item.get("title", "")
            questions = self._parse_questions(soup, sel, subject)
        except Exception as exc:  # noqa: BLE001
            logger.error("网页解析失败 %s: %s", url, exc)
            return None

        total = float(sum(q.score for q in questions)) or 0.0
        if total == 0 and questions:
            total = 150.0
        return ExtractedPaper(
            title=title or item.get("title", ""),
            subject=subject,
            year=item.get("year", 2026),
            source_id=self.source_id,
            source_url=url,
            questions=questions,
            total_score=total,
            file_path=None,
            metadata=item.get("metadata", {}),
        )

    def _parse_questions(self, soup: BeautifulSoup, sel: dict,
                         subject: str) -> List[ExtractedQuestion]:
        q_sel = sel.get("question_block") or ".question, .q, li"
        nodes = soup.select(q_sel)
        questions: List[ExtractedQuestion] = []
        for node in nodes:
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            q_type = self._classify_q_type(text)
            options: List[Dict[str, str]] = []
            opt_sel = sel.get("options")
            if opt_sel:
                for om in node.select(opt_sel):
                    t = om.get_text(strip=True)
                    m = re.match(r"^([A-D])[\.、．\)]\s*(.*)", t)
                    if m:
                        options.append({"label": m.group(1), "text": m.group(2)})
            answer = ""
            ans_sel = sel.get("answer")
            if ans_sel:
                ans_node = node.select_one(ans_sel)
                if ans_node:
                    answer = ans_node.get_text(strip=True)
            score = self._guess_score(q_type)
            kps = self._map_knowledge(text, subject)
            questions.append(ExtractedQuestion(
                q_type=q_type,
                content=text,
                options=options,
                answer=answer,
                score=score,
                knowledge_points=kps,
            ))
        return questions


class AdapterRegistry:
    """适配器注册表：类型名 -> 类。支持运行时注册自定义适配器。"""

    _registry = {
        "local_fixture": LocalFixtureAdapter,
        "generic_web": GenericWebAdapter,
    }

    @classmethod
    def register(cls, adapter_type: str, adapter_cls) -> None:
        """注册（或覆盖）一个适配器类。"""
        cls._registry[adapter_type] = adapter_cls

    @classmethod
    def get(cls, adapter_type: str) -> Any:
        """获取适配器类；未知类型返回 None。"""
        return cls._registry.get(adapter_type)

    @classmethod
    def available(cls) -> List[str]:
        """返回已注册的适配器类型列表。"""
        return list(cls._registry.keys())


class ScraperManager:
    """爬虫管理器：构建适配器、兼容旧 collect_all API、fetch_paper 结构化抽取、ingest 落库前去重。

    - collect_all：仅发现候选元数据（兼容 routes/scrape.py 既有调用与字段契约）。
    - fetch_paper：结构化抽取单份试卷为 ExtractedPaper，并在落库前调用 DedupEngine 标记
      dedup_status（弃用 LLM，纯规则/BS4 抽取）。
    """

    def __init__(self, data_sources: Optional[List[dict]] = None,
                 network_config: Optional[dict] = None,
                 deepseek_api_key: str = ""):
        self.sources_cfg = data_sources if data_sources is not None else get_data_sources_config()
        self.network = network_config or get_scraper_network_config()
        self.fetcher = Fetcher(self.network)
        self.kp_mapper = KnowledgeMapper()
        self.dedup = DedupEngine(deepseek_api_key=deepseek_api_key or None)
        self._adapters: Dict[str, BaseSourceAdapter] = {}
        self._build_adapters()

    def _build_adapters(self) -> None:
        """据数据源配置构建适配器实例。"""
        for src in self.sources_cfg:
            if not src.get("enabled", True):
                continue
            adapter_cls = AdapterRegistry.get(src.get("adapter_type", "generic_web"))
            if adapter_cls is None:
                logger.warning("未知适配器类型: %s（源 %s 跳过）",
                               src.get("adapter_type"), src.get("id"))
                continue
            try:
                self._adapters[src["id"]] = adapter_cls(src, self.fetcher, self.kp_mapper)
            except Exception as exc:  # noqa: BLE001
                logger.error("适配器初始化失败 %s: %s", src.get("id"), exc)

    # ---- 兼容旧 API：仅发现候选元数据 ----
    async def collect_all(self, year: int = 2026,
                          subjects: Optional[List[str]] = None,
                          keyword: str = "") -> List[Dict[str, Any]]:
        """发现所有启用数据源的候选试卷元数据（兼容旧契约）。

        单源失败不影响其他源；返回列表可能包含 {"error": ...} 项。
        """
        if subjects is None:
            subjects = list(SUBJECTS.keys())
        all_results: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.network.get("max_concurrent", 3) or 3)

        async def _discover_one(source_id: str, subject_key: str) -> List[Dict[str, Any]]:
            adapter = self._adapters.get(source_id)
            if not adapter:
                return []
            async with semaphore:
                try:
                    loop = asyncio.get_event_loop()
                    items = await loop.run_in_executor(
                        None, lambda: adapter.discover(subject_key, year, keyword)
                    )
                    for it in items:
                        it["source_id"] = source_id
                    return items
                except Exception as exc:  # noqa: BLE001
                    logger.error("发现失败 %s/%s: %s", source_id, subject_key, exc)
                    return [{"error": str(exc), "source_id": source_id}]

        tasks = [_discover_one(sid, sub)
                 for sid in self._adapters for sub in subjects]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                all_results.extend(res)
            elif isinstance(res, Exception):
                logger.error("collect_all 任务异常: %s", res)

        # 按 url 去重
        seen, unique = set(), []
        for it in all_results:
            u = it.get("url", "")
            if u and u not in seen:
                seen.add(u)
                unique.append(it)
        return unique

    async def fetch_paper(self, item: Dict[str, Any],
                          metadata_only: bool = False) -> Optional[ExtractedPaper]:
        """结构化抽取单份试卷（含落库前去重标记）。

        Args:
            item: 候选元数据（至少含 source_id / url / title / subject / year）。
            metadata_only: True 时不下载大文件，file_path=None。
        Returns:
            ExtractedPaper 或 None（源缺失 / 抽取失败）。
        """
        source_id = item.get("source_id") or item.get("id")
        adapter = self._adapters.get(source_id)
        if adapter is None:
            for ad in self._adapters.values():
                if ad.source_id == source_id:
                    adapter = ad
                    break
        if adapter is None:
            logger.warning("未找到源 %s 的适配器，无法抽取", source_id)
            return None

        # 结构化抽取（CPU/IO 放线程池，避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        paper = await loop.run_in_executor(None, adapter.fetch_and_parse, item, metadata_only)
        if paper is None:
            return None

        # 落库前去重：标记 dedup_status（容错：失败则视为 unique）
        try:
            content_hash = self._content_hash(item, adapter, paper.questions)
            paper.content_hash = content_hash
            dedup_result = await self.dedup.check_duplicate(
                title=paper.title or item.get("title", ""),
                subject_id=paper.subject,
                year=paper.year,
                source_url=paper.source_url or item.get("url", ""),
                content_hash=content_hash,
            )
            paper.dedup_status = dedup_result["status"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("去重检查失败（跳过）: %s", exc)
            paper.dedup_status = "unique"
        return paper

    @staticmethod
    def _content_hash(item: Dict[str, Any], adapter: BaseSourceAdapter,
                      questions: Optional[List[ExtractedQuestion]] = None) -> str:
        """内容哈希（标题 + url + 源 + 首题内容片段），用于查重，降低碰撞率。"""
        raw = "|".join([
            str(item.get("title", "")),
            str(item.get("url", "")),
            adapter.source_id,
        ])
        if questions:
            raw += "|" + questions[0].content[:100]
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    async def close(self) -> None:
        """关闭底层资源。"""
        try:
            self.fetcher.close()
        except Exception:  # noqa: BLE001
            pass


__all__ = [
    "ExtractedQuestion",
    "ExtractedPaper",
    "Fetcher",
    "BaseSourceAdapter",
    "LocalFixtureAdapter",
    "GenericWebAdapter",
    "AdapterRegistry",
    "ScraperManager",
]
