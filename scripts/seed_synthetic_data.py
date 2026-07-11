#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合成种子数据采集脚本 — gaokao-analyzer v6.1 数据采集落地。

向 data/gaokao.db 灌入「合成模拟卷 + 近 5 年真题风格卷」，
严格按照现有真实 schema（papers / questions / subjects / knowledge_points /
question_types / sources）写入，使智能组卷、质量诊断、多维检索可端到端演示与压测。

说明：
- 学科网 / 组卷网需付费登录，本脚本生成的是 *结构化合成数据*（非真实版权卷），
  用于打通采集→入库→组卷全链路；真实卷子请走 edu_source_adapters / auto_scraper
  提供的导入通道（见报告 6.2）。
- 幂等：重跑先清除 collector='seed-script' 的合成行与合成知识点/题型，再重新生成。
- 动态读取表结构，NOT NULL 列自动兜底，避免踩字段约束。

用法：
    python scripts/seed_synthetic_data.py            # 默认 1000 模拟卷 + 5 年真题风格卷
    python scripts/seed_synthetic_data.py --mock 200 --real-years 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "gaokao.db"
COLLECTOR = "seed-script"
SOURCE_ID = "synthetic"

# 9 大学科：id, 中文名, 满分, 考试时长(分钟)
SUBJECTS = [
    ("chinese", "语文", 150, 150),
    ("math", "数学", 150, 120),
    ("english", "英语", 150, 120),
    ("physics", "物理", 100, 90),
    ("chemistry", "化学", 100, 90),
    ("biology", "生物", 100, 90),
    ("politics", "政治", 100, 90),
    ("history", "历史", 100, 90),
    ("geography", "地理", 100, 90),
]

PROVINCES = ["全国", "北京", "上海", "江苏", "浙江", "广东", "山东", "河南", "四川", "湖北"]
DIFFS = ["easy", "medium", "hard"]
DIFF_CN = {"easy": "易", "medium": "中", "hard": "难"}
COGNITIVE = ["记忆", "理解", "应用", "分析", "评价", "创造"]
CORE = ["数学抽象", "逻辑推理", "直观想象", "数学运算", "数据分析", "数学建模",
        "宏观辨识", "变化观念", "证据推理", "模型认知", "生命观念", "科学探究"]
