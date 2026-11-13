# -*- coding: utf-8 -*-
"""按内容核验结果收敛名单：仅保留 垂直/半相关，回滚 253 个无关号。"""
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
CONF = SKILL / "config"
ROSTER = CONF / "ups.tsv"
BAK = CONF / "ups.tsv.bak"
FANS = CONF / "fans.json"
PMAP = CONF / "prefix_map.tsv"
CLASSIFIED = CONF / "candidates_classified.tsv"
REPORT = PROJ / "1AMdata" / "_candidates_report.md"

RULES = [
    (r"炒股|股市|A股|基金|理财|投资|财报|资本|财经|利率|楼市|房价", "炒股投资"),
    (r"黑客|安全|渗透|攻防|漏洞|逆向", "黑客"),
    (r"机器人|具身|机械臂|人形|无人机|自动驾驶", "机器人行业"),
    (r"创客|DIY|开发板|树莓派|单片机|硬件|3D打印", "创客"),
    (r"局势|时政|国际|地缘|中美|俄乌|中东|大国|博弈|政经", "局势"),
    (r"创业|商业|生意|赚钱|公司|品牌|营销|副业|变现|一人公司", "商业"),
    (r"课程|训练营|学院|教育|培训|就业|面试|考研|课堂|私塾|教学|教程", "教程"),
]


def guess_prefix(name, sign=""):
    text = f"{name} {sign}"
    for pat, pref in RULES:
        if re.search(pat, text):
            return pref
    return "ai"


def fmt_fans(n):
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


def main():
    # 1) 恢复原始 87
    if BAK.exists():
        shutil.copy2(BAK, ROSTER)
    base = []
    for line in ROSTER.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c = line.split("\t")
        try:
            base.append((int(c[0]), c[1] if len(c) > 1 else "", c[2] if len(c) > 2 else "使用"))
        except ValueError:
            pass
    print(f"基础名单: {len(base)}")

    # 2) 取核验通过的
    keep = []
    for line in CLASSIFIED.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 6:
            continue
        if c[3] not in ("垂直", "半相关"):
            continue
        try:
            keep.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                         "tier": c[3], "ratio": c[4],
                         "sample": c[7] if len(c) > 7 else ""})
        except ValueError:
            continue
    print(f"核验通过: {len(keep)}（垂直 {sum(1 for k in keep if k['tier']=='垂直')}）")

    fans_map = json.loads(FANS.read_text(encoding="utf-8")) if FANS.exists() else {}
    all_mids = [m for m, _, _ in base]
    added = []
    for k in keep:
        if k["mid"] in all_mids:
            continue
        all_mids.append(k["mid"])
        base.append((k["mid"], k["name"], "发展" if k["tier"] == "半相关" else "AI垂直"))
        fans_map[str(k["mid"])] = {"name": k["name"], "fans": k["fans"], "sign": ""}
        added.append(k)

    with ROSTER.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t方向\n")
        for mid, nm, topic in base:
            f.write(f"{mid}\t{nm}\t{topic}\n")
    FANS.write_text(json.dumps(fans_map, ensure_ascii=False), encoding="utf-8")

    # 3) 重建 prefix_map
    rows = []
    for mid, nm, topic in base:
        fm = fans_map.get(str(mid)) or {}
        pref = guess_prefix(nm, fm.get("sign", ""))
        rows.append((mid, nm, pref, fm.get("fans") or 0))
    rows.sort(key=lambda r: -r[3])
    with PMAP.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t前缀\t粉丝数\n")
        for mid, nm, pref, fans in rows:
            f.write(f"{mid}\t{nm}\t{pref}\t{fans}\n")

    # 4) 报告
    pref = Counter(r[2] for r in rows)
    lines = [
        "# B站 AI 相关 UP 主扩搜与核验报告\n",
        "- 时间：2026-11-01",
        "## 过程\n",
        "1. 42 个主题关键词 × 视频播放榜 → 587 个作者",
        "2. 逐个核粉 → **332 个 ≥10 万粉**，其中 276 个不在原名单",
        "3. 对 276 个抽样最近 15 条投稿标题，按 AI 相关占比分级",
        "",
        "## 核验结果（关键）\n",
        "| 等级 | 判据 | 数量 |",
        "|---|---|---|",
        "| 垂直 | AI 视频 ≥40% | **9** |",
        "| 半相关 | 15–40% | **14** |",
        "| 无关 | <15% | **253** |",
        "",
        "**结论：视频搜索扩出来的 276 个里，只有 23 个真正沾 AI，253 个是「某条视频蹭了 AI 关键词」的无关大号**",
        "（老番茄、何同学、戴建业老师、毕导等均属此类）。因此名单只保留核验通过的 23 个。",
        "",
        f"## 最终名单：**{len(base)} 个**\n",
        "| 前缀 | 数量 |",
        "|---|---|",
    ]
    for p, n in pref.most_common():
        lines.append(f"| {p} | {n} |")
    lines += ["", "## 新增（核验通过）\n", "| 粉丝 | 名称 | 等级 | AI视频占比 |", "|---|---|---|---|"]
    for k in sorted(added, key=lambda x: -x["fans"]):
        lines.append(f'| {fmt_fans(k["fans"])} | {k["name"]} | {k["tier"]} | {float(k["ratio"])*100:.0f}% |')
    lines += ["", "## 目录格式\n",
              "`1AMdata/bilibili/<前缀>_<UP主>_<粉丝量>/<bvid>_<标题>/`",
              "前缀：ai / 商业 / 教程 / 炒股投资 / 局势 / 机器人行业 / 创客 / 黑客"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"最终名单 {len(base)} 个，前缀分布 {dict(pref)}")
    print(f"新增核验通过 {len(added)} 个：")
    for k in sorted(added, key=lambda x: -x["fans"]):
        print(f'  {fmt_fans(k["fans"]):>9} {k["tier"]:<4} {k["name"]}')
    print(f"报告: {REPORT}")


if __name__ == "__main__":
    main()
