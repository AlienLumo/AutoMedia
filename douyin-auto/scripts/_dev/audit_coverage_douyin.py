# -*- coding: utf-8 -*-
"""抖音 4 主题的覆盖度估计：关键词饱和分析。

思路：若关键词覆盖充分，多数作者会被「多个关键词」同时命中；
     若多数作者只被 1 个关键词命中，说明覆盖依赖关键词选择，容易漏。
"""
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

CFG = SKILL / "config"
st = json.loads((CFG / "video_search_state.json").read_text(encoding="utf-8"))
authors = st.get("authors") or []
done = set(st.get("done_keywords") or [])

THEMES = ["名人访谈", "前沿资讯", "科技前沿", "创业"]
MIN_FANS = 100000

print(f"总作者 {len(authors)}，已完成关键词 {len(done)}\n")

for theme in THEMES:
    au = [x for x in authors if theme in (x.get("themes") or [])]
    big = [x for x in au if (x.get("fans") or 0) >= MIN_FANS]
    print(f"=== {theme} ===")
    print(f"  作者 {len(au)}，≥10万粉 {len(big)}")

    # 每个作者被几个关键词命中
    dist = Counter(len(x.get("keywords") or []) for x in big)
    print(f"  被 N 个关键词命中的人数分布: {dict(sorted(dist.items()))}")
    multi = sum(v for k, v in dist.items() if k >= 2)
    print(f"  被 ≥2 个关键词命中: {multi}/{len(big)} = {multi/len(big)*100:.0f}%")

    # 每个关键词贡献多少 ≥10万粉 作者
    kw_count = defaultdict(int)
    for x in big:
        for k in (x.get("keywords") or []):
            kw_count[k] += 1
    # 只用该关键词能找到的人数
    solo = sum(1 for x in big if len(x.get("keywords") or []) == 1)
    print(f"  只被 1 个关键词找到: {solo}（{solo/len(big)*100:.0f}%）")

    # 关键词效力排行
    top_kw = sorted(kw_count.items(), key=lambda kv: -kv[1])[:5]
    print(f"  关键词效力: {top_kw}")
    print()
