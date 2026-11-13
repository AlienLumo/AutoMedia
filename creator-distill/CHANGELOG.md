# CHANGELOG

## 0.1.0 — 2026-11-09

- 建立平台无关骨架：`schema/creator.schema.json`（schema v1）、`adapters/`、`distill/`、`scripts/distill.py`。
- 实现小红书 adapter：
  - 搜索 + 主页列表（含 `xsec_token` 补全）；
  - 详情页解析（title/desc/tags/counts/author/author_id/date）；
  - 视频下载（Referer + HTML 提取 mp4）；
  - ffmpeg 抽帧（默认 4 帧）+ contact_sheet 拼接；
  - faster-whisper large-v3 ASR（wav 用 wave 直读，绕开 PyAV `metadata_errors` 兼容问题）。
- 报告：画像、标题公式、高赞榜、逐字稿结构（钩子/首句/收尾/语速/原理词/60s 分段）、视觉待分析清单。
- 首次样本：`鹏鹏有个想法`（30 条作品，2 条深度：视频+抽帧+ASR），报告
  `1AMdata/distill/xiaohongshu/鹏鹏有个想法/report.md`；视觉分析由 AI 读 contact_sheet 后写入。

## 0.1.1 — 2026-11-09

- 修复 ASR 质量：加 initial_prompt、condition_on_previous_text=False，中文标点恢复，
  消除“请不吝点赞…明镜与点点栏目”这类片尾幻觉；同音字仍存（可用画面字幕校正）。
- 修复报告结构：首句/收尾改为按字幕分段取，不再出现“首句=收尾”。
- 标题清洗：去掉 #话题 与固定标签词（心理学/涨知识等）。
- 视频选择：改用网络响应监听 + 页面播放器时长校验（避免抓到推荐位视频）。
- 新增 --reuse：复用 creator.json 重算报告，不重复下载/ASR。
- 新增“来源可疑信号”检测（订阅/打赏/栏目等片尾话术），并注明 ASR 幻觉可能误报。
