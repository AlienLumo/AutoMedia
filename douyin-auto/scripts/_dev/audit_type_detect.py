# -*- coding: utf-8 -*-
"""验证：能否用「时长 / 文案长度 / 评论」等便宜信号，在采集前判断口播型 vs 展示型。

用已采的 889 个作品做回归：真实标签 = 字/秒（≥1.5 口播）
特征：duration、desc 长度、评论数、标签数
"""
import json
import statistics
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import DATA

BASE = DATA / "douyin"

rows = []
for d in BASE.iterdir():
    if not d.is_dir():
        continue
    for v in d.iterdir():
        if not v.is_dir():
            continue
        mp, tp = v / "meta.json", v / "transcript.zh.txt"
        if not mp.exists() or not tp.exists():
            continue
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            continue
        dur = (m.get("duration_ms") or 0) / 1000
        if dur <= 0:
            continue
        chars = len(tp.read_text(encoding="utf-8").replace("\n", ""))
        cps = chars / dur
        desc = m.get("desc") or ""
        rows.append({
            "acct": d.name,
            "dur": dur,
            "chars": chars,
            "cps": cps,
            "desc_len": len(desc),
            "tags": desc.count("#"),
            "cm": m.get("comment_count") or 0,
            "digg": m.get("digg_count") or 0,
            "label": "talk" if cps >= 1.5 else "visual",
        })

print(f"样本 {len(rows)} 个作品")
talk = [r for r in rows if r["label"] == "talk"]
vis = [r for r in rows if r["label"] == "visual"]
print(f"  口播型 {len(talk)}（{len(talk)/len(rows)*100:.0f}%）  视觉型 {len(vis)}\n")


def stat(arr, key):
    vals = [r[key] for r in arr]
    if not vals:
        return "—"
    return f"{statistics.median(vals):.1f}"


print(f"{'特征':<12} {'口播型中位数':>12} {'视觉型中位数':>12}")
print("-" * 40)
for k, label in [("dur", "时长(秒)"), ("desc_len", "文案长度"), ("tags", "标签数"),
                 ("cm", "评论数"), ("digg", "点赞数")]:
    print(f"{label:<12} {stat(talk,k):>12} {stat(vis,k):>12}")

# 用时长单特征分类的准确率
print("\n=== 用「时长」单特征分类的准确率 ===")
for th in [20, 30, 40, 50, 60, 90, 120]:
    pred = ["visual" if r["dur"] < th else "talk" for r in rows]
    acc = sum(1 for p, r in zip(pred, rows) if p == r["label"]) / len(rows)
    # 视觉型召回率
    vp = sum(1 for p, r in zip(pred, rows) if p == "visual" and r["label"] == "visual")
    vr = vp / len(vis) if vis else 0
    print(f"  时长<{th:>3}s 判视觉 → 总准确率 {acc*100:>5.1f}%  视觉召回 {vr*100:>5.1f}%")

# 组合特征：时长<45 且 文案<40 字
print("\n=== 组合规则：时长<45s 且 文案<40字 → 视觉 ===")
pred = ["visual" if (r["dur"] < 45 and r["desc_len"] < 40) else "talk" for r in rows]
acc = sum(1 for p, r in zip(pred, rows) if p == r["label"]) / len(rows)
vp = sum(1 for p, r in zip(pred, rows) if p == "visual" and r["label"] == "visual")
fp = sum(1 for p, r in zip(pred, rows) if p == "visual" and r["label"] == "talk")
print(f"  准确率 {acc*100:.1f}%  视觉召回 {vp}/{len(vis)} = {vp/len(vis)*100:.0f}%  "
      f"误判口播为视觉 {fp} 个")

# 账号级：能否用账号均时长判断整号类型
print("\n=== 账号级：均时长 vs 账号是否偏视觉 ===")
by_acct = {}
for r in rows:
    by_acct.setdefault(r["acct"], []).append(r)
print(f"{'账号':<26} {'均时长':>6} {'均字/秒':>7} {'视觉占比':>8} {'判定':>6}")
print("-" * 62)
for a, rs in sorted(by_acct.items(), key=lambda kv: statistics.mean(x["dur"] for x in kv[1])):
    md = statistics.mean(r["dur"] for r in rs)
    mc = statistics.mean(r["cps"] for r in rs)
    vshare = sum(1 for r in rs if r["label"] == "visual") / len(rs)
    verdict = "视觉" if vshare >= 0.5 else ("混合" if vshare >= 0.25 else "口播")
    print(f"{a[:24]:<26} {md:>6.0f} {mc:>7.2f} {vshare*100:>7.0f}% {verdict:>6}")
