# -*- coding: utf-8 -*-
"""给 classify_broad.py 加「机构号排除」：只保留个人自媒体。

三级判定：
  HARD   —— 明确官方媒体/政府机构，直接排除
  SOFT   —— 疑似机构（研究院/大学/公司/商城/官方…），排除但单独列出供复核
  PERSONAL —— 其余保留
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "classify_broad.py"
t = f.read_text(encoding="utf-8")

INST = '''
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
    "协会", "基金会", "工作室", "团队", "科技有限", "企业",
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
'''

# 插入到 OFFTOPIC 之后
anchor = 'OFFTOPIC = ['
i = t.index(anchor)
j = t.index(']', t.index('"鬼畜"')) + 1
t = t[:j] + "\n" + INST + t[j:]

# 在主循环里加机构判定
t = t.replace('''        alltext = " ".join(c["kws"]) + " " + " ".join(c["titles"])
        # 明显跑偏的垂类直接跳过
        if any(w in alltext for w in OFFTOPIC):
            continue''',
'''        alltext = " ".join(c["kws"]) + " " + " ".join(c["titles"])
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
            continue''')

# 声明 institutional 列表
t = t.replace("    assigned = []\n    used = set()",
              "    assigned = []\n    institutional = []\n    used = set()")

# 输出机构号清单
t = t.replace('''    out = CONF / "final_roster_new.tsv"''',
'''    inst_out = CONF / "excluded_institutional.tsv"
    with inst_out.open("w", encoding="utf-8") as f:
        f.write("mid\\t名称\\t粉丝\\t类型\\t命中词\\t样例标题\\n")
        for c in sorted(institutional, key=lambda x: -x["fans"]):
            f.write(f'{c["mid"]}\\t{c["name"]}\\t{c["fans"]}\\t{c["reason"]}\\t'
                    f'{",".join(c["kws"][:3])}\\t{" / ".join(c["titles"][:1])}\\n')
    print(f"\\n排除机构号 {len(institutional)} 个 → {inst_out}")

    out = CONF / "final_roster_new.tsv"''')

f.write_text(t, encoding="utf-8")
print("已加入机构号排除（HARD 硬排除 / SOFT 软排除+个人特征豁免）")
