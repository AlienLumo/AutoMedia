# -*- coding: utf-8 -*-
"""更新 douyin-auto/SKILL.md：补机构号过滤、类型探测、队列续跑、字幕密度等。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "SKILL.md"
t = f.read_text(encoding="utf-8")

old = 'description: "抖音单账号按需采集：给一个主页链接，采集该账号置顶+播放量Top10与最新5个作品，含文案、作者、点赞/评论/收藏/分享、评论、封面、可选视频，以及中文字幕（GPU ASR 转写）。"'
new = ('description: "抖音采集全套：①单账号按需采集（置顶+播放Top10+最新N，含文案/数据/评论/封面/'
       '中文字幕 ASR）②按主题找号（视频内容搜索反查作者 + 机构号过滤）③双账号并行队列 ④采集前判断'
       '口播型/视觉型。用于「采这个博主」「找某领域的博主」「批量采一批账号」这类需求。"')
if old in t:
    t = t.replace(old, new, 1)

APPEND = r'''

---

# 找号 / 批量队列 / 类型判定（2026-11-04-05 新增，已验证）

## 三条工作流

### A) 单博主采集（最常用）
```powershell
cd <项目根>\AutoMedia\douyin-auto\scripts
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
'''

if "找号 / 批量队列 / 类型判定" not in t:
    t = t.rstrip() + APPEND
    f.write_text(t, encoding="utf-8")
    print("已追加新能力章节")
else:
    print("章节已存在")

print(f"SKILL.md: {f.stat().st_size/1024:.1f} KB")
