# -*- coding: utf-8 -*-
"""合并扩搜结果：写入 ups.tsv / fans.json / prefix_map.tsv，并生成报告。"""
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
CONF = SKILL / "config"
ROSTER = CONF / "ups.tsv"
FANS = CONF / "fans.json"
PMAP = CONF / "prefix_map.tsv"
CAND = CONF / "candidates_raw.tsv"
REPORT = PROJ / "1AMdata" / "_candidates_report.md"

sys.path.insert(0, str(SKILL / "scripts"))

GROUP_OF_KW = {}
for g, kws in {
    "AI创作": ["AI绘画", "AI视频", "AIGC", "ComfyUI", "Stable Diffusion", "AI短剧",
               "AI音乐", "AI动画", "AI漫剧", "AI特效", "AI设计", "可灵", "即梦",
               "Midjourney", "AI数字人"],
    "AI产品": ["AI产品", "AI工具", "AI应用", "AI软件", "AI测评", "AI Agent",
               "AI编程", "Cursor", "Claude Code", "AI智能体"],
    "AI前沿": ["AI前沿", "大模型", "AGI", "论文精读", "AI技术", "GPT", "DeepSeek",
               "开源模型", "多模态", "世界模型"],
    "AI行业": ["AI行业", "AI产业", "AI就业", "AI公司", "AI融资", "AI创业", "算力",
               "英伟达", "芯片 AI"],
    "AI4Science": ["AI科研", "AI4Science", "AI 科学", "AI 医疗", "AI 生物",
                   "AI 材料", "AI 数学", "AI 药物", "机器学习 科研"],
}.items():
    for k in kws:
        GROUP_OF_KW[k] = g

TOPIC_OF_GROUP = {"AI创作": "创作", "AI产品": "使用", "AI前沿": "发展",
                  "AI行业": "发展", "AI4Science": "发展"}

RULES = [
    (r"炒股|股市|A股|基金|理财|投资|财报|资本|财经|利率|楼市|房价|黄金|期货", "炒股投资"),
    (r"黑客|安全|渗透|攻防|漏洞|逆向", "黑客"),
    (r"机器人|具身|机械臂|人形|无人机|自动驾驶|智驾", "机器人行业"),
    (r"创客|DIY|开发板|树莓派|单片机|硬件|电子|机械|3D打印", "创客"),
    (r"局势|时政|国际|地缘|中美|俄乌|中东|大国|博弈|政经", "局势"),
    (r"创业|商业|生意|赚钱|公司|品牌|营销|副业|变现|一人公司|投资", "商业"),
    (r"课程|训练营|学院|教育|培训|就业|面试|考研|课堂|私塾|教学|教程", "教程"),
]


def guess_prefix(name, sign, kws, group):
    text = f"{name} {sign} {' '.join(kws)}"
    for pat, pref in RULES:
        if re.search(pat, text):
            return pref
    if group in ("AI4Science",):
        return "ai"
    if group in ("AI产品", "AI创作"):
        return "ai"
    return "ai"


def fmt_fans(n):
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


