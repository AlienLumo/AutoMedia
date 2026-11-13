# -*- coding: utf-8 -*-
"""生成 prefix_map.tsv：为每个 UP 主分配「最强关联主题前缀」+ 粉丝量。

前缀候选：ai / 商业 / 教程 / 炒股投资 / 局势 / 机器人行业 / 创客 / 黑客
输出：config/prefix_map.tsv   mid <tab> 名称 <tab> 前缀 <tab> 粉丝数
"""
import json
import re
import sys
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
ROSTER = SKILL / "config" / "ups.tsv"
FANS = SKILL / "config" / "fans.json"
OUT = SKILL / "config" / "prefix_map.tsv"

# 人工指定（内容方向最突出的一类），优先于规则
OVERRIDE = {
    385670211: "教程",      # 秋芝2046 Codex/Claude Code 教程
    49746395: "教程",       # GenJi 教程
    316183842: "教程",      # 技术爬爬虾
    281120100: "教程",      # 我是阿众
    1815948385: "教程",     # 马克的技术工作坊
    165659472: "教程",      # 技术胖
    37974444: "教程",       # 黑马程序员
    302417610: "教程",      # 尚硅谷
    507961306: "教程",      # IT私塾
    12890453: "教程",       # 程序员鱼皮
    523995133: "教程",      # 林粒粒呀
    590784254: "教程",      # 来真的
    17919458: "教程",       # WorkFisher
    193580090: "教程",      # 御风大世界
    2103633335: "教程",
    14097567: "创客",       # 花叔v：无代码创作者，做 skill/App
    1900783: "机器人行业",   # 同济子豪兄：机器人/具身
    20259914: "机器人行业",  # 稚晖君
    520819684: "商业",      # 小Lin说 财经商业
    434376696: "商业",      # 阿Test
    37950062: "炒股投资",    # 硬核资本论
    596847138: "局势",      # 棱镜Talk
    17239951: "局势",       # 战辉
    8420618: "商业",        # 统一的奸商之路
    3493277944776820: "商业",  # 老达AI创业圈
    1189153030: "商业",     # 王钦文
    385047828: "商业",      # 认知便利店M
    14719402: "商业",       # 半撇老师
    4848323: "商业",        # 数字游牧人
    3619835000: "商业",
    1306: "机器人行业",
    12566101: "ai",         # 秋葉aaaki AI绘画
    1814756990: "ai",       # Nenly AI绘画
    3562949: "ai",          # 梨子格格 AI绘画
    1208823126: "ai",       # 大圆镜科普
    371846699: "ai",        # 图灵的猫
    4401694: "ai",          # 林亦LYi
    350632501: "ai",        # 在下小苏
    486989780: "ai",        # 老麦的工具库
    598464467: "ai",        # 苏星河牛通
    267939460: "ai",
    67079745: "ai",
    393163404: "ai",
    14739873: "ai",
    517937049: "ai",
    3546652415625413: "ai",
    1619549806: "ai",
    946974: "ai",
    327247876: "ai",
    302188068: "ai",
    382853747: "ai",
    668097429: "ai",
    16433002: "ai",
    503558013: "ai",
    2475977: "ai",
    3493277319825652: "ai",
    474921808: "ai",
    14848367: "ai",
    38061207: "ai",
    3546572358945017: "ai",
    65564239: "ai",
    325864133: "ai",
    2066911559: "ai",
    367442833: "ai",
    436400072: "ai",
    3546914725300503: "ai",
    5211573: "ai",
    1383971575: "ai",
    3546588899183349: "ai",
    3546894057868162: "ai",
    28457: "ai",
    496413617: "ai",
    319521269: "教程",
    12590: "ai",
    331507846: "ai",
    1190294984: "教程",
    492456340: "教程",
    317623716: "教程",
    341376543: "教程",
    545194898: "ai",
    3546659109735216: "教程",
    296399504: "局势",
    12566101: "ai",
    90183256: "商业",
    520155988: "商业",
    673779175: "ai",
    627947058: "ai",
    612932327: "机器人行业",
    39613022: "ai",
    515019371: "ai",
    20826656: "ai",
    1567748478: "ai",
    520153000: "ai",
}

RULES = [
    (r"炒股|股市|A股|基金|理财|投资|财报|资本|财经|利率|楼市|房价|黄金|期货", "炒股投资"),
    (r"黑客|安全|渗透|攻防|漏洞|逆向", "黑客"),
    (r"机器人|具身|机械臂|人形|无人机|自动驾驶", "机器人行业"),
    (r"创客|DIY|开发板|树莓派|单片机|硬件|电子|机械", "创客"),
    (r"局势|时政|国际|地缘|中美|俄乌|中东|大国|博弈|政经", "局势"),
    (r"创业|商业|生意|赚钱|公司|品牌|营销|副业|变现|一人公司", "商业"),
    (r"课程|训练营|学院|教育|培训|就业|面试|考研|机构|课堂|私塾|硅谷|黑马|程序员", "教程"),
]


def guess(name, sign, topic):
    text = f"{name} {sign}"
    for pat, pref in RULES:
        if re.search(pat, text):
            return pref
    if topic == "机构":
        return "教程"
    if topic in ("AI垂直",):
        return "ai"
    if topic in ("Skill", "Agent"):
        return "教程"
    if topic == "发展":
        return "商业"
    return "ai"


def main():
    fans_map = {}
    if FANS.exists():
        try:
            fans_map = json.loads(FANS.read_text(encoding="utf-8"))
        except Exception:
            pass

    rows = []
    for line in ROSTER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        c = line.split("\t")
        try:
            mid = int(c[0])
        except ValueError:
            continue
        name = c[1] if len(c) > 1 else str(mid)
        topic = c[2] if len(c) > 2 else ""
        hit = fans_map.get(str(mid)) or {}
        fans = hit.get("fans")
        sign = hit.get("sign", "")
        pref = OVERRIDE.get(mid) or guess(name, sign, topic)
        rows.append((mid, name, pref, fans if fans is not None else 0))

    rows.sort(key=lambda r: -r[3])
    with OUT.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t前缀\t粉丝数\n")
        for mid, name, pref, fans in rows:
            f.write(f"{mid}\t{name}\t{pref}\t{fans}\n")

    from collections import Counter
    print(f"写入 {OUT}  共 {len(rows)} 个")
    print("前缀分布:", dict(Counter(r[2] for r in rows)))
    missing = [r for r in rows if not r[3]]
    if missing:
        print(f"缺粉丝数 {len(missing)} 个:", [m[1] for m in missing])
    print("\n样例：")
    for mid, name, pref, fans in rows[:12]:
        print(f"  {pref}_{name}_{fans/1e4:.1f}万  (mid={mid})")


if __name__ == "__main__":
    main()
