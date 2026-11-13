# -*- coding: utf-8 -*-
"""核验 1w–10w 区间候选：按候选所属主题使用对应的相关性判定面料。

不同主题判「他是不是这个领域的号」，而不是统一看 AI 浓度。
输出 config/candidates_mid_classified.tsv
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

TERMS = {
    "科研": ("科研", "科学", "论文", "实验", "物理", "化学", "材料", "分子", "蛋白",
             "基因", "细胞", "生物", "药物", "医学", "天文", "气象", "气候", "地球",
             "遥感", "仿真", "模拟", "计算", "数学", "晶体", "催化", "实验室", "学术",
             "期刊", "模型", "算法", "ai", "机器学习", "深度学习", "数据集"),
    "创客": ("diy", "创客", "极客", "maker", "硬件", "电路", "单片机", "树莓派",
             "arduino", "3d打印", "焊", "改装", "拆解", "发明", "自制", "电子",
             "机械", "模型", "动手", "手工", "开源硬件"),
    "黑客": ("黑客", "安全", "渗透", "攻防", "漏洞", "逆向", "ctf", "白帽", "红队",
             "加密", "木马", "网络安全", "信息泄露", "hack"),
    "机器人": ("机器人", "具身", "机械臂", "四足", "人形", "无人机", "slam", "ros",
               "视觉", "传感器", "运动控制", "伺服", "电机", "自动驾驶"),
    "炒股投资": ("股", "基金", "投资", "理财", "财报", "涨", "跌", "市场", "经济",
                 "板块", "仓位", "牛市", "熊市", "a股", "港股", "美股", "收益",
                 "量化", "k线"),
    "局势": ("局势", "国际", "地缘", "中美", "俄乌", "中东", "军事", "战争", "政治",
             "外交", "大国", "博弈", "制裁", "台海", "欧洲", "美国"),
    "科技": ("科技", "数码", "产品", "评测", "测评", "芯片", "手机", "电脑", "相机",
             "硬件", "黑科技", "新品", "发布会", "智能", "创新", "未来", "体验"),
    "商业": ("创业", "商业", "公司", "生意", "品牌", "融资", "营销", "变现", "副业",
             "一人公司", "出海", "产品", "市场", "增长", "私域", "就业"),
    "ai": ("ai", "人工智能", "大模型", "aigc", "智能体", "agent", "gpt", "claude",
           "deepseek", "机器学习", "提示词", "prompt", "copilot", "cursor",
           "生成", "模型", "算法"),
}


def score_titles(titles, themes):
    """返回该号在其所属主题上的最高命中比例。"""
    if not titles:
        return 0.0, ""
    best, best_theme = 0.0, ""
    for th in themes or ["科技"]:
        terms = TERMS.get(th, TERMS["科技"])
        hit = sum(1 for t in titles if any(k in t.lower() for k in terms))
        r = hit / len(titles)
        if r > best:
            best, best_theme = r, th
    return best, best_theme


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", default=str(CONF / "candidates_mid.tsv"), dest="inp")
    ap.add_argument("--out", default=str(CONF / "candidates_mid_classified.tsv"))
    ap.add_argument("--ps", type=int, default=12)
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
        if len(c) < 5:
            continue
        try:
            cands.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                          "themes": [x for x in c[3].split(",") if x],
                          "kws": c[4] if len(c) > 4 else "",
                          "sign": c[5] if len(c) > 5 else ""})
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
            vids = list_videos(b, c["mid"], c["name"], a.ps, "pubdate", "auto")
            titles = [v.get("title") or "" for v in vids]
        except (Throttled, Budget) as e:
            print(f"[STOP] {c['name']}: {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  ! {c['name']}: {str(e)[:45]}", file=sys.stderr)
        score, theme = score_titles(titles, c["themes"])
        tier = ("垂直" if score >= 0.5 else
                "半相关" if score >= 0.3 else "无关")
        out.append({**c, "sampled": len(titles), "score": round(score, 2),
                    "tier": tier, "theme": theme or (c["themes"][0] if c["themes"] else "科技"),
                    "sample": titles[:4]})
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(todo)}", file=sys.stderr)
        time.sleep(0.7)

    order = {"垂直": 0, "半相关": 1, "无关": 2}
    out.sort(key=lambda x: (order[x["tier"]], -x["fans"]))
    with Path(a.out).open("w", encoding="utf-8") as f:
        f.write("mid\t名称\t粉丝\t等级\t相关度\t主题\t抽样\t命中词\t样例\n")
        for o in out:
            f.write(f'{o["mid"]}\t{o["name"]}\t{o["fans"]}\t{o["tier"]}\t'
                    f'{o["score"]}\t{o["theme"]}\t{o["sampled"]}\t{o["kws"]}\t'
                    f'{" | ".join(o["sample"][:2])}\n')

    cnt = Counter(o["tier"] for o in out)
    print(f"\n核验完成 {len(out)}：{dict(cnt)}", file=sys.stderr)
    keep = [o for o in out if o["tier"] in ("垂直", "半相关")]
    print(f"通过 {len(keep)}，按主题:", dict(Counter(o["theme"] for o in keep)),
          file=sys.stderr)
    for tier in ("垂直", "半相关"):
        sub = [o for o in out if o["tier"] == tier]
        print(f"\n=== {tier} ({len(sub)}) ===", file=sys.stderr)
        for o in sub[:15]:
            print(f'  {o["fans"]/1e4:>5.1f}万 {o["score"]:.2f} [{o["theme"]}] '
                  f'{o["name"]}', file=sys.stderr)
    b.persist_cred()


if __name__ == "__main__":
    main()
