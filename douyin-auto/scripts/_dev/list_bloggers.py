# -*- coding: utf-8 -*-
"""生成抖音已发现博主的完整清单（Markdown），并打印分组摘要。"""
import json
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

CFG = SKILL / "config"
d = json.loads((CFG / "video_search_state.json").read_text(encoding="utf-8"))
authors = d.get("authors") or []
done_kw = d.get("done_keywords") or []


def fmt(n):
    n = n or 0
    return f"{n/1e4:.0f}万" if n >= 1e4 else str(n)


big = [x for x in authors if (x.get("fans") or 0) >= 100000]
big.sort(key=lambda x: (-(x.get("videos_hit") or 0), -(x.get("fans") or 0)))

L = ["# 抖音已发现博主清单\n",
     f"- 数据来源：视频内容搜索反查作者（36/53 关键词已完成）",
     f"- 累计作者：**{len(authors)}** 个，其中 ≥10 万粉 **{len(big)}** 个",
     f"- 更新：{d.get('updated')}",
     "",
     "## 按领域分组（每组建按「命中视频数」再按粉丝排序）\n"]

by_theme = defaultdict(list)
for x in big:
    for t in (x.get("themes") or ["未分类"]):
        by_theme[t].append(x)

for theme in ["创业", "创客", "名人访谈", "科技前沿", "前沿资讯"]:
    lst = sorted(by_theme.get(theme, []),
                 key=lambda x: (-(x.get("videos_hit") or 0), -(x.get("fans") or 0)))
    if not lst:
        continue
    L.append(f"\n### {theme}（{len(lst)} 个）\n")
    L.append("| 粉丝 | 命中 | 昵称 | 简介 |")
    L.append("|---|---|---|---|")
    for x in lst[:40]:
        sig = (x.get("signature") or "").replace("|", " ")[:40]
        L.append(f'| {fmt(x.get("fans"))} | {x.get("videos_hit")} | '
                 f'{x["nickname"]} | {sig} |')

L.append("\n## 全部 ≥10万粉 博主（按命中数排序）\n")
L.append("| # | 粉丝 | 命中 | 领域 | 昵称 | sec_uid |")
L.append("|---|---|---|---|---|---|")
for i, x in enumerate(big, 1):
    L.append(f'| {i} | {fmt(x.get("fans"))} | {x.get("videos_hit")} | '
             f'{",".join((x.get("themes") or [])[:2])} | {x["nickname"]} | {x["sec_uid"]} |')

out = CFG / "抖音博主清单.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"REPORT={out}  size={out.stat().st_size/1024:.0f}KB  rows={len(big)}")
print()
print(f"=== 命中 ≥3 条（最对口）===")
for x in [y for y in big if (y.get("videos_hit") or 0) >= 3][:20]:
    print(f'  {fmt(x.get("fans")):>6}  {x.get("videos_hit")}条  '
          f'[{",".join((x.get("themes") or [])[:2])}]  {x["nickname"]}')
print()
print(f"=== 粉丝最多（≥300万）===")
for x in sorted(big, key=lambda y: -(y.get("fans") or 0))[:15]:
    print(f'  {fmt(x.get("fans")):>7}  {x.get("videos_hit")}条  '
          f'[{",".join((x.get("themes") or [])[:2])}]  {x["nickname"]}')
print()
print("=== 各领域数量 ===")
for t, lst in sorted(by_theme.items(), key=lambda kv: -len(kv[1])):
    print(f"  {t:<8} {len(lst)}")
