---
name: bilibili-auto
description: "项目内 B 站数据采集与监听：按 UP 主批量抓取视频元数据、评论、字幕（逐字稿）；也可按主题找号扩池（视频搜索反查 + 宽口径账号搜索 + 采样核验 + 机构号过滤）。用于「盯住 N 个 UP 是否更新」「按最近N条/最高赞N条采集全量」「找某个领域的所有 UP 主」这类需求。"
---

# B 站自动采集与监听（项目内）

> 本项目规则要求：代码、数据、缓存、**账号凭证**都留在 `<项目根>` 内。
> 平台 Cookie 会失效，**不承诺永久登录**（见 `规则.md`）。

## 目录

```
AutoMedia/bilibili-auto/
  SKILL.md
  scripts/bili.py            # 找号、核粉、榜单（87 名单维护）
  scripts/bili_collect.py    # 单 UP 批量采集：元数据+评论+字幕
  scripts/bili_subs.py       # 底层：WBI 签名、限流熔断、凭据、字幕
  config/ups.tsv             # 监听名单：mid <tab> 名称 <tab> 方向
  credentials/bili_cookie.txt# 登录态（不提交、不外传）
  cache/                     # WBI key、card 缓存
  data/                      # 采集产出
  logs/
```

## 凭据（优先用项目账号真源）

**主来源**：`data/sau/cookies/bilibili_alien.json`（biliup TV 扫码）
含 `cookie_info.cookies`：SESSDATA / bili_jct / DedeUserID / DedeUserID__ckMd5 / sid，
另有 OAuth `access_token`(180 天) + `refresh_token`。项目重新扫码后采集器自动用上新凭据。

读取优先级：`BILI_COOKIE` 环境变量 → `--cred-file` 显式文件 →
**biliup 真源** → `credentials/bili_cookie.txt`（手工备用）。

- 每次运行结束 `persist_cred()` 会把刷新后的 cookie 写回 `credentials/bili_cookie.txt`。
- 启动 `preflight()` 检查 `nav.isLogin`，失效 `exit=3` 并提示重登，不会空跑。
- **不要同时另开第二套登录通道**：项目规则要求账号真源独占，同账号多通道会互踢。

手工备用格式（两行或一行完整 cookie 字符串，BOM 也支持）：
`SESSDATA=xxx; buvid3=yyy; bili_jct=zzz; DedeUserID=...; b_nut=...`

## 实测结论（2026-11-01，用项目凭据）

- 登录有效（TV 扫码态），`isLogin=true`。
- **AI 字幕可下载**：3/3 抽样视频都有 `ai-zh`，多数另有 `ai-en` / `ai-ja`；
  单视频 264–546 条字幕。覆盖率需更大样本确认。
- **评论全量可翻页**：匿名只有 3 条（`is_end=true`），登录后 2937 条可正常分页。

## 采集能力与实测边界（2026-11-01 验证）

| 数据 | 免登录 | 登录后 | 说明 |
|---|---|---|---|
| 元数据 | ✅ | ✅ | `x/web-interface/view`，含播放/点赞/投币/收藏/弹幕数/tags |
| 视频列表 | ⚠️ 不稳 | ✅ | `arc/search` 必须带 `dm_img` 三参数；失败自动回退搜索接口 |
| 评论全量 | ❌ 只给 3 条 | ✅ | 匿名 `is_end=true`，只有 3 条热评 |
| 字幕/逐字稿 | ❌ 恒为空 | ✅ | 且只有热门视频有 AI 字幕，覆盖率需实测 |
| 弹幕 | ✅ | ✅ | `comment.bilibili.com/{cid}.xml`，raw-deflate 压缩 |
| 音频流 | ✅ | ✅ | dash 3 条音轨；本地无 torch/whisper，ASR 不现实 |

## 命令

### 单 UP 采集（元数据 + 评论 + 字幕）
```powershell
python scripts/bili_collect.py --mid 385670211 --limit 50 `
    --outdir data/up-秋芝2046 --with-comments --with-subs --budget 600
