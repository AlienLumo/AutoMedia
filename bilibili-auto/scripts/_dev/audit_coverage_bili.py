# -*- coding: utf-8 -*-
"""B站覆盖率审计：用独立的账号级搜索重新扫各领域，比对现有 420 人名单。

输出：每个领域「搜索发现 N 个 ≥10万粉 UP → 已在名单 M 个 → 覆盖率 M/N」
同时列出高频未收录的 UP（漏采候选）。
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, read_cred, Throttled, Budget  # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"
OUT = CONF / "coverage_audit.json"

# 每领域一组「发现用」关键词（比建库时更宽，用来检验漏采）
KEYWORDS = {
    "ai": ["AI", "人工智能", "AI工具", "AI应用", "大模型", "AIGC", "AI Agent",
           "智能体", "AI编程", "AI绘画", "AI视频"],
    "商业": ["科技创业", "创业", "商业模式", "商业分析", "科技公司", "独立开发",
             "一人公司", "出海创业", "产品经理"],
    "创客": ["创客", "极客", "DIY", "电子制作", "开源硬件", "3D打印", "硬件开发",
             "创意发明"],
    "机器人": ["机器人", "具身智能", "机械臂", "人形机器人", "机器人开发",
               "机器人DIY"],
    "科研": ["科研", "AI4Science", "科学研究", "论文解读", "学术", "生物信息"],
    "教程": ["教程", "编程教程", "AI教程", "开源项目", "技术教程"],
    "科技": ["科技", "前沿科技", "黑科技", "数码科技", "科技产品", "科技资讯"],
    "黑客": ["黑客", "网络安全", "渗透测试", "信息安全", "CTF"],
    "炒股投资": ["炒股", "股票", "投资", "基金", "理财", "价值投资"],
    "局势": ["国际局势", "地缘政治", "时事", "军事", "世界局势"],
}


def load_known():
    mids = {}
    p = CONF / "ups.tsv"
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        try:
            mids[int(parts[0])] = parts[1] if len(parts) > 1 else ""
        except ValueError:
            pass
    return mids


def prefix_of(mid, known, pmap):
    return pmap.get(mid, "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--pace", type=float, default=1.5)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--budget", type=int, default=0)
    a = ap.parse_args()

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=read_cred())
    b.preflight()
    known = load_known()

    # mid -> 前缀
    pmap = {}
    for line in (CONF / "prefix_map.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            try:
                pmap[int(parts[0])] = parts[2]
            except ValueError:
                pass

    found = {}          # mid -> {name, fans, kws:set, domain:set}
    domain_total = defaultdict(int)
    total_kw = sum(len(v) for v in KEYWORDS.values())
    done = 0

    for domain, kws in KEYWORDS.items():
        for kw in kws:
            for page in range(1, a.pages + 1):
                done += 1
                try:
                    r = b.get("x/web-interface/wbi/search/type",
                              {"search_type": "bili_user", "keyword": kw,
                               "page": page, "order": "fans"}, tries=2)
                except Throttled:
                    print(f"  [throttled] {kw} p{page}，冷却后重试…", flush=True)
                    time.sleep(a.cooldown)
                    continue
                except Exception as e:
                    print(f"  ! {kw} p{page}: {str(e)[:60]}", flush=True)
                    continue
                data = (r.get("data") or {}).get("result") or []
                if not data:
                    break
                for u in data:
                    mid = u.get("mid")
                    fans = u.get("fans") or 0
                    if not mid or fans < a.min_fans:
                        continue
                    if mid not in found:
                        found[mid] = {"mid": mid, "name": u.get("uname"),
                                      "fans": fans,
                                      "sign": (u.get("usign") or "")[:120],
                                      "kws": set(), "domains": set()}
                    found[mid]["kws"].add(kw)
                    found[mid]["domains"].add(domain)
                if done % 20 == 0:
                    print(f"  进度 {done}/{total_kw* a.pages}，已发现 {len(found)} 个 UP",
                          flush=True)
                time.sleep(b.pace)

    # 统计覆盖
    rows = []
    for mid, v in found.items():
        rows.append({"mid": mid, "name": v["name"], "fans": v["fans"],
                     "sign": v["sign"], "domains": sorted(v["domains"]),
                     "kws": sorted(v["kws"])[:6],
                     "in_roster": mid in known,
                     "roster_prefix": pmap.get(mid, "")})

    by_domain = defaultdict(lambda: {"found": 0, "matched": 0})
    for r in rows:
        for d in r["domains"]:
            by_domain[d]["found"] += 1
            if r["in_roster"]:
                by_domain[d]["matched"] += 1

    print("\n" + "=" * 66)
    print(f"{'领域':<10} {'搜索发现':>8} {'已收录':>7} {'覆盖率':>8}")
    print("=" * 66)
    tot_f = tot_m = 0
    for d in KEYWORDS:
        s = by_domain[d]
        cov = (s["matched"] / s["found"] * 100) if s["found"] else 0
        print(f"{d:<10} {s['found']:>8} {s['matched']:>7} {cov:>7.1f}%")
        tot_f += s["found"]
        tot_m += s["matched"]
    print("-" * 66)
    uniq_f = len(rows)
    uniq_m = sum(1 for r in rows if r["in_roster"])
    print(f"{'去重合计':<10} {uniq_f:>8} {uniq_m:>7} {(uniq_m/uniq_f*100 if uniq_f else 0):>7.1f}%")

    missing = [r for r in rows if not r["in_roster"]]
    missing.sort(key=lambda x: -x["fans"])
    print(f"\n未收录（漏采）{len(missing)} 个，按粉丝排序前 25：")
    for r in missing[:25]:
        print(f"  {r['fans']/1e4:>8.1f}万  {r['name'][:20]:<22} "
              f"[{','.join(r['domains'])}]  {(r['sign'] or '')[:36]}")

    OUT.write_text(json.dumps({"by_domain": {k: dict(v) for k, v in by_domain.items()},
                               "summary": {"found": uniq_f, "matched": uniq_m,
                                           "coverage": round(uniq_m / uniq_f * 100, 1)},
                               "found": rows, "missing": missing},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n明细已写入 {OUT}")


if __name__ == "__main__":
    main()
