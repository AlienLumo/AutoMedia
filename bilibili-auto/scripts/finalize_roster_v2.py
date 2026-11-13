# -*- coding: utf-8 -*-
"""finalize_roster_v2.py — 由采样核验结果生成最终采集名单（新口径）。

规则：
  ok(≥40%)    直接收录（A）
  mid(15-40%) 收录但标为复核档（B）
  bad(<15%)   淘汰
  数码评测：只取粉丝 Top 5
  创客 1-10万粉：限 100 个
"""
import json
from collections import Counter
from pathlib import Path
from _paths import SKILL

CONF = SKILL / "config"
PROG = CONF / "sample_progress.json"
OUT = CONF / "final_roster_final.tsv"
QUEUE1 = CONF / "queue_new_p1.txt"
QUEUE2 = CONF / "queue_new_p2.txt"

EXTRA_INST = ["联合国", "NASA", "哔哩哔哩", "弹幕网", "欧盟", "世卫",
              "教科文", "红十字会", "中科院", "中国航天", "国家航天",
              "航天局", "气象局", "地震局", "博物馆", "美术馆", "图书馆",
              "档案馆", "国资委", "税务局", "统计局"]

prog = json.loads(PROG.read_text(encoding="utf-8"))
rows = list(prog.values())
print(f"核验记录 {len(rows)}")

ok = [r for r in rows if r.get("verdict") == "ok"]
mid = [r for r in rows if r.get("verdict") == "mid"]
print(f"  ok {len(ok)} / mid {len(mid)}")

for r in ok:
    r["grade"] = "A"
for r in mid:
    r["grade"] = "B"

def _bad_inst(name):
    return any(w in (name or "") for w in EXTRA_INST)

ok = [r for r in ok if not _bad_inst(r.get("name"))]
mid = [r for r in mid if not _bad_inst(r.get("name"))]
print(f"  额外剔除机构号后 ok {len(ok)} / mid {len(mid)}")

picked = ok + mid

# 数码评测 Top5
digital = sorted([r for r in picked if r.get("prefix") == "数码评测"],
                 key=lambda x: -(x.get("fans") or 0))
keep_digital = digital[:5]
picked = [r for r in picked if r.get("prefix") != "数码评测"] + keep_digital
print(f"  数码评测保留 {len(keep_digital)}（原 {len(digital)}）")

# 创客小号限 100
low_makers = sorted([r for r in picked
                     if r.get("prefix") == "创客" and (r.get("fans") or 0) < 100000],
                    key=lambda x: -(x.get("fans") or 0))
keep_low = {id(r) for r in low_makers[:100]}
picked = [r for r in picked
          if not (r.get("prefix") == "创客" and (r.get("fans") or 0) < 100000)
          or id(r) in keep_low]
print(f"  小号创客保留 {min(100, len(low_makers))}/{len(low_makers)}")

picked.sort(key=lambda x: (x.get("prefix") or "", -(x.get("fans") or 0)))

with OUT.open("w", encoding="utf-8", newline="") as f:
    f.write("mid\t名称\t粉丝\t前缀\t档位\t主题占比\t命中/样本\n")
    for r in picked:
        f.write(f'{r["mid"]}\t{r["name"]}\t{r.get("fans") or 0}\t{r.get("prefix")}\t'
                f'{r["grade"]}\t{r.get("ratio")}\t{r.get("hit")}/{r.get("n")}\n')

print(f"\n最终名单: {len(picked)}")
print("按前缀:", dict(Counter(r.get("prefix") for r in picked)))
print("按档位:", dict(Counter(r["grade"] for r in picked)))

# 拆两份采集队列（按粉丝降序交替）
picked.sort(key=lambda x: -(x.get("fans") or 0))
for p in range(2):
    sub = [r for i, r in enumerate(picked) if i % 2 == p]
    f = QUEUE1 if p == 0 else QUEUE2
    f.write_text("\n".join(f'https://space.bilibili.com/{r["mid"]}' for r in sub) + "\n",
                 encoding="utf-8")
    print(f"  队列{p+1}: {len(sub)} 个 → {f.name}")

print(f"\n输出: {OUT}")
print("\n名单 Top 15：")
for r in picked[:15]:
    print(f'  {r.get("fans",0)/1e4:>8.1f}万 [{r.get("prefix")}] {r["name"][:20]:<22} '
          f'{r["grade"]} 占比{r.get("ratio")}')

est = len(picked) / 6.7  # B站实测 6.7 个账号/小时
print(f"\n预估采集: {len(picked)} 个账号 ≈ {est:.0f} 小时（约 {est/24:.1f} 天）")
