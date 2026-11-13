# -*- coding: utf-8 -*-
"""titles.py — 标题句式与用词统计（平台无关）。"""
import re
from collections import Counter

STOP = set("的了是我你他她它这那有在和就都不也一个我们你们他们可以没有如果但是所以因为并且以及对于关于"
           "这个那个什么怎么如何为什么真的其实已经还是可能自己现在知道觉得应该时候问题东西事情就是")

PATTERNS = {
    "只要…就": r"只要",
    "最…（最可怕/最终/最后）": r"最(可怕|终|后|大|小)",
    "反而/却/竟": r"(反而|却|竟)",
    "当…（条件开场）": r"^当",
    "为什么/怎么": r"(为什么|怎么)",
    "不是…而是": r"不是.*而是",
    "问号": r"[？?]",
    "句号结尾": r"。$",
    "含数字": r"\d",
    "第二人称(你)": r"你",
    "否定(别/不/没)": r"(别|不|没)",
}


def build_titles(works):
    titles = [w.get("title") or "" for w in works if w.get("title")]
    if not titles:
        return {}
    lens = [len(t) for t in titles]
    pat = {k: sum(1 for t in titles if re.search(p, t)) for k, p in PATTERNS.items()}
    cnt = Counter()
    for t in titles:
        seg = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", t)
        for part in seg.split():
            for n in (2, 3, 4):
                for i in range(len(part) - n + 1):
                    g = part[i:i + n]
                    if g in STOP:
                        continue
                    cnt[g] += 1
    return {
        "count": len(titles),
        "len_min": min(lens), "len_median": sorted(lens)[len(lens) // 2], "len_max": max(lens),
        "patterns": pat,
        "top_terms": [g for g, c in cnt.most_common(40) if c >= 2][:25],
        "samples": titles[:10],
    }
