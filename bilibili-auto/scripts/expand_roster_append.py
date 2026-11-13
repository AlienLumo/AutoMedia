# -*- coding: utf-8 -*-
"""把 406 个新账号追加入 B站 采集名单（ups.tsv + prefix_map.tsv）。

- 保留原 420 个不动
- 新增 406 个，前缀来自 final_roster_final.tsv
- 备份原文件
"""
import shutil
from pathlib import Path
from _paths import SKILL

CONF = SKILL / "config"
UPS = CONF / "ups.tsv"
PMAP = CONF / "prefix_map.tsv"

# 读取新名单
new = []
for ln in (CONF / "final_roster_final.tsv").read_text(encoding="utf-8").splitlines()[1:]:
    if not ln.strip():
        continue
    c = ln.split("\t")
    if len(c) < 5:
        continue
    try:
        new.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                    "prefix": c[3], "grade": c[4]})
    except ValueError:
        continue
print(f"新名单 {len(new)} 个")

# 读旧名单
old_mids = set()
for ln in UPS.read_text(encoding="utf-8").splitlines():
    if ln.strip() and not ln.startswith("#"):
        try:
            old_mids.add(int(ln.split("\t")[0]))
        except ValueError:
            pass

fresh = [x for x in new if x["mid"] not in old_mids]
print(f"旧名单 {len(old_mids)} 个，真正新增 {len(fresh)} 个")

# 备份
shutil.copy2(UPS, UPS.with_suffix(".tsv.bak_before_expand"))
shutil.copy2(PMAP, PMAP.with_suffix(".tsv.bak_before_expand"))
print("已备份 ups.tsv / prefix_map.tsv")

# 追加 ups.tsv（格式：mid\t名称\t方向）
with UPS.open("a", encoding="utf-8") as f:
    for x in fresh:
        f.write(f'{x["mid"]}\t{x["name"]}\t使用\n')

# 追加 prefix_map.tsv（格式：mid\t名称\t前缀\t粉丝数）
with PMAP.open("a", encoding="utf-8") as f:
    for x in fresh:
        f.write(f'{x["mid"]}\t{x["name"]}\t{x["prefix"]}\t{x["fans"]}\n')

# 校验
n_ups = sum(1 for ln in UPS.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#"))
n_pm = sum(1 for ln in PMAP.read_text(encoding="utf-8").splitlines()
           if ln.strip() and not ln.startswith("#"))
print(f"\n追加后：ups.tsv {n_ups} 个，prefix_map.tsv {n_pm} 个")

# 前缀分布
from collections import Counter
cnt = Counter()
for ln in PMAP.read_text(encoding="utf-8").splitlines():
    if ln.strip() and not ln.startswith("#"):
        c = ln.split("\t")
        if len(c) >= 3:
            cnt[c[2]] += 1
print("\n全量前缀分布（含旧 420）：")
for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
    print(f"  {k:<10} {v}")
