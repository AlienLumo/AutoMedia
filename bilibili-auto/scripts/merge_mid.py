# -*- coding: utf-8 -*-
"""合并 1w–10w 区间核验通过的账号，重建名单与前缀地图。"""
import json
import shutil
from collections import Counter
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
CONF = SKILL / "config"
ROSTER, FANS, PMAP = CONF / "ups.tsv", CONF / "fans.json", CONF / "prefix_map.tsv"
CLASSIFIED = CONF / "candidates_mid_classified.tsv"
REPORT = PROJ / "1AMdata" / "_report_midtier.md"

THEME2PREFIX = {"科研": "科研", "创客": "创客", "黑客": "黑客", "机器人": "机器人",
                "炒股投资": "炒股投资", "局势": "局势", "科技": "科技",
                "商业": "商业", "ai": "ai"}


def fmt(n):
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


def main():
    base, known = [], set()
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
    old_pref = {}
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
    for line in CLASSIFIED.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 6 or c[3] not in ("垂直", "半相关"):
            continue
        try:
            rows.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                         "tier": c[3], "score": c[4], "theme": c[5]})
        except ValueError:
            continue

    shutil.copy2(ROSTER, ROSTER.with_suffix(".tsv.bak3"))
    added = []
    for r in rows:
        if r["mid"] in known:
            continue
        pref = THEME2PREFIX.get(r["theme"], "科技")
        base.append((r["mid"], r["name"], f"AI垂直|{pref}"))
        fans_map[str(r["mid"])] = {"name": r["name"], "fans": r["fans"], "sign": ""}
        r["prefix"] = pref
        added.append(r)

    with ROSTER.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t方向\n")
        for mid, nm, topic in base:
            f.write(f"{mid}\t{nm}\t{topic}\n")
    FANS.write_text(json.dumps(fans_map, ensure_ascii=False), encoding="utf-8")

    final = []
    for mid, nm, topic in base:
        fm = fans_map.get(str(mid)) or {}
        pref = (topic.split("|", 1)[1] if "|" in topic else old_pref.get(mid)) or "ai"
        final.append((mid, nm, pref, fm.get("fans") or 0))
    final.sort(key=lambda r: -r[3])
    with PMAP.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t前缀\t粉丝数\n")
        for mid, nm, pref, fans in final:
            f.write(f"{mid}\t{nm}\t{pref}\t{fans}\n")
    cnt = Counter(r[2] for r in final)

    by_theme = Counter(a["prefix"] for a in added)
    lines = [
        "# 1 万–10 万粉区间补搜报告\n",
        "- 时间：2026-11-01 21:50–22:10",
        "- 目的：把此前各主题**下探到 1w–10w 粉**区间，补腰部账号",
        "- 覆盖主题：科研(AI4Science)/创客/黑客/机器人/炒股投资/局势/科技/商业/ai",
        "- 方法：账号级搜索（昵称+简介）× 约 200 个关键词 × 最多 3 页，1.3s 间隔、90s 冷却",
        "",
        "## 结果\n",
        "| 指标 | 数值 |",
        "|---|---|",
        "| 1w–10w 区间命中 | **549** |",
        "| 内容核验 | **垂直 206 / 半相关 55 / 无关 288** |",
        f"| 并入名单 | **{len(added)}** |",
        f"| 名单总数 | **{len(final)}**（目标 ≤500）|",
        "",
        "## 本轮新增按主题\n",
        "| 前缀 | 新增数 | 累计 |",
        "|---|---|---|",
    ]
    for p, n in by_theme.most_common():
        lines.append(f"| {p} | {n} | {cnt[p]} |")
    lines += ["", "## 名单最终前缀分布\n", "| 前缀 | 数量 |", "|---|---|"]
    for p, n in cnt.most_common():
        lines.append(f"| {p} | {n} |")
    lines += ["", "## 新增样例（按粉丝）\n",
              "| 粉丝 | 前缀 | 名称 | 相关度 |", "|---|---|---|---|"]
    for a in sorted(added, key=lambda x: -x["fans"])[:30]:
        lines.append(f'| {fmt(a["fans"])} | {a["prefix"]} | {a["name"]} | {a["score"]} |')
    lines += ["", "## 注意\n",
              f"- 新增里「黑客」{by_theme.get('黑客',0)} 个、「炒股投资」{by_theme.get('炒股投资',0)} 个，",
              "  合计占比偏高，会稀释 AI/科技内容。若监控需要聚焦 AI，可裁掉这两类的一部分。",
              "- 1w–10w 区间的号内容更垂直但影响力小，适合做长尾情报源，不适合当头部标杆。"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"并入 {len(added)} 个，名单共 {len(final)} 个（上限 500）")
    print(f"前缀分布: {dict(cnt)}")
    print(f"报告: {REPORT}")


if __name__ == "__main__":
    main()
