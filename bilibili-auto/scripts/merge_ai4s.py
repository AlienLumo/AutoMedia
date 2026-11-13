# -*- coding: utf-8 -*-
"""从 AI4Science 核验结果里挑出「真做科研/AI科研」的号，加入名单（前缀=科研）。

其余科学科普/学科教学号只记录在报告里，不进主名单——它们不是 AI4Science。
"""
import json
import re
from collections import Counter
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
CONF = SKILL / "config"
ROSTER, FANS, PMAP = CONF / "ups.tsv", CONF / "fans.json", CONF / "prefix_map.tsv"
CLASSIFIED = CONF / "candidates_ai4s_classified.tsv"
REPORT = PROJ / "1AMdata" / "_report_ai4science.md"

# 真正属于「AI/科研」方向的（人工筛）
KEEP_NAMES = [
    "中科院自动化所", "阿里达摩院扫地僧", "科研云", "宇凡聊学术",
    "催化剂加CatalystPlus", "生信曲线", "可疑的癌细胞", "啥都会一点的研究生",
    "环球科学", "硅谷101", "MATLAB中国", "分析学爱好者", "生物化学online",
]

# 明确不是 AI4Science 的（科学科普/教学/媒体），只记录不并入
SCI_POP = re.compile(r"高考|课堂|生物|化学|物理|宇宙|妈咪说|一化儿|环球科学|"
                     r"科普|学科|课程|教学|高中|考研")


def fmt(n):
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


def main():
    known = set()
    base = []
    for line in ROSTER.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c = line.split("\t")
        try:
            mid = int(c[0])
        except ValueError:
            continue
        known.add(mid)
        base.append((mid, c[1] if len(c) > 1 else "", c[2] if len(c) > 2 else ""))
    fans_map = json.loads(FANS.read_text(encoding="utf-8")) if FANS.exists() else {}

    rows = []
    for line in CLASSIFIED.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 6:
            continue
        try:
            rows.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                         "tier": c[3], "score": c[4],
                         "kws": c[6] if len(c) > 6 else ""})
        except ValueError:
            continue

    added = []
    for r in rows:
        if r["name"] not in KEEP_NAMES:
            continue
        if r["mid"] in known:
            continue
        base.append((r["mid"], r["name"], "AI垂直|科研"))
        fans_map[str(r["mid"])] = {"name": r["name"], "fans": r["fans"], "sign": ""}
        added.append(r)

    with ROSTER.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t方向\n")
        for mid, nm, topic in base:
            f.write(f"{mid}\t{nm}\t{topic}\n")
    FANS.write_text(json.dumps(fans_map, ensure_ascii=False), encoding="utf-8")

    # 重建 prefix_map
    prows = []
    for mid, nm, topic in base:
        fm = fans_map.get(str(mid)) or {}
        pref = topic.split("|", 1)[1] if "|" in topic else None
        if not pref:
            pref = "ai"
        p = PMAP.read_text(encoding="utf-8") if PMAP.exists() else ""
        prows.append((mid, nm, pref, fm.get("fans") or 0))
    # 保留原有前缀（除非是本次新增）
    old = {}
    for line in (PMAP.read_text(encoding="utf-8") if PMAP.exists() else "").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c = line.split("\t")
        if len(c) >= 3:
            try:
                old[int(c[0])] = c[2]
            except ValueError:
                pass
    added_mids = {a["mid"] for a in added}
    final = []
    for mid, nm, topic in base:
        fm = fans_map.get(str(mid)) or {}
        if mid in added_mids:
            pref = "科研"
        elif mid in old:
            pref = old[mid]
        elif "|" in topic:
            pref = topic.split("|", 1)[1]
        else:
            pref = "ai"
        final.append((mid, nm, pref, fm.get("fans") or 0))
    final.sort(key=lambda r: -r[3])
    with PMAP.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t前缀\t粉丝数\n")
        for mid, nm, pref, fans in final:
            f.write(f"{mid}\t{nm}\t{pref}\t{fans}\n")
    cnt = Counter(r[2] for r in final)

    # 报告
    vert = [r for r in rows if r["tier"] == "垂直"]
    half = [r for r in rows if r["tier"] == "半相关"]
    lines = [
        "# AI4Science 定向扩搜报告\n",
        "- 时间：2026-11-01 20:34–21:25",
        "- 关键词：用户给定 7 个子领域共 83 个词（核心/物理/化学材料/生物医学/机器人实验/地学天文/科研Agent）",
        "- 通道：账号搜索 + 视频搜索，1.4s 间隔、90s 冷却",
        "",
        "## 结果\n",
        "| 指标 | 数值 |",
        "|---|---|",
        "| 命中账号 | 1118 |",
        "| ≥10 万粉 | 231 |",
        "| 新增候选 | 205 |",
        "| 内容核验 | **垂直 6 / 半相关 34 / 无关 165** |",
        f"| 并入主名单 | **{len(added)} 个（前缀=科研）** |",
        "",
        "## 关键结论\n",
        "**B 站 10 万粉以上没有真正的「AI4Science 垂直号」。**",
        "命中的 40 个相关账号里，绝大多数是**科学科普或学科教学**（高考生物/物理、化学课、宇宙科普），",
        "而不是「用 AI 做科学研究」的账号。这符合 B 站受众结构：科研细分领域受众小，难以做到 10 万粉。",
        "",
        "## 并入名单的科研向账号\n",
        "| 粉丝 | 名称 | 等级 | 相关度 |",
        "|---|---|---|---|",
    ]
    for a in sorted(added, key=lambda x: -x["fans"]):
        lines.append(f'| {fmt(a["fans"])} | {a["name"]} | {a["tier"]} | {a["score"]} |')
    lines += ["", "## 判定为科学科普/教学，未并入（备查）\n", "| 粉丝 | 名称 | 相关度 |", "|---|---|---|"]
    for r in sorted([x for x in rows if x["tier"] in ("垂直", "半相关")
                     and x["name"] not in KEEP_NAMES], key=lambda x: -x["fans"])[:20]:
        lines.append(f'| {fmt(r["fans"])} | {r["name"]} | {r["score"]} |')
    lines += ["", "## 名单现状\n",
              f"总计 **{len(final)} 个**", "", "| 前缀 | 数量 |", "|---|---|"]
    for p, n in cnt.most_common():
        lines.append(f"| {p} | {n} |")
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"并入 {len(added)} 个科研向账号；名单共 {len(final)} 个")
    print(f"前缀分布: {dict(cnt)}")
    print(f"报告: {REPORT}")


if __name__ == "__main__":
    main()
