---
name: douyin-auto
description: "抖音采集全套：①单账号按需采集（置顶+播放Top10+最新N，含文案/数据/评论/封面/中文字幕 ASR）②按主题找号（视频内容搜索反查作者 + 机构号过滤）③双账号并行队列 ④采集前判断口播型/视觉型。用于「采这个博主」「找某领域的博主」「批量采一批账号」这类需求。"
---

# 抖音单账号采集

> 与 `bilibili-auto` 并列的独立采集管线。项目入口 `../AGENTS.md`，规则 `../规则.md`、`规则.md`。

## 一条命令（推荐）

```powershell
cd <仓库根>\douyin-auto\scripts
.\collect.ps1 -Link "https://v.douyin.com/xxxx/"          # 短链自动解析
.\collect.ps1 -Link "https://www.douyin.com/user/MS4w..."  # 或直接给主页
.\collect.ps1 -Link "<链接>" -SaveVideo yes -Comments 30   # 需保存视频时
```

`collect.ps1` 一次完成：解析短链 → 采集 → 生成报告，屏幕只输出极简摘要。

## Token 纪律（很重要，决定成本）

**跑一次采集的成本与数据量几乎无关**，关键是别把数据读进对话：

| 做法 | Token |
|---|---|
| 采集 12 个作品、4039 字字幕、51 条评论 | **0**（全写磁盘）|
| `collect.ps1` 屏幕摘要 | ~50 |
| 只读 `_report_*.md` 前 60 行 | ~600 |
| 只读 `GET /log -Tail 5` 看进度 | ~80 |
| ❌ 读 `meta.json` / `comments.jsonl` / 完整日志 | 会爆 |

**禁止**：把 `comments.jsonl` 全文、`meta.json` 全文、完整 log 读进上下文；
需要细节时读 `_report_*.md`（已汇总），或让我用脚本回答具体问题。

**正常一次单账号采集的对话成本 ≈ 2–5k token**，与采 5 个还是 15 个作品无关。

## 前置条件（已验证）

| 组件 | 位置 | 状态 |
|---|---|---|
| Python 3.12 | `../../runtime/python/python.exe` | ✅ |
| patchright（反检测 Playwright） | 同 Python 环境 | ✅ |
| Chromium 1208 | `../../runtime/browsers/chromium-1208/chrome-win64/chrome.exe` | ✅ |
| 完整 ffmpeg 7.1 | `...\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe` | ✅ |
| faster-whisper + CUDA 库 | 同 Python 环境 | ✅ |
| ASR 模型 | `large-v3`（已下载）+ `small` | ✅ |
| 登录 profile | `../../data/social/douyin-verify-profile` | ✅ 已扫码登录并持久化 |
| GPU | RTX 4060 Laptop 8GB / CUDA 12.x | ✅ 约 6× 实时 |

## 用法

```powershell
$py = "<项目根>\runtime\python\python.exe"
& $py douyin_collect.py --url "https://www.douyin.com/user/MS4wLjABAAAA..." `
    --save-video auto --comments 20 --asr-model large-v3
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--url` | 必填 | 博主主页链接 |
| `--top-play` | 10 | 置顶 + 播放量排名合计条数（置顶必然入选）|
| `--latest` | 5 | 另取最新 N 个，与上面去重 |
| `--save-video` | auto | `yes` 全存 / `no` 全不存 / `auto` 时长≤180s 且 ≤80MB 才存 |
| `--comments` | 20 | 每作品评论条数 |
| `--asr-model` | large-v3 | `large-v3`（准）或 `small`（快）|
| `--gap` | 25 | 作品间最小间隔秒（防风控）|

## 产出

```
1AMdata/douyin/<博主名>_<粉丝量>/
  _account.json
  <aweme_id>/
    meta.json            文案/作者/点赞/评论数/收藏/分享/时长/封面/音乐/play_urls
    comments.jsonl       评论（含点赞数、日期）
    transcript.zh.srt    中文字幕（带时间轴、已转简体）
    transcript.zh.txt    中文字幕纯文本
    video.mp4            仅 --save-video yes 或 auto 且未超阈值时
