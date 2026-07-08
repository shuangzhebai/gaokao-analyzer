"""
repositories 子包：DAO 层，封装所有 SQL 操作（aiosqlite，不引入 ORM）。
"""
from .paper_repo import PaperRepository
from .question_repo import QuestionRepository
from .analysis_repo import AnalysisRepository

__all__ = ["PaperRepository", "QuestionRepository", "AnalysisRepository"]
