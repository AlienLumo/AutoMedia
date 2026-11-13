# -*- coding: utf-8 -*-
"""更新 bilibili-auto/SKILL.md：补 2026-11-04/05 的新能力与实测结论。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "SKILL.md"
t = f.read_text(encoding="utf-8")

# 1) 更新 frontmatter 描述
old_desc = 'description: "项目内 B 站数据采集与监听：按 UP 主批量抓取视频元数据、评论、字幕（逐字稿），并做每日增量更新检查。用于「盯住 N 个 UP 是否更新」「按最近 N 条 / 最高赞 N 条批量采集全量信息」这类需求。"'
new_desc = 'description: "项目内 B 站数据采集与监听：按 UP 主批量抓取视频元数据、评论、字幕（逐字稿）；也可按主题找号扩池（视频搜索反查 + 宽口径账号搜索 + 采样核验 + 机构号过滤）。用于「盯住 N 个 UP 是否更新」「按最近N条/最高赞N条采集全量」「找某个领域的所有 UP 主」这类需求。"'
if old_desc in t:
    t = t.replace(old_desc, new_desc, 1)

APPEND = r'''

---

# 找号 / 扩池 / 无人值守批量采集（2026-11-04-05 新增，已验证）

## 一键入口

```powershell
$S = "<项目根>\AutoMedia\bilibili-auto\scripts"

# A) 单个 UP 采集（元数据+评论+字幕）
.\collect_one.ps1 -Mid 385670211 -Limit 30

# B) 全名单批量（无人值守，一轮接一轮，无空档）
.\run_bili_continuous.ps1

# C) 按主题找号（三步：搜 → 核验 → 定稿）
python $S\bili_video_search.py --all --pages 2 --pace 1.4      # 视频搜索反查
python $S\expand_broad.py --pages 1 --pace 2.5                 # 账号搜索（242 词）
python $S\sample_resume.py --input config\combined_roster.tsv --budget 400   # 采样核验
python $S\finalize_roster_v2.py                                 # 定稿 + 拆双队列
python $S\expand_roster_append.py                               # 并入 ups.tsv
```

## 三条发现渠道（按效果排序）

| 渠道 | 脚本 | 原理 | 效果 |
|---|---|---|---|
| **视频搜索反查** | `bili_video_search.py` | 搜视频标题，从作者反推 UP | **最好**：商业类 11 → 1238 个候选 |
| 账号搜索 | `expand_broad.py` | `bili_user` 匹配昵称+简介 | 中等：785 个候选 |
| 分区榜单 | `ranking/v2` | 每日热门 Top100 | 差：全是全站爆款，非领域创作者 |

**关键教训**：账号搜索只匹配昵称/简介，商业/局势类 UP 主简介里不写这些词 → 搜不到。
视频搜索匹配**标题**，命中率高 10 倍以上。

## 机构号过滤（只保留个人自媒体）

`is_personal()` 三级判定（在 `expand_broad.py` / `classify_broad.py` / `build_combined_roster.py` / `build_talk_queue.py` 里都有）：

- **HARD 排除**：央视/人民日报/新华社/共青团/观察者网/卫视/日报/新闻网/大学/学院/研究院 + 品牌（华为/小米/腾讯/阿里/字节…）
- **SOFT 排除**：集团/公司/商城/官方/频道/传媒/协会/出版社/杂志/工作室（若有「老师/哥/姐/叔/博士/教授」等个人特征词则豁免）
- **保留**：其余

**踩过的误伤**：思维实验室、卢克文工作室 → 「实验室」「工作室」不能当机构词，已移除。

## 采样核验（决定收录的关键一步）

`sample_resume.py`：对每个候选抓最近 20 个视频标题，算主题词占比。

| 占比 | 判定 | 处理 |
|---|---|---|
| ≥40% | ok | 收录（A 档）|
| 15–40% | mid | 收录但标 B 档 |
| <15% | bad | 淘汰 |

**为什么必须做**：离线关键词匹配会把「食贫道」「陈翔六点半」判成商业号（标题里偶尔有「开店」「生意」）。
采样 20 条标题后真实主题占比只有 0-5%，直接被淘汰。

**断点续跑**：进度写 `config/sample_progress.json`，被风控打断后重跑自动续。

## 风控实测（重要，决定 pace）

| 端点 | 实测结果 |
|---|---|
| `search/type`（搜索）| **pace 1.3 秒时约 1300 次请求触发 `v_voucher`**；冷却约 70 分钟 |
| `space/wbi/arc/search`（列表）| **宽容得多**：400 次 2 分钟内跑完无风控 |
| `card`（粉丝查询）| 1,238 次连着打会加速触发风控 |

**结论**：
- 搜索类任务 pace **2.5 秒**，每批 ≤400 请求
- 列表类可以快（1.5 秒）
- 避免无谓的 `card` 查询：`bili_user` 搜索结果里**已经带 fans**，不用再查

## 无人值守：连续运行器 vs 计划任务

计划任务在 2026-11-01 注册（每 25 分钟、5 天期限），**期限无法延长**（权限拒绝）。

改用 `run_bili_continuous.ps1`：
- 一轮跑完立刻接下一轮，**无 11 分钟空档**
- 实测速率从 **6.7 → 17.4 个账号/小时**（快 2.6 倍）
- 与计划任务共存：靠采集器 PID 锁，计划任务会 `[skip] 实例 XXX 仍在运行·退出`，无冲突

## 当前名单规模（2026-11-05）

826 个账号：

| 前缀 | 数量 |
|---|---|
| 商业（含财经）| 244 |
| 炒股投资 | 108 |
| 创客 | 86 |
| 黑客 | 85 |
| ai | 80 |
| 局势 | 67 |
| 科技 | 60 |
| 科研 | 42 |
| 教程 | 32 |
| 机器人 | 17 |
| 数码评测 | **5**（严格限制，按粉丝取 Top5）|

## 采集参数（当前最优）

```powershell
python scripts\bili_deep_collect.py `
  --max-requests 850 `      # 填满 22 分钟窗口（原来 500 只用 14 分钟，浪费 11 分钟）
  --pace 1.3 `              # 0 限流余量充足
  --rest-every 600 `        # 减少休息
  --cooldown 120 `
  --comment-cap 100 `
  --top-n 20 `
  --pool-cap 80 `           # 大账号候选池截断，省打分成本
  --sub-langs zh
```

## 无字幕博主（重要）

B站 只有约 **80.5%** 的视频有 CC 字幕（`sub-langs zh`），其余 UP 主从不上传字幕。

- 统计脚本：`AutoMedia/douyin-auto/scripts/list_no_subtitle2.py`
- 产出：`1AMdata/无字幕博主清单.md` / `.tsv`（266 个博主 / 1,299 个视频）
- 补 ASR 成本：1,299 视频 × 30 秒 ≈ 11 小时 GPU

## Token 纪律

| 操作 | Token |
|---|---|
| 跑一轮采集（850 请求）| ~0（结果写盘 + 日志）|
| 看进度（读 state 一行）| ~80 |
| **禁止**：读 `deep_run.log` 全文 | 会爆（单轮 800+ 行）|

正确查进度：
```powershell
python scripts\show_state.py
# 或只统计 state 里的 finished 数
```
'''

if "找号 / 扩池 / 无人值守批量采集" not in t:
    t = t.rstrip() + APPEND
    f.write_text(t, encoding="utf-8")
    print("已追加新能力章节")
else:
    print("章节已存在")
