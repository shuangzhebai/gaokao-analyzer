#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实卷子爬虫运行器 — gaokao-analyzer 数据采集 v6.1 落地。

复用项目既有爬虫框架（scraper.ScraperManager + edu_source_adapters 的
学科网/组卷网适配器），注入你的登录态 Cookie 后，按「学科 × 年份」驱动：
    discover（发现候选）→ fetch_paper（结构化抽取 + 去重）→ 落库（papers/questions）

──────────────────────────────────────────────────────────
使用前提（合法合规 · 个人使用）
- 你本人是学科网/组卷网的付费订阅用户，仅下载自己账号有权访问的卷子，用于个人分析。
- 凭据以「浏览器登录后的 Cookie 字符串」提供；本脚本不实现自动登录 / 验证码绕过。
- 遵守站点限频（默认每源间隔 5 秒），不用于转售或再分发。
──────────────────────────────────────────────────────────

凭据配置（credentials.json，已被 .gitignore 忽略，切勿提交）：
{
  "xueke_wang": {"cookies": "xxx=...; yyy=..."},
  "zujuan_wang": {"cookies": "xxx=...; yyy=..."}
}
或环境变量：XKW_COOKIE=...  ZUJUAN_COOKIE=...

运行：
  python scripts/crawl_real_papers.py --dry-run                 # 仅发现，验证 Cookie 是否有效
  python scripts/crawl_real_papers.py                           # 全量爬取并落库（近 5 年 × 9 学科）
  python scripts/crawl_real_papers.py --subjects math --years 2024 --limit 20
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "gaokao.db"
CRED_PATH = ROOT / "credentials.json"

import config
import edu_source_adapters  # 触发适配器注册（xueke_wang / zujuan_wang）
from scraper import ScraperManager, ExtractedPaper


