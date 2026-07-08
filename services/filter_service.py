"""
筛选业务层：封装筛选元数据获取。
"""
from repositories.paper_repo import PaperRepository


class FilterService:
    """筛选元数据业务服务"""

    def __init__(self, paper_repo: PaperRepository):
        self.paper_repo = paper_repo

    async def get_filter_options(self, db) -> dict:
        """获取筛选元数据"""
        return await self.paper_repo.get_filter_options(db)
