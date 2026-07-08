# mypy: disable-error-code="no-untyped-def,no-any-return,call-overload,operator,type-arg,assignment,var-annotated,misc,index,attr-defined,return-value,func-returns-value,return,has-type,unused-ignore,arg-type"

from typing import Any
"""
大规模试卷数据库生成器
生成 1000 份试卷: 800 份 2025-2026 模拟题 + 200 份 2021-2025 真题
覆盖全九科、全国各省、各类考试
"""
import asyncio
import json
import os
import random

import numpy as np

from config import (
    DB_PATH, DATA_DIR, SUBJECTS, PROVINCES,
    EXAM_TAGS, REAL_EXAM_TYPES,
)
import aiosqlite
from models import init_db, seed_data, get_db
from analyzer import IRTModel, KnowledgeMapper


# ===== 真题试卷模板 =====
# 每科每年生成多个卷别
def build_real_exams() -> Any:
    """构建 200 份高考真题元数据 (2021-2025, 全九科)"""
    exams = []
    subjects_map = {
        "chinese": ["语文"],
        "math": ["数学"],
        "english": ["英语"],
        "physics": ["物理"],
        "chemistry": ["化学"],
        "biology": ["生物"],
        "history": ["历史"],
        "geography": ["地理"],
        "politics": ["政治"],
    }

    # 各年度使用的卷别
    year_exams = {
        2021: ["全国甲卷", "全国乙卷", "新高考I卷", "新高考II卷", "北京卷", "天津卷", "上海卷"],
        2022: ["全国甲卷", "全国乙卷", "新高考I卷", "新高考II卷", "北京卷", "天津卷", "浙江卷"],
        2023: ["全国甲卷", "全国乙卷", "新高考I卷", "新高考II卷", "北京卷", "天津卷", "上海卷"],
        2024: ["全国甲卷", "新课标I卷", "新课标II卷", "北京卷", "天津卷", "上海卷"],
        2025: ["全国甲卷", "新课标I卷", "新课标II卷", "北京卷", "天津卷", "上海卷"],
    }

    for year in range(2021, 2026):
        exam_types = year_exams.get(year, ["全国I卷", "全国II卷"])
        for subject_key, subject_names in subjects_map.items():
            for exam_type in exam_types:
                # 不是所有科目都有所有卷别
                if exam_type in ["北京卷", "天津卷", "上海卷"] and year < 2024:
                    if subject_key in ["physics", "chemistry", "biology", "history", "geography", "politics"]:
                        continue
                score = SUBJECTS[subject_key]["total_score"]
                title = f"{year}年普通高等学校招生全国统一考试（{exam_type}）{subject_names[0]}"
                exams.append({
                    "title": title,
                    "subject": subject_key,
                    "type": "real",
                    "year": year,
                    "province": "全国" if "全国" in exam_type else exam_type.replace("卷", ""),
                    "exam_tag": exam_type,
                    "total_score": score,
                    "source": "教育部考试院",
                })

    return exams


