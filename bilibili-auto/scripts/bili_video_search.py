# -*- coding: utf-8 -*-
"""bili_video_search.py — B站「视频搜索反查 UP 主」。

与账号搜索（bili_user，匹配昵称+简介）不同，本脚本搜的是**视频**，
从视频作者反推 UP 主。视频标题包含关键词的概率远高于简介，
对商业/财经/局势/科技这类「主题词不进简介」的领域效果更好。

输出 config/candidates_video.tsv：mid  名称  粉丝  命中词  视频标题

用法：
  python bili_video_search.py --groups 商业,局势 --pages 2
  python bili_video_search.py --all
"""
import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, read_cred, Throttled, Budget  # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"
OUT = CONF / "candidates_video.tsv"

# 视频标题导向的关键词（不是简介词）
GROUPS = {
    "商业": [
        "AI创业", "创业经历", "创业亏了", "普通人创业", "小本生意", "摆摊月入",
        "商业模式拆解", "赚钱逻辑", "公司怎么赚钱", "行业分析", "生意经",
        "一人公司", "副业怎么做", "开店经验", "实体店怎么做",
    ],
    "财经": [
        "财经解读", "看懂经济", "经济下行", "美联储加息", "房价分析",
        "人口危机", "行业寒冬", "裁员潮", "消费降级", "产业链分析",
        "财报解读", "公司估值", "货币政策",
    ],
    "局势": [
        "国际局势分析", "中美关系", "地缘政治", "俄乌最新", "中东局势",
        "大国博弈", "世界格局变化", "军事分析", "台海局势", "时政解读",
    ],
    "科技": [
        "芯片突破", "光刻机", "量子计算", "核聚变进展", "SpaceX星舰",
        "人形机器人", "具身智能", "自动驾驶落地", "半导体产业",
        "脑机接口", "商业航天",
    ],
    "科技创客": [
        "自制机器人", "DIY机器人", "开源硬件", "单片机项目", "树莓派项目",
        "Arduino项目", "电路设计", "机械臂制作", "AI Agent搭建",
        "本地大模型部署", "3D打印教程", "ESP32项目",
    ],
    "科普": [
        "硬核科普", "原理讲解", "深度访谈", "人物专访", "对话创始人",
    ],
    "ai": [
        "AI工具实测", "AI工作流", "大模型实测", "AI编程实战", "智能体开发",
    ],
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
    ap.add_argument("--groups", default="", help="逗号分隔，默认全部")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--pace", type=float, default=1.4)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--min-fans", type=int, default=1000, dest="min_fans",
                    help="反查阶段先收宽，后续按主题再卡")
    a = ap.parse_args()

    picked = list(GROUPS) if (a.all or not a.groups) else \
        [g.strip() for g in a.groups.split(",") if g.strip() in GROUPS]

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=read_cred())
    b.preflight()
    known = load_known()

    hits = defaultdict(lambda: {"name": None, "kws": set(), "titles": []})
    total = sum(len(GROUPS[g]) * a.pages for g in picked)
    done = 0

    for g in picked:
        for kw in GROUPS[g]:
            for page in range(1, a.pages + 1):
                done += 1
                try:
                    r = b.get("x/web-interface/wbi/search/type",
                              {"search_type": "video", "keyword": kw,
                               "page": page, "order": "click"}, tries=2)
                except (Throttled, Budget) as e:
                    print(f"[STOP] {kw}: {e}", file=sys.stderr)
                    raise SystemExit(2)
                except Exception as e:
                    print(f"  ! {kw} p{page}: {str(e)[:60]}", file=sys.stderr)
                    continue
                res = (r.get("data") or {}).get("result") or []
                for v in res:
                    mid = v.get("mid")
                    if not mid:
                        continue
                    e = hits[mid]
                    e["name"] = v.get("author") or e["name"]
                    e["kws"].add(kw)
                    t = (v.get("title") or "").replace("<em class=\"keyword\">", "") \
                        .replace("</em>", "").strip()
                    if t and len(e["titles"]) < 3:
                        e["titles"].append(t[:60])
                print(f"  [{g}] {kw} p{page}: {len(res)} 条 | 累计 UP {len(hits)} "
                      f"| {done}/{total}", file=sys.stderr)
                time.sleep(b.pace)

    # 补粉丝数（card 接口，去重后逐个查）
    print(f"\n反查到 {len(hits)} 个 UP，开始补粉丝数…", file=sys.stderr)
    rows = []
    for i, (mid, e) in enumerate(hits.items(), 1):
        fans = 0
        try:
            r = b.get("x/web-interface/card", {"mid": mid}, tries=2)
            card = (r.get("data") or {}).get("card") or {}
            fans = card.get("fans") or 0
            e["name"] = card.get("name") or e["name"]
        except Exception:
            pass
        if fans >= a.min_fans:
            rows.append({"mid": mid, "name": e["name"], "fans": fans,
                         "kws": sorted(e["kws"]),
                         "titles": e["titles"],
                         "in_roster": mid in known})
        if i % 25 == 0:
            print(f"  粉丝查询 {i}/{len(hits)}", file=sys.stderr)
        time.sleep(b.pace)

    rows.sort(key=lambda x: -x["fans"])
    with OUT.open("w", encoding="utf-8") as f:
        f.write("mid\t名称\t粉丝\t命中词\t视频标题\t已在名单\n")
        for r in rows:
            f.write(f'{r["mid"]}\t{r["name"]}\t{r["fans"]}\t'
                    f'{",".join(r["kws"])}\t{" | ".join(r["titles"])}\t'
                    f'{"是" if r["in_roster"] else "否"}\n')

    new = [r for r in rows if not r["in_roster"]]
    print(f"\n完成：候选 {len(rows)} 个（其中名单外 {len(new)} 个）→ {OUT}")
    print("\n名单外 Top 30（按粉丝）：")
    for r in new[:30]:
        print(f'  {r["fans"]/1e4:>8.1f}万  {r["name"][:22]:<24} [{",".join(r["kws"][:3])}]')


if __name__ == "__main__":
    main()
