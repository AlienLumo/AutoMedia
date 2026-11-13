# -*- coding: utf-8 -*-
"""统计两平台已采集的视频数量（对畸形文件名容错）。"""
import json
from pathlib import Path
from _paths import PROJECT

PROJ = PROJECT


def count_platform(root, is_bili=False):
    accs = [d for d in root.iterdir() if d.is_dir()]
    accounts = 0
    real = pool = subs = cms = 0
    bad = 0
    for a in accs:
        try:
            vs = [v for v in a.iterdir() if v.is_dir() and v.name != "_pool"]
        except Exception:
            bad += 1
            continue
        p = a / "_pool"
        try:
            pn = len([v for v in p.iterdir() if v.is_dir()]) if p.exists() else 0
        except Exception:
            pn = 0
        if not vs and not pn:
            continue
        if vs:
            accounts += 1
        real += len(vs)
        pool += pn
        for v in vs:
            try:
                if is_bili:
                    if any(v.glob("subtitle.*")):
                        subs += 1
                else:
                    if (v / "transcript.zh.txt").exists():
                        subs += 1
            except Exception:
                pass
            cf = v / "comments.jsonl"
            if cf.exists():
                try:
                    cms += sum(1 for _ in cf.open(encoding="utf-8"))
                except Exception:
                    pass
    return {"accounts": accounts, "videos": real, "pool": pool,
            "subs": subs, "comments": cms, "bad": bad}


dy = count_platform(PROJ / "1AMdata/douyin")
bl = count_platform(PROJ / "1AMdata/bilibili", is_bili=True)

print("=" * 60)
print("抖音")
print("=" * 60)
print(f"  博主账号 : {dy['accounts']}")
print(f"  视频     : {dy['videos']}")
print(f"  有字幕   : {dy['subs']}  (缺 {dy['videos'] - dy['subs']})")
print(f"  评论     : {dy['comments']}")

print()
print("=" * 60)
print("B站")
print("=" * 60)
print(f"  博主账号（有正式作品）: {bl['accounts']}")
print(f"  正式采集视频          : {bl['videos']}")
print(f"  候选池视频（_pool）    : {bl['pool']}   ← 仅打分用，非正式采集")
print(f"  有字幕                : {bl['subs']}")
print(f"  评论                  : {bl['comments']}")
if bl["bad"]:
    print(f"  （{bl['bad']} 个目录读取异常已跳过）")

print()
print("=" * 60)
print("合计")
print("=" * 60)
print(f"  视频: {dy['videos'] + bl['videos']:,}  "
      f"（抖音 {dy['videos']:,} + B站 {bl['videos']:,}）")
print(f"  评论: {dy['comments'] + bl['comments']:,}")
print(f"  账号: {dy['accounts'] + bl['accounts']}")
