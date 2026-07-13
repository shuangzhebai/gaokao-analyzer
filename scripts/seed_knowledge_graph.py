"""P0: 知识图谱种子数据 — 数学核心知识点DAG"""
import json
# 知识点层级：
# Level 0: 基础概念
# Level 1: 核心方法
# Level 2: 综合应用
# Level 3: 拓展创新

KNOWLEDGE_GRAPH_SEED = {
    "math": [
        # ─── 代数 ───
        {"kp_code": "2.1", "kp_name": "集合与常用逻辑用语", "prerequisites": [],
         "difficulty": 0.3, "exam_frequency": 0.65, "cognitive_level": "基础", "importance": "高"},
        {"kp_code": "2.1.1", "kp_name": "集合的概念与运算", "prerequisites": ["2.1"],
         "difficulty": 0.3, "exam_frequency": 0.60, "cognitive_level": "基础", "importance": "高"},
        {"kp_code": "2.1.2", "kp_name": "充分条件与必要条件", "prerequisites": ["2.1"],
         "difficulty": 0.4, "exam_frequency": 0.55, "cognitive_level": "理解", "importance": "中"},
        {"kp_code": "2.2.1", "kp_name": "函数的概念与性质", "prerequisites": ["2.1"],
         "difficulty": 0.4, "exam_frequency": 0.75, "cognitive_level": "理解", "importance": "高"},
        {"kp_code": "2.2.2", "kp_name": "基本初等函数", "prerequisites": ["2.2.1"],
         "difficulty": 0.5, "exam_frequency": 0.75, "cognitive_level": "理解", "importance": "高"},
        {"kp_code": "2.2.3", "kp_name": "函数与方程", "prerequisites": ["2.2.1"],
         "difficulty": 0.55, "exam_frequency": 0.70, "cognitive_level": "应用", "importance": "高"},
        {"kp_code": "2.3.1", "kp_name": "导数的概念与运算", "prerequisites": ["2.2.1"],
         "difficulty": 0.5, "exam_frequency": 0.80, "cognitive_level": "理解", "importance": "高"},
        {"kp_code": "2.3.2", "kp_name": "导数在函数中的应用", "prerequisites": ["2.3.1"],
         "difficulty": 0.7, "exam_frequency": 0.92, "cognitive_level": "综合", "importance": "高"},
        {"kp_code": "2.3.3", "kp_name": "定积分", "prerequisites": ["2.3.1"],
         "difficulty": 0.6, "exam_frequency": 0.40, "cognitive_level": "应用", "importance": "中"},
        {"kp_code": "2.4.1", "kp_name": "三角函数的概念与图像", "prerequisites": ["2.2.1"],
         "difficulty": 0.5, "exam_frequency": 0.72, "cognitive_level": "理解", "importance": "高"},
        {"kp_code": "2.4.2", "kp_name": "三角恒等变换", "prerequisites": ["2.4.1"],
         "difficulty": 0.6, "exam_frequency": 0.65, "cognitive_level": "应用", "importance": "高"},
        {"kp_code": "2.4.3", "kp_name": "解三角形", "prerequisites": ["2.4.2"],
         "difficulty": 0.6, "exam_frequency": 0.88, "cognitive_level": "应用", "importance": "高"},
        {"kp_code": "2.5.1", "kp_name": "等差数列与等比数列", "prerequisites": ["2.2.1"],
         "difficulty": 0.5, "exam_frequency": 0.82, "cognitive_level": "理解", "importance": "高"},
        {"kp_code": "2.5.2", "kp_name": "数列求和", "prerequisites": ["2.5.1"],
         "difficulty": 0.65, "exam_frequency": 0.75, "cognitive_level": "应用", "importance": "高"},
        {"kp_code": "2.5.3", "kp_name": "数学归纳法", "prerequisites": ["2.5.1"],
         "difficulty": 0.7, "exam_frequency": 0.35, "cognitive_level": "综合", "importance": "中"},
        {"kp_code": "2.6", "kp_name": "不等式", "prerequisites": ["2.2.1"],
         "difficulty": 0.45, "exam_frequency": 0.60, "cognitive_level": "理解", "importance": "高"},
        {"kp_code": "2.6.1", "kp_name": "基本不等式", "prerequisites": ["2.6"],
         "difficulty": 0.5, "exam_frequency": 0.55, "cognitive_level": "应用", "importance": "中"},
        {"kp_code": "2.6.2", "kp_name": "线性规划", "prerequisites": ["2.6"],
         "difficulty": 0.5, "exam_frequency": 0.45, "cognitive_level": "应用", "importance": "中"},

        # ─── 几何 ───
        {"kp_code": "2.7.1", "kp_name": "空间几何体", "prerequisites": ["2.1"],
         "difficulty": 0.45, "exam_frequency": 0.60, "cognitive_level": "理解", "importance": "中"},
        {"kp_code": "2.7.2", "kp_name": "点线面位置关系", "prerequisites": ["2.7.1"],
         "difficulty": 0.55, "exam_frequency": 0.65, "cognitive_level": "理解", "importance": "高"},
        {"kp_code": "2.7.3", "kp_name": "空间向量与立体几何", "prerequisites": ["2.7.2"],
         "difficulty": 0.65, "exam_frequency": 0.85, "cognitive_level": "综合", "importance": "高"},
        {"kp_code": "2.8.1", "kp_name": "直线与圆", "prerequisites": ["2.1"],
         "difficulty": 0.45, "exam_frequency": 0.55, "cognitive_level": "理解", "importance": "中"},
        {"kp_code": "2.8.2", "kp_name": "圆锥曲线", "prerequisites": ["2.8.1"],
         "difficulty": 0.75, "exam_frequency": 0.80, "cognitive_level": "综合", "importance": "高"},

        # ─── 概率与统计 ───
        {"kp_code": "2.9.1", "kp_name": "随机事件与概率", "prerequisites": ["2.1"],
         "difficulty": 0.4, "exam_frequency": 0.50, "cognitive_level": "理解", "importance": "中"},
        {"kp_code": "2.9.2", "kp_name": "统计与统计案例", "prerequisites": ["2.9.1"],
         "difficulty": 0.45, "exam_frequency": 0.55, "cognitive_level": "理解", "importance": "中"},
        {"kp_code": "2.9.3", "kp_name": "二项式定理", "prerequisites": ["2.9.1"],
         "difficulty": 0.5, "exam_frequency": 0.45, "cognitive_level": "应用", "importance": "中"},
        {"kp_code": "2.9.4", "kp_name": "随机变量及其分布", "prerequisites": ["2.9.1"],
         "difficulty": 0.6, "exam_frequency": 0.68, "cognitive_level": "应用", "importance": "高"},

        # ─── 复数与向量 ───
        {"kp_code": "2.10.1", "kp_name": "平面向量", "prerequisites": ["2.1"],
         "difficulty": 0.4, "exam_frequency": 0.60, "cognitive_level": "理解", "importance": "高"},
        {"kp_code": "2.10.2", "kp_name": "复数", "prerequisites": ["2.1"],
         "difficulty": 0.3, "exam_frequency": 0.45, "cognitive_level": "基础", "importance": "中"},
    ]
}

