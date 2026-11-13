# bilibili-auto

B 站只读采集与监听 skill：按 UP 主批量抓取视频元数据、评论、字幕（逐字稿），按主题找号扩池，
以及 UP / 关键词增量监听与每日日报。整个 skill **只读**，不产生任何写平台行为。

## 作用

- **单 UP / 全名单采集**：元数据（播放、点赞、投币、收藏、弹幕）、评论、AI 字幕（多语种），断点续传。
- **深度采集**：近 90 天 + 历史播放 Top10 → 热度 Top20，落盘元数据 + 字幕 + 高赞评论。
- **找号扩池**：视频搜索反查 → 账号搜索 → 采样核验 → 机构号过滤 → 名单定稿。
- **增量监听**：UP 投稿轮询 + 关键词轮询 + 收件箱兜底 + 每日日报。
- 底层能力：WBI 签名、限流熔断、网络锁、静默时段、请求预算。

## 前置依赖

| 组件 | 说明 |
|---|---|
| Python 3.12 | 建议用项目内 `runtime/python/python.exe`（`PROJECT/runtime/python`） |
| B 站登录态 | 自备，不入库：`data/sau/cookies/*.json` 或手工 `credentials/bili_cookie.txt` |
| 可选：faster-whisper + ffmpeg | 给没有 AI 字幕的视频补本地 ASR |
| 可选：飞书机器人 | 日报推送（应用凭证，或 `config/feishu.json` 里的自定义机器人） |

## 快速开始

```powershell
cd <仓库根>\bilibili-auto\scripts

# 1) 单个 UP：最近 30 条（元数据 + 评论 + 字幕）
.\collect_one.ps1 -Mid 385670211 -Limit 30

# 2) 找号：按主题搜视频、反查作者
python bili_video_search.py --topics "AI Agent" --pages 2

# 3) 看深度采集进度
python show_state.py
```

全部入口都支持 `--help`：`bili.py`、`bili_collect.py`、`bili_deep_collect.py`、
`bili_subs.py`、`bili_video_search.py`、`bili_ups_watch.py`、`bili_kw_watch.py`、
`bili_inbox_collect.py`、`bili_digest.py`。

## 产出目录

```
<项目根>/1AMdata/bilibili/<前缀>_<UP>_<粉丝量>/<bvid>_<标题>/
<项目根>/1AMdata/watch/        # 监听收件箱、视频、日报
<项目根>/1AMdata/_state/       # 断点状态
<skill>/logs/  <skill>/cache/  # 运行日志 / WBI 缓存（运行时生成，不入库）
```

`1AMdata/` 位于项目根，**不写进本发布仓**。

## 安全边界

- 只读：不点赞 / 投币 / 收藏 / 评论 / 关注 / 发布；不绕过验证码、不改账号资料。
- 单实例串行：列表接口 pace 1.5s、搜索 2.5s；23:00–08:00 静默；每轮有请求上限。
- 凭据只从本地读取，不进日志、不随仓库分发；登录失效时直接停机，等人工重登。
- 产出标注采样时间与覆盖范围，抽样不宣称「全站完整」。

## 路径约定

- 脚本统一通过 `scripts/_paths.py` 解析路径：
  - `PROJECT`：含 `1AMdata/`、`data/`、`runtime/` 的项目根；默认为仓库根（发布仓布局）或仓库根上一级（skills 布局），可用 `AUTOMEDIA_ROOT` 覆盖。
  - `DATA` = `PROJECT/1AMdata`；`SKILL` = 本 skill 目录；`SCRIPTS` = `SKILL/scripts`。
- 文档中的 `<项目根>` 即上述项目根；`<B站账号>`、`<USER_HOME>` 等为脱敏占位符。

## 与源仓关系

- 本目录是工作区 `skills/bilibili-auto/` 的**脱敏发布快照**。
- 已移除：`credentials/`、`logs/`、`data/`、`cache/`、`__pycache__/`、`*.pyc`、`*.log`、`*.bak*`、
  本机绝对路径、个人账号 / 邮箱、机器人密钥明文。
- 保留：公开 UP 主名单（`config/*.tsv`）、公开主页 URL、`SKILL.md` 结构与实测结论。
- 运行时的工作副本与数据仍在工作区；改动 skill 后需同步回本目录再提交。
