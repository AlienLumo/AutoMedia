# -*- coding: utf-8 -*-
"""直接验证 collect_subs 的 sub_langs 过滤是否生效（不依赖运行中的 chunk）。"""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import DATA, SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from bili_subs import Bili, read_cred
from bili_collect import collect_subs

b = Bili(pace=1.2, cooldown=60, cookies=read_cred())
b.preflight()

# 找一个有字幕的 meta.json
meta = None
for p in DATA / "bilibili".rglob("meta.json"):
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
        if m.get("aid") and m.get("cid"):
            meta = m
            break
    except Exception:
        continue
print("测试视频:", meta["bvid"], meta["title"][:30])

with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    # A) 不过滤
    files_all, n_all = collect_subs(b, meta["aid"], meta["cid"], d, "all")
    print(f"\n不过滤: 可用字幕 {n_all} 种，下载 {len(files_all)} 个")
    for f in files_all:
        print("   -", f)
    # B) 只中文
    files_zh, n_zh = collect_subs(b, meta["aid"], meta["cid"], d, "zhonly", sub_langs=["zh"])
    print(f"\n仅中文: 可用字幕 {n_zh} 种，下载 {len(files_zh)} 个")
    for f in files_zh:
        print("   -", f)
    print("\n实际落盘文件:")
    for p in sorted(d.iterdir()):
        print("   ", p.name)
