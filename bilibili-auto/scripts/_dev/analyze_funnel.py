# -*- coding: utf-8 -*-
"""分析 B站 各主题的候选漏斗：搜索发现 → 分类等级 → 最终入册。"""
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

CONF = SKILL / "config"


def read_tsv(p):
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    hdr = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        parts = ln.split("\t")
        rows.append(dict(zip(hdr, parts)))
    return rows


# 1) 最终名单前缀
final = read_tsv(CONF / "prefix_map.tsv")
final_cnt = defaultdict(int)
for r in final:
    if r.get("前缀"):
        final_cnt[r["前缀"]] += 1

# 2) 中腰部候选（有主题列）
mid = read_tsv(CONF / "candidates_mid.tsv")
mid_theme = defaultdict(int)
for r in mid:
    mid_theme[r.get("主题") or "?"] += 1

# 3) 中腰部分类结果
midc = read_tsv(CONF / "candidates_mid_classified.tsv")
mid_grade = defaultdict(lambda: defaultdict(int))
for r in midc:
    t = r.get("主题") or "?"
    g = r.get("等级") or "?"
    mid_grade[t][g] += 1

# 4) 搜索候选（按命中词反推主题）
sys.path.insert(0, str(CONF.parent / "scripts"))
import ast
kw_table = {}
try:
    src = (CONF.parent / "scripts" / "expand_accounts.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(x, "id", None) == "KEYWORDS"
                                                for x in node.targets):
            d = ast.literal_eval(node.value)
            for bucket, kws in d.items():
                for k in kws:
                    kw_table.setdefault(k, bucket)
except Exception as e:
    print("关键词表读取失败:", e)

search = read_tsv(CONF / "candidates_search.tsv")
search_bucket = defaultdict(int)
for r in search:
    kws = (r.get("命中词") or "").split(",")
    buckets = {kw_table.get(k.strip()) for k in kws if kw_table.get(k.strip())}
    if buckets:
        for b in buckets:
            search_bucket[b] += 1

print("=" * 74)
print("B站 各主题候选漏斗")
print("=" * 74)
print(f"\n{'主题':<10} {'搜索候选':>8} {'中腰候选':>8} {'垂直':>6} {'半相关':>6} {'无关':>6} {'入册':>6}")
print("-" * 74)

themes = sorted(set(list(final_cnt) + list(mid_theme) + list(search_bucket)),
                key=lambda t: -final_cnt.get(t, 0))
for t in themes:
    s = search_bucket.get(t, 0)
    m = mid_theme.get(t, 0)
    v = mid_grade.get(t, {}).get("垂直", 0)
    h = mid_grade.get(t, {}).get("半相关", 0)
    w = mid_grade.get(t, {}).get("无关", 0)
    f = final_cnt.get(t, 0)
    print(f"{t:<10} {s:>8} {m:>8} {v:>6} {h:>6} {w:>6} {f:>6}")

print("\n" + "=" * 74)
print("分类等级分布（中腰部候选）")
print("=" * 74)
tot = defaultdict(int)
for t, gs in mid_grade.items():
    for g, n in gs.items():
        tot[g] += n
for g, n in sorted(tot.items(), key=lambda kv: -kv[1]):
    print(f"  {g:<6} {n}")

# 未进入最终名单的高粉候选（漏采）
final_mids = {r.get("mid") for r in final}
print("\n" + "=" * 74)
print("被分类刷掉但粉丝 ≥50万 的候选（前 20）")
print("=" * 74)
cand = []
for r in midc:
    try:
        fans = int(r.get("粉丝") or 0)
    except ValueError:
        fans = 0
    if fans >= 500000 and r.get("mid") not in final_mids:
        cand.append((fans, r.get("名称"), r.get("主题"), r.get("等级"),
                     r.get("相关度"), r.get("命中词")))
cand.sort(reverse=True)
for fans, name, theme, grade, rel, kw in cand[:20]:
    print(f"  {fans/1e4:>7.1f}万  [{theme:<4}] {grade:<4} 相关度{rel:<5} {(name or '')[:18]:<20} {kw}")
print(f"\n  共 {len(cand)} 个 ≥50万粉 被刷掉")
