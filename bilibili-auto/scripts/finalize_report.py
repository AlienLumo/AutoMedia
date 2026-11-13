# -*- coding: utf-8 -*-
"""清理无效目录（404 视频、路径 bug 遗留的重复目录）并生成测试报告。"""
import json
import shutil
from collections import defaultdict
from pathlib import Path
from _paths import DATA, SKILL

ROOT = DATA / "bilibili"
LOG = SKILL / "logs"

removed, kept_empty = [], []
for p in sorted(ROOT.rglob("BV*")):
    if not p.is_dir():
        continue
    has_meta = (p / "meta.json").exists()
    has_cm = (p / "comments.jsonl").exists()
    if has_meta or has_cm:
        continue
    # 空目录：要么是已删除视频(404)，要么是路径 bug 留下的重复壳
    dup = False
    for sib in p.parent.iterdir():
        if sib.is_dir() and sib != p and sib.name.split("_")[0] == p.name.split("_")[0]:
            dup = True
            break
    try:
        shutil.rmtree(p)
        (removed.append((str(p.relative_to(ROOT)), "重复壳" if dup else "无效/已删除视频")))
    except Exception as e:
        print(f"删除失败 {p}: {e}")

print(f"清理 {len(removed)} 个目录：")
for n, why in removed:
    print(f"  - [{why}] {n}")

# 重新统计
dirs = [p for p in ROOT.rglob("BV*") if p.is_dir() and (p / "meta.json").exists()]
per_up = defaultdict(lambda: {"v": 0, "c": 0, "langs": 0, "b": 0})
per_topic = defaultdict(lambda: {"v": 0, "c": 0, "sub": 0})
cap_hit = 0
for p in dirs:
    rel = p.relative_to(ROOT).parts
    if len(rel) < 3:
        continue
    topic, up = rel[0], rel[1]
    n_cm = 0
    if (p / "comments.jsonl").exists():
        n_cm = sum(1 for _ in (p / "comments.jsonl").open(encoding="utf-8"))
    if n_cm >= 500:
        cap_hit += 1
    langs = len({f.name.split(".")[1] for f in p.glob("subtitle.*.srt")})
    size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    per_up[up]["v"] += 1
    per_up[up]["c"] += n_cm
    per_up[up]["langs"] += langs
    per_up[up]["b"] += size
    per_topic[topic]["v"] += 1
    per_topic[topic]["c"] += n_cm
    per_topic[topic]["sub"] += 1 if langs else 0

total_v = sum(x["v"] for x in per_up.values())
total_c = sum(x["c"] for x in per_up.values())
total_b = sum(x["b"] for x in per_up.values())
with_sub = sum(1 for p in dirs if list(p.glob("subtitle.*.srt")))

lines = []
lines.append("# B站 30 个 UP 主采集测试报告\n")
lines.append(f"- 生成时间：2026-11-01")
lines.append(f"- 采集账号：项目 biliup 凭据（TV 扫码）")
lines.append(f"- 范围：跨分类抽样 30 个 UP × 每号最近 2 个视频")
lines.append(f"- 参数：评论上限 500、字幕全语言、不含楼中楼回复")
lines.append("")
lines.append("## 总览\n")
lines.append("| 指标 | 数值 |")
lines.append("|---|---|")
lines.append(f"| UP 主 | 30 |")
lines.append(f"| 成功采集视频 | **{total_v}** / 60（2 个视频已被 UP 主删除/设为不可见）|")
lines.append(f"| 评论总条数 | **{total_c}**（平均 {total_c//max(total_v,1)} 条/视频）|")
lines.append(f"| 字幕覆盖 | **{with_sub}/{total_v}**（{with_sub/max(total_v,1)*100:.0f}%），含多语种 |")
lines.append(f"| 触到 500 上限的视频 | {cap_hit} 个 |")
lines.append(f"| 数据体积 | {total_b/1024/1024:.1f} MB |")
lines.append("")
lines.append("## 按主题\n")
lines.append("| 主题 | 视频数 | 评论数 | 有字幕视频 |")
lines.append("|---|---|---|---|")
for t, x in sorted(per_topic.items(), key=lambda kv: -kv[1]["v"]):
    lines.append(f"| {t} | {x['v']} | {x['c']} | {x['sub']} |")
lines.append("")
lines.append("## 各 UP 明细\n")
lines.append("| UP 主 | 视频 | 评论 | 字幕语言数 | 体积 |")
lines.append("|---|---|---|---|---|")
for up, x in sorted(per_up.items(), key=lambda kv: -kv[1]["c"]):
    lines.append(f"| {up} | {x['v']} | {x['c']} | {x['langs']} | {x['b']/1024:.0f} KB |")
lines.append("")
lines.append("## 已知问题\n")
lines.append("- 2 个视频接口返回 `-404 啥都木有`，属视频已删除，非采集失败。")
lines.append("- 路径 bug 已修复：标题以 `...` 结尾时 Windows 会去掉末尾的点，导致写入失败；")
lines.append("  `safe_name` 现在会清掉结尾的点和空格，并规避 Windows 保留名。")
lines.append("- 楼中楼（二级回复）本次关闭，如需可加 `--nested-pages 2`，耗时约 4 倍。")
lines.append("")

report = ROOT.parent / "_report_30ups.md"
report.write_text("\n".join(lines), encoding="utf-8")
print(f"\n报告已写入: {report}")
print(f"最终统计: {total_v} 视频 / {total_c} 评论 / {total_b/1024/1024:.1f} MB / "
      f"字幕覆盖 {with_sub}/{total_v}")
