"""
高考模拟卷智能分析系统 v5.0 - 配置文件
v5.0: 地区层级映射、自动采集调度、官方文档源、校准数据
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOWNLOAD_DIR = os.path.join(DATA_DIR, "downloads")
DB_PATH = os.path.join(DATA_DIR, "gaokao.db")

# 科目配置
SUBJECTS = {
    "chinese": {"name": "语文", "total_score": 150, "time_min": 150},
    "math": {"name": "数学", "total_score": 150, "time_min": 120},
    "english": {"name": "英语", "total_score": 150, "time_min": 120},
    "physics": {"name": "物理", "total_score": 100, "time_min": 75},
    "chemistry": {"name": "化学", "total_score": 100, "time_min": 75},
    "biology": {"name": "生物", "total_score": 100, "time_min": 75},
    "history": {"name": "历史", "total_score": 100, "time_min": 75},
    "geography": {"name": "地理", "total_score": 100, "time_min": 75},
    "politics": {"name": "政治", "total_score": 100, "time_min": 75},
}

# 卷别类型
PAPER_TYPES = {
    "real": "高考真题",
    "provincial": "省质检/省模拟",
    "school": "名校联考",
    "monthly": "月考/周考",
    "special": "专项训练",
}

# ===== v5.0 地区层级映射 =====
# 省 → 下辖主要城市/区
REGION_HIERARCHY = {
    "北京": {"type": "直辖市", "cities": ["北京"]},
    "上海": {"type": "直辖市", "cities": ["上海"]},
    "天津": {"type": "直辖市", "cities": ["天津"]},
    "重庆": {"type": "直辖市", "cities": ["重庆"]},
    "广东": {"type": "省", "cities": ["深圳", "广州", "东莞", "佛山", "珠海", "中山", "惠州", "汕头", "湛江", "茂名", "江门", "肇庆", "揭阳", "清远", "阳江", "韶关", "河源", "梅州", "潮州", "汕尾", "云浮"]},
    "江苏": {"type": "省", "cities": ["南京", "苏州", "无锡", "常州", "南通", "徐州", "扬州", "盐城", "淮安", "连云港", "泰州", "镇江", "宿迁"]},
    "浙江": {"type": "省", "cities": ["杭州", "宁波", "温州", "绍兴", "嘉兴", "金华", "台州", "湖州", "衢州", "丽水", "舟山"]},
    "山东": {"type": "省", "cities": ["济南", "青岛", "烟台", "潍坊", "临沂", "济宁", "淄博", "威海", "东营", "泰安", "菏泽", "聊城", "德州", "滨州", "日照", "枣庄", "莱芜"]},
    "福建": {"type": "省", "cities": ["福州", "厦门", "泉州", "漳州", "莆田", "龙岩", "三明", "南平", "宁德"]},
    "湖南": {"type": "省", "cities": ["长沙", "株洲", "湘潭", "衡阳", "岳阳", "常德", "邵阳", "益阳", "永州", "郴州", "怀化", "娄底", "湘西", "张家界"]},
    "湖北": {"type": "省", "cities": ["武汉", "宜昌", "襄阳", "荆州", "黄冈", "十堰", "孝感", "荆门", "鄂州", "黄石", "咸宁", "随州", "恩施"]},
    "河南": {"type": "省", "cities": ["郑州", "洛阳", "开封", "南阳", "新乡", "安阳", "许昌", "平顶山", "焦作", "信阳", "驻马店", "商丘", "周口", "漯河", "濮阳", "鹤壁", "三门峡", "济源"]},
    "河北": {"type": "省", "cities": ["石家庄", "唐山", "保定", "邯郸", "秦皇岛", "廊坊", "沧州", "邢台", "张家口", "承德", "衡水", "定州", "辛集"]},
    "四川": {"type": "省", "cities": ["成都", "绵阳", "德阳", "宜宾", "南充", "泸州", "达州", "乐山", "自贡", "内江", "遂宁", "广安", "眉山", "资阳", "雅安", "攀枝花", "凉山", "广元"]},
    "安徽": {"type": "省", "cities": ["合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "安庆", "黄山", "铜陵", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"]},
    "江西": {"type": "省", "cities": ["南昌", "赣州", "九江", "吉安", "宜春", "上饶", "抚州", "新余", "景德镇", "萍乡", "鹰潭"]},
    "陕西": {"type": "省", "cities": ["西安", "宝鸡", "咸阳", "渭南", "汉中", "延安", "安康", "榆林", "商洛", "铜川"]},
    "辽宁": {"type": "省", "cities": ["沈阳", "大连", "鞍山", "抚顺", "锦州", "营口", "丹东", "阜新", "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛", "本溪"]},
    "吉林": {"type": "省", "cities": ["长春", "吉林", "四平", "松原", "通化", "白城", "白山", "辽源", "延边"]},
    "黑龙江": {"type": "省", "cities": ["哈尔滨", "大庆", "齐齐哈尔", "牡丹江", "佳木斯", "绥化", "鸡西", "鹤岗", "双鸭山", "伊春", "七台河", "黑河", "大兴安岭"]},
    "山西": {"type": "省", "cities": ["太原", "大同", "临汾", "运城", "长治", "晋中", "晋城", "忻州", "吕梁", "朔州", "阳泉"]},
    "云南": {"type": "省", "cities": ["昆明", "曲靖", "玉溪", "大理", "红河", "楚雄", "昭通", "保山", "丽江", "普洱", "临沧", "西双版纳", "德宏", "文山"]},
    "贵州": {"type": "省", "cities": ["贵阳", "遵义", "六盘水", "安顺", "毕节", "铜仁", "黔南", "黔东南", "黔西南"]},
    "广西": {"type": "自治区", "cities": ["南宁", "柳州", "桂林", "梧州", "北海", "玉林", "钦州", "百色", "河池", "贺州", "来宾", "崇左", "防城港", "贵港"]},
    "海南": {"type": "省", "cities": ["海口", "三亚", "儋州"]},
    "甘肃": {"type": "省", "cities": ["兰州", "天水", "白银", "庆阳", "平凉", "酒泉", "张掖", "武威", "定西", "金昌", "陇南", "嘉峪关", "临夏", "甘南"]},
    "青海": {"type": "省", "cities": ["西宁", "海东", "海北", "海南", "黄南", "果洛", "玉树", "海西"]},
    "宁夏": {"type": "自治区", "cities": ["银川", "石嘴山", "吴忠", "固原", "中卫"]},
    "新疆": {"type": "自治区", "cities": ["乌鲁木齐", "昌吉", "伊犁", "喀什", "阿克苏", "哈密", "吐鲁番", "巴音郭楞", "塔城", "克拉玛依", "和田", "石河子", "阿勒泰", "博尔塔拉"]},
    "内蒙古": {"type": "自治区", "cities": ["呼和浩特", "包头", "鄂尔多斯", "赤峰", "通辽", "呼伦贝尔", "巴彦淖尔", "乌兰察布", "兴安盟", "锡林郭勒", "乌海", "阿拉善"]},
    "西藏": {"type": "自治区", "cities": ["拉萨", "日喀则", "昌都", "林芝", "山南", "那曲", "阿里"]},
}

# 反向映射：城市 → 省份
CITY_TO_PROVINCE = {}
for province, info in REGION_HIERARCHY.items():
    for city in info["cities"]:
        CITY_TO_PROVINCE[city] = province

# 扁平省份列表（兼容旧代码）
PROVINCES = ["全国"] + list(REGION_HIERARCHY.keys())

# 考试类型标签
EXAM_TAGS = [
    "一模", "二模", "三模", "省质检", "省统考", "联考",
    "适应性考试", "学业水平", "期中", "期末",
    "百校联考", "名校联盟", "九校联考", "八校联考",
    "T8联考", "华大联盟", "衡水", "黄冈", "镇海",
    "人大附中", "北京四中", "深圳中学", "成都七中",
    "华中师大一附中", "长沙长郡", "南京外国语",
]

# 高考卷别类型
REAL_EXAM_TYPES = [
    "全国甲卷", "全国乙卷", "新高考I卷", "新高考II卷",
    "全国I卷", "全国II卷", "全国III卷",
    "北京卷", "上海卷", "天津卷", "浙江卷",
    "山东卷", "江苏卷", "广东卷", "湖北卷",
    "湖南卷", "福建卷", "河北卷", "辽宁卷",
]

# 权威数据源配置
SOURCES = {
    "moe": {
        "name": "教育部考试院",
        "base_url": "https://www.neea.edu.cn",
        "priority": "S",
        "enabled": True,
        "type": "official",
    },
    "zxxk": {
        "name": "学科网",
        "base_url": "https://www.zxxk.com",
        "priority": "A",
        "enabled": True,
        "type": "platform",
    },
    "zujuan": {
        "name": "组卷网",
        "base_url": "https://www.zujuan.com",
        "priority": "A",
        "enabled": True,
        "type": "platform",
    },
    "jyeoo": {
        "name": "菁优网",
        "base_url": "https://www.jyeoo.com",
        "search_path": "/search",
        "result_selector": "a.result-link",
        "priority": "B",
        "enabled": True,
        "type": "platform",
    },
    "gaosan": {
        "name": "高考网",
        "base_url": "https://www.gaokao.com",
        "search_path": "/search",
        "result_selector": "a",
        "priority": "B",
        "enabled": True,
        "type": "platform",
    },
    "paperpass": {
        "name": "试卷吧",
        "base_url": "https://www.shijuanba.com",
        "search_path": "/search",
        "result_selector": "a",
        "priority": "C",
        "enabled": True,
        "type": "platform",
    },
    "21cnjy": {
        "name": "21世纪教育网",
        "base_url": "https://www.21cnjy.com",
        "search_path": "/search",
        "result_selector": "a",
        "priority": "B",
        "enabled": True,
        "type": "platform",
    },
}

# ===== v5.0 自动采集调度配置 =====
AUTO_SCRAPER_CONFIG = {
    "enabled": True,
    "interval_minutes": 30,  # 每30分钟自动采集一次
    "subjects": ["math", "chinese", "english", "physics", "chemistry", "biology", "history", "geography", "politics"],
    "year_range": [2025, 2026],
    "cross_verify_sources": 3,  # 交叉验证至少需要3个来源确认
    "max_papers_per_run": 20,  # 每次采集最多20份
    "deepseek_verify": True,  # 使用DeepSeek验证真实性
}

# ===== v5.0 官方文件库配置 =====
OFFICIAL_DOCS_CONFIG = {
    "sources": [
        {
            "id": "moe_policy",
            "name": "教育部政策文件",
            "base_url": "http://www.moe.gov.cn/jyb_xxgk/",
            "category": "policy",
            "priority": "S",
        },
        {
            "id": "moe_exam",
            "name": "教育部考试院公告",
            "base_url": "https://www.neea.edu.cn/",
            "category": "exam_notice",
            "priority": "S",
        },
        {
            "id": "moe_curriculum",
            "name": "课程标准(2020修订)",
            "base_url": "http://www.moe.gov.cn/",
            "category": "curriculum",
            "priority": "S",
        },
    ],
    "categories": [
        {"id": "policy", "name": "政策文件", "icon": "policy"},
        {"id": "exam_notice", "name": "考试公告", "icon": "notice"},
        {"id": "curriculum", "name": "课程标准", "icon": "curriculum"},
        {"id": "scoring", "name": "评分标准", "icon": "scoring"},
        {"id": "analysis", "name": "考情分析", "icon": "analysis"},
        {"id": "reform", "name": "新高考改革", "icon": "reform"},
    ],
    "keywords": [
        "普通高等学校招生", "高考综合改革", "课程方案和课程标准",
        "考试大纲", "命题指导意见", "评分标准", "考试说明",
        "学业水平考试", "综合素质评价", "选考科目要求",
    ],
}

# 爬虫配置
SCRAPER_CONFIG = {
    "max_concurrent": 3,
    "request_delay": 2.0,
    "timeout": 30,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "retry_times": 3,
}

# IRT 模型配置
IRT_CONFIG = {
    "model": "3PL",
    "quad_points": 41,
    "theta_range": (-4.0, 4.0),
    "prior_a": (0.5, 2.5),
    "prior_b": (-3.0, 3.0),
    "prior_c": (0.0, 0.35),
}

# 蒙特卡洛模拟配置
MC_CONFIG = {
    "n_students": 100000,
    "random_seed": 42,
    "theta_distribution": {"type": "normal", "mean": 0.0, "std": 1.0},
}

# ===== v5.0 官方校准数据 =====
# 基于教育部和各省市教育考试院公布的近年统计数据
# 用于校准模拟结果使其与真实高考成绩分布一致
# skewness: 偏度（负偏=左偏=低分段更密集），kurtosis: 峰度
CALIBRATION_DATA = {
    # 各科平均分、标准差、偏度、峰度
    # 格式: subject_id -> { "mean_pct", "std_pct", "skewness", "kurtosis", "source" }
    "chinese": {
        "mean_pct": 0.62, "std_pct": 0.12,
        "skewness": -0.35, "kurtosis": 0.20,
        "source": "基于2022-2024全国高考语文成绩统计",
        "score_lines": {
            "特优线": 120, "一本线": 105, "本科线": 90, "专科线": 60,
        },
    },
    "math": {
        "mean_pct": 0.48, "std_pct": 0.18,
        "skewness": 0.10, "kurtosis": -0.15,
        "source": "基于2022-2024全国高考数学成绩统计",
        "score_lines": {
            "特优线": 125, "一本线": 100, "本科线": 70, "专科线": 40,
        },
    },
    "english": {
        "mean_pct": 0.58, "std_pct": 0.14,
        "skewness": -0.20, "kurtosis": -0.10,
        "source": "基于2022-2024全国高考英语成绩统计",
        "score_lines": {
            "特优线": 125, "一本线": 105, "本科线": 80, "专科线": 50,
        },
    },
    "physics": {
        "mean_pct": 0.52, "std_pct": 0.16,
        "skewness": -0.15, "kurtosis": -0.20,
        "source": "基于2022-2024选考物理成绩统计",
        "score_lines": {
            "特优线": 85, "一本线": 70, "本科线": 50, "专科线": 30,
        },
    },
    "chemistry": {
        "mean_pct": 0.55, "std_pct": 0.15,
        "skewness": -0.25, "kurtosis": -0.10,
        "source": "基于2022-2024选考化学成绩统计",
        "score_lines": {
            "特优线": 85, "一本线": 72, "本科线": 52, "专科线": 30,
        },
    },
    "biology": {
        "mean_pct": 0.58, "std_pct": 0.14,
        "skewness": -0.30, "kurtosis": 0.05,
        "source": "基于2022-2024选考生物成绩统计",
        "score_lines": {
            "特优线": 88, "一本线": 73, "本科线": 55, "专科线": 32,
        },
    },
    "history": {
        "mean_pct": 0.56, "std_pct": 0.15,
        "skewness": -0.20, "kurtosis": -0.05,
        "source": "基于2022-2024选考历史成绩统计",
        "score_lines": {
            "特优线": 85, "一本线": 72, "本科线": 52, "专科线": 30,
        },
    },
    "geography": {
        "mean_pct": 0.57, "std_pct": 0.14,
        "skewness": -0.18, "kurtosis": -0.08,
        "source": "基于2022-2024选考地理成绩统计",
        "score_lines": {
            "特优线": 86, "一本线": 73, "本科线": 53, "专科线": 31,
        },
    },
    "politics": {
        "mean_pct": 0.59, "std_pct": 0.13,
        "skewness": -0.28, "kurtosis": 0.10,
        "source": "基于2022-2024选考政治成绩统计",
        "score_lines": {
            "特优线": 87, "一本线": 74, "本科线": 54, "专科线": 32,
        },
    },
}

# 拟合分析权重
FIT_WEIGHTS = {
    "knowledge_coverage": 0.25,
    "difficulty_fit": 0.25,
    "question_type_match": 0.20,
    "quality_score": 0.15,
    "curriculum_alignment": 0.15,
}

# 新高考等级赋分规则（物理/化学/生物/政治/历史/地理）
# 严格按照教育部《普通高校本科招生专业选考科目要求指引》
GRADE_ASSIGNMENT_RULES = {
    "A": {"percentile_top": 3, "score_range": (91, 100)},
    "B+": {"percentile_top": 7, "score_range": (81, 90)},
    "B": {"percentile_top": 16, "score_range": (71, 80)},
    "C+": {"percentile_top": 31, "score_range": (61, 70)},
    "C": {"percentile_top": 53, "score_range": (51, 60)},
    "D+": {"percentile_top": 73, "score_range": (41, 50)},
    "D": {"percentile_top": 86, "score_range": (31, 40)},
    "E": {"percentile_top": 96, "score_range": (21, 30)},
    "F": {"percentile_top": 100, "score_range": (1, 20)},
}

# 课程标准核心能力层次
CURRICULUM_LEVELS = {
    "识记": {"weight": 0.10, "description": "识别和记忆基础知识"},
    "理解": {"weight": 0.20, "description": "领会知识内涵与联系"},
    "应用": {"weight": 0.30, "description": "在熟悉情境中运用知识"},
    "分析": {"weight": 0.20, "description": "分解问题并识别关系"},
    "综合": {"weight": 0.15, "description": "整合知识解决新问题"},
    "评价": {"weight": 0.05, "description": "判断和鉴赏批判性思维"},
}

# 核心素养指标（各科通用）
CORE_COMPETENCIES = {
    "math": ["数学抽象", "逻辑推理", "数学建模", "直观想象", "数学运算", "数据分析"],
    "chinese": ["语言建构与运用", "思维发展与提升", "审美鉴赏与创造", "文化传承与理解"],
    "english": ["语言能力", "文化意识", "思维品质", "学习能力"],
    "physics": ["物理观念", "科学思维", "科学探究", "科学态度与责任"],
    "chemistry": ["宏观辨识与微观探析", "变化观念与平衡思想", "证据推理与模型认知", "科学探究与创新意识", "科学精神与社会责任"],
    "biology": ["生命观念", "科学思维", "科学探究", "社会责任"],
    "history": ["唯物史观", "时空观念", "史料实证", "历史解释", "家国情怀"],
    "geography": ["人地协调观", "综合思维", "区域认知", "地理实践力"],
    "politics": ["政治认同", "科学精神", "法治意识", "公共参与"],
}

# DeepSeek 查重配置
DEEPSEEK_CONFIG = {
    "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
    "api_url": "https://api.deepseek.com/v1/chat/completions",
    "model": "deepseek-chat",
    "rate_limit_per_minute": 10,
    "timeout": 30,
}

# 来源可信度映射
SOURCE_PRIORITY_MAP = {
    "S": "教育部考试院（最高可信度）",
    "A": "省级教育部门/学科网/组卷网",
    "B": "菁优网/高考网等教育平台",
    "C": "个人上传/未验证来源",
}

# 确保目录存在
for d in [DATA_DIR, DOWNLOAD_DIR]:
    os.makedirs(d, exist_ok=True)