# ===========================================================================
# 凭据加载
# ===========================================================================
def load_credentials() -> dict:
    """从 credentials.json 与环境变量读取凭据（环境变量优先）。"""
    creds: dict = {}
    if os.environ.get("XKW_COOKIE"):
        creds["xueke_wang"] = {"cookies": os.environ["XKW_COOKIE"]}
    if os.environ.get("ZUJUAN_COOKIE"):
        creds["zujuan_wang"] = {"cookies": os.environ["ZUJUAN_COOKIE"]}
    if CRED_PATH.exists():
        try:
            creds.update(json.loads(CRED_PATH.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            print(f"[警告] 读取 {CRED_PATH} 失败: {exc}")
    # 去掉示例占位（未真正填值）
    for sid in list(creds):
        c = creds[sid]
        if not (c.get("cookies") and "在此粘贴" not in c.get("cookies", "")) and \
           not c.get("auth_token"):
            creds.pop(sid, None)
    return creds


def ensure_credentials(args) -> dict:
    """读取凭据；若为空且未禁用自动抽取，则尝试从已登录浏览器抠 Cookie。"""
    creds = load_credentials()
    if creds or getattr(args, "no_grab", False):
        return creds
    try:
        import grab_cookies
        print("[*] 未找到凭据，尝试从已登录浏览器自动抽取 Cookie ...")
        grabbed = grab_cookies.grab_all()
        if grabbed:
            return load_credentials()  # 重新读取刚写入的 credentials.json
    except Exception as exc:  # noqa: BLE001
        print(f"[警告] 自动抽取失败: {exc}")
    return creds


def build_sources(creds: dict) -> list:
    """深拷贝 DATA_SOURCES，注入凭据并启用对应源（不改全局配置）。

    本脚本定位为「真实卷子爬虫」，强制关闭 local_fixture（测试样例源），
    避免把本地 fixture 当真实卷入库。
    """
    sources = copy.deepcopy(config.DATA_SOURCES)
    for src in sources:
        if src.get("id") == "local_fixture":
            src["enabled"] = False
            continue
        sid = src.get("id")
        if sid in creds and creds[sid].get("cookies"):
            src["cookies"] = creds[sid]["cookies"]
            src["enabled"] = True
        elif sid in creds and creds[sid].get("auth_token"):
            src["auth_token"] = creds[sid]["auth_token"]
            src["enabled"] = True
    return sources


# ===========================================================================
# 落库（复用 seed 脚本已验证的 schema 写法，动态写入避免 NOT NULL 报错）
# ===========================================================================
def cols_info(conn: sqlite3.Connection, table: str):
    return [(r[1], r[2], r[3]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def insert_row(conn: sqlite3.Connection, table: str, values: dict) -> int:
    ci = cols_info(conn, table)
    notnull = {name for name, _, nn in ci if nn == 1}
    final: dict = {}
    for name, ctype, _ in ci:
        if name == "id":
            continue
        if name in values and values[name] is not None:
            final[name] = values[name]
        elif name in notnull:
            final[name] = "" if ("CHAR" in ctype or "TEXT" in ctype or "CLOB" in ctype) else 0
    cols = list(final)
    placeholders = ",".join("?" for _ in cols)
    conn.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                 [final[c] for c in cols])
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def qtype_map(conn: sqlite3.Connection, subject: str) -> dict:
    """构建 main_type -> question_types.id 映射（best-effort）。"""
    rows = conn.execute(
        "SELECT id, main_type FROM question_types WHERE subject_id=?", (subject,)
    ).fetchall()
    m = {r[1]: r[0] for r in rows}
    # 题型归一：solve -> calc
    if "solve" in m and "calc" not in m:
        m["calc"] = m["solve"]
    return m


def persist_paper(conn: sqlite3.Connection, paper: ExtractedPaper) -> str:
    """落库单份试卷 + 题目。已存在 content_hash 则跳过。返回 saved/skipped。"""
    ch = paper.content_hash or hashlib.sha256(
        (paper.title + paper.source_url).encode("utf-8")).hexdigest()[:32]
    if conn.execute("SELECT 1 FROM papers WHERE content_hash=?", (ch,)).fetchone():
        return "skipped"
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    qmap = qtype_map(conn, paper.subject)
    pid = insert_row(conn, "papers", {
        "title": paper.title,
        "subject_id": paper.subject,
        "paper_type": "real",
        "year": paper.year,
        "exam_tag": "real-crawl",
        "source_id": paper.source_id,
        "source_url": paper.source_url,
        "source_priority": "high",
        "collected_at": ts,
        "collector": "real-crawl",
        "verified": 1,
        "total_score": paper.total_score or 0.0,
        "difficulty_tag": paper.difficulty_tag or "",
        "question_count": len(paper.questions),
        "analysis_status": "pending",
        "content_hash": ch,
        "dedup_status": paper.dedup_status or "unique",
        "created_at": ts,
        "updated_at": ts,
    })
    for i, q in enumerate(paper.questions, 1):
        opts = json.dumps(q.options, ensure_ascii=False) if q.options else None
        qtid = qmap.get(q.q_type, next(iter(qmap.values()), 0)) if qmap else 0
        insert_row(conn, "questions", {
            "paper_id": pid,
            "q_number": i,
            "q_type": q.q_type,
            "content": q.content,
            "options": opts,
            "answer": q.answer,
            "score": q.score,
            "knowledge_points": json.dumps(q.knowledge_points, ensure_ascii=False) if q.knowledge_points else None,
            "difficulty_tag": q.difficulty_tag or "",
            "content_hash": hashlib.sha256(
                (paper.source_url + str(i) + q.content[:50]).encode("utf-8")).hexdigest()[:32],
            "question_type_id": qtid,
        })
    return "saved"


# ===========================================================================
# 主流程
# ===========================================================================
async def run(args, creds: dict) -> None:
    sources = build_sources(creds)
    enabled = [s["id"] for s in sources if s.get("enabled")]
    if not enabled:
        print("[错误] 没有任何「已启用且已配置凭据」的源。请先在 credentials.json 填入 Cookie。")
        print("        参考 credentials.example.json；或用环境变量 XKW_COOKIE / ZUJUAN_COOKIE。")
        return

    print(f"[*] 启用数据源: {enabled}")
    manager = ScraperManager(data_sources=sources)
    subjects = args.subjects or list(config.SUBJECTS.keys())
    years = args.years or list(range(2021, 2026))  # 近 5 年

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=OFF")
    total_saved = total_skip = total_fail = 0
    try:
        for subject in subjects:
            for year in years:
                items = await manager.collect_all(year=year, subjects=[subject])
                print(f"[发现] {subject} {year}: {len(items)} 条候选")
                if args.dry_run:
                    continue
                for item in (items[:args.limit] if args.limit else items):
                    try:
                        paper = await manager.fetch_paper(item)
                        if paper is None:
                            total_fail += 1
                            continue
                        rl = next((s.get("rate_limit", 5)
                                  for s in sources if s["id"] == paper.source_id), 5)
                        status = persist_paper(conn, paper)
                        if status == "saved":
                            total_saved += 1
                        else:
                            total_skip += 1
                        conn.commit()
                        time.sleep(max(rl, args.delay))  # 礼貌限频
                    except Exception as exc:  # noqa: BLE001
                        total_fail += 1
                        print(f"[失败] {item.get('title', '')}: {exc}")
                        conn.rollback()
    finally:
        conn.close()
        await manager.close()
    print(f"[完成] 保存 {total_saved} / 跳过(重复) {total_skip} / 失败 {total_fail}")


def main() -> None:
    ap = argparse.ArgumentParser(description="gaokao-analyzer 真实卷子爬虫运行器")
    ap.add_argument("--subjects", nargs="+", help="限定学科（默认全部 9 科）")
    ap.add_argument("--years", nargs="+", type=int, help="限定年份（默认 2021-2025）")
    ap.add_argument("--limit", type=int, default=0, help="每个(学科,年份)最多抓取卷数（0=不限制）")
    ap.add_argument("--delay", type=float, default=3.0, help="每卷之间最小间隔秒（默认 3，叠加源 rate_limit）")
    ap.add_argument("--dry-run", action="store_true", help="仅发现候选，不下载正文、不落库（验证 Cookie 用）")
    ap.add_argument("--no-grab", action="store_true", help="禁用「无凭据时自动从浏览器抽取」")
    args = ap.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"找不到数据库：{DB_PATH}")

    creds = ensure_credentials(args)
    asyncio.run(run(args, creds))


if __name__ == "__main__":
    main()
