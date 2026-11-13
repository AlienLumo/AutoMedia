---
name: news-source
version: 0.1.0
description: "AI 资讯选题素材库（信息源）：从上游资讯池聚类当日大事件 → 抓取原文 → 生成事件 README 与 60 秒口播文案 → 抓截图/录屏/人物头像 → 输出可直接做短视频的素材库（1信息源/<日期>/）。用于「今天 AI 圈有什么大事」「把今日新闻做成选题素材」「给某条新闻配原文/截图/录屏/口播稿」这类需求。"
---

# 信息源（AI 大事件素材库）

> 采集管线成员之一，与 `bilibili-auto` / `douyin-auto` / `xiaohongshu-auto` / `creator-distill` 并列。
> **上游**：资讯池由 `1AMdata/news/` 引擎每小时轮询产生（计划任务 `\NewsHourlyPoll`、`\NewsDaily1700`），不归本 skill 管，本 skill 只消费 `pool/items.jsonl`。
> **下游**：成片渲染交给 `video-studio`（通用竖屏渲染器）；发布走小绿工作台。

## 边界

```
1AMdata/news/pool/items.jsonl        ← 上游资讯池（每小时追加，独立引擎）
        │  cluster.py（按桶聚类当日条目）
        ▼  人工挑选 10 个大事件 → config/events/<日期>.json
        │  collect.py（抓原文）→ add_official.py（补官方动态页）
        ▼
1信息源/<日期>/<事件>/{原文/, raw/, links.json, README.md, 文案素材.md, 截图/, 录屏/}
        │  capture_visuals.py（截图/录屏/人物头像）+ build_docs.py（文档成品）
        ▼
video-studio / 小绿发布                  ← 下游消费方
```

## 一条命令（每个阶段独立）

```powershell
$py = "<项目根>/runtime/python/python.exe"
cd <项目根>/news-source/scripts

& $py cluster.py                         # 1) 当日资讯池聚类，打印候选事件（只读）
& $py collect.py                         # 2) 按 config/events/261111.json 抓原文
& $py build_docs.py                      # 3) 生成每个事件的 README.md + 文案素材.md
& $py capture_visuals.py                 # 4) 截图/录屏（可 --only 01_anthropic-ipo）
& $py stats.py                           # 5) 统计核对（原文/字数/截图/录屏）
```

换一天：`$env:NEWS_DATE="261115"` 后复制一份 `config/events/261115.json` 改事件，其余命令不变。

## 前置条件

| 组件 | 位置 | 用途 |
|---|---|---|
| Python 3.12 | `<项目根>/runtime/python/python.exe` | 全部脚本 |
| requests | 同 Python 环境 | `collect.py` / `add_official.py` |
| patchright + Chromium 1208 | `<项目根>/runtime/` | `capture_visuals.py` 截图录屏 |
| ffmpeg（imageio_ffmpeg） | `<项目根>/runtime/python/.../binaries/` | 分镜拼录屏 mp4 |
| Pillow + numpy | 同 Python 环境 | 拼图/清晰度对比 |

## 产出结构

```
1信息源/<日期>/
  README.md               当日素材库索引（事件/原文/链接/截图/录屏 + 抓取缺口）
  _index.json             抓取状态索引
  _visual_manifest.json   视觉素材清单（capture_visuals 产出）
  <事件>/
    README.md             事件摘要 + 时间线 + 关键数字 + 素材清单 + 视觉素材
    文案素材.md            60 秒口播草稿 + 3 分钟结构 + 钩子/标题/金句/数据/观点/风险
    原文/*.md             清洗后的正文（含官方动态页）
    raw/*.html            原始 HTML
    links.json            链接与抓取状态（chars > 200 才算有正文）
    截图/*.png|jpg        整页长图 / 标题区 / 滚动分镜 / 页面大图
    录屏/*.mp4            页面滚动视频（可直接做 B-roll）
  关键人物/                人物头像 + 来源授权说明
```

## 配置

| 文件 | 作用 |
|---|---|
| `config/buckets.json` | 事件分桶关键词（`cluster.py` 用） |
| `config/events/<日期>.json` | 当日选题：事件 slug、标题、原文链接清单 |
| 环境变量 | `NEWS_DATE` 日期目录、`NEWS_DATA_ROOT` 素材根、`NEWS_POOL` 资讯池路径、`NEWS_RUNTIME` 运行时根（见 `scripts/news_paths.py`） |

