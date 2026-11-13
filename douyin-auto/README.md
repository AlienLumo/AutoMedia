# douyin-auto

抖音只读采集 skill：单账号按需采集、按主题找号、视频反查作者 / 相关博主、串行队列，
以及采集前判断「口播型 / 视觉展示型」。整个 skill **只读**，不产生任何写平台行为。

## 作用

- **单账号采集**：置顶 + 播放量 Top10 + 最新 N；抓文案 / 互动数据 / 评论 / 封面；
  没有字幕时用 faster-whisper 生成中文字幕（已转简体）。
- **找号**：视频内容搜索反查作者（比按名字搜准 10 倍）+ 机构号过滤 + 队列生成。
- **视频 → 作者 / 相关视频 / 相关博主**：`from_video.py`、`related.py`。
- **串行队列**：多博主排队采集、断点续跑；双账号用不同 profile 并行。
- **采集前探测**：`probe_creator_type.py` 用一条作品的前 60 秒音频算字 / 秒，判断口播或视觉型。

## 前置依赖

| 组件 | 说明 |
|---|---|
| Python 3.12 + patchright | 反检测 Playwright，需要 headful 浏览器 |
| Chromium 1208 | `PROJECT/runtime/browsers/chromium-1208/` |
| 完整 ffmpeg | imageio-ffmpeg 自带的 v7.1（Playwright 自带版本不支持 WAV） |
| faster-whisper + CUDA 库 + 模型 | `large-v3`（准）/ `small`（快） |
| 抖音登录 profile | 自备，不入库：`data/social/<profile>`（默认 `douyin-verify-profile`） |
| 可选 GPU | RTX 4060 级别，约 6 倍实时 |

## 快速开始

```powershell
cd <仓库根>\douyin-auto\scripts
$py = "<项目根>\runtime\python\python.exe"

# 一条命令采集一个博主（短链自动解析）
.\collect.ps1 -Link "https://v.douyin.com/xxxx/"

# 按主题找号 → 生成队列
& $py douyin_find_by_video.py --themes 科技创客 --gap 360 --min-fans 100000
& $py build_talk_queue.py --themes "科技前沿" --split 2

# 串行队列采集（文件每行一个主页链接）
.\run_queue.ps1 -LinksFile config\queue_talk_p1.txt
```

`--help`：`douyin_collect.py`、`douyin_find_bloggers.py`、`douyin_find_by_video.py`、
`probe_creator_type.py`、`related.py`、`report.py`。

## 产出目录

```
<项目根>/1AMdata/douyin/<博主名>_<粉丝量>/
  _account.json                 # 累计已采、游标、模式
  <aweme_id>/
    meta.json                   # 文案 / 作者 / 互动数 / 时长 / 封面 / 播放地址
    comments.jsonl              # 评论
    transcript.zh.srt / .txt    # 中文字幕
    video.mp4                   # 仅 --save-video 开启且未超阈值时
<项目根>/1AMdata/douyin/_report_*.md
<skill>/logs/                   # 队列状态与日志（运行时生成，不入库）
```

`1AMdata/` 位于项目根，**不写进本发布仓**。

## 安全边界

- 只读：不点赞 / 收藏 / 关注 / 评论 / 发布；不绕过验证码，触发验证码立即停止并保留进度。
- 必须 headful；单账号 ≤1 主页 + ≤15 作品页，作品间隔 25–40s；不同账号用不同 profile。
- 队列串行，禁止同时跑多个采集实例（会互相抢浏览器锁并放大风控）。
- 凭据 / profile 只从本地读取，不随仓库分发。

## 路径约定

- 脚本统一通过 `scripts/_paths.py` 解析路径：
  - `PROJECT`：含 `1AMdata/`、`data/`、`runtime/` 的项目根；默认为仓库根（发布仓布局）或仓库根上一级（skills 布局），可用 `AUTOMEDIA_ROOT` 覆盖。
  - `DATA` = `PROJECT/1AMdata`；`SKILL` = 本 skill 目录；`SCRIPTS` = `SKILL/scripts`。
- 文档中的 `<项目根>` 即上述项目根；`<抖音账号>`、`<USER_HOME>` 等为脱敏占位符。

## 与源仓关系

- 本目录是工作区 `skills/douyin-auto/` 的**脱敏发布快照**。
- 已移除：`logs/`、`__pycache__/`、`*.pyc`、本机绝对路径、个人账号 / 邮箱、机器人密钥明文。
- 保留：公开博主名单（`config/*.tsv`）、公开主页 URL、`SKILL.md` 结构与实测结论。
- 运行时的工作副本与数据仍在工作区；改动 skill 后需同步回本目录再提交。