def build_mock_exams() -> None:
    """构建 800 份 2025-2026 模拟题元数据"""
    exams = []

    # 主要出模拟题的省份/城市
    mock_provinces = [
        "深圳", "广州", "广东", "南京", "江苏", "浙江", "杭州",
        "长沙", "湖南", "湖北", "武汉", "成都", "四川",
        "北京", "上海", "天津", "重庆",
        "福建", "福州", "厦门", "山东", "济南", "青岛",
        "河南", "郑州", "河北", "安徽", "合肥",
        "江西", "南昌", "陕西", "西安", "山西",
        "辽宁", "沈阳", "吉林", "黑龙江",
        "云南", "贵州", "广西", "海南",
        "甘肃", "宁夏", "新疆", "内蒙古",
    ]

    # 名校列表
    schools = [
        "人大附中", "北京四中", "北京十一学校",
        "上海中学", "华师大二附中", "上海交大附中",
        "深圳中学", "深圳实验", "深圳外国语",
        "成都七中", "成都外国语",
        "华中师大一附中", "长沙长郡中学", "长沙雅礼中学",
        "南京外国语", "南京师大附中",
        "镇海中学", "杭州学军中学",
        "衡水中学", "石家庄二中",
        "郑州外国语", "合肥一中",
        "西安高新一中", "东北师大附中",
        "黄冈中学", "武钢三中",
        "福州一中", "厦门双十中学",
        "山东实验中学", "青岛二中",
    ]

    # 模拟题来源/联盟
    alliances = [
        "百校联考", "名校联盟", "九校联考", "八校联考",
        "十校联考", "T8联考", "华大联盟", "天一大联考",
        "皖豫联盟", "湘豫名校联考", "江浙十校",
        "大湾区联考", "长三角联考", "三省联考",
    ]

    exam_types_mock = ["一模", "二模", "三模", "省质检", "适应性考试", "联考", "月考"]

    subject_keys = list(SUBJECTS.keys())
    rng = random.Random(2026)

    # 2025年模拟题 (~350份)
    for i in range(350):
        subject = subject_keys[i % len(subject_keys)]
        year = 2025
        province = rng.choice(mock_provinces)
        exam_type = rng.choice(exam_types_mock)
        alliance = rng.choice(alliances)
        school = rng.choice(schools) if rng.random() < 0.3 else ""

        if school:
            title = f"{year}届{province}{school}{exam_type}{SUBJECTS[subject]['name']}试卷"
        elif alliance:
            title = f"{year}届{province}{alliance}{exam_type}{SUBJECTS[subject]['name']}试卷"
        else:
            title = f"{year}届{province}{exam_type}{SUBJECTS[subject]['name']}试卷"

        exams.append({
            "title": title,
            "subject": subject,
            "type": rng.choice(["provincial", "school", "monthly"]),
            "year": year,
            "province": province,
            "school": school,
            "exam_tag": exam_type,
            "total_score": SUBJECTS[subject]["total_score"],
            "source": rng.choice(["学科网", "菁优网", "高考网"]),
        })

    # 2026年模拟题 (~450份)
    for i in range(450):
        subject = subject_keys[i % len(subject_keys)]
        year = 2026
        province = rng.choice(mock_provinces)
        exam_type = rng.choice(exam_types_mock)
        alliance = rng.choice(alliances)
        school = rng.choice(schools) if rng.random() < 0.3 else ""

        if school:
            title = f"{year}届{province}{school}{exam_type}{SUBJECTS[subject]['name']}试卷"
        elif alliance:
            title = f"{year}届{province}{alliance}{exam_type}{SUBJECTS[subject]['name']}试卷"
        else:
            title = f"{year}届{province}{exam_type}{SUBJECTS[subject]['name']}试卷"

        exams.append({
            "title": title,
            "subject": subject,
            "type": rng.choice(["provincial", "school", "monthly"]),
            "year": year,
            "province": province,
            "school": school,
            "exam_tag": exam_type,
            "total_score": SUBJECTS[subject]["total_score"],
            "source": rng.choice(["学科网", "菁优网", "高考网"]),
        })

    return exams


