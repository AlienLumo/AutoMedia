# -*- coding: utf-8 -*-
"""生成最终汇总报告（格式变更 + 扩搜核验 + 最终名单分布）。"""
from collections import Counter
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
CONF = SKILL / "config"
PMAP = CONF / "prefix_map.tsv"
DATA = PROJ / "1AMdata" / "bilibili"
OUT = PROJ / "1AMdata" / "_report_final.md"


def fmt(n):
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


rows = []
for line in PMAP.read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    c = line.split("\t")
    rows.append((int(c[0]), c[1], c[2], int(c[3])))
rows.sort(key=lambda r: -r[3])

ups_on_disk = [p for p in DATA.iterdir() if p.is_dir()] if DATA.exists() else []
vids = [p for p in DATA.rglob("BV*") if p.is_dir() and (p/"meta.json").exists()] if DATA.exists() else []
cm = sum(sum(1 for _ in (v/"comments.jsonl").open(encoding="utf-8"))
         for v in vids if (v/"comments.jsonl").exists())
size = sum(f.stat().st_size for f in DATA.rglob("*") if f.is_file()) if DATA.exists() else 0

pref = Counter(r[2] for r in rows)
lines = [
    "# B站采集：最终报告\n",
    "## 一、目录格式（已变更）\n",
    "旧：`1AMdata/bilibili/<主题>/<UP主>_<mid>/<视频>/`",
    "新：`1AMdata/bilibili/<前缀>_<UP主>_<粉丝量>/<bvid>_<标题>/`\n",
    "前缀候选：ai / 商业 / 教程 / 炒股投资 / 局势 / 机器人行业 / 创客 / 黑客\n",
    "已迁移实例（30 个）：",
    "```",
    "1AMdata/bilibili/",
    "  教程_秋芝2046_110.5万/",
    "    BV1PcJd6UE81_AI时代，如何选电脑？【小白必看】/",
    "        meta.json  comments.jsonl  subtitle.ai-zh.srt/.txt  …",
    "  ai_苏星河牛通_315.2万/",
    "  商业_小Lin说_758.6万/",
    "  炒股投资_硬核资本论_257.2万/",
    "  局势_棱镜Talk_199.5万/",
    "  创客_花叔v_21.6万/",
    "```\n",
    "## 二、扩搜与核验\n",
    "| 步骤 | 结果 |",
    "|---|---|",
    "| 42 个主题关键词 × 视频播放榜 | 587 个作者 |",
    "| 逐个核粉 ≥10 万 | 332 个（其中 276 个不在原名单）|",
    "| 抽样最近 15 条投稿判 AI 浓度 | **垂直 9 / 半相关 14 / 无关 253** |",
    "| 最终并入 | **23 个** |\n",
    "**为什么 253 个是噪声**：按视频播放榜反查作者，任何一条蹭了 AI 关键词的爆款都会把",
    "非 AI 大号带进来（老番茄、何同学、戴建业老师、毕导、半佛仙人均属此类，样本 AI 浓度 0%）。",
    "所以按「账号是否做 AI」核验后几乎全部剔除。\n",
    f"## 三、最终名单：**{len(rows)} 个**（原 87 + 核验新增 23）\n",
    "| 前缀 | 数量 |",
    "|---|---|",
]
for p, n in pref.most_common():
    lines.append(f"| {p} | {n} |")
lines += ["", "### TOP30\n", "| 粉丝 | 前缀 | UP 主 |", "|---|---|---|"]
for mid, nm, pf, fans in rows[:30]:
    lines.append(f"| {fmt(fans)} | {pf} | {nm} |")

lines += ["", "## 四、已采集数据现状\n",
          f"- 已落盘 UP 目录：{len(ups_on_disk)} 个",
          f"- 已采集视频：{len(vids)} 个（30 个 UP × 每号 2 条）",
          f"- 评论总数：{cm} 条",
          f"- 体积：{size/1024/1024:.1f} MB",
          f"- 字幕覆盖：52/58 ≈ 90%（多语种）\n",
          "## 五、下一步\n",
          f"1. 用新格式采集名单里剩余 {len(rows)-30} 个 UP（未采过）。",
          "2. 监听调度器：每日扫名单比对发布时间，新视频入队采集。",
          "3. 前缀目前是启发式判断，可按需人工修正 `config/prefix_map.tsv`。"]
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"报告: {OUT}")
print(f"名单 {len(rows)} 个；已落盘 {len(ups_on_disk)} UP / {len(vids)} 视频 / {cm} 评论 / {size/1024/1024:.1f}MB")
