# -*- coding: utf-8 -*-
"""清理已采数据里的非中文字幕文件，只保留中文（ai-zh / zh-CN 等）。

用法：
  python cleanup_nonzh_subs.py            # 先看会删多少（dry-run）
  python cleanup_nonzh_subs.py --apply    # 真正删除
"""
import argparse
import re
from pathlib import Path
from _paths import PROJECT

PROJ = PROJECT
DATA = PROJ / "1AMdata"

PAT = re.compile(r"^subtitle\.([A-Za-z0-9\-_]+)\.(srt|txt)$")


def is_zh(lang):
    toks = [t for t in lang.lower().replace("_", "-").split("-") if t]
    return "zh" in toks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正删除（默认只统计）")
    a = ap.parse_args()

    keep, drop = [], []
    for p in DATA.rglob("subtitle.*"):
        m = PAT.match(p.name)
        if not m:
            continue
        (keep if is_zh(m.group(1)) else drop).append(p)

    keep_files = len(keep) // 2
    keep_bytes = sum(p.stat().st_size for p in keep)
    drop_bytes = sum(p.stat().st_size for p in drop)
    print(f"中文文件: {len(keep)} 个 ({keep_bytes/1024/1024:.1f} MB)，覆盖 {keep_files} 个视频·语言")
    print(f"非中文文件: {len(drop)} 个 ({drop_bytes/1024/1024:.1f} MB)")
    from collections import Counter
    langs = Counter(PAT.match(p.name).group(1) for p in drop)
    print("将删除的语言分布:")
    for lang, n in langs.most_common():
        print(f"   {lang}: {n}")

    if not a.apply:
        print(f"\n[dry-run] 预计释放 {drop_bytes/1024/1024:.1f} MB。加 --apply 执行删除。")
        return

    n = 0
    for p in drop:
        try:
            p.unlink()
            n += 1
        except OSError as e:
            print(f"  删除失败 {p.name}: {e}")
    print(f"\n已删除 {n} 个文件，释放 {drop_bytes/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
