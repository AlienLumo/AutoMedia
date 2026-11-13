# -*- coding: utf-8 -*-
"""合并账号级扩搜结果，统一前缀为 9 个大类：
   ai / 科技 / 创客 / 机器人 / 商业 / 教程 / 炒股投资 / 局势 / 黑客
"""
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
CONF = SKILL / "config"
ROSTER, FANS, PMAP = CONF / "ups.tsv", CONF / "fans.json", CONF / "prefix_map.tsv"
CLASSIFIED = CONF / "candidates_search_classified.tsv"
REPORT = PROJ / "1AMdata" / "_report_expand2.md"

BIG = ["ai", "科技", "创客", "机器人", "商业", "教程", "炒股投资", "局势", "黑客"]

# 顺序很重要：先匹配更具体的品类，最后才是泛商业/泛科技
RULES = [
    (r"炒股|股市|A股|基金|理财|财报|资本论|财经|利率|楼市|投资", "炒股投资"),
    (r"黑客|安全|渗透|攻防|漏洞|逆向", "黑客"),
    (r"机器人|具身|机械臂|人形|机械狗|宇树|unitree", "机器人"),
    (r"创客|DIY|开发板|树莓派|单片机|硬件|电子制作|3D打印|发明|极客|maker", "创客"),
    (r"局势|时政|地缘|中美|俄乌|中东|大国|博弈|政经", "局势"),
    (r"课程|训练营|学院|培训|就业|面试|考研|课堂|私塾|教学|教程|入门", "教程"),
    (r"科技|黑科技|数码|前沿|未来|新品|测评|评测", "科技"),
    (r"创业|生意|一人公司|超级个体|出海|副业|变现", "商业"),
]


try:
    from build_prefix_map import OVERRIDE as _MANUAL
except Exception:
    _MANUAL = {}


def pick_prefix(*texts):
    t = " ".join([x for x in texts if x]).lower()
    for pat, pref in RULES:
        if re.search(pat, t):
            return pref
    return "ai"


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

    keep = []
    for line in CLASSIFIED.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 6 or c[3] not in ("垂直", "半相关"):
            continue
        try:
            keep.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                         "tier": c[3], "score": c[4],
                         "kws": c[6] if len(c) > 6 else ""})
        except ValueError:
            continue
    added = [k for k in keep if k["mid"] not in known]
    print(f"核验通过 {len(keep)}，其中新增 {len(added)}")

    # 备份并追加
    shutil.copy2(ROSTER, ROSTER.with_suffix(".tsv.bak2"))
    for k in added:
        pref = pick_prefix(k["name"], k["kws"])
        base.append((k["mid"], k["name"], f"AI垂直|{pref}"))
        fans_map[str(k["mid"])] = {"name": k["name"], "fans": k["fans"], "sign": ""}
        k["prefix"] = pref

    with ROSTER.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t方向\n")
        for mid, nm, topic in base:
            f.write(f"{mid}\t{nm}\t{topic}\n")
    FANS.write_text(json.dumps(fans_map, ensure_ascii=False), encoding="utf-8")

    # 重建 prefix_map（统一 9 大类，保留已有 ai/商业 等）
    rows = []
    for mid, nm, topic in base:
        fm = fans_map.get(str(mid)) or {}
        fans = fm.get("fans") or 0
        pref = None
        if mid in _MANUAL:
            pref = _MANUAL[mid]
        elif "|" in topic:
            pref = topic.split("|", 1)[1]
        if not pref:
            pref = pick_prefix(nm)
        if pref == "机器人行业":
            pref = "机器人"
        rows.append((mid, nm, pref, fans))
    rows.sort(key=lambda r: -r[3])
    with PMAP.open("w", encoding="utf-8") as f:
        f.write("# mid\t名称\t前缀\t粉丝数\n")
        for mid, nm, pref, fans in rows:
            f.write(f"{mid}\t{nm}\t{pref}\t{fans}\n")
    pref_cnt = Counter(r[2] for r in rows)

    lines = [
        "# 账号级扩搜报告（第 2 轮）\n",
        "- 时间：2026-11-01 20:20–20:30",
        "- 方法：**账号级搜索**（`bili_user`，匹配昵称+简介），99 个关键词 × 最多 2 页",
        "- 速度：1.6s/请求、90s 冷却，慢速优先",
        "",
        "## 结果\n",
        "| 指标 | 数值 |",
        "|---|---|",
        "| 关键词覆盖 | 99 个词，分 6 组（商业/创客/机器人/ai/科技/教程）|",
        "| 命中账号 | 1494 个 |",
        "| ≥10 万粉 | 87 个 |",
        "| 新增候选 | 84 个 |",
        "| 内容核验后 | **垂直 25 / 半相关 11 / 无关 48** |",
        "| 最终并入 | **36 个** |",
        "",
        "## 与第 1 轮（视频榜反查）对比\n",
        "| | 视频榜反查 | 账号级搜索 |",
        "|---|---|---|",
        "| 候选 | 332（≥10w）| 87（≥10w） |",
        "| 核验通过率 | 7%（23/332）| **43%（36/84）** |",
        "",
        "账号级搜索精度高 6 倍：因为匹配的是「这个号自称是什么」，而不是「某条视频标题」。",
        "",
        f"## 名单：**{len(base)} 个**\n",
        "| 前缀（9 大类）| 数量 |",
        "|---|---|",
    ]
    for p in BIG:
        if pref_cnt.get(p):
            lines.append(f"| {p} | {pref_cnt[p]} |")
    lines += ["", "## 本轮新增（前 30）\n", "| 粉丝 | 前缀 | 名称 | AI/科技 相关度 |", "|---|---|---|---|"]
    for k in sorted(added, key=lambda x: -x["fans"])[:30]:
        lines.append(f'| {fmt(k["fans"])} | {k["prefix"]} | {k["name"]} | {k["score"]} |')
    lines += ["", "## 未通过核验的典型（说明筛选有效）\n",
              "- 极客鞋谈（球鞋）、KBT篮球训练营、世界舞蹈训练营、竹洋洗涤科技有限公司",
              "- 这些是昵称里带「极客/训练营/科技公司」但内容完全无关的号，已剔除。"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"最终名单 {len(base)} 个；前缀分布 {dict(pref_cnt)}")
    print(f"报告: {REPORT}")


if __name__ == "__main__":
    main()
