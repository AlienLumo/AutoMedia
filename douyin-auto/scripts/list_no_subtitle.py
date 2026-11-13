# -*- coding: utf-8 -*-
"""列出「有视频但没有字幕/文案」的博主，供人工去主页查看。

输出：
  1AMdata/无字幕博主清单.md      —— 按缺失数排序，含主页链接
  1AMdata/无字幕博主清单.tsv     —— 同样的表格，便于筛选
"""
import json
import re
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
OUT_MD = PROJ / "1AMdata/无字幕博主清单.md"
OUT_TSV = PROJ / "1AMdata/无字幕博主清单.tsv"


def fmt(n):
    n = n or 0
    return f"{n/1e4:.1f}万" if n >= 1e4 else str(n)


def scan(root, is_bili):
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

        # 账号信息
        name = a.name
        fans = 0
        prefix = ""
        url = ""
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
        # B站：目录名是 <前缀>_<名称>_<粉丝>
        pm = None
        try:
            pm = next((c for c in (SKILL.parent / "bilibili-auto/config/prefix_map.tsv")
                       .read_text(encoding="utf-8").splitlines()
                       if c.endswith(a.name)), None) if is_bili else None
        except Exception:
            pm = None
        parts = a.name.split("_")
        if is_bili and len(parts) >= 3:
            prefix = parts[0]
            fans = fans or 0
        if not url and is_bili:
            mid = None
            try:
                for c in (SKILL.parent / "bilibili-auto/config/prefix_map.tsv").read_text(
                        encoding="utf-8").splitlines():
                    cc = c.split("\t")
                    if len(cc) >= 2 and cc[1] == parts[1] if len(parts) > 1 else False:
                        mid = cc[0]
                        break
            except Exception:
                pass

        has_sub = 0
        missing = []
        for v in vs:
            ok = False
            if is_bili:
                try:
                    ok = any(v.glob("subtitle.*"))
                except Exception:
                    ok = False
            else:
                ok = (v / "transcript.zh.txt").exists()
            if ok:
                has_sub += 1
            else:
                # 取标题
                title = v.name
                mp = v / "meta.json"
                if mp.exists():
                    try:
                        mm = json.loads(mp.read_text(encoding="utf-8"))
                        title = mm.get("title") or mm.get("desc") or title
                    except Exception:
                        pass
                missing.append((v.name, (title or "")[:50]))

        if not missing:
            continue
        rows.append({
            "name": name, "dir": a.name, "fans": fans, "prefix": prefix,
            "total": len(vs), "has_sub": has_sub, "missing": len(missing),
            "coverage": has_sub / len(vs) * 100,
            "missing_list": missing, "platform": "B站" if is_bili else "抖音",
        })
    return rows


bili = scan(PROJ / "1AMdata/bilibili", True)
dy = scan(PROJ / "1AMdata/douyin", False)

# 输出 TSV
all_rows = sorted(bili + dy, key=lambda r: -r["missing"])
with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
    f.write("平台\t博主\t粉丝\t前缀\t作品数\t有字幕\t缺字幕\t覆盖率%\t缺字幕视频样例\n")
    for r in all_rows:
        samples = " | ".join(t for _, t in r["missing_list"][:3])
        f.write(f'{r["platform"]}\t{r["name"]}\t{r["fans"]}\t{r["prefix"]}\t'
                f'{r["total"]}\t{r["has_sub"]}\t{r["missing"]}\t'
                f'{r["coverage"]:.0f}%\t{samples}\n')

# 输出 Markdown
L = []
L.append("# 无字幕（文案）博主清单\n")
L.append(f"> 生成时间：2026-11-05")
L.append(f"> 用途：这些博主的视频**采集到了但没有字幕文件**，可自行去主页观看\n")

bt = sum(r["missing"] for r in bili)
dt = sum(r["missing"] for r in dy)
L.append(f"## 总览\n")
L.append(f"| 平台 | 有缺字幕的博主 | 缺字幕视频数 |")
L.append(f"|---|---|---|")
L.append(f"| B站 | {len(bili)} | **{bt}** |")
L.append(f"| 抖音 | {len(dy)} | **{dt}** |")
L.append(f"| 合计 | {len(bili)+len(dy)} | **{bt+dt}** |")
L.append("")

for label, rows in [("B站", bili), ("抖音", dy)]:
    if not rows:
        continue
    L.append(f"\n## {label}（{len(rows)} 个博主）\n")
    L.append("| 博主 | 粉丝 | 前缀 | 作品 | 有字幕 | 缺 | 覆盖率 |")
    L.append("|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(f'| {r["name"]} | {fmt(r["fans"])} | {r["prefix"] or "—"} | '
                 f'{r["total"]} | {r["has_sub"]} | **{r["missing"]}** | '
                 f'{r["coverage"]:.0f}% |')
    L.append("\n### 缺字幕的视频样例（每个博主最多 3 条）\n")
    for r in rows[:60]:
        L.append(f'**{r["name"]}**（缺 {r["missing"]}/{r["total"]}）')
        for vid, title in r["missing_list"][:3]:
            L.append(f'- `{vid}` {title}')
        L.append("")

OUT_MD.write_text("\n".join(L), encoding="utf-8")

print(f"B站：{len(bili)} 个博主有缺字幕，共缺 {bt} 个视频")
print(f"抖音：{len(dy)} 个博主有缺字幕，共缺 {dt} 个视频")
print(f"\n输出:\n  {OUT_MD}\n  {OUT_TSV}")
print("\n缺字幕最多的 10 个博主：")
for r in all_rows[:10]:
    print(f'  [{r["platform"]}] {r["fans"]/1e4:>7.1f}万  {r["name"][:22]:<24} '
          f'缺 {r["missing"]:>3}/{r["total"]:<3} 覆盖率 {r["coverage"]:.0f}%')
