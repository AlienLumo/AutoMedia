# -*- coding: utf-8 -*-
"""核验候选号是否真的做 AI 内容：抽样最近 15 条投稿标题，统计 AI 相关比例。

输出 config/candidates_classified.tsv
    垂直 >= 40%   |  半相关 15-40%  |  无关 < 15%
"""
import json
import sys
import time
from pathlib import Path
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, read_cred, Throttled, Budget   # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"
CAND = CONF / "candidates_raw.tsv"
OUT = CONF / "candidates_classified.tsv"
ROSTER = CONF / "ups.tsv.bak"   # 合并前的原始 87 个，用于区分新增

AI_RE = ("ai", "人工智能", "大模型", "aigc", "智能体", "agent", "gpt", "claude",
         "deepseek", "chatgpt", "机器学习", "深度学习", "算法", "神经网络",
         "提示词", "prompt", "comfyui", "midjourney", "openai", "模型",
         "多模态", "算力", "具身", "机器人", "自动化", "copilot", "cursor")


def is_ai_title(t):
    s = t.lower()
    return any(k in s for k in AI_RE)


def main():
    known = set()
    for line in ROSTER.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        try:
            known.add(int(line.split("\t")[0]))
        except ValueError:
            pass

    cands = []
    for line in CAND.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 3:
            continue
        try:
            mid = int(c[0]); fans = int(c[2])
        except ValueError:
            continue
        cands.append({"mid": mid, "name": c[1], "fans": fans,
                      "kws": c[3] if len(c) > 3 else "",
                      "sign": c[4] if len(c) > 4 else ""})
    todo = [c for c in cands if c["mid"] not in known]
    print(f"待核验 {len(todo)} 个（名单内 {len(cands)-len(todo)} 个已跳过）",
          file=sys.stderr)

    b = Bili(pace=0.9, cooldown=60, cookies=read_cred())
    b.preflight()

    out = []
    for i, c in enumerate(todo):
        titles = []
        try:
            r = b.get("x/web-interface/wbi/search/type",
                      {"search_type": "video", "keyword": c["name"],
                       "page": 1, "order": "pubdate"}, tries=2)
            res = (r.get("data") or {}).get("result") or []
            for v in res:
                if v.get("mid") != c["mid"]:
                    continue
                t = v.get("title") or ""
                for tag in ('<em class="keyword">', "</em>"):
                    t = t.replace(tag, "")
                titles.append(t)
        except (Throttled, Budget) as e:
            print(f"[STOP] {c['name']}: {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  ! {c['name']}: {str(e)[:50]}", file=sys.stderr)

        n = len(titles)
        hit = sum(1 for t in titles if is_ai_title(t))
        ratio = hit / n if n else 0
        tier = ("垂直" if ratio >= 0.4 else
                "半相关" if ratio >= 0.15 else "无关")
        out.append({**c, "sampled": n, "ai_videos": hit,
                    "ratio": round(ratio, 2), "tier": tier,
                    "sample_titles": titles[:6]})
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(todo)}", file=sys.stderr)
        time.sleep(0.7)

    order = {"垂直": 0, "半相关": 1, "无关": 2}
    out.sort(key=lambda x: (order[x["tier"]], -x["fans"]))
    with OUT.open("w", encoding="utf-8") as f:
        f.write("mid\t名称\t粉丝\t等级\tAI视频比例\t抽样数\t命中关键词\t样例标题\n")
        for o in out:
            f.write(f'{o["mid"]}\t{o["name"]}\t{o["fans"]}\t{o["tier"]}\t'
                    f'{o["ratio"]}\t{o["sampled"]}\t{o["kws"]}\t'
                    f'{" | ".join(o["sample_titles"][:2])}\n')

    from collections import Counter
    cnt = Counter(o["tier"] for o in out)
    print(f"\n核验完成 {len(out)} 个：{dict(cnt)}", file=sys.stderr)
    for tier in ("垂直", "半相关", "无关"):
        sub = [o for o in out if o["tier"] == tier]
        print(f"\n=== {tier} ({len(sub)}) ===", file=sys.stderr)
        for o in sub[:12]:
            print(f'  {o["fans"]/1e4:>7.1f}万 {o["ratio"]*100:>3.0f}% '
                  f'{o["name"]}', file=sys.stderr)
    b.persist_cred()


if __name__ == "__main__":
    main()
