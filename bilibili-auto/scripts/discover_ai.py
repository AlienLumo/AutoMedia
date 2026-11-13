# -*- coding: utf-8 -*-
"""扩搜：AI创作 / AI产品 / AI前沿 / AI行业 / AI4Science 方向的 B站 UP 主。

输出 config/candidates_raw.tsv：mid <tab> 名称 <tab> 粉丝 <tab> 命中关键词 <tab> 简介
只写入 >= --min-fans 的号，并标注是否已在 ups.tsv。
"""
import argparse
import json
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
    "AI创作": ["AI绘画", "AI视频", "AIGC", "ComfyUI", "Stable Diffusion",
               "AI短剧", "AI音乐", "AI动画", "AI漫剧", "AI特效", "AI设计",
               "可灵", "即梦", "Midjourney", "AI数字人"],
    "AI产品": ["AI产品", "AI工具", "AI应用", "AI软件", "AI测评", "AI Agent",
               "AI编程", "Cursor", "Claude Code", "AI智能体"],
    "AI前沿": ["AI前沿", "大模型", "AGI", "论文精读", "AI技术", "GPT",
               "DeepSeek", "开源模型", "多模态", "世界模型"],
    "AI行业": ["AI行业", "AI产业", "AI就业", "AI公司", "AI融资", "AI创业",
               "算力", "英伟达", "芯片 AI"],
    "AI4Science": ["AI科研", "AI4Science", "AI 科学", "AI 医疗", "AI 生物",
                   "AI 材料", "AI 数学", "AI 药物", "机器学习 科研"],
}


def load_roster():
    mids = set()
    p = CONF / "ups.tsv"
    if p.exists():
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
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--pace", type=float, default=1.2)
    ap.add_argument("--cooldown", type=int, default=60)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--out", default=str(CONF / "candidates_raw.tsv"))
    ap.add_argument("--max-verify", type=int, default=600, dest="max_verify")
    a = ap.parse_args()

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=read_cred())
    b.preflight()
    known = load_roster()

    hits = defaultdict(set)      # mid -> keywords
    for group, kws in GROUPS.items():
        for kw in kws:
            for page in range(1, a.pages + 1):
                try:
                    r = b.get("x/web-interface/wbi/search/type",
                              {"search_type": "video", "keyword": kw,
                               "page": page, "order": "click"}, tries=2)
                except (Throttled, Budget) as e:
                    print(f"[STOP] {kw}: {e}", file=sys.stderr)
                    raise SystemExit(2)
                except Exception as e:
                    print(f"  ! {kw}: {str(e)[:70]}", file=sys.stderr)
                    continue
                res = (r.get("data") or {}).get("result") or []
                for v in res:
                    if v.get("mid"):
                        hits[v["mid"]].add(kw)
                print(f"  [{group}] {kw}: {len(res)} hits / 累计 {len(hits)} 作者",
                      file=sys.stderr)
                time.sleep(b.pace)

    print(f"\n去重后 {len(hits)} 个作者，开始核粉（上限 {a.max_verify}）",
          file=sys.stderr)
    rows = []
    seen = 0
    for mid, kws in hits.items():
        if seen >= a.max_verify:
            print(f"[warn] 已达核粉上限 {a.max_verify}", file=sys.stderr)
            break
        seen += 1
        try:
            d = b.get("x/web-interface/card", {"mid": mid}).get("data") or {}
            cards = d.get("card") or {}
            fans = d.get("follower") or 0
            if fans >= a.min_fans:
                rows.append({"mid": mid, "name": cards.get("name"),
                             "fans": fans,
                             "sign": (cards.get("sign") or "").replace("\n", " ")[:80],
                             "kws": sorted(kws), "known": mid in known})
        except (Throttled, Budget) as e:
            print(f"[STOP] card {mid}: {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  ! card {mid}: {str(e)[:50]}", file=sys.stderr)
        if seen % 25 == 0:
            print(f"  核粉 {seen}/{len(hits)}，达标 {len(rows)}", file=sys.stderr)
        time.sleep(0.45)

    rows.sort(key=lambda x: -x["fans"])
    Path(a.out).write_text(
        "mid\t名称\t粉丝\t命中关键词\t简介\n" +
        "\n".join(f'{r["mid"]}\t{r["name"]}\t{r["fans"]}\t'
                  f'{",".join(r["kws"])}\t{r["sign"]}' for r in rows),
        encoding="utf-8")
    new = [r for r in rows if not r["known"]]
    print(f"\n达标(>={a.min_fans}) {len(rows)} 个，其中新增 {len(new)} 个 -> {a.out}",
          file=sys.stderr)
    for r in new[:30]:
        print(f'  {r["fans"]/1e4:>7.1f}万  {r["name"]}', file=sys.stderr)
    b.persist_cred()


if __name__ == "__main__":
    main()
