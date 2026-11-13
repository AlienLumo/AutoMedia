# creator-distill · 对标博主结构化解剖

按需取**单个博主**的作品 → 元数据 + 文案（字幕/ASR）+ 抽帧图像 → 生成结构化蒸馏报告
（画像 / 标题公式 / 文案结构 / 视觉分析 / 可复用模板）。

- 独立于批量采集器：采集器是数据源，本 skill 只消费统一契约（schema v1），不 import 采集器代码。
- 平台无关：当前实现小红书 adapter，B站 / 抖音 adapter 待做。
- 只读：不点赞 / 收藏 / 关注 / 评论 / 发布，控制频率（3–8 秒间隔）。

完整流水线、报告结构与踩坑见 **[SKILL.md](SKILL.md)**。

## 目录

```
creator-distill/
  VERSION                      # 语义化版本（当前 0.1.0）
  SKILL.md  README.md  CHANGELOG.md
  schema/creator.schema.json   # 统一契约（schema v1）
  adapters/                    # 平台取数：xiaohongshu（已实现）/ bilibili / douyin（待实现）
  distill/                     # stats / titles / structure / report
  scripts/distill.py           # 统一 CLI
  scripts/_paths.py            # 统一路径解析（项目根 / runtime / profile / 输出根）
```

## 快速开始

```powershell
$py = "<项目根>/runtime/python/python.exe"
cd <项目根>/creator-distill/scripts

# 小红书：取主页作品 + 前 2 条下载/抽帧/ASR + 生成报告
& $py distill.py --platform xiaohongshu --creator "<博主名>" --detail 2 --frames 4

# 只看数据不下载：--detail 0 --no-asr
& $py distill.py --platform xiaohongshu --creator "<博主名>" --detail 0 --no-asr

# 复用已有 creator.json，仅重算报告
& $py distill.py --platform xiaohongshu --creator "<博主名>" --reuse
```

## 产出

```
1AMdata/distill/<platform>/<creator>/
  creator.json                 # 统一契约数据
  report.md                    # 蒸馏报告
  works/<work_id>/{detail.json, video.mp4, audio.wav, transcript.json, frames/}
```

## 依赖

| 组件 | 用途 |
|---|---|
| Python 3.12 | 全部脚本 |
| patchright + Chromium | 小红书页面取数（`runtime/` 提供，或自行安装） |
| ffmpeg（imageio_ffmpeg） | 抽帧、拼接 contact_sheet、音频抽取 |
| faster-whisper + numpy | 视频文案 ASR（GPU int8_float16） |
| 登录态 | 需自备小红书浏览器 profile（`data/accounts/xiaohongshu/profile`，**不入库**） |

## 路径约定

所有路径由 `scripts/_paths.py` 解析，默认以本仓库根为项目根，可用环境变量覆盖：

| 环境变量 | 作用 |
|---|---|
| `AUTOMEDIA_ROOT` | 项目根（默认本仓库根） |
| `CREATOR_RUNTIME` | 运行时根目录（默认 `<项目根>/runtime`） |
| `CREATOR_PROFILE` | 小红书登录 profile 目录（默认 `<项目根>/data/accounts/xiaohongshu/profile`） |
| `CREATOR_OUT_ROOT` | 蒸馏输出根目录（默认 `<项目根>/1AMdata/distill`） |

## 平台适配进度

| 平台 | 视频信息 | 文案 | 状态 |
|---|---|---|---|
| 小红书 | 搜索/主页列表 + 详情 | 视频→下载+ASR；图文→desc | ✅ v0.1 |
| B站 | 元数据 API | 平台字幕（~80%） | 待做 |
| 抖音 | 页面解析 | 下载+ASR | 待做 |

## 注意

- 小红书详情必须带 `xsec_token`：搜索卡片可取，主页列表需按标题二次搜索补。
- 小红书视频地址从详情页 HTML 提取（`sns-video-*.mp4`），下载带 Referer。
- 视觉分析是唯一需要模型参与的步骤：读 `contact_sheet.jpg` + 单帧，把结论写回 `report.md`。
- 版本规则：新增平台只加 `adapters/<platform>.py`，不改 schema；schema 变更升 `schema_version` 并记录到 CHANGELOG。
