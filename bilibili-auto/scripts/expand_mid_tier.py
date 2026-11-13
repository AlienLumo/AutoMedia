# -*- coding: utf-8 -*-
"""1万–10万粉区间补搜（此前各主题的腰部账号）。

覆盖主题：AI4Science / 创客 / 黑客 / 机器人 / 炒股投资 / 局势 / 科技 / 商业 / ai
只用账号级搜索（匹配昵称+简介），因为它精度高；每个词翻多页以触达 1w–10w 区间。
输出 config/candidates_mid.tsv
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

THEMES = {
    "科研": ["AI4Science", "AI for Science", "AI科研", "科学智能", "智能科研",
             "AI科学家", "科学基础模型", "科研自动化", "科研工具", "科研助手",
             "AI物理", "AI化学", "AI材料", "AI生物", "计算生物学", "蛋白质结构预测",
             "AlphaFold", "生信", "AI制药", "分子动力学", "机器人科学家",
             "自主实验室", "AI气象", "AI天文", "AI遥感", "科研智能体",
             "AI Scientist", "论文复现", "文献综述", "科学计算", "仿真模拟"],
    "创客": ["创客", "极客", "Maker", "硬核DIY", "科技DIY", "创意发明", "发明家",
             "硬件开发", "开源硬件", "3D打印", "电子制作", "单片机", "树莓派",
             "Arduino", "机械键盘", "创意设计", "交互装置", "创客教育", "DIY电子"],
    "黑客": ["黑客", "网络安全", "渗透测试", "信息安全", "漏洞挖掘", "逆向工程",
             "CTF", "白帽子", "红队", "代码审计", "网络攻防"],
    "机器人": ["具身智能", "机器人开发", "机器人DIY", "智能机器人", "人形机器人",
               "机械臂", "四足机器人", "计算机视觉", "SLAM", "ROS", "无人机",
               "运动控制", "传感器融合"],
    "炒股投资": ["炒股", "股市", "A股", "基金", "理财", "投资", "财报分析",
                 "量化交易", "价值投资", "投资理财"],
    "局势": ["国际局势", "时政", "地缘政治", "中美关系", "国际关系", "军事",
             "宏观分析", "政经"],
    "科技": ["前沿科技", "黑科技", "未来科技", "科技新品", "数码科技", "产品测评",
             "科技测评", "科技好物", "数码测评", "小众科技", "科技实验",
             "科研成果转化", "创新产品", "未来产品", "科技公司"],
    "商业": ["科技创业", "AI创业", "硬科技创业", "创新创业", "创业项目",
             "初创企业", "独立创业", "一人公司", "超级个体", "商业创新",
             "产品创业", "出海创业", "独立开发者", "个人开发者", "独立产品",
             "Side Project", "Build in Public", "小而美产品", "创业",
             "商业模式", "商业思维"],
    "ai": ["AI产品", "AI工具", "AI应用", "AI工作流", "AI Agent", "智能体",
           "AI自动化", "AI编程", "AI开发", "AI开源项目", "AI效率工具",
           "AI落地", "AI产品测评", "AI创作", "AIGC", "生成艺术", "Vibe Coding",
           "AI教程", "大模型应用", "AI变现"],
}


def load_known():
    mids = set()
    for line in (CONF / "ups.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        try:
            mids.add(int(line.split("\t")[0]))
        except ValueError:
            pass
    return mids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-fans", type=int, default=10000, dest="min_fans")
    ap.add_argument("--max-fans", type=int, default=100000, dest="max_fans")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--pace", type=float, default=1.3)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--out", default=str(CONF / "candidates_mid.tsv"))
    a = ap.parse_args()

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=read_cred())
    b.preflight()
    known = load_known()

    hits = defaultdict(lambda: {"kws": set(), "themes": set(), "name": None,
                                "fans": 0, "sign": ""})
    total = sum(len(v) for v in THEMES.values())
    done = 0
    for theme, kws in THEMES.items():
        for kw in kws:
            for page in range(1, a.pages + 1):
                try:
                    r = b.get("x/web-interface/wbi/search/type",
                              {"search_type": "bili_user", "keyword": kw,
                               "page": page, "order": "fans"}, tries=2)
                except (Throttled, Budget) as e:
                    print(f"[STOP] {kw}: {e}", file=sys.stderr)
                    raise SystemExit(2)
                except Exception as e:
                    print(f"  ! {kw} p{page}: {str(e)[:50]}", file=sys.stderr)
                    break
                res = (r.get("data") or {}).get("result") or []
                if not res:
                    break
                lowest = min((u.get("fans") or 0) for u in res)
                for u in res:
                    mid = u.get("mid")
                    if not mid:
                        continue
                    fans = u.get("fans") or 0
                    if not (a.min_fans <= fans < a.max_fans):
                        continue
                    e = hits[mid]
                    e["kws"].add(kw)
                    e["themes"].add(theme)
                    e["name"] = u.get("uname")
                    e["fans"] = fans
                    e["sign"] = (u.get("usign") or "").replace("\n", " ")[:100]
                print(f"  [{theme}] {kw} p{page}: {len(res)} (最低 {lowest}) "
                      f"| 累计 {len(hits)}", file=sys.stderr)
                time.sleep(b.pace)
                if lowest < a.min_fans:
                    break
            done += 1
            if done % 10 == 0:
                print(f"  --- 关键词 {done}/{total} ---", file=sys.stderr)

    rows = [{"mid": m, "name": e["name"], "fans": e["fans"],
             "kws": sorted(e["kws"]), "themes": sorted(e["themes"]),
             "sign": e["sign"], "known": m in known}
            for m, e in hits.items()]
    rows.sort(key=lambda x: -x["fans"])
    Path(a.out).write_text(
        "mid\t名称\t粉丝\t主题\t命中词\t简介\n" +
        "\n".join(f'{r["mid"]}\t{r["name"]}\t{r["fans"]}\t'
                  f'{",".join(r["themes"])}\t{",".join(r["kws"][:6])}\t{r["sign"]}'
                  for r in rows), encoding="utf-8")
    new = [r for r in rows if not r["known"]]
    print(f"\n补搜完成：1w–10w 区间命中 {len(rows)}，其中新增 {len(new)} -> {a.out}",
          file=sys.stderr)
    from collections import Counter
    print("主题分布:", dict(Counter(t for r in rows for t in r["themes"])),
          file=sys.stderr)
    b.persist_cred()


if __name__ == "__main__":
    main()
