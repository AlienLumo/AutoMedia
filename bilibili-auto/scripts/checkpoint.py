# -*- coding: utf-8 -*-
"""按项目 project-handoff 规则：备份旧进度 -> 追加检查点；并补 SKILL.md 故障结论。"""
from pathlib import Path
from datetime import datetime
from _paths import PROJECT, SKILL as _SKILL

PROJ = PROJECT
进度 = PROJ / "进度.md"
规则 = PROJ / "规则.md"
备份 = PROJ / "备份.md"
SKILL = _SKILL / "SKILL.md"

# 1) 备份：保留上一份规则与进度
old_prog = 进度.read_text(encoding="utf-8")
old_rules = 规则.read_text(encoding="utf-8")
stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
备份.write_text(
    f"# 备份（{stamp} 检查点前的规则与进度）\n\n"
    f"> 本文件只保留上一份快照，不是代码/数据备份。\n\n"
    f"## 规则.md（快照）\n\n{old_rules}\n\n"
    f"## 进度.md（快照）\n\n{old_prog}\n",
    encoding="utf-8")

# 2) 追加检查点
checkpoint = f"""

## {stamp} B站数据采集与监听（bilibili-auto）v0.1

**已落地**：项目内新技能 `AutoMedia/bilibili-auto/`（SKILL.md + scripts + config/ups.tsv 87 个 UP 名单 + credentials + data + logs）。

**能力 verified（真实接口、真实账号）**：
- 元数据 `x/web-interface/view`：播放/点赞/投币/收藏/分享/弹幕/评论数/tags 全量，58/58 成功。
- 评论 `x/v2/reply/wbi/main` 翻页：登录后可翻全量；匿名仅 3 条（`is_end=true`）。
- 字幕 `x/player/wbi/v2` + 字幕 JSON 下载：**52/58 视频有 AI 字幕（90%）**，含 ai-zh/en/ja/es/ar/id 等多语种。
- 凭据：直接复用 `data/sau/cookies/bilibili_alien.json`（biliup TV 扫码），登录名 <B站账号>；
  优先级 env → 显式文件 → biliup 真源 → 手工 cookie 文件；每次运行 `persist_cred()` 回写刷新后的 cookie。

**30 UP 测试结果**：58 个视频、8868 条评论（上限 500/视频）、15.6 MB，用时 15.6 分钟。
数据落在 `1AMdata/bilibili/<主题>/<UP主>_<mid>/<bvid>_<标题>/`，报告 `1AMdata/_report_30ups.md`。

**故障结论（现象 → 原因 → 修复 → 验证）**：
- 现象：2 个视频 `meta.json` 写入报 `Errno 2`，但目录已建。
  原因：标题以 `...` 结尾，Windows 静默去掉目录名末尾的点，mkdir 与写入路径不一致。
  修复：`safe_name()` 清掉结尾点和空格、规避 Windows 保留名。验证：补采后 58/58 有 meta。
- 现象：同一 bvid 出现两个目录。原因：修复前后目录名算法不同，重跑生成新目录。
  修复：按 `bvid_safe_name(title,40)` 归并去重。验证：重复 bvid = 0。
- 现象：匿名请求 `x/space/wbi/arc/search` 稳定 -352。原因：缺 `dm_img_list/dm_img_str/dm_cover_img_str` 反爬参数。
  修复：内置 `DM_PARAMS` + 搜索接口回退。验证：30 个 UP 列表全部取到。
- 现象：2 个视频 `-404 啥都木有`。原因：视频已被 UP 主删除，不是采集故障。已从目录清理并在报告标注。

**未完成 / 下一步**：监听调度器（每日增量检查 → 入队 → 采集 → 日报）未实现；
楼中楼（二级回复）本次关闭，开启约 4 倍耗时；名单待扩到 100–300。
"""
with 进度.open("a", encoding="utf-8") as f:
    f.write(checkpoint)
print(f"备份已写入: {备份}  ({len(备份.read_text(encoding='utf-8'))} 字符)")
print(f"进度已追加检查点: {进度}")

# 3) SKILL.md 补故障结论
txt = SKILL.read_text(encoding="utf-8")
marker = "## 纪律"
add = """## 故障结论（已修复，别重复踩）

- **标题以 `...` 结尾 → 目录建了但写文件报 Errno 2**：Windows 静默去掉目录名末尾的点，
  mkdir 与写入路径不一致。`safe_name()` 现已清掉结尾点和空格，并规避 `CON/PRN/AUX` 等保留名。
- **同一 bvid 出现两个目录**：目录名算法变更后重跑会生成新目录。归并时以
  `f"{bvid}_{safe_name(title,40)}"` 为准，其余删除。
- **匿名请求 `arc/search` 稳定 -352**：缺 `dm_img_list/dm_img_str/dm_cover_img_str` 三个反爬参数；
  脚本已内置 `DM_PARAMS`，失败还会回退搜索接口。
- **`-404 啥都木有`**：视频已被删除或设为不可见，不是采集故障，不要重试。

"""
if marker in txt and "故障结论（已修复" not in txt:
    txt = txt.replace(marker, add + marker)
    SKILL.write_text(txt, encoding="utf-8")
    print("SKILL.md 已补充故障结论")
else:
    print("SKILL.md 跳过（已存在或无锚点）")
