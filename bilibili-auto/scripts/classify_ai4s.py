# -*- coding: utf-8 -*-
"""核验 AI4Science 候选：抽样最近 15 条投稿，判断「AI + 科学」相关性。

判定面料：必须同时命中「AI 类词」与「科学类词」之一，否则降级。
输出 config/candidates_ai4s_classified.tsv
"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, read_cred, Throttled, Budget   # noqa: E402
from bili_collect import list_videos   # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"

AI_TERMS = ("ai", "人工智能", "大模型", "aigc", "智能体", "agent", "gpt", "claude",
            "deepseek", "机器学习", "深度学习", "神经网络", "模型", "算法",
            "训练", "数据集", "开源", "多模态", "强化学习", "llm")
SCI_TERMS = ("科研", "科学", "论文", "实验", "物理", "化学", "材料", "分子",
             "蛋白", "基因", "基因组", "细胞", "生物", "药物", "制药", "医学",
             "天文", "天体", "气象", "气候", "地球", "遥感", "海洋", "环境",
             "仿真", "模拟", "计算", "数学", "统计", "晶体", "催化", "机器人",
             "自动化", "实验室", "学术", "期刊", "nature", "science", "cell",
             "博士", "研究生", "导师", "课题", "科研工具", "论文复现", "文献")


def relevance(title):
    s = title.lower()
    a = any(t in s for t in AI_TERMS)
    c = any(t in s for t in SCI_TERMS)
    if a and c:
        return 1.0          # AI + 科学，最贴合
    if c:
        return 0.6          # 纯科学内容（可能是科研号但 AI 少）
    if a:
        return 0.3          # 纯 AI，科学性弱
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", default=str(CONF / "candidates_ai4s.tsv"), dest="inp")
    ap.add_argument("--out", default=str(CONF / "candidates_ai4s_classified.tsv"))
    ap.add_argument("--pace", type=float, default=1.1)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--budget", type=int, default=0)
    a = ap.parse_args()

    known = set()
    for line in (CONF / "ups.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        try:
            known.add(int(line.split("\t")[0]))
        except ValueError:
            pass

    cands = []
    for line in Path(a.inp).read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 3:
            continue
        try:
            cands.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                          "kws": c[3] if len(c) > 3 else "",
                          "sign": c[4] if len(c) > 4 else ""})
        except ValueError:
            continue
    todo = [c for c in cands if c["mid"] not in known]
    print(f"待核验 {len(todo)}（名单内 {len(cands)-len(todo)} 跳过）", file=sys.stderr)

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=read_cred())
    b.preflight()

    out = []
    for i, c in enumerate(todo):
        titles = []
        try:
            vids = list_videos(b, c["mid"], c["name"], 15, "pubdate", "auto")
            titles = [v.get("title") or "" for v in vids]
        except (Throttled, Budget) as e:
            print(f"[STOP] {c['name']}: {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  ! {c['name']}: {str(e)[:50]}", file=sys.stderr)
        n = len(titles)
        score = sum(relevance(t) for t in titles) / n if n else 0
        tier = ("垂直" if score >= 0.55 else
                "半相关" if score >= 0.3 else "无关")
        out.append({**c, "sampled": n, "score": round(score, 2), "tier": tier,
                    "sample": titles[:6]})
        if (i + 1) % 15 == 0:
            print(f"  {i+1}/{len(todo)}", file=sys.stderr)
        time.sleep(0.8)

    order = {"垂直": 0, "半相关": 1, "无关": 2}
    out.sort(key=lambda x: (order[x["tier"]], -x["fans"]))
    with Path(a.out).open("w", encoding="utf-8") as f:
        f.write("mid\t名称\t粉丝\t等级\t相关度\t抽样\t命中词\t样例\n")
        for o in out:
            f.write(f'{o["mid"]}\t{o["name"]}\t{o["fans"]}\t{o["tier"]}\t'
                    f'{o["score"]}\t{o["sampled"]}\t{o["kws"]}\t'
                    f'{" | ".join(o["sample"][:2])}\n')

    cnt = Counter(o["tier"] for o in out)
    print(f"\n核验完成 {len(out)}：{dict(cnt)}", file=sys.stderr)
    for tier in ("垂直", "半相关"):
        sub = [o for o in out if o["tier"] == tier]
        print(f"\n=== {tier} ({len(sub)}) ===", file=sys.stderr)
        for o in sub[:25]:
            print(f'  {o["fans"]/1e4:>7.1f}万 {o["score"]:.2f} {o["name"]}',
                  file=sys.stderr)
    b.persist_cred()


if __name__ == "__main__":
    main()
