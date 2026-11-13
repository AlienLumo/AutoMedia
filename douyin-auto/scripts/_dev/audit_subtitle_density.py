# -*- coding: utf-8 -*-
"""统计已采抖音账号的「字幕密度」，验证创客类是否普遍无字幕/字幕稀疏。"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import DATA

BASE = DATA / "douyin"

rows = []
for d in BASE.iterdir():
    if not d.is_dir():
        continue
    vs = [v for v in d.iterdir() if v.is_dir()]
    if not vs:
        continue
    chars, empty, durs = [], 0, []
    for v in vs:
        tr = v / "transcript.zh.txt"
        mp = v / "meta.json"
        dur = 0
        if mp.exists():
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
                dur = (m.get("duration_ms") or 0) / 1000
            except Exception:
                pass
        if tr.exists():
            n = len(tr.read_text(encoding="utf-8").replace("\n", ""))
            chars.append(n)
            if n < 50:
                empty += 1
        else:
            chars.append(0)
            empty += 1
        durs.append(dur)
    if not chars:
        continue
    avg = sum(chars) / len(chars)
    avg_dur = sum(durs) / len(durs) if durs else 0
    rows.append({"name": d.name, "n": len(chars), "avg": avg,
                 "empty": empty, "empty_pct": empty / len(chars) * 100,
                 "avg_dur": avg_dur,
                 "cps": avg / avg_dur if avg_dur else 0})

rows.sort(key=lambda x: x["avg"])
print(f"{'账号':<26} {'作品':>3} {'均字':>6} {'空/极少':>7} {'均时长':>6} {'字/秒':>5}")
print("-" * 70)
for r in rows:
    print(f"{r['name'][:24]:<26} {r['n']:>3} {r['avg']:>6.0f} "
          f"{r['empty']:>3}({r['empty_pct']:>4.0f}%) {r['avg_dur']:>5.0f}s "
          f"{r['cps']:>5.2f}")

tot = sum(r["n"] for r in rows)
low = sum(r["empty"] for r in rows)
print("-" * 70)
print(f"合计 {tot} 个作品，字幕<50字 的 {low} 个（{low/tot*100:.1f}%）")
print(f"全库平均字数/作品: {sum(r['avg']*r['n'] for r in rows)/tot:.0f}")
