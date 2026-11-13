# -*- coding: utf-8 -*-
"""对账：目录树 vs manifest，找出缺失/失败项，输出最终统计。"""
import json
from pathlib import Path
from collections import Counter, defaultdict
from _paths import DATA

ROOT = DATA / "bilibili"
man = json.loads((ROOT / "_manifest.json").read_text(encoding="utf-8"))
items = man.get("items", [])
print(f"manifest 条目: {len(items)}")
print(f"manifest stats: {man.get('stats')}")

videos = sorted([p for p in ROOT.rglob("*") if p.is_dir() and "_" in p.name
                 and (p.name.split("_")[0].startswith("BV") or p.parent.parent != ROOT)])
# 更可靠的判定：包含 meta.json 或 comments.jsonl 的叶子目录
leaves = [p for p in ROOT.rglob("*") if p.is_dir() and
          (any((p / f).exists() for f in ("meta.json", "comments.jsonl"))
           or (p.name.split("_")[0].startswith("BV") and p.parent.parent.parent != ROOT))]

all_dirs = [p for p in ROOT.rglob("BV*") if p.is_dir()]
print(f"\n视频目录总数: {len(all_dirs)}")
no_meta = [p for p in all_dirs if not (p / "meta.json").exists()]
no_cm = [p for p in all_dirs if not (p / "comments.jsonl").exists()]
no_sub = [p for p in all_dirs if not list(p.glob("subtitle.*.srt"))]
print(f"缺 meta.json : {len(no_meta)}")
for p in no_meta:
    print(f"   - {p.relative_to(ROOT)}")
print(f"缺 comments  : {len(no_cm)}")
for p in no_cm:
    print(f"   - {p.relative_to(ROOT)}")
print(f"缺字幕       : {len(no_sub)}")
for p in no_sub:
    print(f"   - {p.relative_to(ROOT)}")

# 按主题/UP 汇总
per_up = defaultdict(lambda: {"videos": 0, "comments": 0, "subs": 0, "bytes": 0})
per_topic = Counter()
for p in all_dirs:
    parts = p.relative_to(ROOT).parts
    if len(parts) < 3:
        continue
    topic, up = parts[0], parts[1]
    per_topic[topic] += 1
    per_up[up]["videos"] += 1
    if (p / "comments.jsonl").exists():
        lines = sum(1 for _ in (p / "comments.jsonl").open(encoding="utf-8"))
        per_up[up]["comments"] += lines
    per_up[up]["subs"] += len({f.name.split(".")[1] for f in p.glob("subtitle.*.srt")})
    per_up[up]["bytes"] += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

print(f"\n=== 按主题 ===")
for t, n in per_topic.most_common():
    print(f"  {t:<10} {n} 个视频")

total_cm = sum(v["comments"] for v in per_up.values())
total_bytes = sum(v["bytes"] for v in per_up.values())
print(f"\n=== 汇总 ===")
print(f"  UP 主: {len(per_up)}   视频: {len(all_dirs)}   评论总数: {total_cm}   "
      f"体积: {total_bytes/1024/1024:.1f} MB")
print(f"  平均每视频评论: {total_cm/max(len(all_dirs),1):.0f}")

print(f"\n=== 各 UP 明细 ===")
for up, v in sorted(per_up.items(), key=lambda kv: -kv[1]["comments"]):
    print(f"  {up:<28} 视频{v['videos']} 评论{v['comments']:>5} 字幕语言{v['subs']:>3} "
          f"{v['bytes']/1024:.0f}KB")
