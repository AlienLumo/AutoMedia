---
name: creator-distill
version: 0.1.0
description: "博主蒸馏（独立 skill，与批量采集器解耦）：按需取单个博主的作品→元数据+文案（字幕/ASR）+抽帧图像→生成结构化蒸馏报告（画像/标题公式/文案结构/视觉分析/可复用模板）。平台无关，当前已实现小红书 adapter。"
---

# creator-distill（v0.1.0）

> 独立于 bilibili-auto / douyin-auto / xiaohongshu-auto 的**按需单博主分析** skill。
> 采集器是“数据源”；本 skill 只消费统一契约（schema v1），不 import 采集器代码。
> 运行时：项目根 `runtime/`（patchright + chromium + faster-whisper）。

## 目录与版本

```
creator-distill/
  VERSION                  # 语义化版本（当前 0.1.0）
  CHANGELOG.md
  schema/creator.schema.json   # 统一契约（schema v1）
  adapters/                    # 平台取数：xiaohongshu（已实现）/bilibili/douyin（待实现）
  distill/                     # stats / titles / structure / report
  scripts/distill.py           # 统一 CLI
1AMdata/distill/<platform>/<creator>/
  creator.json                 # 统一契约数据
  report.md                    # 蒸馏报告
  works/<work_id>/{detail.json, video.mp4, audio.wav, transcript.json, frames/}
```

## 用法

```powershell
$py = "<项目根>/runtime/python/python.exe"
cd <项目根>/creator-distill/scripts

# 小红书：取主页作品 + 前 2 条下载/抽帧/ASR + 生成报告
& $py distill.py --platform xiaohongshu --creator "鹏鹏有个想法" --detail 2 --frames 4

# 只看数据不下载：--detail 0 --no-asr
```

## 流水线（平台无关）

1. **adapter.fetch()** → `creator.json`（schema v1：creator + works + metrics + transcript + frames）
2. **媒体处理**：视频号下载 mp4 → ffmpeg 抽帧（默认 4 帧 + contact_sheet）→ 可选 ASR
   （faster-whisper large-v3；wav 用 wave 直读，绕开 PyAV 版本坑）
3. **报告**：`distill/report.py` 生成画像、标题公式、高赞榜、逐字稿结构、视觉待分析清单
4. **视觉分析（AI 读图）**：agent 用 `read_image` 看 `contact_sheet.jpg` + 单帧，
   把结论写回 `report.md` 第 4 节（这是当前唯一需要模型参与的步骤）

## 平台适配进度

| 平台 | 视频信息 | 文案 | 状态 |
|---|---|---|---|
| 小红书 | 搜索/主页列表 + 详情 | 视频→下载+ASR；图文→desc | ✅ v0.1 |
| B站 | 元数据 API | 平台字幕（~80%） | 待做（最省，建议下一个） |
| 抖音 | 页面解析 | 下载+ASR | 待做 |

## 注意

- 小红书详情必须带 `xsec_token`：搜索卡片可取；主页列表需按标题二次搜索补。
- 小红书视频地址从详情页 HTML 提取（`sns-video-*.mp4`），下载带 Referer。
- ASR 用 GPU（int8_float16）；单条 2 分钟视频约 20–40 秒。
- 只读；不点赞/收藏/关注/评论/发布；控制频率（3–8 秒间隔）。
- 版本规则：新增平台只加 `adapters/<platform>.py`，不改 schema；schema 变更升
  `schema_version` 并在 CHANGELOG 记录。
