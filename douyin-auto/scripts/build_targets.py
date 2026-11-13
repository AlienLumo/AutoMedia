# -*- coding: utf-8 -*-
"""从搜索结果里挑出「创客 / 创业」博主，按粉丝降序生成采集队列文件。"""
import json
import re
from pathlib import Path
from _paths import DATA as _DATA, SKILL

CFG = SKILL / "config"
DATA = _DATA / "douyin"
STATE = CFG / "video_search_state.json"
OUT = CFG / "queue_creators.txt"
OUT_TSV = CFG / "queue_creators.tsv"

import argparse

_ap = argparse.ArgumentParser()
_ap.add_argument("--themes", default="创客")
_ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
_ap.add_argument("--split", type=int, default=1)
_args = _ap.parse_args()

WANT = tuple(x.strip() for x in _args.themes.split(",") if x.strip())
MIN_FANS = _args.min_fans

d = json.loads(STATE.read_text(encoding="utf-8"))
authors = d.get("authors") or []

# 已在采过的账号 sec_uid
collected = set()
for acc in DATA.iterdir() if DATA.exists() else []:
    if not acc.is_dir():
        continue
    ap = acc / "_account.json"
    if not ap.exists():
        continue
    try:
        a = json.loads(ap.read_text(encoding="utf-8"))
        m = re.search(r"/user/([A-Za-z0-9_\-]{20,})", a.get("url") or "")
        if m:
            collected.add(m.group(1))
    except Exception:
        pass

targets = []
for x in authors:
    themes = x.get("themes") or []
    if not any(t in WANT for t in themes):
        continue
    if (x.get("fans") or 0) < MIN_FANS:
        continue
    uid = x.get("sec_uid")
    if not uid:
        continue
    targets.append(x)

# 按粉丝降序
targets.sort(key=lambda x: -(x.get("fans") or 0))

# 去重（同一 uid 可能因多主题重复）
seen, rows = set(), []
for x in targets:
    if x["sec_uid"] in seen:
        continue
    seen.add(x["sec_uid"])
    rows.append(x)

if _args.split > 1:
    for part in range(_args.split):
        sub = [x for i, x in enumerate(rows) if i % _args.split == part]
        p = OUT.with_name(f"queue_creators_p{part + 1}.txt")
        p.write_text("\n".join(f'https://www.douyin.com/user/{x["sec_uid"]}' for x in sub) + "\n",
                     encoding="utf-8")
        print(f"SPLIT={p}  count={len(sub)}")
else:
    OUT.write_text("\n".join(f'https://www.douyin.com/user/{x["sec_uid"]}' for x in rows) + "\n",
                   encoding="utf-8")

with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
    f.write("序号\t昵称\t粉丝\t命中\t领域\t已采\t主页\n")
    for i, x in enumerate(rows, 1):
        done = "是" if x["sec_uid"] in collected else ""
        f.write(f'{i}\t{x["nickname"]}\t{x.get("fans")}\t{x.get("videos_hit")}\t'
                f'{",".join(x.get("themes") or [])}\t{done}\t'
                f'https://www.douyin.com/user/{x["sec_uid"]}\n')

print(f"QUEUE={OUT}  count={len(rows)}")
print(f"TSV={OUT_TSV}")
print(f"其中已采过: {sum(1 for x in rows if x['sec_uid'] in collected)}")
print()
print("前 25 个（按粉丝降序）:")
for i, x in enumerate(rows[:25], 1):
    tag = " [已采]" if x["sec_uid"] in collected else ""
    print(f'  {i:>2}. {x.get("fans",0)/1e4:>7.1f}万  命中{x.get("videos_hit")}  '
          f'[{",".join(x.get("themes") or [])[:12]}]  {x["nickname"]}{tag}')