所有脚本路径都由 `scripts/news_paths.py` 解析，默认回到项目布局；
**换机器/换目录不需要改脚本**，设环境变量或保持 `1信息源/<日期>/` 结构即可。

## 流程要点（人工介入点）

1. `cluster.py` 只做候选，**事件取舍靠人**：10 个事件通常覆盖 2–3 个不同方向（资本/产品/成本）。
2. `collect.py` 抓不到的付费墙（Bloomberg/NYT/MarketWatch 等返回 403/401）会记进 `links.json`，
   在 README 的「抓取缺口」里显式列出，**不编造正文**。
3. `build_docs.py` 里 `E` 字典是「当日素材摘要」（摘要/时间线/数字/钩子/标题/观点/风险），
   换日需替换或由 AI 重写 —— 这是本 skill 唯一需要人工/模型参与的部分。
4. `capture_visuals.py` 每页抓：整页长图 → 标题区 → 4 张滚动分镜 → 页面大图 → 36 帧拼滚动 mp4。
5. 交付前跑 `stats.py` 核对，`check_wayback.py` 查付费墙是否有公开快照可引用。

## 踩过的坑

- **英文站点的 CN_ 截图是误分类**：同一链接可能同时产生 `CN_*` 与 `EN_*`，用 `clean_dups.py` 清理。
- **Cookie/订阅浮层会糊满整页**：`dismiss()` 按 Esc + 遍历 iframe + 移除 fixed 浮层，滚动中每 6 帧再清一次。
- **整页长图超时**：`full_page` 截图给 60s 超时，懒加载要先滚到 6000px 再回顶。
- **录屏不是真录屏**：用 36 张分镜帧拼 mp4（8fps），比 Playwright video 稳定且体积小。
- **`device_scale_factor` 影响清晰度**：2x 原生截图更清楚，对比见 `_dev/make_dpi_compare.py`。
- **Wayback 要用 `id_` 版本**：`web.archive.org/web/<ts>id_/<url>` 才能拿到原始 HTML。
- **tmtpost 同一链接挂多个事件**：抓取前先看 `links.json` 里的重复，避免同一篇进两个事件。
- **`chars > 200` 才算正文**：付费墙/反爬页会返回 200 但正文为空，判定按正文字数而不是 HTTP 状态。

## 安全与边界

- **只读**：不登录、不改平台账号、不绕过付费墙或验证码；拿不到就标注缺口。
- 付费墙内容只使用标题/摘要级信息；Wayback 公开快照仅为事实核查，引用以原文为准。
- 所有数字必须标来源与日期；AI 生成画面需加「AI 生成」标识。
- 素材库（`1信息源/`）**不进 git**：截图/录屏/原文是数据产物，仓库只留本 skill 的代码与配置。

## Token 纪律

采集全程写盘，**不要把 `原文/*.md`、`links.json` 全文读进对话**；
需要概览时读 `README.md`（已汇总）或跑 `stats.py`（一张表）。单日 10 事件 ≈ 33 篇原文 / 20 万字符，
直接读会爆上下文，按需只看 1–2 篇。

## 目录

```
news-source/
  SKILL.md  README.md  VERSION  CHANGELOG.md  requirements.txt
  scripts/
    news_paths.py        统一路径解析（PROJECT/DATA_ROOT/DATE/POOL/RUNTIME）
    cluster.py           资讯池 → 当日候选事件
    collect.py           按事件配置抓原文
    add_official.py      补官方动态页（Anthropic/OpenAI/Google）
    build_docs.py        生成事件 README + 文案素材
    capture_visuals.py   截图/录屏/人物头像
    stats.py             素材量统计
    clean_dups.py        清理 CN_/EN_ 重复截图
    extract_key.py       关键词关键句抽取
    extract_snippets.py  事实句抽取（控制输出长度）
    check_wayback.py     付费墙 Wayback 快照检查
    _dev/                一次性调试脚本（清晰度对比、dsf 测试）
  config/
    buckets.json         事件分桶关键词
    events/<日期>.json   当日选题与链接
```
