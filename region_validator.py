"""
v5.0 地区校验与纠错引擎
解决：试卷地区与实际不对应的问题
功能：省→市层级映射、地区自动纠正、城市→省份反查
"""
# mypy: disable-error-code="no-untyped-def,no-any-return,call-overload,operator,type-arg,assignment,var-annotated,misc,index,attr-defined,return-value,func-returns-value,return,has-type,unused-ignore,arg-type"
import re
import logging
from config import REGION_HIERARCHY, CITY_TO_PROVINCE

logger = logging.getLogger("gaokao")


class RegionValidator:
    """地区校验引擎"""

    # 常见地区误写纠正
    CORRECTIONS = {
        "深圳市": "深圳", "广州市": "广州", "南京市": "南京",
        "杭州市": "杭州", "成都市": "成都", "武汉市": "武汉",
        "长沙市": "长沙", "西安市": "西安", "济南市": "济南",
        "青岛市": "青岛", "大连市": "大连", "厦门市": "厦门",
        "福州市": "福州", "郑州市": "郑州", "合肥市": "合肥",
        "沈阳市": "沈阳", "哈尔滨市": "哈尔滨", "长春市": "长春",
        "石家庄市": "石家庄", "太原市": "太原", "兰州市": "兰州",
        "昆明市": "昆明", "贵阳市": "贵阳", "南宁市": "南宁",
        "海口市": "海口", "银川市": "银川", "西宁市": "西宁",
        "乌鲁木齐市": "乌鲁木齐", "呼和浩特市": "呼和浩特",
        "拉萨市": "拉萨", "苏州市": "苏州", "无锡市": "无锡",
        "宁波市": "宁波", "温州市": "温州", "佛山市": "佛山",
        "东莞市": "东莞", "烟台市": "烟台", "保定市": "保定",
    }

    # 常见试卷标题中的地区关键词模式
    PROVINCE_PATTERNS = [
        # "XX省" → 去掉"省"字
        (r'(\w{2,3})省', lambda m: m.group(1)),
        # "XX市" → 查找是否是直辖市
        (r'(\w{2,3})市', lambda m: m.group(1) if m.group(1) in CITY_TO_PROVINCE or m.group(1) in REGION_HIERARCHY else None),
    ]

    @classmethod
    def validate_region(cls, province: str, city: str = "", title: str = "") -> dict:
        """
        校验地区信息的一致性

        Returns:
            {
                "valid": bool,
                "province": str,  # 纠正后的省份
                "city": str,  # 纠正后的城市
                "errors": [str],  # 错误列表
                "warnings": [str],  # 警告列表
                "auto_corrected": bool,  # 是否自动纠正
            }
        """
        errors = []
        warnings = []
        corrected_province = province or ""
        corrected_city = city or ""
        auto_corrected = False

        # 从标题中提取地区信息
        title_province, title_city = cls._extract_region_from_title(title)

        # 纠正常见误写
        if corrected_city in cls.CORRECTIONS:
            corrected_city = cls.CORRECTIONS[corrected_city]
            auto_corrected = True

        if corrected_province in cls.CORRECTIONS:
            corrected_province = cls.CORRECTIONS[corrected_province]
            auto_corrected = True

        # 检查城市是否属于省份
        if corrected_city and corrected_province:
            expected_province = CITY_TO_PROVINCE.get(corrected_city)
            if expected_province and expected_province != corrected_province:
                errors.append(
                    f"城市'{corrected_city}'属于{expected_province}，"
                    f"但试卷标记为{corrected_province}"
                )
                # 自动纠正省份
                corrected_province = expected_province
                auto_corrected = True

        # 如果没有省份但有城市，自动推断省份
        if corrected_city and not corrected_province:
            expected_province = CITY_TO_PROVINCE.get(corrected_city)
            if expected_province:
                corrected_province = expected_province
                auto_corrected = True

        # 如果省份为空，尝试从标题提取
        if not corrected_province and title_province:
            corrected_province = title_province
            auto_corrected = True

        # 如果城市为空，尝试从标题提取
        if not corrected_city and title_city:
            corrected_city = title_city
            auto_corrected = True

        # 验证省份是否在已知列表中
        if corrected_province and corrected_province not in REGION_HIERARCHY and corrected_province != "全国":
            warnings.append(f"省份'{corrected_province}'不在标准省份列表中")
            # 尝试模糊匹配
            fuzzy = cls._fuzzy_match_province(corrected_province)
            if fuzzy:
                corrected_province = fuzzy
                auto_corrected = True

        # 验证城市是否属于省份
        if corrected_city and corrected_province and corrected_province != "全国":
            province_cities = REGION_HIERARCHY.get(corrected_province, {}).get("cities", [])
            if province_cities and corrected_city not in province_cities:
                expected_province = CITY_TO_PROVINCE.get(corrected_city)
                if expected_province:
                    warnings.append(
                        f"城市'{corrected_city}'属于{expected_province}而非{corrected_province}"
                    )

        # 直辖市特殊处理：直辖市下的试卷省份应标记为直辖市本身
        if corrected_city in REGION_HIERARCHY and corrected_province != corrected_city:
            if REGION_HIERARCHY.get(corrected_city, {}).get("type") == "直辖市":
                warnings.append(f"'{corrected_city}'是直辖市，省份应标记为'{corrected_city}'")

        valid = len(errors) == 0

        return {
            "valid": valid,
            "province": corrected_province,
            "city": corrected_city,
            "errors": errors,
            "warnings": warnings,
            "auto_corrected": auto_corrected,
        }

    @classmethod
    def _extract_region_from_title(cls, title: str) -> tuple:
        """从试卷标题中提取地区信息"""
        if not title:
            return "", ""

        province = ""
        city = ""

        # 尝试匹配城市（优先匹配更具体的城市名）
        for city_name in sorted(CITY_TO_PROVINCE.keys(), key=len, reverse=True):
            if city_name in title:
                city = city_name
                province = CITY_TO_PROVINCE[city_name]
                break

        # 如果没有匹配到城市，尝试匹配省份
        if not province:
            for prov_name in sorted(REGION_HIERARCHY.keys(), key=len, reverse=True):
                if prov_name in title:
                    province = prov_name
                    break

        # 处理 "XX省" 格式
        m = re.search(r'(\w{2,3})省', title)
        if m and not province:
            prov_candidate = m.group(1)
            if prov_candidate in REGION_HIERARCHY:
                province = prov_candidate

        return province, city

    @classmethod
    def _fuzzy_match_province(cls, name: str) -> str:
        """模糊匹配省份名称"""
        # 去掉"省""市""自治区"等后缀
        clean = re.sub(r'(省|市|自治区|壮族|维吾尔|回族)$', '', name)
        for province in REGION_HIERARCHY:
            if clean in province or province in clean:
                return province
        return ""

    @classmethod
    def normalize_province(cls, raw: str) -> str:
        """标准化省份名称"""
        if not raw:
            return ""
        # 去掉"省""市"等后缀
        clean = re.sub(r'(省|市|壮族自治区|维吾尔自治区|回族自治区|自治区)$', '', raw)
        if clean in REGION_HIERARCHY:
            return clean
        # 尝试模糊匹配
        fuzzy = cls._fuzzy_match_province(clean)
        return fuzzy or raw

    @classmethod
    def get_sub_regions(cls, province: str) -> list:
        """获取省份下的所有城市"""
        info = REGION_HIERARCHY.get(province)
        if info:
            return info["cities"]
        return []

    @classmethod
    def batch_validate(cls, papers: list) -> list:
        """批量校验试卷地区信息"""
        results = []
        for paper in papers:
            result = cls.validate_region(
                province=paper.get("province", ""),
                city=paper.get("school", ""),  # school 字段常存城市名
                title=paper.get("title", ""),
            )
            results.append({
                "paper_id": paper.get("id"),
                "original_province": paper.get("province", ""),
                "corrected_province": result["province"],
                "corrected_city": result["city"],
                "valid": result["valid"],
                "errors": result["errors"],
                "warnings": result["warnings"],
                "auto_corrected": result["auto_corrected"],
            })
        return results
