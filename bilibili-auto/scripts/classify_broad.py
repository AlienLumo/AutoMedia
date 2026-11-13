# -*- coding: utf-8 -*-
"""classify_broad.py — 按新口径分类 B站候选（离线，靠已抓到的视频标题）。

数据源：candidates_video.tsv（含 粉丝 / 命中词 / 视频标题）
输出：final_roster_new.tsv（mid 名称 粉丝 前缀 层级 依据）

新口径：
  商业 / 局势 / 炒股投资：只看主题相关，**不要求 AI**
  科技：主题相关，但**排除数码评测**（手机/电脑/开箱/测评）
  数码评测：按粉丝取 **Top 5**
  创客（科技创客）：≥10万粉全收；1万-10万粉**限 100 个**
  科普：并入科技
"""
import argparse
from pathlib import Path
from _paths import SKILL

CONF = SKILL / "config"

# 各主题的判定词（出现在 命中词 或 视频标题 里即算相关）
RULES = {
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

# ===== 机构号识别（只保留个人自媒体）=====
# 1) 硬排除：官方媒体、政府、大型机构
HARD_INST = [
    "央视", "中央电视", "CCTV", "CNTV", "人民日报", "人民网", "新华社", "新华网",
    "共青团", "观察者网", "环球时报", "澎湃", "界面新闻", "财新", "第一财经",
    "中国网", "中国日报", "光明网", "经济日报", "参考消息", "环球网",
    "政府", "国务院", "外交部", "国防部", "卫健委", "教育部", "央行", "证监会",
    "卫视", "广电", "广播电台", "电视台", "日报", "晚报", "晨报", "新闻网",
    "全国妇联", "科协", "红十字会",
]

# 2) 软排除：疑似机构/团队/公司（排除，但单独输出供人工复核）
SOFT_INST = [
    "研究院", "研究所", "实验室", "大学", "学院", "中学", "小学",
    "集团", "公司", "商城", "官方", "频道", "传媒", "文化传播",
    "协会", "基金会", "科技有限", "科技公司",
    "爱奇艺", "腾讯", "优酷", "芒果", "哔哩哔哩", "B站官方",
    "出版社", "杂志", "周刊", "报社",
]

# 3) 个人特征词（命中则优先判为个人，抵消软排除）
PERSONAL_HINT = [
    "老师", "老", "哥", "姐", "叔", "阿姨", "同学", "老师好", "小明",
    "阿", "小", "Mr", "先生", "博士", "教授", "up主", "UP主",
]


def classify_owner(name):
    """返回 'hard' / 'soft' / 'personal'。"""
    n = name or ""
    if any(w in n for w in HARD_INST):
        return "hard"
    soft = any(w in n for w in SOFT_INST)
    if soft:
        # 同时有强个人特征 → 判个人（如「程校长」）
        if any(w in n for w in PERSONAL_HINT):
            return "personal"
        return "soft"
    return "personal"


DIGITAL = ["数码评测", "手机评测", "电脑评测", "开箱评测",
           "数码", "手机", "电脑", "笔记本", "装机", "显卡", "耳机", "相机"]


def load_video_candidates():
    p = CONF / "candidates_video.tsv"
    rows = []
    lines = p.read_text(encoding="utf-8").splitlines()
    for ln in lines[1:]:
        if not ln.strip():
            continue
        c = ln.split("\t")
        if len(c) < 6:
            continue
        try:
            mid = int(c[0]); fans = int(c[2])
        except ValueError:
            continue
        rows.append({"mid": mid, "name": c[1], "fans": fans,
                     "kws": [k for k in c[3].split(",") if k],
                     "titles": [t for t in c[4].split(" | ") if t],
                     "in_roster": c[5] == "是"})
    return rows


def load_roster():
    mids = set()
    for line in (CONF / "ups.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        try:
            mids.add(int(line.split("\t")[0]))
        except ValueError:
            pass
    return mids


def score(cand, rule):
    """标题命中权重 2，关键词命中权重 1；返回 (加权分, 标题命中数)。"""
    ktext = " ".join(cand["kws"])
    ttext = " ".join(cand["titles"])
    t_hits = sum(1 for w in rule["include"] if w in ttext)
    k_hits = sum(1 for w in rule["include"] if w in ktext)
    exc = sum(1 for w in rule["exclude"] if w in (ttext + " " + ktext))
    return t_hits * 2 + k_hits, t_hits, exc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
    ap.add_argument("--maker-low-fans", type=int, default=10000, dest="maker_low")
    ap.add_argument("--maker-low-cap", type=int, default=100, dest="maker_cap")
    ap.add_argument("--digital-cap", type=int, default=5, dest="digital_cap")
    a = ap.parse_args()

    cands = load_video_candidates()
    roster = load_roster()
    print(f"视频搜索候选: {len(cands)} 个（其中已在名单 {sum(1 for c in cands if c['in_roster'])} 个）")

    assigned = []
    institutional = []
    used = set()

    # 1) 数码评测：单独判定，先占位（后面只取 TopN）
    digital = []
    for c in cands:
        if c["in_roster"]:
            continue
        text = " ".join(c["kws"]) + " " + " ".join(c["titles"])
        if any(w in text for w in DIGITAL):
            # 同时要求是评测类词
            if any(w in " ".join(c["kws"]) for w in ["数码评测", "手机评测", "电脑评测", "开箱评测"]):
                digital.append(c)
    digital.sort(key=lambda x: -x["fans"])
    for c in digital[:a.digital_cap]:
        c["prefix"] = "数码评测"
        c["tier"] = "A"
        c["reason"] = "数码评测 Top5"
        assigned.append(c)
        used.add(c["mid"])

    # 2) 其他主题
    for c in cands:
        if c["in_roster"] or c["mid"] in used:
            continue
        alltext = " ".join(c["kws"]) + " " + " ".join(c["titles"])
        # 明显跑偏的垂类直接跳过
        if any(w in alltext for w in OFFTOPIC):
            continue
        # 机构号排除（只保留个人自媒体）
        owner = classify_owner(c["name"])
        if owner in ("hard", "soft"):
            c["prefix"] = "机构号"
            c["reason"] = "hard" if owner == "hard" else "soft"
            institutional.append(c)
            used.add(c["mid"])
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
                best = (prefix, inc)
        if not best:
            continue
        c["prefix"] = best[0]
        is_off = any(w in c["name"] for w in OFFICIAL)
        c["reason"] = f"主题分{best[1]}" + ("｜官方/机构号" if is_off else "")
        if c["fans"] >= a.min_fans:
            c["tier"] = "A"
            assigned.append(c)
            used.add(c["mid"])
        elif c["prefix"] == "创客" and c["fans"] >= a.maker_low:
            c["tier"] = "B"   # 小号创客，后面限量
            assigned.append(c)
            used.add(c["mid"])

    # 3) 创客 B 层限量 100
    b_makers = sorted([c for c in assigned if c.get("tier") == "B"], key=lambda x: -x["fans"])
    for c in b_makers[a.maker_cap:]:
        assigned.remove(c)

    inst_out = CONF / "excluded_institutional.tsv"
    with inst_out.open("w", encoding="utf-8") as f:
        f.write("mid\t名称\t粉丝\t类型\t命中词\t样例标题\n")
        for c in sorted(institutional, key=lambda x: -x["fans"]):
            f.write(f'{c["mid"]}\t{c["name"]}\t{c["fans"]}\t{c["reason"]}\t'
                    f'{",".join(c["kws"][:3])}\t{" / ".join(c["titles"][:1])}\n')
    print(f"\n排除机构号 {len(institutional)} 个 → {inst_out}")

    out = CONF / "final_roster_new.tsv"
    assigned.sort(key=lambda x: (x["prefix"], -x["fans"]))
    with out.open("w", encoding="utf-8") as f:
        f.write("mid\t名称\t粉丝\t前缀\t层级\t依据\t命中词\t样例标题\n")
        for c in assigned:
            f.write(f'{c["mid"]}\t{c["name"]}\t{c["fans"]}\t{c["prefix"]}\t'
                    f'{c["tier"]}\t{c["reason"]}\t{",".join(c["kws"][:4])}\t'
                    f'{" / ".join(c["titles"][:1])}\n')

    from collections import Counter
    cnt = Counter(c["prefix"] for c in assigned)
    tier = Counter(c["tier"] for c in assigned)
    print(f"\n新入选 {len(assigned)} 个（A层 {tier['A']} / B层 {tier['B']}）")
    print("按前缀:")
    for k, v in cnt.most_common():
        print(f"  {k:<8} {v}")
    print(f"\n输出: {out}")
    print("\n各主题 Top 5：")
    for p in cnt:
        print(f"  [{p}]")
        for c in [x for x in assigned if x["prefix"] == p][:5]:
            print(f'    {c["fans"]/1e4:>8.1f}万  {c["name"][:20]:<22} ({c["tier"]})')


if __name__ == "__main__":
    main()