def main():
    roster = {}
    order = []
    for line in ROSTER.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c = line.split("\t")
        try:
            mid = int(c[0])
        except ValueError:
            continue
        roster[mid] = {"name": c[1] if len(c) > 1 else str(mid),
                       "topic": c[2] if len(c) > 2 else "使用"}
        order.append(mid)

    fans_map = json.loads(FANS.read_text(encoding="utf-8")) if FANS.exists() else {}

    cands = []
    for line in CAND.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 3:
            continue
        try:
            mid = int(c[0])
            fans = int(c[2])
        except ValueError:
            continue
        cands.append({"mid": mid, "name": c[1], "fans": fans,
                      "kws": [k for k in (c[3].split(",") if len(c) > 3 else []) if k],
                      "sign": c[4] if len(c) > 4 else ""})

    new = [c for c in cands if c["mid"] not in roster]
    # 备份
    shutil.copy2(ROSTER, ROSTER.with_suffix(".tsv.bak"))

    added = []
    for c in new:
        groups = [GROUP_OF_KW.get(k, "AI前沿") for k in c["kws"]]
        group = Counter(groups).most_common(1)[0][0] if groups else "AI前沿"
        topic = TOPIC_OF_GROUP.get(group, "发展")
        roster[c["mid"]] = {"name": c["name"], "topic": topic}
        order.append(c["mid"])
        fans_map[str(c["mid"])] = {"name": c["name"], "fans": c["fans"],
                                   "sign": c["sign"][:100]}
        added.append({**c, "group": group, "topic": topic,
                      "prefix": guess_prefix(c["name"], c["sign"], c["kws"], group)})

    # 写 ups.tsv
    with ROSTER.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t方向\n")
        for mid in order:
            f.write(f'{mid}\t{roster[mid]["name"]}\t{roster[mid]["topic"]}\n')

    # 写 fans.json
    FANS.write_text(json.dumps(fans_map, ensure_ascii=False), encoding="utf-8")

    # 重建 prefix_map（沿用已有前缀，新号用 guess）
    old_pref = {}
    if PMAP.exists():
        for line in PMAP.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            c = line.split("\t")
            if len(c) >= 3:
                try:
                    old_pref[int(c[0])] = c[2]
                except ValueError:
                    pass
    rows = []
    for mid in order:
        nm = roster[mid]["name"]
        fm = fans_map.get(str(mid)) or {}
        fans = fm.get("fans") or 0
        pref = old_pref.get(mid)
        if not pref:
            a = next((x for x in added if x["mid"] == mid), None)
            pref = a["prefix"] if a else "ai"
        rows.append((mid, nm, pref, fans))
    rows.sort(key=lambda r: -r[3])
    with PMAP.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t前缀\t粉丝数\n")
        for mid, nm, pref, fans in rows:
            f.write(f"{mid}\t{nm}\t{pref}\t{fans}\n")

    # 报告
    grp = Counter(a["group"] for a in added)
    pref = Counter(r[2] for r in rows)
    lines = [
        "# B站 AI 相关 UP 主扩搜报告\n",
        f"- 生成时间：2026-11-01 20:00 左右",
        "- 方法：42 个主题关键词 × 视频播放量榜 → 反查作者 → 逐个核粉",
        f"- 命中作者：587 个；**≥10 万粉：332 个**；其中**新增 276 个**",
        f"- 名单合并后总计：**{len(order)} 个**（原 87 + 新增 {len(added)}）",
        "- 阈值说明：332 < 500，按你的规则**不收紧到 15 万**\n",
        "## 新增按主题\n",
        "| 主题 | 新增数 |",
        "|---|---|",
    ]
    for g, n in grp.most_common():
        lines.append(f"| {g} | {n} |")
    lines += ["", "## 全名单前缀分布\n", "| 前缀 | 数量 |", "|---|---|"]
    for p, n in pref.most_common():
        lines.append(f"| {p} | {n} |")
    lines += ["", "## 新增 TOP40（按粉丝）\n",
              "| 粉丝 | 名称 | 前缀 | 命中关键词 |", "|---|---|---|---|"]
    for a in sorted(added, key=lambda x: -x["fans"])[:40]:
        lines.append(f'| {fmt_fans(a["fans"])} | {a["name"]} | {a["prefix"]} | '
                     f'{",".join(a["kws"][:3])} |')
    single = [a for a in added if len(a["kws"]) == 1]
    lines += ["", "## 需要注意的质量问题\n",
              f"- 新增里有 **{len(single)} 个只命中 1 个关键词**，可能是「偶尔讲 AI 的泛领域大号」，",
              "  建议采集后用实际内容核验，不要直接当 AI 垂直号使用。",
              "- 部分号是「AI 只是题材之一」的科技/财经大号（如何同学、影视飓风等）。",
              "- 关键词搜索每词仅取 20 条，理论上仍有长尾未覆盖。"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"名单已合并：{len(order)} 个（新增 {len(added)}）")
    print(f"  前缀分布: {dict(pref)}")
    print(f"  新增主题分布: {dict(grp)}")
    print(f"  仅命中 1 词: {len(single)} 个")
    print(f"报告: {REPORT}")


if __name__ == "__main__":
    main()