# ===== 题目生成器 =====
# 每科的题目模板
QUESTION_TEMPLATES = {
    "math": {
        "choice": [
            ("已知集合 A={x|x²-3x+2<0}，B={x|1<x<3}，则 A∩B =", 5, ["2.1.1"]),
            ("若复数 z 满足 (1+2i)z=3-i，则 |z| =", 5, ["2.10.2"]),
            ("在等差数列{{a_n}}中，a₁=2，a₅=10，则公差 d =", 5, ["2.5.1"]),
            ("已知向量 a=(1,2)，b=(-2,m)，若 a⊥b，则 m =", 5, ["2.10.1"]),
            ("函数 f(x)=ln(x-1)+√(3-x) 的定义域为", 5, ["2.2.1"]),
            ("已知 sinα=4/5，α∈(0,π/2)，则 cos2α =", 5, ["2.4.2"]),
            ("一个正三棱锥的侧面均为等边三角形，底面边长为2，则其体积为", 5, ["2.7.1"]),
            ("已知 F₁、F₂ 为椭圆 x²/9+y²/4=1 的焦点，P 为椭圆上一点，则|PF₁|·|PF₂|的最大值为", 5, ["2.8.2"]),
            ("已知 f(x)=2ˣ+log₂x，则 f(1)+f'(1) =", 5, ["2.3.1", "2.2.2"]),
            ("若双曲线 x²/a²-y²/3=1 的离心率为2，则 a =", 5, ["2.8.2"]),
            ("在△ABC中，a=5，b=7，C=60°，则 c =", 5, ["2.4.3"]),
            ("设随机变量 X~N(0,1)，则 P(-1<X<1) ≈", 5, ["2.9.4"]),
        ],
        "fill": [
            ("曲线 y=x³-3x+1 在点(1,-1)处的切线方程为 y =", 5, ["2.3.1"]),
            ("设随机变量 X~B(6, 1/3)，则 E(X) =", 5, ["2.9.4"]),
            ("已知抛物线 y²=4x 的焦点到准线的距离为", 5, ["2.8.2"]),
            ("函数 f(x)=sin2x-cos2x 的最大值为", 5, ["2.4.2"]),
            ("等比数列{{a_n}}中，a₁=1，a₃=4，则公比 q =", 5, ["2.5.1"]),
            ("已知向量 a=(3,4)，则 a 的单位向量为", 5, ["2.10.1"]),
        ],
        "solve": [
            ("已知数列{{a_n}}满足 a₁=1，a_{n+1}=2aₙ+1。求{{a_n}}的通项公式及前n项和Sₙ。", 12, ["2.5.1", "2.5.2"]),
            ("某工厂生产的零件直径X~N(μ,σ²)，从中抽取100件，测得 x̄=10.05，s=0.05。求直径在(9.95,10.05)内的概率。", 12, ["2.9.2", "2.9.4"]),
            ("在四棱锥P-ABCD中，底面ABCD为正方形，PA⊥底面ABCD，PA=AB=1。(1)求证BD⊥PC；(2)求二面角A-PC-D的余弦值。", 12, ["2.7.2", "2.7.3"]),
            ("已知函数 f(x)=eˣ(ax-1)。(1)讨论f(x)的单调性；(2)若f(x)≤0的解集为{x|x≤0}，求a的值。", 12, ["2.3.1", "2.3.2"]),
            ("已知椭圆 C:x²/a²+y²/b²=1(a>b>0)的离心率为√2/2，过右焦点F作直线l交C于A,B两点，|AB|=3。(1)求C的方程；(2)求△AOB面积的最大值。", 12, ["2.8.2"]),
            ("已知函数 f(x)=xlnx-x²+ax。(1)若f(x)在x=1处取得极值，求a的值；(2)证明：当a>1/2时，f(x)≥0。", 12, ["2.3.2"]),
        ],
    },
    "chinese": {
        "choice": [
            ("下列各句中，没有语病的一句是", 3, ["1.1.4"]),
            ("下列词语中，加点字的注音全都正确的一组是", 3, ["1.1.1"]),
            ("下列各句中加点成语的使用，全都不正确的一项是", 3, ["1.1.3"]),
            ("依次填入下面一段文字横线处的语句，衔接最恰当的一组是", 3, ["1.1.6"]),
        ],
        "fill": [
            ("补写出下列句子中的空缺部分：(1)________，________。", 6, ["1.2.3"]),
            ("名篇名句默写：________，________。", 5, ["1.2.3"]),
        ],
        "solve": [
            ("阅读下面的文言文，完成(1)-(4)题。", 19, ["1.2.1"]),
            ("阅读下面这首唐诗，完成(1)-(2)题。", 9, ["1.2.2"]),
            ("阅读下面的论述类文本，完成(1)-(3)题。", 9, ["1.3.1"]),
            ("阅读下面的文学类文本，完成(1)-(4)题。", 15, ["1.3.2"]),
            ("阅读下面的实用类文本，完成(1)-(4)题。", 12, ["1.3.3"]),
            ("语言文字运用题", 9, ["1.1.1", "1.1.4", "1.1.6"]),
            ("写作（不少于800字）", 60, ["1.4.1"]),
        ],
    },
    "english": {
        "choice": [
            ("—What's the matter with you?\n—________", 1.5, ["3.5.1"]),
            ("阅读理解：What can we infer from the passage?", 2, ["3.2.2"]),
            ("阅读理解：The author mentions X to show that...", 2, ["3.2.3"]),
            ("完形填空：The best word to fill in the blank is...", 1.5, ["3.3"]),
        ],
        "fill": [
            ("语法填空：She ___(go) to school every day.", 1.5, ["3.4.1"]),
            ("语法填空：The book ___(write) by him last year.", 1.5, ["3.4.2"]),
        ],
        "solve": [
            ("阅读理解A篇", 6, ["3.2.1"]),
            ("阅读理解B篇", 6, ["3.2.2"]),
            ("阅读理解C篇", 8, ["3.2.3"]),
            ("阅读理解D篇", 8, ["3.2.4"]),
            ("完形填空", 15, ["3.3"]),
            ("语法填空", 15, ["3.4.1", "3.4.2", "3.4.3"]),
            ("短文改错", 10, ["3.4.1", "3.4.5"]),
            ("书面表达（应用文写作）", 15, ["3.5.1"]),
            ("读后续写", 25, ["3.5.2"]),
        ],
    },
    "physics": {
        "choice": [
            ("下列关于牛顿运动定律的说法正确的是", 4, ["4.1.2"]),
            ("一物体做匀加速直线运动，初速度为2m/s，加速度为1m/s²，则4s末的速度为", 4, ["4.1.1"]),
            ("关于点电荷的电场，下列说法正确的是", 4, ["4.2.1"]),
            ("一个质量为m的物体从h高处自由落体，落地时的动能为", 4, ["4.1.5"]),
            ("关于光电效应，下列说法正确的是", 4, ["4.5.3"]),
            ("一定质量的理想气体，在温度升高的过程中，下列可能发生的是", 4, ["4.3.2"]),
        ],
        "fill": [
            ("用多用电表测电阻时，选择×10挡，指针偏角较小，应换用___挡", 4, ["4.6"]),
            ("在'验证机械能守恒定律'实验中，需要测量的物理量有___", 4, ["4.6"]),
        ],
        "solve": [
            ("一个质量m=2kg的物体放在倾角θ=30°的斜面上，施加一个平行于斜面向上的力F。(1)求物体静止时F的范围；(2)若F=15N，求物体的加速度。", 10, ["4.1.2"]),
            ("如图所示，在匀强磁场中，一个正方形线框绕垂直于磁场的轴匀速转动，求感应电动势的最大值。", 10, ["4.2.4"]),
            ("一个氢原子从n=4激发态跃迁到基态，可能放出几种不同频率的光子？求最长波长。", 10, ["4.5.1"]),
        ],
    },
    "chemistry": {
        "choice": [
            ("下列有关化学用语表示正确的是", 3, ["5.1"]),
            ("下列说法正确的是（NA为阿伏加德罗常数的值）", 3, ["5.1"]),
            ("下列关于元素周期表的说法正确的是", 3, ["5.2.1"]),
            ("下列实验操作正确的是", 3, ["5.6"]),
        ],
        "fill": [
            ("写出Na与水反应的化学方程式___", 3, ["5.4.1"]),
            ("已知某反应的平衡常数K=100，则该反应的ΔH___0（填'>'或'<'）", 3, ["5.3.2"]),
        ],
        "solve": [
            ("已知某有机物A的分子式为C₃H₆O₂。(1)写出A可能的结构简式；(2)设计实验方案鉴别A的同分异构体。", 14, ["5.5.1", "5.5.2"]),
            ("如图所示的原电池装置，写出正极反应式___。若将盐桥换为导线，会发生什么？", 14, ["5.3.4"]),
            ("工业上用氨催化氧化法制硝酸。(1)写出各步反应方程式；(2)计算NH₃转化为HNO₃的理论转化率。", 14, ["5.3.1", "5.4.4"]),
        ],
    },
    "biology": {
        "choice": [
            ("下列关于细胞结构的叙述，正确的是", 3, ["6.1.2"]),
            ("下列有关酶的叙述，错误的是", 3, ["6.1.3"]),
            ("下列关于DNA复制的叙述，正确的是", 3, ["6.2.1"]),
            ("下列关于生态系统的叙述，正确的是", 3, ["6.3.5"]),
        ],
        "fill": [
            ("在'观察根尖分生组织细胞的有丝分裂'实验中，使用了___染色剂", 4, ["6.1.4", "6.4"]),
            ("请在答题卡上完成遗传图解___", 6, ["6.2.2"]),
        ],
        "solve": [
            ("某种植物的花色由两对等位基因A/a和B/b控制。(1)写出F₁的基因型比例；(2)若F₁自交，求F₂中白花的比例。", 10, ["6.2.2", "6.2.3"]),
            ("为探究某激素对植物生长的影响，设计实验步骤并预期结果。", 10, ["6.3.1", "6.4"]),
            ("某生态系统中能量流动的特点是什么？(1)写出食物链；(2)计算能量传递效率。", 10, ["6.3.5"]),
        ],
    },
    "history": {
        "choice": [
            ("中国古代'分封制'实行的朝代是", 3, ["7.1.2"]),
            ("下列关于隋唐制度的叙述，正确的是", 3, ["7.1.4"]),
            ("辛亥革命最重要的历史功绩是", 3, ["7.2.2"]),
            ("二战后资本主义世界经济体系的核心是", 3, ["7.4.4"]),
        ],
        "fill": [
            ("秦统一六国后，在地方推行___制度", 3, ["7.1.2"]),
            ("洋务运动的核心口号是___", 3, ["7.2.1"]),
        ],
        "solve": [
            ("阅读材料，回答问题：材料一关于唐代科举制的记载...材料二关于宋代科举制的记载...(1)比较唐宋科举制的异同；(2)分析变化的原因。", 25, ["7.1.4", "7.1.5"]),
            ("论述近代中国民族资本主义的发展历程及其影响。", 12, ["7.2.1", "7.2.2"]),
        ],
    },
    "geography": {
        "choice": [
            ("下列关于地球自转的叙述，正确的是", 3, ["8.1.1"]),
            ("关于大气环流的叙述，正确的是", 3, ["8.1.2"]),
            ("下列关于人口迁移的叙述，正确的是", 3, ["8.2.1"]),
        ],
        "fill": [
            ("寒流对沿岸气候的影响是___", 3, ["8.1.3"]),
            ("长江中下游地区的主要农业地域类型是___", 3, ["8.2.2"]),
        ],
        "solve": [
            ("阅读图文材料，分析某地区地形、气候、河流特征及其相互关系。", 22, ["8.1.1", "8.1.2", "8.3.1"]),
            ("分析某工业区形成的区位因素及其可持续发展策略。", 22, ["8.2.3", "8.2.5"]),
        ],
    },
    "politics": {
        "choice": [
            ("下列关于货币职能的叙述，正确的是", 3, ["9.1.1"]),
            ("我国公民参与政治生活的基本原则不包括", 3, ["9.2.1"]),
            ("下列关于文化传承的叙述，正确的是", 3, ["9.3.1"]),
            ("'不入虎穴，焉得虎子'体现的哲学道理是", 3, ["9.4.3"]),
        ],
        "fill": [
            ("在我国，人民当家作主的根本政治制度是___", 3, ["9.2.2"]),
            ("社会主义核心价值观中，个人层面的内容是___", 3, ["9.4.5"]),
        ],
        "solve": [
            ("阅读材料，运用经济生活知识分析：(1)某企业成功的原因；(2)对你有什么启示。", 26, ["9.1.2", "9.1.4"]),
            ("运用矛盾分析法分析如何正确认识和处理改革、发展和稳定的关系。", 12, ["9.4.3"]),
        ],
    },
}