```

## 技术要点（踩过的坑）

- **必须 headful**：headless 会被下发「验证码中间页」，抖音能识别无头浏览器。
- **数据走接口拦截，不走 DOM**：拦截 `/aweme/detail/` 与 `/comment/list/` 响应，
  一次拿到全部结构化字段；DOM 上点赞数抓不到、作者会误抓成导航栏「我的」。
- **视频 URL 要点击播放**：`<video>` 是 blob:（MSE），必须 `page.click("video")`
  才会触发真实 `douyinvod.com` 请求；也可从 detail 的 `play_addr.url_list` 直接取。
- **播放量只在主页卡片**：列表页拿不到点赞数；「最火」用卡片播放量近似，
  严格按点赞需要全量打开作品页（会触发风控）。
- **字幕**：抖音无字幕接口，全部走 ASR。Whisper 中文默认输出**繁体**，
  已用 OpenCC `t2s` 统一转简体。
- **PyAV 版本冲突**：faster-whisper 调 `av.open(metadata_errors=...)`，
  PyAV 19 已移除该参数 → **直接用 ffmpeg 解码成 numpy** 喂模型，绕开 PyAV。
- **必须用 imageio 的完整 ffmpeg**：Playwright 自带的是精简版，不支持 WAV。
- **验证码判定**：正常页面常驻隐藏 captcha iframe，必须判「可见」或标题含「验证码」，
  不能凭元素存在。
- **风控节奏**：实测搜索页约 5 次自动访问即触发验证码；单账号采集控制在
  1 主页 + ≤15 作品页，作品间隔 25–40s，触发验证码立即停止保留进度。

## 已知限制

- 单账号 15 个作品约需 20–40 分钟（含 ASR）。
- 触发验证码后需人工在浏览器过一次再继续（脚本会停止并保留已完成部分）。
- 视频保存阈值在 `auto` 下按「时长≤180s 且 ≤80MB」，超过则只留字幕。
- 未验证：多账号批量、验证码自动过、非中文语种字幕。
## 今日新增的四个坑（2026-11-02 已修，别再踩）

1. **主页滚动会混入推荐/相关视频**：主页作品列表滚多了会出现非本账号的视频。
   必须用 `author_sec_uid == 目标账号 sec_uid` 校验，不匹配直接丢弃并删目录。
   曾误采「真会玩车的蛋哥」的本田 P7 视频。
2. **账号目录名要用接口的昵称/粉丝数**：页面 `title()` 是「XXX的抖音」，且粉丝数正则
   常误匹配（曾把 22110 解析成 8）。已改为：目录复用按昵称前 4 字模糊匹配 +
   结尾用 detail 的 `author.follower_count` 覆盖。
3. **PowerShell 脚本必须带 UTF-8 BOM**：`.ps1` 含中文时，PS 5.1 按 GBK 解析会报
   「Missing closing ')'」语法错误。已给 `collect.ps1` 加 BOM。
4. **`*>>` 在 PS 5.1 不捕获原生 stderr**：Python 的 traceback 可能不进日志。
   排查时直接前台跑 Python 看完整堆栈。

## 已知数据瑕疵

- ASR 对同音词会错（如「意念」→「一脸」）。如需更高可读性，可加 LLM 后处理纠错
  （把 transcript.zh.txt 过一遍同音纠错 prompt）。
## 接力采集（断点续传，2026-11-02 已验证）

两种「续传」语义：

### 1) 幂等跳过（默认，任何模式生效）
已采过的 `aweme_id` 目录里同时存在 `meta.json` 和 `transcript.zh.txt` 就跳过，
重跑不会重复请求、不重复花 ASR 算力。

### 2) 接力往更早采（`--mode next`）
```powershell
# 第一次：置顶+播放Top10+最新5
.\collect.ps1 -Link "<主页>"

# 第二次起：从上次最后一条继续往更早采 15 个
.\collect.ps1 -Link "<主页>" -Mode next -Count 15 -Scroll 10

# 再下一次：继续往更早（自动接着上次的游标）
.\collect.ps1 -Link "<主页>" -Mode next -Count 15 -Scroll 15
```

**游标机制**（关键设计）：不靠序号，而是在**当前时间轴**上找「最后一条已采作品」的位置，
从它之后往更早取。这样即使博主发了新视频（插到最前面），也不会错位。

`_account.json` 记录：
| 字段 | 含义 |
|---|---|
| `collected[]` | 累计已采 aweme_id（跨批次保留）|
| `works_order[]` | 上次抓到的完整作品顺序（发布倒序）|
| `works_seen` | 主页能加载到的作品数 |
| `cursor_last` | 上次采到的最早一条 aweme_id |
| `mode` | 上次运行模式 |

**实测**：蓝星智人 12 → 15 → 17 个作品，每次接力都正确接着更早的。

**限制**：主页是无限滚动，`--scroll` 决定能加载多深。想看很老的历史就把 `--scroll` 调大
（8–15 轮），但滚动越多越容易触发风控，建议分批。

## 串行队列（run_queue.ps1，2026-11-02 加入）

多个博主排队采集时**不能并行**（共用同一个浏览器 profile，会冲突且风控翻倍）。
用队列串行：

```powershell
# 链接写进文件（避免命令行逗号被拆错）
# config\queue_links.txt 每行一个短链或主页
Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',
  '"<仓库根>\douyin-auto\scripts\run_queue.ps1"','-LinksFile','"<仓库根>\douyin-auto\config\queue_links.txt"' -WindowStyle Hidden
