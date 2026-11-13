# -*- coding: utf-8 -*-
"""汇总两个平台实际使用的主题关键词。"""
import ast
import json
import re
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT, SKILL

PROJ = PROJECT
BILI = SKILL.parent / "bilibili-auto/scripts"
DY = SKILL.parent / "douyin-auto"


def extract_dict_const(path, name):
    """从 py 文件里静态提取某个顶层 dict 常量。"""
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as e:
        return None, str(e)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    try:
                        return ast.literal_eval(node.value), None
                    except Exception as e:
                        return None, str(e)
    return None, "not found"


def extract_list_const(path, name):
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as e:
        return None, str(e)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    try:
                        return ast.literal_eval(node.value), None
                    except Exception as e:
                        return None, str(e)
    return None, "not found"


print("=" * 72)
print("【B站】名单前缀分布")
print("=" * 72)
cnt = Counter()
total = 0
for line in (SKILL.parent / "bilibili-auto/config/prefix_map.tsv").read_text(
        encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    p = line.split("\t")
    if len(p) >= 3:
        cnt[p[2]] += 1
        total += 1
for k, v in cnt.most_common():
    print(f"  {k:<10} {v}")
print(f"  合计 {total}")

print()
print("=" * 72)
print("【B站】建库时用过的关键词（来自各发现脚本）")
print("=" * 72)
for fname, cname in [("expand_accounts.py", "KEYWORDS"),
                     ("expand_ai4science.py", "KEYWORDS"),
                     ("expand_mid_tier.py", "KEYWORDS"),
                     ("discover_ai.py", "KEYWORDS")]:
    d, err = extract_dict_const(BILI / fname, cname)
    if d:
        n = sum(len(v) for v in d.values())
        print(f"\n--- {fname}（{len(d)} 组 / {n} 词）")
        for bucket, kws in d.items():
            print(f"  [{bucket}] {', '.join(kws)}")
    else:
        # 可能是 list 变量或名字不同
        for cand in ("KEYWORDS", "QUERIES", "KWS"):
            d2, e2 = extract_dict_const(BILI / fname, cand)
            if d2:
                print(f"\n--- {fname}.{cand}: {d2}")
                break
        else:
            print(f"\n--- {fname}: 未找到 dict 常量（{err}）")

print()
print("=" * 72)
print("【抖音】主题关键词（douyin_find_by_video.py THEMES）")
print("=" * 72)
d, err = extract_dict_const(DY / "scripts/douyin_find_by_video.py", "THEMES")
if d:
    tot = 0
    for theme, kws in d.items():
        tot += len(kws)
        print(f"\n  {theme}（{len(kws)} 词）")
        print(f"    {', '.join(kws)}")
    print(f"\n  合计 {len(d)} 个主题 / {tot} 个关键词")
else:
    print("  提取失败:", err)

print()
print("=" * 72)
print("【抖音】已完成搜索的关键词")
print("=" * 72)
st = json.loads((DY / "config/video_search_state.json").read_text(encoding="utf-8"))
done = st.get("done_keywords") or []
print(f"  已完成 {len(done)} 个: {', '.join(done)}")

print()
print("【抖音】按主题统计完成度")
for theme, kws in (d or {}).items():
    hit = [k for k in kws if k in done]
    miss = [k for k in kws if k not in done]
    print(f"  {theme:<8} {len(hit)}/{len(kws)}" + (f"  缺: {', '.join(miss)}" if miss else ""))