async def seed_knowledge_graph(db):
    """注入知识图谱种子数据"""
    count = 0
    for subject_id, kps in KNOWLEDGE_GRAPH_SEED.items():
        for kp in kps:
            prerequisites_json = json.dumps(kp["prerequisites"])
            await db.execute(
                """INSERT OR REPLACE INTO knowledge_graph
                   (kp_code, kp_name, subject_id, prerequisites, difficulty,
                    exam_frequency, cognitive_level, importance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (kp["kp_code"], kp["kp_name"], subject_id, prerequisites_json,
                 kp["difficulty"], kp["exam_frequency"],
                 kp["cognitive_level"], kp["importance"])
            )
            count += 1
    await db.commit()
    print(f"Seeded {count} knowledge graph nodes")
    return count


async def seed_achievements(db):
    """注入默认成就定义"""
    achievements = [
        ("first_login", "初次启程", "首次登录系统", "🌟"),
        ("first_diagnosis", "认识自己", "完成第一次学习诊断", "🎯"),
        ("streak_3", "三天打鱼", "连续学习3天", "🔥"),
        ("streak_7", "一周坚持", "连续学习7天", "🔥🔥"),
        ("streak_30", "月冠军", "连续学习30天", "🏆"),
        ("weakness_mastered_3", "攻克难关", "攻克3个薄弱知识点", "💪"),
        ("weakness_mastered_10", "学有所成", "攻克10个薄弱知识点", "🎓"),
        ("questions_100", "百题斩", "完成100道练习题", "⚔️"),
        ("questions_1000", "千题达人", "完成1000道练习题", "👑"),
        ("assessment_pass", "初试锋芒", "首次通过阶段测评", "📝"),
    ]
    count = 0
    for code, name, desc, icon in achievements:
        await db.execute(
            """INSERT OR IGNORE INTO user_achievements
               (user_id, achievement_code, achievement_name, description, icon_url)
               VALUES (0, ?, ?, ?, ?)""",
            (code, name, desc, icon)
        )
        count += 1
    await db.commit()
    print(f"Seeded {count} achievement templates")
    return count


if __name__ == "__main__":
    import asyncio
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    async def main():
        from models import init_db, get_db
        await init_db()
        db_gen = get_db()
        db = await db_gen.__anext__()
        try:
            await seed_knowledge_graph(db)
            await seed_achievements(db)
        finally:
            await db.close()

    asyncio.run(main())