```
断点续传：已完成的视频记在 `videos.jsonl`，重跑自动跳过。

### 找号 / 核粉 / 榜单
```powershell
python scripts/bili.py check --mids-file config/ups.tsv --min-fans 100000 --limit 70
python scripts/bili.py discover --topics "AI Agent|Agent Skills" --mode both
```

## 规模与耗时（实测推算，1.5–2 s/请求）

| 任务 | 请求数 | 耗时 |
|---|---|---|
| 300 个 UP 检查是否更新 | 每 UP 1 次 ≈ 300 | 8–12 分钟 |
| 采集 1 个新视频全量（评论限 200） | 13 | — |
| 每天新增 90–150 个视频的全量 | 1200–2000 | 40–70 分钟，宜分批 |
| 1 个 UP 最近 100 条全量 | ≈ 1300 | 30–40 分钟 |
| 1 个 UP 最高赞 100 条全量 | ≈ 1900 | 45–60 分钟（需先逐个取 stat 才能排序） |

**关键限制**：列表接口不返回 like/favorite，「最高赞」必须逐个视频查 `view` 才能排序，成本翻倍。

## 故障结论（已修复，别重复踩）

- **标题以 `...` 结尾 → 目录建了但写文件报 Errno 2**：Windows 静默去掉目录名末尾的点，
  mkdir 与写入路径不一致。`safe_name()` 现已清掉结尾点和空格，并规避 `CON/PRN/AUX` 等保留名。
- **同一 bvid 出现两个目录**：目录名算法变更后重跑会生成新目录。归并时以
  `f"{bvid}_{safe_name(title,40)}"` 为准，其余删除。
- **匿名请求 `arc/search` 稳定 -352**：缺 `dm_img_list/dm_img_str/dm_cover_img_str` 三个反爬参数；
  脚本已内置 `DM_PARAMS`，失败还会回退搜索接口。
- **`-404 啥都木有`**：视频已被删除或设为不可见，不是采集故障，不要重试。

### F. 全名单深度采集（近90天 + 历史Top10 → 热度Top20）
```powershell
python scripts/bili_deep_collect.py --max-requests 550 --pace 1.5 --rest-every 300 --comment-cap 100 --top-n 20 --quiet
```
选片：`近90天全部 ∪ 历史播放量Top10` → 逐个查详情 → `热度分 = 点赞*1.0 + 收藏*1.5 + 投币*2.0` → 取前 20。
采集：元数据 + 全语言字幕 + 高赞评论前 100 条。
落盘：`1AMdata/bilibili/<前缀>_<UP>_<粉丝量>/<bvid>_<标题>/`，未入选候选进 `_pool/`。

**安全机制**：单并发；间隔 1.5s + 0.75~1.35 抖动；每 300 请求休息 45–90s；
连续限流 120s→300s→600s 退避后优雅停机；每轮上限 550 请求 + 防重入锁 + 静默时段 23:00–08:00；
每完成一个视频即写 state（中断零损失）；纯只读，无任何写行为。

**无人值守**：`setup_deep_task.ps1` 注册每 25 分钟触发的计划任务；`show_state.py` 看进度；`--reset <mid>` 重置单号。

## 纪律

- 单并发、1.5–2 s 间隔、`--budget` 分批；绝不并发跑两个实例。
- 账号级风控比 IP 限流代价高；真被限就等 5–10 分钟或换网络，再续传。
- 静默时段 23:00–08:00 不发起新任务（见 `规则.md`），定时任务排在 08:00 后。
- 与本项目已有的 B 站登录通道（biliup 扫码）可能互踢，**同账号不要两套通道同时高频使用**。
- 产出必须标注采样时间与覆盖范围，不宣称「全站完整」。

---

# 找号 / 扩池 / 无人值守批量采集（2026-11-04-05 新增，已验证）

## 一键入口

```powershell
$S = "<仓库根>\bilibili-auto\scripts"

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

---

# 监听 / 定时任务 / 飞书日报（2026-11-08 新增）

## 组件