```

特点：
- 每个任务开始前轮询「没有其它 douyin_collect.py 在跑」，自动等待
- 任务之间休息 120s
- 状态写 `logs/queue-status.txt`，日志写 `logs/queue-*.log`
- 全程不占用对话（独立进程），token 为 0

---

# 找号 / 批量队列 / 类型判定（2026-11-04-05 新增，已验证）

## 三条工作流

### A) 单博主采集（最常用）
```powershell
cd <仓库根>\douyin-auto\scripts
.\collect.ps1 -Link "https://v.douyin.com/xxxx/"        # 短链自动解析
```
产出：`1AMdata/douyin/<博主名>_<粉丝量>/<aweme_id>/{meta.json, comments.jsonl, transcript.zh.srt/.txt}`

### B) 按主题找号
```powershell
# 1) 视频内容搜索反查作者（比按名字搜准 10 倍）
python douyin_find_by_video.py --themes 科技创客 --gap 360 --min-fans 100000
# 2) 生成采集队列（含机构号过滤）
python build_talk_queue.py --themes "名人访谈,前沿资讯,科技前沿,创业" --split 2
```

### C) 双账号并行批量采集
```powershell
# 两个 queue 文件分别跑（必须用不同 profile，否则 Chromium 锁冲突）
.\run_queue.ps1 -LinksFile <p1.txt> -TopPlay 10 -Latest 5 -Gap 55 -StatusTag acct1
.\run_queue.ps1 -LinksFile <p2.txt> -TopPlay 10 -Latest 5 -Gap 55 `
    -Profile "<项目根>\data\social\douyin-account2-profile" -StatusTag acct2
```

**代价**：每账号 15 视频约 35–50 分钟；双账号合计约 **3 个/小时**。

## 发现渠道：视频搜索 > 名字搜索

| 方式 | 接口 | 效果 |
|---|---|---|
| **视频内容搜索** ✅ | 拦截 `/aweme/v1/web/search/item/` | 每关键词 26 条视频 → 18–26 个新作者 |
| 账号搜索 | `search?type=user` | 名字模糊、同名多，命中「ai」这种词全是噪声 |
| 短链解析 | `resolve_share.py` | 分享链接 → 主页 |

**关键实现细节**：搜索结果要**主动等接口返回**（最多 25 秒）。只等 4–5 秒会拿到 0 条。

## 机构号过滤（只要个人自媒体）

`build_talk_queue.py` 里的 `is_personal()`：

- **HARD 排除**：央视/人民日报/新华社/共青团/观察者网/卫视/日报/新闻网 + 品牌（华为/小米/腾讯/阿里/字节/特斯拉/比亚迪…）+ 大学/研究院
- **SOFT 排除**：集团/公司/商城/官方/频道/传媒/协会/出版社/杂志（有「老师/哥/姐/叔/博士/教授」等个人词则豁免）

**踩过的坑**：`SOFT_INST` 里不能放「工作室」「实验室」——思维实验室、卢克文工作室是个人创作者。

## 采集前判断：口播型 vs 视觉展示型

创客类视频很多是纯展示（无旁白），ASR 出来接近空。

```powershell
python probe_creator_type.py --url "<主页链接>"
```
采样 1 个作品的前 60 秒音频跑 ASR，算「字/秒」：

| 字/秒 | 判定 | 建议 |
|---|---|---|
| ≥1.5 | 口播型 | 正常全量采（含字幕）|
| 0.8–1.5 | 混合型 | 正常采 + 标记 |
| **<0.8** | **视觉型** | 只采元数据+评论+封面，跳过 ASR |

**成本**：2 次页面访问 + 10 秒 ASR ≈ 40 秒/博主（全量采集要 60 分钟，探测只占 1%）。

**不能用便宜信号判断**：时长、文案长度、标签数都不可靠（实测反例：蓝星智人 45 秒却字/秒 6.78 = 口播；八零彪子 211 秒却 0.43 = 视觉）。

## 字幕密度实测（858 个作品）

| 指标 | 数值 |
|---|---|
| 全库平均 | 1,293 字/作品 |
| 字幕 <50 字（纯展示）| **12.4%** |
| 口播型（≥4 字/秒）| 大部分 |

