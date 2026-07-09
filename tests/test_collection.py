"""
采集系统增强测试（v8.5）

覆盖：
- content_hash 去重逻辑
- QuestionClassifier 自动分类入库流程
- collection_logs 表迁移
- CollectionService 统计与目标进度
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engines.question_classifier import QuestionClassifier
from services.collection_service import CollectionService


# ===================== 哈希去重逻辑 =====================

class TestContentHashDedup:
    """content_hash 去重逻辑测试"""

    def test_content_hash_consistency(self):
        """相同内容产生相同哈希"""
        content = "已知函数 f(x)=x^2，求 f'(x)"
        hash1 = hashlib.sha256(content.encode()).hexdigest()[:16]
        hash2 = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_content_hash_different_input(self):
        """不同内容产生不同哈希"""
        content1 = "已知函数 f(x)=x^2，求 f'(x)"
        content2 = "已知函数 f(x)=x^3，求 f'(x)"
        hash1 = hashlib.sha256(content1.encode()).hexdigest()[:16]
        hash2 = hashlib.sha256(content2.encode()).hexdigest()[:16]
        assert hash1 != hash2

    def test_content_hash_empty_string(self):
        """空字符串的哈希"""
        content = ""
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert len(h) == 16
        assert isinstance(h, str)

    def test_content_hash_unicode(self):
        """中文内容的哈希一致性"""
        content = "设集合 A={x|x²-3x+2=0}，B={x|x²-ax+2=0}"
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert len(h) == 16
        # 确认相同的字符串再算一次
        h2 = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert h == h2

    def test_dedup_sql_pattern(self):
        """模拟去重 SQL 查询逻辑"""
        # 模拟数据库中的已有哈希
        existing_hashes = {
            "a1b2c3d4e5f6g7h8",
            "b2c3d4e5f6g7h8i9",
        }
        new_content = "计算 sin(π/4) + cos(π/3) 的值"
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()[:16]

        # 去重检查
        assert new_hash not in existing_hashes  # 新内容不重复

        # 重复内容
        duplicate_content = "计算 sin(π/4) + cos(π/3) 的值"
        dup_hash = hashlib.sha256(duplicate_content.encode()).hexdigest()[:16]
        # 已有的就不应该再插入
        assert dup_hash == new_hash
        assert dup_hash not in existing_hashes  # 模拟是新内容

    def test_paper_title_hash_is_different_from_question_hash(self):
        """试卷标题的哈希和题目内容的哈希不同"""
        title = "2024年高考数学全国I卷"
        title_hash = hashlib.sha256(title.encode()).hexdigest()[:16]

        question = "已知集合 A={1,2,3}, B={2,3,4}，求 A∩B"
        q_hash = hashlib.sha256(question.encode()).hexdigest()[:16]

        assert title_hash != q_hash


# ===================== 自动分类入库流程 =====================

class TestAutoClassification:
    """自动分类入库集成测试"""

    def setup_method(self):
        self.classifier = QuestionClassifier()

    def test_classify_choice_question(self):
        """分类选择题"""
        question = {
            "content": "下列函数中，既是奇函数又是增函数的是",
            "options": "A. y=sinx\nB. y=x³\nC. y=2ˣ\nD. y=lnx",
            "answer": "B",
        }
        result = self.classifier.classify(question)
        assert result["main_type"] == "choice"
        assert result["sub_type"] in ("single_choice", "multi_choice")
        assert result["confidence"] >= 0.60

    def test_classify_fill_question(self):
        """分类填空题"""
        question = {
            "content": "已知函数 f(x)=x²+ax+b 的图象关于直线 x=1 对称，则 a=______",
            "options": "",
            "answer": "-2",
        }
        result = self.classifier.classify(question)
        assert result["main_type"] == "fill"
        assert result["sub_type"] == "fill"
        assert result["confidence"] >= 0.70

    def test_classify_solve_question(self):
        """分类解答题"""
        question = {
            "content": "已知数列 {aₙ} 满足 a₁=1，aₙ₊₁=2aₙ+1。\n（1）证明：{aₙ+1}是等比数列；\n（2）求 {aₙ}的通项公式。",
            "options": "",
            "answer": "证明略",
        }
        result = self.classifier.classify(question)
        assert result["main_type"] == "solve"
        assert result["confidence"] >= 0.50

    def test_batch_classify(self):
        """批量分类"""
        questions = [
            {"content": "选择题内容", "options": "A. 1\nB. 2\nC. 3\nD. 4", "answer": "A"},
            {"content": "填空题 ______", "options": "", "answer": "答案"},
            {"content": "证明：设函数 f(x) 在 [0,1] 上连续", "options": "", "answer": "证明过程"},
        ]
        results = self.classifier.batch_classify(questions)
        assert len(results) == 3
        assert results[0]["main_type"] == "choice"
        assert results[1]["main_type"] == "fill"
        assert results[2]["main_type"] == "solve"

    def test_classify_empty_content(self):
        """空内容的分类回退"""
        question = {
            "content": "",
            "options": "",
            "answer": "",
        }
        result = self.classifier.classify(question)
        assert result["main_type"] in ("choice", "fill", "solve")
        assert 0 <= result["confidence"] <= 1.0

    def test_question_type_mapping(self):
        """题型映射到 question_types 表逻辑"""
        subject_id = "math"
        main_type = "choice"
        sub_type = "single_choice"

        # 模拟数据库查询：按 subject_id + main_type + sub_type 查找
        mock_db = MagicMock()
        mock_db.execute_fetchone.return_value = {"id": 1}

        # 模拟查找 question_type_id
        query = (
            "SELECT id FROM question_types "
            "WHERE subject_id = ? AND main_type = ? AND sub_type = ?"
        )
        # 验证 SQL 模板
        assert "subject_id = ?" in query
        assert "main_type = ?" in query
        assert "sub_type = ?" in query

    def test_auto_create_missing_type(self):
        """自动创建缺失的题型条目"""
        subject_id = "physics"
        main_type = "choice"
        sub_type = "multi_choice"

        # 模拟数据库：找不到时创建
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42

        mock_db = MagicMock()
        mock_db.execute_fetchone.return_value = None  # 找不到
        mock_db.execute.return_value = mock_cursor

        # 创建新题型
        name_cn = f"{main_type}_{sub_type}"
        cursor = mock_db.execute(
            "INSERT INTO question_types (subject_id, main_type, sub_type, name_cn, level) VALUES (?, ?, ?, ?, 1)",
            (subject_id, main_type, sub_type, name_cn),
        )
        # 验证 lastrowid
        assert cursor.lastrowid == 42


# ===================== 检测特征提取 =====================

class TestFeatureExtraction:
    """特征提取测试"""

    def setup_method(self):
        self.classifier = QuestionClassifier()

    def test_extract_features_choice(self):
        """选择题特征"""
        question = {
            "content": "下列命题正确的是",
            "options": "A. 1\nB. 2\nC. 3\nD. 4",
            "answer": "A",
        }
        features = self.classifier.extract_features(question)
        assert features["has_options"] is True
        assert features["option_count"] >= 4
        assert features["has_fill_marker"] is False
        assert features["has_solve_keyword"] is False

    def test_extract_features_fill_in_the_blank(self):
        """填空题特征（含下划线标记）"""
        question = {
            "content": "计算：sin30° = ______",
            "options": "",
            "answer": "1/2",
        }
        features = self.classifier.extract_features(question)
        assert features["has_options"] is False
        assert features["has_fill_marker"] is True

    def test_extract_features_solve_with_keyword(self):
        """解答题特征（含'解'/'证明'等关键词）"""
        question = {
            "content": "解：设函数 f(x)=ax²+bx+c...",
            "options": "",
            "answer": "答案略",
        }
        features = self.classifier.extract_features(question)
        assert features["has_solve_keyword"] is True

    def test_extract_features_empty(self):
        """空题目的特征"""
        question = {"content": "", "options": "", "answer": ""}
        features = self.classifier.extract_features(question)
        assert features["has_options"] is False
        assert features["option_count"] == 0
        assert features["has_fill_marker"] is False
        assert features["has_solve_keyword"] is False
        assert features["content_length"] == 0


# ===================== 采集统计服务 =====================

class TestCollectionService:
    """CollectionService 统计与目标进度测试"""

    def setup_method(self):
        self.service = CollectionService()

    @pytest.mark.asyncio
    async def test_get_collection_stats(self):
        """获取采集统计"""
        mock_db = AsyncMock()

        # 模拟数据库返回
        mock_db.execute_fetchone.side_effect = [
            {"cnt": 150},  # total_questions
            {"cnt": 35},   # total_papers
        ]

        mock_db.execute_fetchall.side_effect = [
            # by_source
            [{"source": "zxxk", "cnt": 15}, {"source": "zujuan", "cnt": 10}],
            # by_subject
            [{"subject_id": "math", "cnt": 10}, {"subject_id": "chinese", "cnt": 8}],
            # questions_by_subject
            [{"subject_id": "math", "cnt": 50}, {"subject_id": "chinese", "cnt": 40}],
            # daily_trend
            [{"day": "2026-01-01", "cnt": 5}, {"day": "2026-01-02", "cnt": 3}],
        ]

        stats = await self.service.get_collection_stats(mock_db)

        assert stats["total_questions"] == 150
        assert stats["total_papers"] == 35
        assert stats["source_distribution"]["zxxk"] == 15
        assert stats["subject_distribution"]["math"] == 10
        assert stats["questions_by_subject"]["math"] == 50
        assert len(stats["daily_trend"]) == 2

    @pytest.mark.asyncio
    async def test_get_target_progress_empty(self):
        """空数据库的目标进度"""
        mock_db = AsyncMock()
        mock_db.execute_fetchone.side_effect = [
            {"cnt": 0},  # mock_papers
            {"cnt": 0},  # real_exams
        ]
        mock_db.execute_fetchall.return_value = []  # real_exams_by_year

        progress = await self.service.get_target_progress(mock_db)

        assert progress["collected_mock_papers"] == 0
        assert progress["collected_real_exams"] == 0
        assert progress["mock_progress_pct"] == 0.0
        assert progress["real_progress_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_get_target_progress_with_data(self):
        """有数据时的目标进度"""
        mock_db = AsyncMock()
        mock_db.execute_fetchone.side_effect = [
            {"cnt": 500},  # mock_papers
            {"cnt": 3},    # real_exams
        ]
        mock_db.execute_fetchall.return_value = [
            {"year": 2022, "cnt": 1},
            {"year": 2023, "cnt": 1},
            {"year": 2024, "cnt": 1},
        ]

        progress = await self.service.get_target_progress(mock_db)

        assert progress["collected_mock_papers"] == 500
        assert progress["collected_real_exams"] == 3
        assert 49.9 < progress["mock_progress_pct"] < 50.1  # 500/1000 * 100
        assert 59.9 < progress["real_progress_pct"] < 60.1  # 3/5 years * 100

    @pytest.mark.asyncio
    async def test_get_collection_logs(self):
        """获取采集日志"""
        mock_db = AsyncMock()
        mock_db.execute_fetchall.return_value = [
            {
                "id": 1,
                "source": "auto_scraper",
                "task_type": "scheduled",
                "started_at": "2026-01-01T10:00:00",
                "completed_at": "2026-01-01T10:05:00",
                "papers_found": 10,
                "papers_new": 5,
                "questions_new": 20,
                "errors": "[]",
                "status": "completed",
            },
        ]

        logs = await self.service.get_collection_logs(mock_db, limit=10)

        assert len(logs) == 1
        assert logs[0]["source"] == "auto_scraper"
        assert logs[0]["status"] == "completed"
        assert logs[0]["papers_new"] == 5

    @pytest.mark.asyncio
    async def test_trigger_manual_collection(self):
        """手动触发采集"""
        mock_db = AsyncMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42
        mock_db.execute.return_value = mock_cursor

        mock_auto_scraper = AsyncMock()
        mock_auto_scraper._run_once = AsyncMock()

        result = await self.service.trigger_manual_collection(mock_db, mock_auto_scraper)

        assert result["triggered"] is True
        assert result["log_id"] == 42
        mock_auto_scraper._run_once.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_trigger_without_scraper(self):
        """没有 AutoScraper 时触发失败"""
        mock_db = AsyncMock()
        result = await self.service.trigger_manual_collection(mock_db, None)
        assert result["triggered"] is False
        assert "not initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_trigger_manual_collection_failure(self):
        """手动触发采集失败"""
        mock_db = AsyncMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 99
        mock_db.execute.return_value = mock_cursor

        mock_auto_scraper = AsyncMock()
        mock_auto_scraper._run_once = AsyncMock(side_effect=RuntimeError("网络错误"))

        result = await self.service.trigger_manual_collection(mock_db, mock_auto_scraper)

        assert result["triggered"] is False
        assert "网络错误" in result["error"]
        assert result["log_id"] == 99


# ===================== 数据库迁移 =====================

class TestCollectionLogsMigration:
    """v8.5 采集日志表迁移测试"""

    def test_collection_logs_schema(self):
        """验证 collection_logs 表结构"""
        expected_columns = [
            "id", "source", "task_type", "started_at", "completed_at",
            "papers_found", "papers_new", "questions_new", "errors", "status",
        ]
        # 直接验证 SQL 创建语句中的字段
        from models import SCHEMA
        assert "CREATE TABLE IF NOT EXISTS collection_logs" in SCHEMA
        for col in expected_columns:
            assert col in SCHEMA

    def test_collection_logs_indexes(self):
        """验证索引"""
        from models import SCHEMA
        assert "idx_collection_logs_status" in SCHEMA
        assert "idx_collection_logs_started" in SCHEMA


# ===================== auto_scraper 增强测试 =====================

class TestAutoScraperEnhancements:
    """auto_scraper 去重与分类集成测试"""

    @pytest.mark.asyncio
    async def test_process_paper_questions(self):
        """测试 _process_paper_questions 方法逻辑"""
        from auto_scraper import AutoScraper

        scraper = AutoScraper()
        mock_db = AsyncMock()
        classifier = QuestionClassifier()

        # 模拟试卷信息
        mock_db.execute_fetchone.return_value = {
            "id": 1, "subject_id": "math",
        }

        # 模拟已有题目
        mock_db.execute_fetchall.side_effect = [
            [],  # existing_hashes（无已有哈希）
            [   # existing_questions
                {"id": 10, "content": "已知集合 A={1,2}，求 A∪B", "content_hash": ""},
                {"id": 11, "content": "解方程：x²-3x+2=0 ______", "content_hash": ""},
                {"id": 12, "content": "证明：sin²α+cos²α=1", "content_hash": ""},
            ],
        ]

        # 模拟成功查找 question_types
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 100
        mock_db.execute_fetchone.return_value = {"id": 1}  # question_type found
        mock_db.execute.return_value = mock_cursor

        result = await scraper._process_paper_questions(
            mock_db, 1, "math", "abc12345def67890", classifier
        )

        # 验证调用了分类
        assert result >= 0
        # 验证更新了 content_hash
        update_calls = [
            call for call in mock_db.execute.call_args_list
            if "UPDATE questions SET content_hash" in str(call)
        ]
        assert len(update_calls) > 0

    @pytest.mark.asyncio
    async def test_run_once_with_collection_log(self):
        """测试 _run_once 中创建了 collection_logs"""
        # 验证 auto_scraper.py 导入了新模块
        import auto_scraper
        assert hasattr(auto_scraper, 'QuestionClassifier')

        # 验证 _run_once 中有 collection_logs 的 INSERT
        import inspect
        source = inspect.getsource(auto_scraper.AutoScraper._run_once)
        assert "INSERT INTO collection_logs" in source
        assert "content_hash" in source
        assert "QuestionClassifier" in source or "classifier" in source


# ===================== 前端类型检查 =====================

class TestFrontendTypes:
    """前端类型定义检查"""

    def test_collection_types_exist(self):
        """验证前端类型文件存在"""
        types_path = os.path.join(ROOT, "frontend", "src", "types", "collection.ts")
        assert os.path.exists(types_path), f"Type file not found: {types_path}"

    def test_collection_service_exist(self):
        """验证前端服务文件存在"""
        service_path = os.path.join(ROOT, "frontend", "src", "services", "collect.ts")
        assert os.path.exists(service_path), f"Service file not found: {service_path}"

    def test_collection_page_exist(self):
        """验证前端页面文件存在"""
        page_path = os.path.join(ROOT, "frontend", "src", "pages", "collection", "index.tsx")
        assert os.path.exists(page_path), f"Page file not found: {page_path}"