| 文件 | 作用 |
|---|---|
| `scripts/watch_common.py` | 公共层：状态、PID 锁、限速、静默、收件箱、已知 bvid 去重 |
| `scripts/bili_ups_watch.py` | UP 投稿增量轮询（tier S/A/B）+ **内联采集元数据与中文逐字稿（不采评论）** |
| `scripts/bili_kw_watch.py` | 关键词轮询（按发布时间排序、游标轮换、标题相关性过滤）+ 内联采集 |
| `scripts/bili_inbox_collect.py` | 收件箱兜底：补元数据/字幕、无字幕按 6h/24h/72h 重试；评论默认关闭（`--comments` 开启） |
| `scripts/bili_digest.py` | 生成日报（Markdown 落盘 + 飞书推送） |
| `scripts/feishu_push.py` | 飞书推送（项目应用凭证 / 自定义机器人） |
| `scripts/register_watch_tasks.ps1` | 注册 / 查询 / 删除 Windows 计划任务 |

## 数据与状态

- 收件箱：`1AMdata/watch/inbox.jsonl`（按 bvid 去重，source=up|kw）
- 视频内容：`1AMdata/watch/videos/<bvid>_<标题>/`（meta / comments / subtitle.zh.*）
- 日报：`1AMdata/watch/digests/YYYY-MM-DD.md`
- 状态：`1AMdata/_state/watch/{ups_state,kw_state,processed,known_bvids}.json`
- 日志：`logs/{ups,kw,inbox,digest}_YYYY-MM-DD.log`

## 常用命令

```powershell
cd <仓库根>\bilibili-auto\scripts
python bili_ups_watch.py --tier S --limit 20 --dry-run    # 只看不写
python bili_kw_watch.py --keywords "AI Agent|具身智能" --pages 1
python bili_inbox_collect.py --max-items 20               # 补字幕/评论
python bili_digest.py                                     # 生成并推飞书
python bili_digest.py --no-push                           # 只落盘
python feishu_push.py --text "测试" --dry-run              # 校验凭证
```