统计脚本：`audit_subtitle_density.py`

## 视觉型视频的信息提取（替代字幕）

对无旁白的视频，按性价比：

| 优先级 | 方法 | 提取什么 | 成本 |
|---|---|---|---|
| 1 | **评论分析** | 观众追问型号/材料/教程 | 0（已有）|
| 2 | **封面图分析** | 成品外观、材料、场景、画面文字 | 1 张图 |
| 3 | 关键帧抽取（4–6 帧）| 制作过程步骤 | ffmpeg 本地 |
| 4 | 画面 OCR | 型号/参数/代码 | 需装 OCR |

封面 URL 就在 `meta.json` 的 `cover` 字段，**零额外请求**。

## 队列续跑机制

- 队列文件：`config/queue_talk_p1.txt` / `p2.txt`（每行一个主页 URL）
- 进度：`logs/queue-status-<tag>.txt`
- **已采作品自动跳过**（`meta.json` + `transcript.zh.txt` 都在才算完成）
- 中断后改用 `queue_talk_pX_resumeN.txt` 只放未采的，避免重复扫描

## 当前数据规模（2026-11-05）

| 项 | 数值 |
|---|---|
| 博主账号 | 250 个 |
| 视频 | 3,530 个 |
| 字幕 | 3,337 个（94.5%）|
| 主题 | 科技创客 61 + 名人访谈/前沿资讯/科技前沿/创业 208 |

## Token 纪律

| 操作 | Token |
|---|---|
| 单博主采集（30 视频）| ~0（全写盘）|
| `collect.ps1` 屏幕摘要 | ~50 |
| 读 `_report_*.md` 前 60 行 | ~600 |
| **禁止**：读 `comments.jsonl` / `meta.json` 全文 | 会爆 |

正常一次单账号采集的对话成本 ≈ **2–5k token**，与采 5 个还是 30 个作品无关。

---

# 五种输入形态 → 对应命令（2026-11-07 补齐）

| 你的输入 | 要什么 | 命令 |
|---|---|---|
| **1. 领域名**（「找 AI 创业类的博主」）| 找号 | `douyin_find_by_video.py --themes <主题> --gap 360` |
| **2. 博主主页链接** | 采该博主全量 | `.\collect.ps1 -Link "<主页>"` |
| **3. 某条视频链接** | 反查作者 → 采他主页其他视频 | `python from_video.py --url "<视频>" --collect` |
| **4. 某条视频链接** | 找**同主题的其他视频** | `python related.py --url "<视频>"` |
| **5. 某条视频链接** | 找**同主题的其他博主** | `python related.py --url "<视频>" --min-fans 100000 --queue [--collect]` |

## ③ from_video.py（视频 → 作者 → 采集）

```powershell
python from_video.py --url "https://v.douyin.com/xxxx/"                  # 只解析作者
python from_video.py --url "https://v.douyin.com/xxxx/" --collect        # 解析并采集
python from_video.py --url "https://www.douyin.com/video/7623..." --collect --top-play 10 --latest 5
```

原理：打开视频页 → 拦截 `/aweme/detail/` → 取 `author.sec_uid` → 拼主页 URL → 交给 `douyin_collect.py`。

## ④⑤ related.py（视频 → 相关视频/博主）

```powershell
python related.py --url "https://v.douyin.com/xxxx/"                       # 列相关视频
python related.py --url "..." --rounds 3                                   # 扩散 3 轮（打开高赞相关视频继续挖）
python related.py --url "..." --min-fans 100000 --queue                    # 生成博主队列
python related.py --url "..." --min-fans 100000 --queue --collect          # 生成并采集
```

**原理（关键）**：抖音作品页会请求 `/aweme/v1/web/aweme/related/`，返回的 `aweme_list`
就是算法按内容相似度排好的「相关视频」，每条带作者与粉丝数。

**比关键词搜索更准** —— 算法已经做过语义匹配，不受关键词措辞影响。
`--rounds N` 会拿上一轮最高赞的相关视频当新种子，指数式扩散。

产出：
- `config/related_result.json`：相关视频（按点赞）+ ≥阈值的作者列表
- `config/queue_related.txt`：可直接喂给 `run_queue.ps1` 采集

## 组合用法示例

> 「这个视频不错，找一批同类型的博主都采了」

```powershell
python related.py --url "<视频链接>" --rounds 2 --min-fans 100000 --queue --collect
```

会自动：打开视频 → 挖相关视频 → 聚合作者 → 筛粉丝 → 逐个采集（每号 top10+latest5）。