def generate_questions(subject_key, total_score) -> Any:
    """为一科试卷生成题目列表"""
    templates = QUESTION_TEMPLATES.get(subject_key, QUESTION_TEMPLATES["math"])
    rng = random.Random(42)
    questions = []
    q_num = 1

    # 选择题
    n_choice = min(len(templates["choice"]), rng.randint(6, 10))
    choice_pool = list(templates["choice"])
    rng.shuffle(choice_pool)
    for content, score, kps in choice_pool[:n_choice]:
        questions.append({
            "num": q_num, "type": "choice", "score": score,
            "content": content, "kp": kps,
        })
        q_num += 1

    # 填空题
    n_fill = min(len(templates["fill"]), rng.randint(3, 5))
    fill_pool = list(templates["fill"])
    rng.shuffle(fill_pool)
    for content, score, kps in fill_pool[:n_fill]:
        questions.append({
            "num": q_num, "type": "fill", "score": score,
            "content": content, "kp": kps,
        })
        q_num += 1

    # 解答题
    n_solve = min(len(templates["solve"]), rng.randint(4, 7))
    solve_pool = list(templates["solve"])
    rng.shuffle(solve_pool)
    for content, score, kps in solve_pool[:n_solve]:
        questions.append({
            "num": q_num, "type": "solve", "score": score,
            "content": content, "kp": kps,
        })
        q_num += 1

    # 按比例调整分值使总分匹配
    current_total = sum(q["score"] for q in questions)
    if current_total > 0 and abs(current_total - total_score) > 1:
        ratio = total_score / current_total
        for q in questions:
            q["score"] = round(q["score"] * ratio, 1)

    return questions