## 定时任务

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_watch_tasks.ps1
# 查看：-Query    删除：-Remove
```

| 任务 | 时间 | 内容 |
|---|---|---|
| BiliWatch-Inbox | 08:00、:30 起每 30 分钟（至 22:30） | 兜底补字幕/元数据 + 字幕重试（每轮 ≤20 条，评论默认关） |
| BiliWatch-UpsS | 08:03 起每小时（至 23:03） | S 级 176 个号 + 内联采字幕（每轮内联 ≤20 条） |
| BiliWatch-UpsA | 08:12 起每 4 小时 | A 级 231 个号 + 内联采字幕 |
| BiliWatch-KW | 08:22 起每 3 小时 | 关键词池 60 词/轮（1 页，每词 ≤3 条、每轮 ≤40 条）+ 内联采字幕（每轮 ≤15 条） |
| BiliWatch-UpsB | 08:35 起每 4 小时 | B 级 419 个号（游标续跑，约 2 轮跑完一圈）+ 内联采字幕 |
| BiliWatch-Digest | 每日 21:00 | 日报 → 飞书 |

### 采集分工（2026-11-08 调整）

- **跟踪阶段（UP/关键词）**：发现新视频时**内联**采元数据 + 中文逐字稿，**不采评论**，每条约 3 个请求。\n- **只收最新**：UP 只收「上次检查之后」发布的（900s 余量），首次见到的号只补最近 6 小时；关键词只收最近 12 小时内、且**必须是名单内创作者**（`only_roster=true`）。不再接受名单外新号。\n- **内联预算**：UP 每轮 ≤20 条、关键词每轮 ≤15 条（全局预算，不是每号各 20）；超出部分进收件箱兜底，避免单轮被首轮/爆发拖过 25 分钟超时。\n- **游标续跑**：每档（S/A/B）记录 cursor，本轮预算用完从断点继续，保证长名单（如 B 级 419 号）也能全量覆盖，不会永远只查前 N 个。
- **收件箱阶段**：只兜底——内联失败/漏掉的补一次；无字幕的按 6h/24h/72h 重试；发布不足 10 分钟的先跳过；**超过 7 天未处理的标记 expired 丢弃**；UP 来源优先于关键词来源。
- **评论**：默认不采；需要时 `python bili_inbox_collect.py --comments`，建议配合 24h 后的成熟样本。

时间表按实测耗时错峰（最坏情况：Inbox :00-02 → UpsS :03-10 → UpsA :12-21 → KW :22-28 → Inbox :30-32 → UpsB :35-50），同一时刻只有一个进程发请求（NetLock）。\n\n### 防膨胀与新鲜度（2026-11-08 晚）\n\n- 关键词：`only_roster=true`（名单外一律丢弃）、`max_age_hours=12`、每词 ≤3、每轮 ≤40、只翻 1 页。\n- UP：按 `prev.checked - 900s` 增量；首见号只补 6 小时；失败不覆盖 checked（下次补回失败窗口）。\n- 日报：只统计名单内、最近 24h；概览里显示「过滤 N 条（名单外/过期）」；新号恒为 0。\n- ⚠️ 配置坑：PowerShell `Set-Content -Encoding UTF8` 会写 BOM，Python json 解析失败会**静默回退代码默认值**（batch=120/每轮 300/补 3 天）。`load_json` 已改用 `utf-8-sig`；改配置请用 Python 写或确认无 BOM。\n\n### 产能与积压（2026-11-08 核算）\n\n- 收件箱产能：20 条/轮 × 29 轮 = **580 条/天**。\n- 关键词流入上限：40 条/轮 × 5 轮 = **200 条/天**（内联再吃 15/轮，实际进收件箱 ≤125/天）。\n- UP 跟踪：约 62 条/天，基本被内联消化；字幕重试约 36 次/天。\n- 合计 ≈170/天 < 580/天，**不会持续积压**；7 天 TTL 兜底防止极端情况无限增长。

### 并发与阻塞（2026-11-08 加固）

- 同一任务：任务计划器策略 `IgnoreNew`，上一次没跑完不会再起第二个。
- 不同任务：靠**全局网络锁 `NetLock`**（`1AMdata/_state/watch/.bili_net.lock`）串行，同一时刻只有一个进程向 B 站发请求；等不到（ups/kw 90s、inbox 300s）就本轮跳过，下次调度补。
- 错峰：Inbox :00/:30、UpsS :08、UpsA :20、UpsB :35、KW :50，避免主要重叠窗口。
- 每个任务 `ExecutionTimeLimit=PT20M`，卡死会被杀掉，不会因 `IgnoreNew` 永久阻塞。
- 电池策略已放开（`DisallowStartIfOnBatteries=false`、`StopIfGoingOnBatteries=false`）；`StartWhenAvailable=true`，休眠唤醒后会补跑。
- 安全节奏：列表接口 pace 1.5s、搜索 2.5s；每 300 请求休息 45–90s；23:00–08:00 静默；每轮请求/时间上限到点优雅退出。

## 飞书

- 默认读 `data/secrets/feishu.env` 的 `FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_CHAT_ID`（tenant_access_token → `im/v1/messages`）。
- 也可在 `config/feishu.json` 填自定义机器人 `feishu_hook` / `secret`（自动签名）。
- 日报无新增时默认跳过推送，`--force-push` 可强制。

## 关键词池与分档

- `config/watch_keywords.txt`：约 180 词，按 AI/硬件/商业/科技/局势/科研/教程 分组，按游标轮换，所有词都会被轮到。
- `config/watch_tiers.tsv`：mid → S/A/B（S=核心 AI 相关；A=科技/创客/黑客；B=商业/炒股/局势）。
- `config/watch.json`：节奏、预算、首见补采窗口（默认 3 天）、关键词每轮上限。

## 运维注意

- Cookie 失效：`preflight()` 直接退出（exit=3），日志出现 `[NO-LOGIN]`；重扫码后自动恢复。
- 无字幕视频（约 20%）不报错，只记 `sub=0`，需要逐字稿时另走 ASR。
- 计划任务用 `pythonw.exe` 静默运行；调试时手动跑同名 .py。
- 关键词轮询只接受「标题含关键词」的结果，避免标签命中带来的噪音。




