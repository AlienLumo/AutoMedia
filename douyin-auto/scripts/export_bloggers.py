# -*- coding: utf-8 -*-
"""从 video_search_state.json 重新导出干净的 TSV（清理 tab/换行），并做统计。"""
import json
from collections import Counter
from pathlib import Path
from _paths import SKILL

CFG = SKILL / "config"
STATE = CFG / "video_search_state.json"
OUT = CFG / "douyin_video_found_bloggers.tsv"
OUT_MID = CFG / "douyin_video_found_bloggers_10w.tsv"


def clean(s, n=120):
    s = (s or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")
    return " ".join(s.split())[:n]


d = json.loads(STATE.read_text(encoding="utf-8"))
authors = d.get("authors") or []
print(f"总作者: {len(authors)}")
print(f"已完成关键词: {len(d.get('done_keywords') or [])}/53")

for x in authors:
    x["nickname"] = clean(x.get("nickname"), 40)
    x["signature"] = clean(x.get("signature"), 100)
    x["best_video"] = clean(x.get("best_video"), 80)

rows = sorted(authors, key=lambda x: -(x.get("fans") or 0))
hdr = ("sec_uid\t昵称\t粉丝\t总获赞\t领域\t命中关键词\t命中视频数\t最高赞\t代表作\t简介\n")


def write(path, data):
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(hdr)
        for b in data:
            f.write("\t".join([
                clean(b.get("sec_uid"), 60), b["nickname"],
                str(b.get("fans") or 0), str(b.get("total_favorited") or 0),
                clean(",".join(b.get("themes") or []), 40),
                clean(",".join((b.get("keywords") or [])[:5]), 80),
                str(b.get("videos_hit") or 0), str(b.get("best_likes") or 0),
                b["best_video"], b["signature"]]) + "\n")


write(OUT, rows)
big = [x for x in rows if (x.get("fans") or 0) >= 100000]
write(OUT_MID, big)

print(f"导出全部: {len(rows)} -> {OUT.name}")
print(f"导出 ≥10万粉: {len(big)} -> {OUT_MID.name}")
print()
print("粉丝分布:",
      {k: len([x for x in rows if (x.get("fans") or 0) >= v])
       for k, v in [("≥1000万", 10_000_000), ("≥500万", 5_000_000),
                    ("≥100万", 1_000_000), ("≥50万", 500_000), ("≥10万", 100_000)]})
print()
print("命中视频数分布:",
      {k: len([x for x in rows if (x.get("videos_hit") or 0) >= v])
       for k, v in [("≥3条", 3), ("≥2条", 2), ("≥1条", 1)]})
print()
print("领域分布:")
cnt = Counter()
for x in rows:
    for t in (x.get("themes") or []):
        cnt[t] += 1
for t, n in cnt.most_common():
    print(f"  {t:<8} {n}")
print()
print("Top 15（≥50万粉，按命中视频数再排序）:")
sub = [x for x in rows if (x.get("fans") or 0) >= 500000]
sub.sort(key=lambda x: (-(x.get("videos_hit") or 0), -(x.get("fans") or 0)))
for b in sub[:15]:
    print(f'  {b.get("videos_hit",0)}条  {b["fans"]/1e4:>7.0f}万  '
          f'[{",".join(b.get("themes") or [])[:10]}]  {b["nickname"]}')
