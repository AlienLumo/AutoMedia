# -*- coding: utf-8 -*-
"""把 1AMdata/bilibili/<主题>/<UP名>_<mid>/ 扁平化为
   1AMdata/bilibili/<前缀>_<UP名>_<粉丝量>/<bvid>_<标题>/
"""
import json
import shutil
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
ROOT = PROJ / "1AMdata" / "bilibili"
PMAP = SKILL / "config" / "prefix_map.tsv"


def load_map():
    m = {}
    for line in PMAP.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c = line.split("\t")
        if len(c) < 4:
            continue
        try:
            mid = int(c[0])
        except ValueError:
            continue
        m[mid] = {"name": c[1], "prefix": c[2], "fans": int(c[3] or 0)}
    return m


def fmt_fans(n):
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


def main():
    pmap = load_map()
    moved, merged, skipped = [], [], []
    for topic_dir in [p for p in ROOT.iterdir() if p.is_dir()]:
        for up_dir in [p for p in topic_dir.iterdir() if p.is_dir()]:
            # 从目录名尾部取 mid
            try:
                mid = int(up_dir.name.rsplit("_", 1)[-1])
            except ValueError:
                skipped.append((str(up_dir.relative_to(ROOT)), "无法解析 mid"))
                continue
            info = pmap.get(mid)
            if not info:
                skipped.append((str(up_dir.relative_to(ROOT)), f"prefix_map 无 mid={mid}"))
                continue
            new_name = f'{info["prefix"]}_{info["name"]}_{fmt_fans(info["fans"])}'
            target = ROOT / new_name
            if target.exists():
                # 已存在则合并视频子目录
                for sub in up_dir.iterdir():
                    dst = target / sub.name
                    if dst.exists():
                        continue
                    shutil.move(str(sub), str(dst))
                up_dir.rmdir()
                merged.append(new_name)
            else:
                shutil.move(str(up_dir), str(target))
                moved.append(new_name)
        try:
            topic_dir.rmdir()
        except OSError:
            pass

    print(f"迁移 {len(moved)} 个 UP 目录")
    for n in moved:
        print(f"  -> {n}")
    if merged:
        print(f"合并 {len(merged)} 个（目标已存在）")
    if skipped:
        print("跳过:")
        for n, why in skipped:
            print(f"  - {n}: {why}")

    # 统计
    ups = [p for p in ROOT.iterdir() if p.is_dir()]
    vids = [p for p in ROOT.rglob("BV*") if p.is_dir() and (p / "meta.json").exists()]
    print(f"\n扁平化后：{len(ups)} 个 UP 目录，{len(vids)} 个视频目录")
    print("前缀分布:", end=" ")
    from collections import Counter
    c = Counter(p.name.split("_")[0] for p in ups)
    print(dict(c))


if __name__ == "__main__":
    main()
