# -*- coding: utf-8 -*-
"""AI4Science 定向扩搜：账号搜索 + 视频搜索双通道，输出候选清单。

关键词覆盖 7 个子领域（用户给定）：核心领域 / 物理 / 化学材料 / 生物医学 /
机器人与自动化实验 / 地球天文环境 / 科研 Agent 与工具。
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

GROUPS = {
    "核心": ["AI4Science", "AI for Science", "AI科学研究", "科学智能", "智能科研",
             "AI科研", "AI科学家", "科学基础模型", "AI科学发现", "科研自动化",
             "Science Foundation Model", "AI驱动科学发现"],
    "物理": ["AI物理", "Physics AI", "物理智能", "物理世界模型", "PINN",
             "神经物理仿真", "神经算子", "Neural Operator", "物理规律发现",
             "可微物理", "科学机器学习", "Scientific Machine Learning"],
    "化学材料": ["AI化学", "AI材料科学", "AI分子设计", "分子生成", "药物发现",
                 "AI制药", "计算化学", "材料发现", "分子动力学", "晶体结构预测",
                 "蛋白质设计", "AI催化剂"],
    "生物医学": ["AI生物", "AI4Bio", "计算生物学", "蛋白质结构预测", "AlphaFold",
                 "蛋白质语言模型", "基因组", "AI药物研发", "合成生物学",
                 "数字细胞", "AI生命科学", "单细胞"],
    "机器人实验": ["机器人科学家", "Robot Scientist", "Self-driving Lab",
                   "自主实验室", "AI实验设计", "自动化实验", "实验机器人",
                   "具身科学智能", "主动学习", "贝叶斯优化", "闭环科学发现",
                   "Autonomous Discovery"],
    "地学天文": ["AI气象", "AI天气预测", "AI气候模型", "AI天文学", "AI天体物理",
                 "AI地球科学", "Earth Foundation Model", "AI遥感", "AI海洋",
                 "AI环境科学", "科学大模型"],
    "科研Agent": ["AI Research Agent", "科研智能体", "AI Scientist", "自动化科研",
                  "AI论文复现", "AI文献综述", "AI科研工作流", "科研Agent",
                  "科学推理模型", "AI辅助实验", "科研开源项目", "科学代码生成"],
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
    ap.add_argument("--pace", type=float, default=1.4)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--out", default=str(CONF / "candidates_ai4s.tsv"))
    ap.add_argument("--no-video", action="store_true", dest="no_video")
    a = ap.parse_args()

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=read_cred())
    b.preflight()
    known = load_known()

    hits = defaultdict(lambda: {"kws": set(), "name": None, "fans": None,
                                "sign": "", "src": set()})
    total = sum(len(v) for v in GROUPS.values())
    done = 0
    for group, kws in GROUPS.items():
        for kw in kws:
            # 通道 1：账号搜索（匹配昵称/简介）
            try:
                r = b.get("x/web-interface/wbi/search/type",
                          {"search_type": "bili_user", "keyword": kw,
                           "page": 1, "order": "fans"}, tries=2)
                res = (r.get("data") or {}).get("result") or []
                for u in res:
                    if not u.get("mid"):
                        continue
                    e = hits[u["mid"]]
                    e["kws"].add(kw)
                    e["name"] = u.get("uname")
                    e["fans"] = u.get("fans") or 0
                    e["sign"] = (u.get("usign") or "").replace("\n", " ")[:100]
                    e["src"].add("user")
                n_user = len(res)
            except (Throttled, Budget) as e:
                print(f"[STOP] user {kw}: {e}", file=sys.stderr)
                raise SystemExit(2)
            except Exception as e:
                n_user = 0
                print(f"  ! user {kw}: {str(e)[:50]}", file=sys.stderr)
            time.sleep(b.pace)

            # 通道 2：视频搜索（按内容反查作者，补简介里没写的）
            n_vid = 0
            if not a.no_video:
                try:
                    r = b.get("x/web-interface/wbi/search/type",
                              {"search_type": "video", "keyword": kw,
                               "page": 1, "order": "click"}, tries=2)
                    vres = (r.get("data") or {}).get("result") or []
                    for v in vres:
                        if not v.get("mid"):
                            continue
                        e = hits[v["mid"]]
                        e["kws"].add(kw)
                        e["src"].add("video")
                        if not e["name"]:
                            e["name"] = v.get("author")
                    n_vid = len(vres)
                except (Throttled, Budget) as e:
                    print(f"[STOP] video {kw}: {e}", file=sys.stderr)
                    raise SystemExit(2)
                except Exception as e:
                    print(f"  ! video {kw}: {str(e)[:50]}", file=sys.stderr)
                time.sleep(b.pace)
            done += 1
            print(f"  [{group}] {kw}: user={n_user} video={n_vid} "
                  f"| 累计 {len(hits)} | {done}/{total}", file=sys.stderr)

    # 补粉丝数（视频通道来的号没有 fans）
    rows = []
    need = [m for m, e in hits.items() if not e["fans"]]
    print(f"\n补粉丝数 {len(need)} 个…", file=sys.stderr)
    for i, mid in enumerate(need):
        try:
            d = b.get("x/web-interface/card", {"mid": mid}).get("data") or {}
            hits[mid]["fans"] = d.get("follower") or 0
            hits[mid]["name"] = (d.get("card") or {}).get("name") or hits[mid]["name"]
            hits[mid]["sign"] = ((d.get("card") or {}).get("sign") or "").replace("\n", " ")[:100]
        except (Throttled, Budget) as e:
            print(f"[STOP] card {mid}: {e}", file=sys.stderr)
            break
        except Exception:
            pass
        if (i + 1) % 30 == 0:
            print(f"  {i+1}/{len(need)}", file=sys.stderr)
        time.sleep(0.4)

    for mid, e in hits.items():
        if (e["fans"] or 0) < a.min_fans:
            continue
        rows.append({"mid": mid, "name": e["name"], "fans": e["fans"],
                     "kws": sorted(e["kws"]), "sign": e["sign"],
                     "src": sorted(e["src"]), "known": mid in known})
    rows.sort(key=lambda x: -x["fans"])
    Path(a.out).write_text(
        "mid\t名称\t粉丝\t命中词\t简介\n" +
        "\n".join(f'{r["mid"]}\t{r["name"]}\t{r["fans"]}\t'
                  f'{",".join(r["kws"])}\t{r["sign"]}' for r in rows),
        encoding="utf-8")
    new = [r for r in rows if not r["known"]]
    print(f"\nAI4Science 扩搜：命中账号 {len(hits)}，≥{a.min_fans} 粉 {len(rows)}，"
          f"新增 {len(new)} -> {a.out}", file=sys.stderr)
    for r in rows[:30]:
        flag = "" if r["known"] else " [新增]"
        print(f'  {r["fans"]/1e4:>7.1f}万 {r["name"]}{flag}  ← '
              f'{",".join(r["kws"][:3])}', file=sys.stderr)
    b.persist_cred()


if __name__ == "__main__":
    main()
