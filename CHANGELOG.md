# CHANGELOG

## 0.1.0 — 2026-11-13

首个公开发布版：四个只读采集/分析 Skill 合集。

- **bilibili-auto**：UP 主批量采集（元数据/评论/字幕）、按主题找号扩池、监听与日报、826 名单。
- **douyin-auto**：单账号采集（置顶+Top10+最新）、按主题找号、中文字幕 ASR、串行队列。
- **creator-distill**：对标博主结构化解剖（schema v1），小红书 adapter 已实现。
- **news-source**：281 个信息源 → 资讯池 → 当日大事件素材库（原文/口播稿/截图/录屏）。
- 发布工程：脱敏（去绝对路径/账号/密钥）、`scripts/install.ps1` 安装、`scripts/doctor.py` 自检、
  `scripts/feishu_setup.py` 飞书一键配置、GitHub Actions CI、MIT License。