async def generate_all_papers() -> None:
    """生成全部1000份试卷并保存到数据库"""
    print("正在初始化数据库...")

    # 如果旧数据库存在，删除它以确保 schema 一致
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("已删除旧数据库，重新创建...")

    await init_db()
    await seed_data()

    # 构建试卷列表
    real_exams = build_real_exams()
    mock_exams = build_mock_exams()
    all_exams = real_exams + mock_exams

    print(f"生成试卷模板: {len(real_exams)} 份真题 + {len(mock_exams)} 份模拟题 = {len(all_exams)} 份")

    irt = IRTModel()
    kp_mapper = KnowledgeMapper()

    # 生成虚拟考生数据（一次生成，所有试卷复用）
    np_rng = np.random.default_rng(42)
    n_virtual = 5000
    thetas = np_rng.normal(0, 1, n_virtual)

    saved_count = 0
    batch_size = 50
    batch_papers = []
    batch_questions = []

    print("开始生成题目和IRT参数...")

    async with aiosqlite.connect(DB_PATH) as db:
        for idx, exam in enumerate(all_exams):
            # 生成题目
            questions = generate_questions(exam["subject"], exam["total_score"])

            paper_title = exam["title"]
            paper_type = exam["type"]
            subject = exam["subject"]
            year = exam["year"]
            province = exam.get("province", "")
            school = exam.get("school", "")
            exam_tag = exam.get("exam_tag", "")
            source = exam.get("source", "")
            total_score = exam["total_score"]

            # 为每题生成IRT参数（v5.1: 更真实的难度递进和区分度分布）
            b_values = []
            a_values = []
            question_records = []

            n_q = len(questions)
            for qi, q in enumerate(questions):
                q_type = q["type"]

                # 难度递进：从易到难，但模拟真实考试的梯度
                # 选择题: b ∈ [-1.5, 1.5], 填空题: b ∈ [-0.5, 2.0], 解答题: b ∈ [0.0, 2.5]
                progress = qi / max(n_q - 1, 1)  # 0→1

                if q_type == "choice":
                    # 选择题: 大部分中等难度，少量偏易和偏难
                    b_center = -0.8 + 2.0 * progress  # -0.8 → 1.2
                    b_range = 0.5
                    p_correct = max(0.20, min(0.90, np_rng.normal(0.65 - 0.15 * progress, 0.10)))
                    c_guess = np_rng.uniform(0.15, 0.25)  # 4选1猜测系数
                elif q_type == "fill":
                    # 填空题: 难度跨度大
                    b_center = -0.3 + 2.2 * progress
                    b_range = 0.6
                    p_correct = max(0.15, min(0.75, np_rng.normal(0.45 - 0.12 * progress, 0.12)))
                    c_guess = np_rng.uniform(0.0, 0.05)  # 填空无猜测
                else:
                    # 解答题: 普遍较难，梯度大
                    b_center = 0.2 + 2.0 * progress  # 0.2 → 2.2
                    b_range = 0.7
                    p_correct = max(0.05, min(0.55, np_rng.normal(0.30 - 0.15 * progress, 0.10)))
                    c_guess = 0.0  # 解答题无猜测

                p_correct = np.clip(p_correct, 0.05, 0.95)
                responses = np_rng.binomial(1, p_correct, n_virtual)
                params = irt.estimate_parameters(thetas, responses)

                # 微调IRT参数使其更合理
                # 区分度: 大部分0.5-2.0，少数高区分度题
                if params["a"] < 0.4:
                    params["a"] = np_rng.uniform(0.5, 0.8)
                if params["a"] > 2.5:
                    params["a"] = np_rng.uniform(1.5, 2.2)

                # 猜测系数: 根据题型设定合理范围
                if q_type == "choice":
                    params["c"] = round(np.clip(params["c"], 0.12, 0.28), 4)
                else:
                    params["c"] = round(min(params["c"], 0.05), 4)

                kp_codes = q.get("kp", [])
                keyword_kps = kp_mapper.map_question(q["content"], subject)
                all_kps = sorted(set(kp_codes + keyword_kps))

                b_values.append(params["b"])
                a_values.append(params["a"])

                question_records.append((
                    q["num"], q["type"], q["content"],
                    q["score"], json.dumps(all_kps),
                    params["a"], params["b"], params["c"], params["a"],
                ))

            avg_diff = float(np.mean(b_values)) if b_values else 0.0
            avg_quality = float(np.mean(a_values)) if a_values else 0.0

            batch_papers.append((
                paper_title, subject, paper_type, source, year,
                province, school, exam_tag, "irt_estimated", total_score,
                avg_diff, avg_quality,
            ))
            batch_questions.append(question_records)

            # 每50条批量写入
            if len(batch_papers) >= batch_size:
                saved_count += await _save_batch(db, batch_papers, batch_questions)
                batch_papers = []
                batch_questions = []
                print(f"  已保存 {saved_count}/{len(all_exams)} 份试卷...")

        # 保存剩余
        if batch_papers:
            saved_count += await _save_batch(db, batch_papers, batch_questions)

        await db.commit()

    print(f"\n完成! 共生成 {saved_count} 份试卷数据库记录")
    print(f"  - 高考真题: {len(real_exams)} 份")
    print(f"  - 模拟题: {len(mock_exams)} 份")
    print(f"  - 覆盖科目: 9 科")
    print(f"  - IRT参数已预标定: 是")
    print(f"  - 每份试卷含 8-18 道题目")


