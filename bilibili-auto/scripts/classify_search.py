# -*- coding: utf-8 -*-
"""核验账号级扩搜的候选：抽样最近 15 条投稿标题，判断科技/AI/创客/创业相关性。

与 classify_candidates.py 的区别：判定面料更宽（不只看 AI），因为本轮覆盖
科技产品/创客/机器人/创业等主题。
输出 config/candidates_search_classified.tsv
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
            "deepseek", "chatgpt", "机器学习", "深度学习", "神经网络", "提示词",
            "prompt", "comfyui", "midjourney", "openai", "多模态", "算力", "具身",
            "copilot", "cursor", "生成式")
TECH_TERMS = ("科技", "数码", "硬件", "芯片", "机器人", "机械臂", "传感器", "无人机",
              "3d打印", "开源", "diy", "创客", "极客", "发明", "电路", "单片机",
              "树莓派", "arduino", "编程", "代码", "开发", "产品", "评测", "测评",
              "黑科技", "前沿", "未来", "创新", "创业", "公司", "独立开发", "项目",
              "工程", "实验", "物理", "化学", "生物", "交互", "设计", "艺术",
              "自动化", "智能", "算法", "模型", "软件", "工具", "app")


def relevance(title):
    s = title.lower()
    a = any(t in s for t in AI_TERMS)
    t = any(x in s for x in TECH_TERMS)
    if a and t:
        return 1.0
    if a:
        return 0.8
    if t:
        return 0.55
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", default=str(CONF / "candidates_search.tsv"),
                    dest="inp")
    ap.add_argument("--out", default=str(CONF / "candidates_search_classified.tsv"))
    ap.add_argument("--pace", type=float, default=1.0)
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
            mid = int(c[0]); fans = int(c[2])
        except ValueError:
            continue
        cands.append({"mid": mid, "name": c[1], "fans": fans,
                      "kws": c[3] if len(c) > 3 else "",
                      "sign": c[4] if len(c) > 4 else ""})
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
        tier = ("垂直" if score >= 0.42 else
                "半相关" if score >= 0.2 else "无关")
        out.append({**c, "sampled": n, "score": round(score, 2), "tier": tier,
                    "sample": titles[:5]})
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(todo)}", file=sys.stderr)
        time.sleep(0.75)

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
        for o in sub[:20]:
            print(f'  {o["fans"]/1e4:>7.1f}万 {o["score"]:.2f} {o["name"]}',
                  file=sys.stderr)
    b.persist_cred()


if __name__ == "__main__":
    main()