# 题型：main_type, sub_type, name_cn
Q_TYPES = [
    ("choice", "单选", "选择题(合成)"),
    ("multi", "多选", "多选题(合成)"),
    ("fill", "填空", "填空题(合成)"),
    ("calc", "解答", "解答题(合成)"),
    ("exp", "实验", "实验题(合成)"),
]
# 每个学科若干知识点（code 前缀 SYN- 便于幂等清除）
KP_POOL = {
    "math": ["函数与导数", "三角函数", "数列", "立体几何", "解析几何", "概率统计", "不等式", "复数"],
    "chinese": ["现代文阅读", "古诗文默写", "文言文翻译", "语言文字运用", "作文", "文学类文本"],
    "english": ["阅读理解", "完形填空", "语法填空", "书面表达", "七选五", "听力理解"],
    "physics": ["力学", "电磁学", "热学", "光学", "原子物理", "实验探究"],
    "chemistry": ["物质的量", "氧化还原反应", "元素周期律", "化学反应原理", "有机化学", "实验设计"],
    "biology": ["细胞结构", "遗传与进化", "稳态调节", "生态系统", "生物技术", "分子与代谢"],
    "politics": ["经济生活", "政治生活", "文化生活", "生活与哲学", "当代国际"],
    "history": ["中国古代史", "中国近现代史", "世界史", "史料实证", "历史解释"],
    "geography": ["自然地理", "人文地理", "区域地理", "地理实践力", "人地协调"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def make_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def cols_info(conn: sqlite3.Connection, table: str):
    return [(r[1], r[2], r[3]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def insert_row(conn: sqlite3.Connection, table: str, values: dict) -> int:
    """动态 INSERT：仅写入提供的列；NOT NULL 缺失时按类型兜底，保证不报约束错误。"""
    ci = cols_info(conn, table)
    notnull = {name for name, _ctype, nn in ci if nn == 1}
    final: dict = {}
    for name, ctype, _ in ci:
        if name == "id":
            continue
        if name in values and values[name] is not None:
            final[name] = values[name]
        elif name in notnull:
            final[name] = "" if "CHAR" in ctype or "TEXT" in ctype or "CLOB" in ctype else 0
        # 其余：可空且未提供 -> 省略（写入 NULL）
    cols = list(final)
    placeholders = ",".join("?" for _ in cols)
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    conn.execute(sql, [final[c] for c in cols])
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_subjects(conn: sqlite3.Connection) -> None:
    for sid, name, total, tmin in SUBJECTS:
        conn.execute(
            "INSERT OR REPLACE INTO subjects (id, name, total_score, time_min) VALUES (?,?,?,?)",
            (sid, name, total, tmin),
        )


def seed_source(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sources "
        "(id, name, base_url, priority, enabled, rate_limit, description) "
        "VALUES (?,?,?,?,?,?,?)",
        (SOURCE_ID, "合成种子数据", "", "normal", 1, 0,
         "本仓库 seed 脚本生成的合成数据，非真实版权卷，用于演示与压测。"),
    )


def seed_knowledge_points(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM knowledge_points WHERE code LIKE 'SYN-%'")
    kp_id = 1
    for sid, _, _, _ in SUBJECTS:
        for kp in KP_POOL.get(sid, []):
            insert_row(conn, "knowledge_points", {
                "subject_id": sid,
                "code": f"SYN-{sid}-{kp_id:02d}",
                "name": kp,
                "level": 1,
                "weight": round(random.uniform(0.5, 1.0), 2),
                "description": f"{kp}（合成）",
                "cognitive_requirement": random.choice(COGNITIVE),
            })
            kp_id += 1


def seed_question_types(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM question_types WHERE name_cn LIKE '%(合成)'")
    for sid, _, _, _ in SUBJECTS:
        for main, sub, cn in Q_TYPES:
            insert_row(conn, "question_types", {
                "subject_id": sid,
                "main_type": main,
                "sub_type": sub,
                "name_cn": cn,
                "level": 1,
            })


def build_questions(conn: sqlite3.Connection, paper_id: int, subject_id: str,
                     n: int, qtype_rows: list, diff: str, year: int) -> tuple[float, float]:
    """生成 n 道题，返回 (总分, 平均难度)。"""
    kps = [r[0] for r in conn.execute(
        "SELECT code FROM knowledge_points WHERE subject_id=? AND code LIKE 'SYN-%'",
        (subject_id,)).fetchall()] or ["SYN-通用"]
    total_score = 0.0
    diff_sum = 0.0
    for i in range(1, n + 1):
        qt = random.choice(qtype_rows)
        qtype_id = qt[0]
        main_type = qt[1]
        base = 5 if main_type in ("choice", "multi", "fill") else 12
        score = float(base + random.choice([0, 0, 3, 5]))
        total_score += score
        irt_b = round(random.uniform(-2.0, 2.0), 2)
        diff_sum += (irt_b + 2) / 4.0  # 归一化
        chosen_kps = random.sample(kps, min(len(kps), random.randint(1, 3)))
        content = f"【{subject_id}·{qt[2].replace('(合成)','')}】第{i}题（{year}）{random.choice(['下列关于','试分析','已知','根据图示','计算'])}……"
        opts = None
        if main_type in ("choice", "multi"):
            opts = json.dumps([
                {"label": l, "text": f"选项{l}内容示例"} for l in ["A", "B", "C", "D"]
            ], ensure_ascii=False)
        q_diff = random.choices(DIFFS, weights=[3, 5, 2])[0]
        insert_row(conn, "questions", {
            "paper_id": paper_id,
            "q_number": i,
            "q_type": main_type,
            "content": content,
            "options": opts,
            "answer": random.choice(["A", "B", "C", "D", "AB", "略"]),
            "explanation": f"解析：本题考查{random.choice(chosen_kps)}相关核心概念。",
            "score": score,
            "knowledge_points": json.dumps(chosen_kps, ensure_ascii=False),
            "difficulty_tag": q_diff,
            "irt_a": round(random.uniform(0.5, 2.0), 2),
            "irt_b": irt_b,
            "irt_c": round(random.uniform(0.1, 0.3), 2),
            "discrimination": round(random.uniform(0.3, 0.9), 2),
            "cognitive_level": random.choice(COGNITIVE),
            "core_competency": random.choice(CORE),
            "quality_rating": random.choice(["A", "B", "C"]),
            "is_quality": 1 if random.random() < 0.3 else 0,
            "content_hash": make_hash("q", str(paper_id), str(i), content),
            "question_type_id": qtype_id,
        })
    avg_diff = round(diff_sum / n, 2) if n else 0.0
    return total_score, avg_diff


def seed_papers(conn: sqlite3.Connection, mock_count: int, real_years: int) -> int:
    # 先清旧合成卷与题目（幂等）
    conn.execute(
        "DELETE FROM questions WHERE paper_id IN (SELECT id FROM papers WHERE collector=?)",
        (COLLECTOR,),
    )
    conn.execute("DELETE FROM papers WHERE collector=?", (COLLECTOR,))

    total = 0
    ts = now_iso()
    # ---- 合成模拟卷 ----
    for n in range(1, mock_count + 1):
        sid, name, total_score_subj, _ = random.choice(SUBJECTS)
        qtype_rows = conn.execute(
            "SELECT id, main_type, name_cn FROM question_types WHERE subject_id=? AND name_cn LIKE '%(合成)'",
            (sid,)).fetchall()
        year = random.randint(2018, 2025)
        province = random.choice(PROVINCES)
        qcount = random.randint(15, 22)
        diff = random.choices(DIFFS, weights=[3, 5, 2])[0]
        title = f"【合成模拟卷】{name}{year}年{province}地区第{n}套"
        chash = make_hash("paper", title, str(n))
        pid = insert_row(conn, "papers", {
            "title": title,
            "subject_id": sid,
            "paper_type": "mock",
            "year": year,
            "province": province,
            "exam_tag": "synthetic-mock",
            "source_id": SOURCE_ID,
            "source_priority": "normal",
            "collected_at": ts,
            "collector": COLLECTOR,
            "verified": 0,
            "total_score": float(total_score_subj),
            "difficulty": diff,
            "difficulty_tag": diff,
            "question_count": qcount,
            "quality_score": round(random.uniform(0.6, 0.95), 2),
            "curriculum_score": round(random.uniform(0.6, 0.95), 2),
            "analysis_status": "pending",
            "content_hash": chash,
            "dedup_status": "unique",
            "created_at": ts,
            "updated_at": ts,
        })
        qs, avg_diff = build_questions(conn, pid, sid, qcount, qtype_rows, diff, year)
        conn.execute("UPDATE papers SET total_score=?, difficulty=? WHERE id=?",
                     (qs, avg_diff, pid))
        total += 1

    # ---- 近 N 年真题风格卷（每学科每年 2 套：新高考I/II卷） ----
    cur_year = 2025
    for y in range(cur_year - real_years + 1, cur_year + 1):
        for sid, name, total_score_subj, _ in SUBJECTS:
            qtype_rows = conn.execute(
                "SELECT id, main_type, name_cn FROM question_types WHERE subject_id=? AND name_cn LIKE '%(合成)'",
                (sid,)).fetchall()
            for vol in ("新高考I卷", "新高考II卷"):
                qcount = random.randint(20, 25)
                diff = "medium"
                title = f"【真题风格】{name}{y}年{vol}"
                chash = make_hash("paper-real", title)
                pid = insert_row(conn, "papers", {
                    "title": title,
                    "subject_id": sid,
                    "paper_type": "real",
                    "year": y,
                    "province": "全国",
                    "exam_tag": "synthetic-real",
                    "source_id": SOURCE_ID,
                    "source_priority": "high",
                    "collected_at": ts,
                    "collector": COLLECTOR,
                    "verified": 1,
                    "total_score": float(total_score_subj),
                    "difficulty": diff,
                    "difficulty_tag": diff,
                    "question_count": qcount,
                    "quality_score": round(random.uniform(0.8, 0.98), 2),
                    "curriculum_score": round(random.uniform(0.8, 0.98), 2),
                    "analysis_status": "done",
                    "content_hash": chash,
                    "dedup_status": "unique",
                    "created_at": ts,
                    "updated_at": ts,
                })
                qs, avg_diff = build_questions(conn, pid, sid, qcount, qtype_rows, diff, y)
                conn.execute("UPDATE papers SET total_score=?, difficulty=? WHERE id=?",
                             (qs, avg_diff, pid))
                total += 1
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="gaokao-analyzer 合成种子数据采集")
    ap.add_argument("--mock", type=int, default=1000, help="合成模拟卷数量（默认 1000）")
    ap.add_argument("--real-years", type=int, default=5, help="真题风格卷回溯年数（默认 5）")
    args = ap.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"找不到数据库：{DB_PATH}")

    random.seed(20260710)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        seed_subjects(conn)
        seed_source(conn)
        seed_knowledge_points(conn)
        seed_question_types(conn)
        n_papers = seed_papers(conn, args.mock, args.real_years)
        conn.commit()
    finally:
        conn.close()

    print(f"[✓] 合成种子数据采集完成：共 {n_papers} 套卷子入库（模拟卷 {args.mock} + "
          f"真题风格卷 {args.real_years * len(SUBJECTS) * 2}）")
    print(f"    数据库：{DB_PATH}")


if __name__ == "__main__":
    main()
