# -*- coding: utf-8 -*-
"""测量：账号近 90 天有多少条投稿（决定「热度排序」阶段的成本）。"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from _paths import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from bili_subs import Bili, read_cred
from bili_collect import list_videos

b = Bili(pace=1.0, cooldown=60, cookies=read_cred())
b.preflight()

cutoff = time.time() - 90 * 86400
# 不同类型：高频更新 / 中频 / 低频
targets = [
    (385670211, "秋芝2046"),
    (1208823126, "大圆镜科普"),
    (14097567, "花叔v"),
    (673779175, "量子位"),
]
for mid, name in targets:
    t0 = time.time()
    try:
        vids = list_videos(b, mid, name, 120, "pubdate", "auto")
    except Exception as e:
        print(f"{name}: 列表失败 {str(e)[:50]}")
        continue
    recent = [v for v in vids if (v.get("created") or 0) >= cutoff]
    print(f"{name}: 取到 {len(vids)} 条，近90天 {len(recent)} 条 "
          f"（{time.time()-t0:.1f}s）")
    for v in recent[:3]:
        d = datetime.fromtimestamp(v["created"]).strftime("%Y-%m-%d")
        print(f"    {d}  play={v.get('play')}  {v['title'][:30]}")
    time.sleep(1.5)
