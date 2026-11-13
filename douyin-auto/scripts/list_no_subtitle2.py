# -*- coding: utf-8 -*-
"""修正版：正确解析 B站 目录名、补粉丝数与主页链接。"""
import json
import re
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
OUT_MD = PROJ / "1AMdata/无字幕博主清单.md"
OUT_TSV = PROJ / "1AMdata/无字幕博主清单.tsv"
PMAP = SKILL.parent / "bilibili-auto/config/prefix_map.tsv"


def fmt(n):
    n = n or 0
    return f"{n/1e4:.1f}万" if n >= 1e4 else str(n)


def parse_fans_tag(tag):
    """'28.1万' -> 281000"""
    m = re.match(r"([\d.]+)\s*(万|亿)?", tag or "")
    if not m:
        return 0
    v = float(m.group(1))
    unit = m.group(2)
    return int(v * (10000 if unit == "万" else 1e8 if unit == "亿" else 1))


def load_bili_map():
    """name -> (mid, fans)"""
    d = {}
    if not PMAP.exists():
        return d
    for ln in PMAP.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        c = ln.split("\t")
        if len(c) >= 4:
            try:
                d[c[1]] = (int(c[0]), int(c[3]))
            except ValueError:
                pass
    return d


def scan_bili():
    root = PROJ / "1AMdata/bilibili"
    mp = load_bili_map()
    rows = []
    for a in root.iterdir():
        if not a.is_dir():
            continue
        try:
            vs = [v for v in a.iterdir() if v.is_dir() and v.name != "_pool"]
        except Exception:
            continue
        if not vs:
            continue
        parts = a.name.split("_")
        prefix = parts[0] if parts else ""
        name = parts[1] if len(parts) > 1 else a.name
        fans = parse_fans_tag(parts[-1]) if len(parts) >= 3 else 0
        mid = None
        if name in mp:
            mid, fans2 = mp[name]
            fans = fans or fans2
        has = 0
        missing = []
        for v in vs:
            ok = False
            try:
                ok = any(v.glob("subtitle.*"))
            except Exception:
                pass
            if ok:
                has += 1
            else:
                title = v.name
                mpf = v / "meta.json"
                if mpf.exists():
                    try:
                        mm = json.loads(mpf.read_text(encoding="utf-8"))
                        title = mm.get("title") or title
                    except Exception:
                        pass
                missing.append((v.name.split("_")[0], (title or "")[:50]))
        if not missing:
            continue
        rows.append({"platform": "B站", "name": name, "fans": fans, "prefix": prefix,
                     "total": len(vs), "has": has, "missing": len(missing),
                     "coverage": has / len(vs) * 100, "missing_list": missing,
                     "url": f"https://space.bilibili.com/{mid}" if mid else ""})
    return rows


def scan_dy():
    root = PROJ / "1AMdata/douyin"
    rows = []
    for a in root.iterdir():
        if not a.is_dir():
            continue
        try:
            vs = [v for v in a.iterdir() if v.is_dir()]
        except Exception:
            continue
        if not vs:
            continue
        name, fans, url = a.name, 0, ""
        af = a / "_account.json"
        if af.exists():
            try:
                acc = json.loads(af.read_text(encoding="utf-8"))
                name = acc.get("nickname") or name
                fans = acc.get("fans") or 0
                m = re.search(r"/user/([A-Za-z0-9_\-]{20,})", acc.get("url") or "")
                if m:
                    url = f'https://www.douyin.com/user/{m.group(1)}'
            except Exception:
                pass
        has = 0
        missing = []
        for v in vs:
            if (v / "transcript.zh.txt").exists():
                has += 1
            else:
                title = v.name
                mpf = v / "meta.json"
                if mpf.exists():
                    try:
                        mm = json.loads(mpf.read_text(encoding="utf-8"))
                        title = mm.get("desc") or title
                    except Exception:
                        pass
                missing.append((v.name, (title or "")[:50]))
        if not missing:
            continue
        rows.append({"platform": "抖音", "name": name, "fans": fans, "prefix": "",
                     "total": len(vs), "has": has, "missing": len(missing),
                     "coverage": has / len(vs) * 100, "missing_list": missing,
                     "url": url})
    return rows


bili = sorted(scan_bili(), key=lambda r: -r["missing"])
dy = sorted(scan_dy(), key=lambda r: -r["missing"])
bt = sum(r["missing"] for r in bili)
dt = sum(r["missing"] for r in dy)

with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
    f.write("平台\t博主\t粉丝\t前缀\t作品数\t有字幕\t缺字幕\t覆盖率%\t主页链接\t缺字幕视频样例\n")
    for r in bili + dy:
        samples = " | ".join(t for _, t in r["missing_list"][:3])
        f.write(f'{r["platform"]}\t{r["name"]}\t{r["fans"]}\t{r["prefix"]}\t'
                f'{r["total"]}\t{r["has"]}\t{r["missing"]}\t{r["coverage"]:.0f}%\t'
                f'{r["url"]}\t{samples}\n')

L = ["# 无字幕（文案）博主清单\n",
     "> 生成：2026-11-05",
     "> 说明：这些博主**视频已采集但无字幕文件**，可点主页链接自行观看\n",
     "## 总览\n",
     "| 平台 | 有缺字幕的博主 | 缺字幕视频 |",
     "|---|---|---|",
     f"| B站 | {len(bili)} | **{bt}** |",
     f"| 抖音 | {len(dy)} | **{dt}** |",
     f"| 合计 | {len(bili)+len(dy)} | **{bt+dt}** |",
     ""]

for label, rows in [("B站", bili), ("抖音", dy)]:
    if not rows:
        continue
    L.append(f"\n## {label}（{len(rows)} 个博主）\n")
    L.append("| 博主 | 粉丝 | 前缀 | 作品 | 有字幕 | 缺 | 覆盖率 | 主页 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        link = f'[打开]({r["url"]})' if r["url"] else "—"
        L.append(f'| {r["name"]} | {fmt(r["fans"])} | {r["prefix"] or "—"} | '
                 f'{r["total"]} | {r["has"]} | **{r["missing"]}** | '
                 f'{r["coverage"]:.0f}% | {link} |')

L.append("\n## B站：缺字幕视频明细（前 80 个博主）\n")
for r in bili[:80]:
    L.append(f'\n**{r["name"]}**（{fmt(r["fans"])}，缺 {r["missing"]}/{r["total"]}）'
             + (f' · [主页]({r["url"]})' if r["url"] else ""))
    for bv, title in r["missing_list"][:5]:
        L.append(f'- `{bv}` {title}')

OUT_MD.write_text("\n".join(L), encoding="utf-8")

print(f"B站: {len(bili)} 博主 / 缺 {bt} 视频")
print(f"抖音: {len(dy)} 博主 / 缺 {dt} 视频")
print(f"\n{OUT_MD}\n{OUT_TSV}")
print("\nB站缺字幕最多的 12 个：")
for r in bili[:12]:
    print(f'  {fmt(r["fans"]):>7}  {r["prefix"]:<6} {r["name"][:18]:<20} '
          f'缺{r["missing"]:>3}/{r["total"]:<3} {r["coverage"]:>3.0f}%  {r["url"]}')
