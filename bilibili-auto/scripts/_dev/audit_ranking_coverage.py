# -*- coding: utf-8 -*-
"""用 B站分区排行榜（不受搜索风控影响）测「头部 UP 覆盖率」。

rid: 36=知识, 188=科技/数码, 202=资讯, 5=娱乐(对照)
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, read_cred  # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"
OUT = CONF / "coverage_ranking.json"

RIDS = {36: "知识", 188: "科技数码", 202: "资讯", 5: "娱乐"}


def load_roster():
    mids = {}
    for line in (CONF / "ups.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        p = line.split("\t")
        try:
            mids[int(p[0])] = p[1] if len(p) > 1 else ""
        except ValueError:
            pass
    return mids


def load_pmap():
    m = {}
    for line in (CONF / "prefix_map.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 3:
            try:
                m[int(p[0])] = p[2]
            except ValueError:
                pass
    return m


def main():
    b = Bili(pace=1.5, cooldown=120, cookies=read_cred())
    b.preflight()
    roster = load_roster()
    pmap = load_pmap()
    print(f"现有名单: {len(roster)} 个 UP")

    result = {}
    all_ups = {}
    for rid, label in RIDS.items():
        ups = {}
        try:
            r = b.get("x/web-interface/ranking/v2", {"rid": rid, "type": "all"}, tries=2)
            lst = (r.get("data") or {}).get("list") or []
        except Exception as e:
            print(f"  {label}(rid={rid}): 失败 {type(e).__name__} {str(e)[:60]}")
            continue
        for v in lst:
            o = v.get("owner") or {}
            mid = o.get("mid")
            if not mid:
                continue
            ups[mid] = {"name": o.get("name"), "fans": o.get("fans") or 0}
        matched = [m for m in ups if m in roster]
        result[label] = {"rid": rid, "ups": len(ups), "matched": len(matched),
                         "coverage": round(len(matched) / len(ups) * 100, 1) if ups else 0,
                         "missing": [{"mid": m, "name": ups[m]["name"],
                                      "fans": ups[m]["fans"]}
                                     for m in ups if m not in roster]}
        for m, v in ups.items():
            all_ups[m] = v
        print(f"  {label:<8} 榜单 {len(ups):>3} 个 UP → 名单命中 {len(matched):>3} "
              f"= {result[label]['coverage']:>5.1f}%")
        time.sleep(1.5)

    # 合并去重
    uniq = len(all_ups)
    uniq_m = sum(1 for m in all_ups if m in roster)
    print(f"\n{'三榜去重':<8} {uniq:>3} 个 UP → 名单命中 {uniq_m:>3} "
          f"= {uniq_m/uniq*100 if uniq else 0:.1f}%")

    # 未覆盖的高粉 UP 前 20
    miss = [{"mid": m, **v} for m, v in all_ups.items() if m not in roster]
    miss.sort(key=lambda x: -(x.get("fans") or 0))
    print(f"\n榜单上但名单里没有的 {len(miss)} 个 UP（按粉丝前 20）：")
    for x in miss[:20]:
        print(f"  {(x.get('fans') or 0)/1e4:>8.1f}万  {x.get('name')}")

    print(f"\n名单前缀覆盖情况（榜单命中项）:")
    cnt = defaultdict(int)
    for m in all_ups:
        if m in roster:
            cnt[pmap.get(m, "?")] += 1
    for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<8} {v}")

    OUT.write_text(json.dumps({"by_area": result,
                               "summary": {"unique": uniq, "matched": uniq_m,
                                           "coverage": round(uniq_m/uniq*100, 1) if uniq else 0},
                               "missing": miss}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\n明细: {OUT}")


if __name__ == "__main__":
    main()
