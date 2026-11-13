# -*- coding: utf-8 -*-
"""覆盖度审计：B站各主题账号数/视频数；抖音各主题关键词完成度与作者数。"""
import json
import re
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT, SKILL

PROJ = PROJECT

print("=" * 70)
print("B站覆盖度")
print("=" * 70)

st = json.loads((PROJ / "1AMdata/_state/deep_collect.json").read_text(encoding="utf-8"))
accs = st.get("accounts") or {}

# 前缀统计（从目录名 <prefix>_<name>_<fans> 或 state 里推）
prefix_stat = defaultdict(lambda: {"n": 0, "videos": 0, "comments": 0, "names": []})
no_prefix = []
for mid, a in accs.items():
    name = a.get("name") or ""
    # state 里没有 prefix 字段时，用账号名反查目录
    dirs = list((PROJ / "1AMdata/bilibili").glob(f"*_{name}_*")) if name else []
    pfx = ""
    if dirs:
        pfx = dirs[0].name.split("_")[0]
    else:
        no_prefix.append(name)
        continue
    s = prefix_stat[pfx]
    s["n"] += 1
    s["videos"] += len(a.get("done") or [])
    s["comments"] += a.get("total_cm") or 0
    s["names"].append(name)

print(f"\n{'前缀':<10} {'账号':>5} {'视频':>6} {'评论':>8}  平均视频")
for p, s in sorted(prefix_stat.items(), key=lambda kv: -kv[1]["n"]):
    avg = s["videos"] / s["n"] if s["n"] else 0
    print(f"{p:<10} {s['n']:>5} {s['videos']:>6} {s['comments']:>8}  {avg:>6.1f}")
print(f"\n合计: {sum(s['n'] for s in prefix_stat.values())} 个账号 / "
      f"{sum(s['videos'] for s in prefix_stat.values())} 视频")
if no_prefix:
    print(f"未能匹配前缀: {len(no_prefix)} 个（{no_prefix[:5]}）")

print("\n" + "=" * 70)
print("抖音覆盖度（主题 × 关键词完成度）")
print("=" * 70)

import sys
sys.path.insert(0, str(SKILL.parent / "douyin-auto/scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "fdv", SKILL.parent / "douyin-auto/scripts/douyin_find_by_video.py")
fdv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fdv)
THEMES = fdv.THEMES

dst = json.loads((SKILL.parent / "douyin-auto/config/video_search_state.json")
                 .read_text(encoding="utf-8"))
done_kw = set(dst.get("done_keywords") or [])
authors = dst.get("authors") or []

print(f"\n累计作者: {len(authors)}")
print(f"\n{'主题':<10} {'关键词':>10} {'完成':>5}  作者数(≥10万粉)")
for theme, kws in THEMES.items():
    total = len(kws)
    hit = sum(1 for k in kws if k in done_kw)
    n_authors = sum(1 for x in authors if theme in (x.get("themes") or []))
    n_big = sum(1 for x in authors
                if theme in (x.get("themes") or []) and (x.get("fans") or 0) >= 100000)
    flag = "  ← 未搜/缺" if hit == 0 else ("  ← 部分" if hit < total else "")
    print(f"{theme:<10} {hit:>4}/{total:<5} {hit:>5}  {n_authors:>6} ({n_big}){flag}")

# 全库未搜过的关键词
all_kws = set(k for kws in THEMES.values() for k in kws)
never = sorted(all_kws - done_kw)
print(f"\n尚未搜索的关键词 ({len(never)}): {never}")

# 科技创客 ≥10万粉 明细统计
tc = [x for x in authors if "科技创客" in (x.get("themes") or [])
      and (x.get("fans") or 0) >= 100000]
print(f"\n科技创客 ≥10万粉: {len(tc)} 个")
buckets = {"≥100万": 0, "50-100万": 0, "10-50万": 0}
for x in tc:
    f = x.get("fans") or 0
    if f >= 1e6:
        buckets["≥100万"] += 1
    elif f >= 5e5:
        buckets["50-100万"] += 1
    else:
        buckets["10-50万"] += 1
print(f"  粉丝分布: {buckets}")
