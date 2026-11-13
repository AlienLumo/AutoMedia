# -*- coding: utf-8 -*-
"""账号级扩搜：用 bili_user 搜索（匹配昵称+简介），覆盖科技创业/创客/科技产品/
AI产品/开源/独立开发/机器人/创意科技 等主题。

数据源是「账号」而不是「视频」，噪声远低于视频榜反查。
慢速优先：默认 1.6s 间隔、90s 冷却。
输出 config/candidates_search.tsv：mid 名称 粉丝 命中词 简介
"""
import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, read_cred, Throttled, Budget   # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"

# 按目标大类组织关键词（账号级匹配：昵称/简介）
KEYWORDS = {
    "商业": ["科技创业", "AI创业", "硬科技创业", "创新创业", "创业项目", "科技公司",
             "初创企业", "独立创业", "一人公司", "超级个体", "商业创新", "产品创业",
             "出海创业", "创业", "独立开发者", "个人开发者", "Indie Hacker",
             "独立产品", "Side Project", "Build in Public", "小而美产品"],
    "创客": ["创客", "极客", "Maker", "DIY", "硬核DIY", "科技DIY", "创意发明",
             "个人发明家", "硬件开发", "开源硬件", "3D打印", "电子制作",
             "创意设计", "创意科技", "交互装置", "Creative Coding", "创意编程"],
    "机器人": ["具身智能", "机器人开发", "机器人DIY", "智能机器人", "人形机器人",
               "机械臂", "桌面机器人", "计算机视觉", "新型传感器"],
    "ai": ["AI产品", "AI应用", "AI工具", "AI神器", "AI工作流", "AI Agent",
           "智能体", "AI自动化", "AI编程", "AI开发", "AI开源项目", "AI效率工具",
           "AI落地", "AI产品测评", "AI创作", "生成艺术", "数字艺术", "Vibe Coding",
           "AI前沿", "大模型", "AIGC"],
    "科技": ["前沿科技", "黑科技", "未来科技", "科技实验", "科研成果转化", "科技新品",
             "数码科技", "科技产品", "创新产品", "产品测评", "科技好物",
             "众筹新品", "Kickstarter", "Product Hunt", "小众科技", "新奇产品",
             "未来产品", "科技科普", "趣味科学", "科学可视化", "交互艺术", "科技艺术"],
    "教程": ["AI教程", "编程教程", "技术教程", "训练营", "开发者工具",
             "GitHub项目", "开源项目", "开源软件", "个人项目"],
}


def load_known():
    mids = set()
    p = CONF / "ups.tsv"
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        try:
            mids.add(int(line.split("\t")[0]))
        except ValueError:
            pass
    return mids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--pace", type=float, default=1.6)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--out", default=str(CONF / "candidates_search.tsv"))
    a = ap.parse_args()

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=read_cred())
    b.preflight()
    known = load_known()

    hits = defaultdict(lambda: {"kws": set(), "name": None, "fans": 0, "sign": ""})
    total_kw = sum(len(v) for v in KEYWORDS.values())
    done = 0
    for bucket, kws in KEYWORDS.items():
        for kw in kws:
            for page in range(1, a.pages + 1):
                if page > 1 and done and kw not in ("AI产品", "创客", "机器人开发",
                                                    "科技产品", "创业", "AI工具"):
                    break
                try:
                    r = b.get("x/web-interface/wbi/search/type",
                              {"search_type": "bili_user", "keyword": kw,
                               "page": page, "order": "fans"}, tries=2)
                except (Throttled, Budget) as e:
                    print(f"[STOP] {kw}: {e}", file=sys.stderr)
                    raise SystemExit(2)
                except Exception as e:
                    print(f"  ! {kw}: {str(e)[:60]}", file=sys.stderr)
                    continue
                res = (r.get("data") or {}).get("result") or []
                for u in res:
                    mid = u.get("mid")
                    if not mid:
                        continue
                    e = hits[mid]
                    e["kws"].add(kw)
                    e["name"] = u.get("uname")
                    e["fans"] = u.get("fans") or 0
                    e["sign"] = (u.get("usign") or "").replace("\n", " ")[:100]
                done += 1
                print(f"  [{bucket}] {kw} p{page}: {len(res)} | 累计 {len(hits)} "
                      f"| {done}/{total_kw}", file=sys.stderr)
                time.sleep(b.pace)

    rows = []
    for mid, e in hits.items():
        if (e["fans"] or 0) < a.min_fans:
            continue
        rows.append({"mid": mid, "name": e["name"], "fans": e["fans"],
                     "kws": sorted(e["kws"]), "sign": e["sign"],
                     "known": mid in known})
    rows.sort(key=lambda x: -x["fans"])
    Path(a.out).write_text(
        "mid\t名称\t粉丝\t命中词\t简介\n" +
        "\n".join(f'{r["mid"]}\t{r["name"]}\t{r["fans"]}\t'
                  f'{",".join(r["kws"])}\t{r["sign"]}' for r in rows),
        encoding="utf-8")
    new = [r for r in rows if not r["known"]]
    print(f"\n搜索完成：命中账号 {len(hits)}，≥{a.min_fans} 粉 {len(rows)} 个，"
          f"新增 {len(new)} 个 -> {a.out}", file=sys.stderr)
    for r in new[:25]:
        print(f'  {r["fans"]/1e4:>7.1f}万 {r["name"]}  ← {",".join(r["kws"][:3])}',
              file=sys.stderr)
    b.persist_cred()


if __name__ == "__main__":
    main()