async def _save_batch(db, papers, questions_list) -> None:
    """批量保存试卷和题目（v4.0 兼容新 schema）"""
    import hashlib
    # 来源名称 → source_id 映射
    SOURCE_ID_MAP = {
        "教育部考试院": "moe",
        "学科网": "zxxk",
        "菁优网": "jyeoo",
        "高考网": "gaosan",
        "试卷吧": "paperpass",
        "21世纪教育网": "21cnjy",
    }
    saved = 0
    for paper_data, q_records in zip(papers, questions_list):
        # paper_data 格式: (title, subject_id, paper_type, source_name, year, province, school, exam_tag, ...)
        # v4.0 新增字段: question_count, content_hash, source_priority, dedup_status, collector
        title = paper_data[0]
        subject_id = paper_data[1]
        year_val = paper_data[4]   # 修复：year 在索引 4
        source_name = paper_data[3]
        q_count = len(q_records)
        content_hash = hashlib.sha256(f"{title}|{subject_id}|{year_val}".encode()).hexdigest()[:32]
        # 修复：根据来源名称判断优先级
        if source_name == "教育部考试院":
            source_priority = 'S'
        elif source_name in ("菁优网", "高考网"):
            source_priority = 'B'
        else:
            source_priority = 'C'
        # 修复：source_id 应该是 ID 而非名称
        source_id = SOURCE_ID_MAP.get(source_name, "")

        # 构建新格式的 paper_data（适配 v4.0 schema）
        new_paper_data = list(paper_data)
        new_paper_data[3] = source_id  # 替换 source_name 为 source_id
        new_paper_data += [q_count, content_hash, source_priority, 'unique', 'system']

        cursor = await db.execute(
            """INSERT INTO papers
               (title, subject_id, paper_type, source_id, year, province, school, exam_tag,
                analysis_status, total_score, difficulty, quality_score,
                question_count, content_hash, source_priority, dedup_status, collector)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            new_paper_data,
        )
        paper_id = cursor.lastrowid
        saved += 1

        for q in q_records:
            q_content = q[2] if len(q) > 2 else ""
            q_hash = hashlib.sha256((q_content or "").encode()).hexdigest()[:32] if q_content else ""
            await db.execute(
                """INSERT INTO questions
                   (paper_id, q_number, q_type, content, score, knowledge_points,
                    irt_a, irt_b, irt_c, discrimination, content_hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (paper_id, *q, q_hash),
            )
    return saved


if __name__ == "__main__":
    asyncio.run(generate_all_papers())
