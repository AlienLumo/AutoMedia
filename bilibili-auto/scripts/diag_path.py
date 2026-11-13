# -*- coding: utf-8 -*-
"""Reproduce the meta.json write failure on the two errored videos."""
import sys, json, traceback
from pathlib import Path
from _paths import DATA, SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from bili_subs import Bili, read_cred, safe_name

b = Bili(pace=1.0, cooldown=30, cookies=read_cred())
b.preflight()

for bvid, topic, upname, mid in [
    ("BV1FKpB6AEsP", "AI发展", "图灵的猫", 371846699),
    ("BV14kJv6FE9F", "Skill", "Xuan_酱", 14848367),
]:
    print(f"\n=== {bvid} ===")
    try:
        v = b.get("x/web-interface/view", {"bvid": bvid})["data"]
    except Exception as e:
        print("  view failed:", e)
        continue
    title = v["title"]
    print(f"  title: {title!r}")
    print(f"  title len: {len(title)}, codepoints: {[c for c in title if ord(c) > 127][:12]}")
    sname = safe_name(title, 40)
    print(f"  safe_name: {sname!r}  len={len(sname)}")
    vdir = (DATA / "bilibili" / topic
            / f"{safe_name(upname, 30)}_{mid}" / f"{bvid}_{sname}")
    full = vdir / "meta.json"
    print(f"  full path: {str(full)}")
    print(f"  path len: {len(str(full))}")
    try:
        vdir.mkdir(parents=True, exist_ok=True)
        full.write_text(json.dumps({"bvid": bvid, "title": title},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        print("  WRITE OK")
    except Exception:
        print("  WRITE FAILED:")
        traceback.print_exc()
    # 检查目录里实际有什么
    try:
        print("  dir exists:", vdir.exists())
        if vdir.exists():
            for p in vdir.iterdir():
                print("     -", repr(p.name), "len=", len(p.name))
    except Exception as e:
        print("  listdir failed:", e)
