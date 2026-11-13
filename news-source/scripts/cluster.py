# -*- coding: utf-8 -*-
"""从今日资讯池聚类出「大事件」，输出候选事件清单（供人工挑选）。"""
import json, re, sys, collections
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import POOL, day_iso, buckets_config

POOL = str(POOL)
DAY = day_iso()

try:
    pool_file = open(POOL, encoding="utf-8", errors="replace")
except FileNotFoundError:
    print(f"[cluster] 资讯池不存在：{POOL}")
    print("提示：设置 NEWS_POOL 指向真实资讯池，或先由上游资讯池引擎产出 pool/items.jsonl。")
    print("today items: 0")
    sys.exit(0)

rows = []
with pool_file:
    for line in pool_file:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ts", "").startswith(DAY):
            rows.append(r)

print("today items:", len(rows))

BUCKETS = [(name, kws) for name, kws in
           json.loads(buckets_config().read_text(encoding="utf-8"))["buckets"]]

assigned = set()
out = []
for name, kws in BUCKETS:
    hit = []
    for i, r in enumerate(rows):
        if i in assigned:
            continue
        t = ((r.get("title") or "") + " " + (r.get("summary") or "")).lower()
        if any(k in t for k in kws):
            hit.append(r)
    hit.sort(key=lambda r: ({"P0": 3, "P1": 2, "P2": 1, "P3": 0}.get(r.get("level"), 0), len(r.get("title") or "")), reverse=True)
    for r in hit:
        assigned.add(rows.index(r))
    out.append((name, len(hit), hit[:6]))

for name, n, top in out:
    print(f"\n=== {name}  ({n}) ===")
    for r in top:
        print(f"  [{r.get('level')}] {r.get('source')} | {(r.get('title') or '')[:70]}")
        print(f"      {r.get('link','')}")
