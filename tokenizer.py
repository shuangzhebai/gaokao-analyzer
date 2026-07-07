"""
中文分词器（公共模块） v5.1
被 search.py 与 dedup.py 复用，统一 exam_patterns 词表（已去重 search.py 中原重复的 "期末"）。
"""
import re
from typing import List

# 统一考试关键词词表（已去重：原 search.py 中 "期末" 出现在两处，已合并为单条）
EXAM_PATTERNS: List[str] = [
    "深圳", "广州", "南京", "杭州", "长沙", "武汉", "成都",
    "北京", "上海", "天津", "重庆", "福州", "厦门", "济南", "青岛",
    "郑州", "合肥", "西安", "南昌",
    "一模", "二模", "三模", "四模",
    "省质检", "省统考", "联考", "月考", "期末", "期中",
    "适应性", "模拟", "真题",
    "数学", "语文", "英语", "物理", "化学", "生物", "历史", "地理", "政治",
    "附中", "中学", "一中", "二中", "三中", "外国语", "实验",
    "百校", "名校", "九校", "八校", "十校",
    "T8", "华大", "天一", "衡水", "黄冈", "镇海",
    "学军", "长郡", "雅礼", "南外", "人大",
    "高考", "中考", "入学",
]

# 科目名称（供其他模块复用）
SUBJECT_NAMES: List[str] = [
    "数学", "语文", "英语", "物理", "化学", "生物", "历史", "地理", "政治",
]


def tokenize(q: str) -> List[str]:
    """中文智能分词：按空格/标点切分，并自动切分连续中文字符为 2-4 字词组。

    例: "深圳二模数学" -> ["深圳", "二模", "数学"]
    """
    raw_tokens = re.split(r'[\s,，。、；;：:！!？?（）()（）【】\[\]{}]+', q.strip())
    tokens: List[str] = []
    for t in raw_tokens:
        if not t:
            continue
        # 英文/数字直接保留
        if re.match(r'^[\w\d]+$', t) and not re.search(r'[\u4e00-\u9fff]', t):
            tokens.append(t)
            continue
        # 中文: 按常见考试关键词模式切分
        remaining = t
        for pattern in EXAM_PATTERNS:
            if pattern in remaining:
                tokens.append(pattern)
                remaining = remaining.replace(pattern, '', 1)
        # 剩余部分: 切分为 2-4 字词组
        if remaining:
            if len(remaining) <= 4:
                tokens.append(remaining)
            else:
                for i in range(0, len(remaining), 2):
                    chunk = remaining[i:i + 2]
                    if chunk:
                        tokens.append(chunk)
    return [t for t in tokens if len(t) >= 1]
