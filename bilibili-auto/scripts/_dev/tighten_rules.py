# -*- coding: utf-8 -*-
"""收紧分类规则：必须「标题命中」才算，且区分官方媒体/个人创作者。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "classify_broad.py"
t = f.read_text(encoding="utf-8")

NEW_RULES = '''RULES = {
    "商业": {
        # 强信号（必须命中之一）
        "include": ["创业", "生意", "商业模式", "商业分析", "赚钱", "副业",
                    "开店", "加盟", "营收", "利润", "公司分析", "企业经营",
                    "营销", "品牌", "私域", "获客", "变现", "财报", "估值",
                    "并购", "上市", "产业链", "供应链", "制造业", "出海",
                    "跨境", "一人公司", "知识付费", "个人IP", "经济",
                    "GDP", "通胀", "利率", "美联储", "央行", "汇率",
                    "房价", "楼市", "人口", "消费", "外贸", "关税", "财经"],
        "exclude": ["美食", "探店", "吃", "搞笑", "段子", "游戏", "舞蹈", "翻唱"],
    },
    "局势": {
        "include": ["局势", "地缘", "国际关系", "中美", "俄乌", "中东", "巴以",
                    "台海", "南海", "朝鲜", "军事", "武器", "国防", "战争",
                    "时政", "时事", "外交", "联合国", "北约", "欧盟", "金砖",
                    "一带一路", "大国博弈", "世界格局", "历史"],
        "exclude": ["游戏", "综艺", "吃", "美食"],
    },
    "炒股投资": {
        "include": ["炒股", "股票", "股市", "A股", "港股", "美股", "基金",
                    "投资", "理财", "债券", "期权", "期货", "黄金", "原油",
                    "外汇", "价值投资", "量化", "选股", "财报", "估值"],
        "exclude": ["游戏", "美食"],
    },
    "科技": {
        "include": ["前沿科技", "科技趋势", "未来科技", "芯片", "半导体",
                    "量子", "核聚变", "光刻", "脑机", "基因编辑", "合成生物",
                    "新材料", "储能", "光伏", "氢能", "固态电池", "航天",
                    "SpaceX", "星舰", "卫星", "算力", "数据中心", "大模型",
                    "自动驾驶", "新能源", "机器人", "硬核科技", "技术解析"],
        "exclude": ["手机", "电脑", "笔记本", "开箱", "评测", "测评", "装机",
                    "显卡", "耳机", "相机", "iPhone", "数码", "美食", "游戏"],
    },
    "创客": {
        "include": ["创客", "自制", "DIY", "开源硬件", "单片机", "树莓派",
                    "Arduino", "ESP32", "电路", "PCB", "机械臂", "机器狗",
                    "嵌入式", "3D打印", "电子制作", "极客", "硬件开发"],
        "exclude": ["手工", "纸箱", "黏土", "折纸", "美食"],
    },
    "科普": {
        "include": ["硬核科普", "科普", "原理", "科学知识", "科学实验"],
        "exclude": ["美食", "游戏"],
    },
}

# 官方媒体/机构号（单独标记，供人工决定是否收录）
OFFICIAL = ["央视", "新闻", "人民日报", "新华社", "共青团", "观察者网",
            "环球时报", "澎湃", "界面", "财新", "第一财经", "政府", "研究院",
            "大学", "学院", "研究所", "官方", "TV", "卫视", "广电", "出版"]

# 明显的非目标垂类（美食/搞笑/游戏等，标题命中也要排除）
OFFTOPIC = ["美食", "探店", "吃播", "搞笑", "段子", "游戏实况", "王者荣耀",
            "原神", "和平精英", "舞蹈", "翻唱", "cos", "vtuber", "鬼畜"]
'''

# 替换整个 RULES 定义块
start = t.index("RULES = {")
end = t.index("DIGITAL = [")
t = t[:start] + NEW_RULES + "\n" + t[end:]

# 修改 score：标题命中权重更高
t = t.replace('''def score(cand, rule):
    text = " ".join(cand["kws"]) + " " + " ".join(cand["titles"])
    inc = sum(1 for w in rule["include"] if w in text)
    exc = sum(1 for w in rule["exclude"] if w in text)
    return inc, exc''',
'''def score(cand, rule):
    """标题命中权重 2，关键词命中权重 1；返回 (加权分, 标题命中数)。"""
    ktext = " ".join(cand["kws"])
    ttext = " ".join(cand["titles"])
    t_hits = sum(1 for w in rule["include"] if w in ttext)
    k_hits = sum(1 for w in rule["include"] if w in ktext)
    exc = sum(1 for w in rule["exclude"] if w in (ttext + " " + ktext))
    return t_hits * 2 + k_hits, t_hits, exc''')

# 判定：要求标题至少命中 1 个，且排除项不多于标题命中
t = t.replace('''        best = None
        for prefix, rule in RULES.items():
            inc, exc = score(c, rule)
            if inc == 0 or exc > inc:
                continue
            # 创客要求有硬件/自制类强信号
            if prefix == "创客" and inc < 2:
                continue
            # 科技排除数码评测
            if prefix == "科技" and any(w in " ".join(c["titles"]) for w in
                                        ["手机", "开箱", "评测", "测评", "装机"]):
                continue
            if best is None or inc > best[1]:
                best = (prefix, inc)''',
'''        alltext = " ".join(c["kws"]) + " " + " ".join(c["titles"])
        # 明显跑偏的垂类直接跳过
        if any(w in alltext for w in OFFTOPIC):
            continue
        best = None
        for prefix, rule in RULES.items():
            inc, t_hits, exc = score(c, rule)
            # 必须标题命中 ≥1（更严），且排除项不能超过标题命中
            if t_hits < 1 or inc < 2 or exc > t_hits:
                continue
            if prefix == "创客" and t_hits < 1:
                continue
            if prefix == "科技" and any(w in " ".join(c["titles"]) for w in
                                        ["手机", "开箱", "评测", "测评", "装机", "数码"]):
                continue
            if best is None or inc > best[1]:
                best = (prefix, inc)''')

# 标记官方媒体
t = t.replace('''        c["prefix"] = best[0]
        c["reason"] = f"命中 {best[1]} 个主题词"''',
'''        c["prefix"] = best[0]
        is_off = any(w in c["name"] for w in OFFICIAL)
        c["reason"] = f"主题分{best[1]}" + ("｜官方/机构号" if is_off else "")''')

t = t.replace('''        f.write("mid\\t名称\\t粉丝\\t前缀\\t层级\\t依据\\t命中词\\t样例标题\\n")''',
'''        f.write("mid\\t名称\\t粉丝\\t前缀\\t层级\\t依据\\t命中词\\t样例标题\\n")''')

f.write_text(t, encoding="utf-8")
print("分类规则已收紧（标题命中权重 2、要求标题≥1、排除跑偏垂类、标记官方号）")
