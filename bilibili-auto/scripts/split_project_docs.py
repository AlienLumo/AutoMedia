# 已停用（2026-11-09 解耦）：本脚本会写入 小绿工作台/ 文档，仅作历史参考，不要运行。
# -*- coding: utf-8 -*-
"""把项目文档拆成两套：小绿工作台 / 采集管线（B站+抖音）。

拆分依据：进度.md 第 1-117 行属于工作台（含内容雷达/自动发现），第 118 行起属于采集管线。
旧版全部快照进 备份.md。根目录只留路由入口。
"""
import shutil
from datetime import datetime
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
WK = PROJ / "小绿工作台"
SK = SKILL.parent
stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

old_agents = (PROJ / "AGENTS.md").read_text(encoding="utf-8")
old_rules = (PROJ / "规则.md").read_text(encoding="utf-8")
old_prog_lines = (PROJ / "进度.md").read_text(encoding="utf-8").splitlines(True)

# ---- 0) 快照旧文档 ----
(PROJ / "备份.md").write_text(
    f"# 备份（{stamp} 文档拆分前的项目文档快照）\n\n"
    f"> 仅保留上一版本，不是代码备份。拆分后：工作台文档在 `小绿工作台/`，"
    f"采集管线文档在 `skills/`。\n\n"
    f"## AGENTS.md（快照）\n\n{old_agents}\n\n"
    f"## 规则.md（快照）\n\n{old_rules}\n\n"
    f"## 进度.md（快照）\n\n{''.join(old_prog_lines)}\n",
    encoding="utf-8")

# ---- 1) 工作台进度的内容（1-117 行）----
wk_prog_body = "".join(old_prog_lines[:117]).rstrip()
# ---- 2) 采集管线进度的内容（118 行起）----
sk_prog_body = "".join(old_prog_lines[117:]).rstrip()

# ---- 3) 小绿工作台 AGENTS.md ----
(WK / "AGENTS.md").write_text(f"""# 小绿工作台（Alien 小绿）入口

> 本目录是产品本体。项目总入口见 `../AGENTS.md`；采集管线见 `../skills/AGENTS.md`。

- 开始时阅读本目录 `进度.md`、`../规则.md`（全局规则），再核对代码与真实状态。
- 本目录自包含：`app/ public/ desktop/ scripts/ pythonbridge/ tests/`
  `.runtime/ vendor/ assets/ work/ archives/ outputs/ logs/ docs/`
- 启动：`启动小绿.cmd` → `Start.ps1`（全部 `$PSScriptRoot` 相对路径，移动须整目录一起动）。
- 停止：`停止小绿.cmd` → `Stop.ps1`。
- 架构：Windows Forms + WebView2 原生窗口；后台走命名管道，无 TCP 监听、无浏览器入口。
- 修改 `public/` 界面后必须运行 `node scripts/desktop-check.mjs` 验证原生窗口，不能只测浏览器页面。
- 详细设计文档在 `docs/`（MEDIA-CONSOLE、MEDIA-OBSERVER、ARCHITECTURE、ACCEPTANCE 等）。
- 不修改 `../data/`（三平台登录真源，采集管线也依赖它）。
""", encoding="utf-8")

# ---- 4) 小绿工作台 进度.md ----
(WK / "进度.md").write_text(
    f"# 小绿工作台 进度\n\n> {stamp} 从项目根 `进度.md` 拆出（第 1-117 行）。"
    f"采集管线进度见 `../skills/进度.md`。\n\n" + wk_prog_body + "\n",
    encoding="utf-8")

# ---- 5) 采集管线 AGENTS.md ----
(SK / "AGENTS.md").write_text(f"""# 采集管线（B站 + 抖音）入口

> 这是与「小绿工作台」并列的独立项目：只做**数据采集、监听、内容分析**，不做发布。
> 项目总入口见 `../AGENTS.md`；工作台见 `../小绿工作台/AGENTS.md`。

- 开始时阅读本目录 `规则.md`、`进度.md`，再核对脚本与真实状态。
- 技能目录：`bilibili-auto/`（已上线，计划任务运行中）、`douyin-auto/`（验证阶段）。
- 产出：`../1AMdata/`（B站采集结果，按 `<前缀>_<UP>_<粉丝量>/<bvid>_<标题>/` 组织）。
- 登录真源：`../data/sau/cookies/*.json`，**只读复用，不另建登录通道**。
- 与工作台的代码零交叉引用；唯一共享点是上述凭据文件。

## 目录

```
skills/
  AGENTS.md  规则.md  进度.md  备份.md
  bilibili-auto/
    SKILL.md  scripts/  config/  credentials/  cache/  data/  logs/
    collect_run.cmd  collect_hidden.vbs  setup_deep_task.ps1
  douyin-auto/
    scripts/douyin_verify.py   (验证阶段)
```
""", encoding="utf-8")

# ---- 6) 采集管线 规则.md ----
(SK / "规则.md").write_text("""# 采集管线 规则

> 全局规则（安全、权限、验收标准）见 `../规则.md`，本文件只列采集特有约束。

## 只读与边界
- 采集**只读**：不点赞、不投币、不收藏、不评论、不关注、不发布。任何写行为默认禁止。
- 不改平台账号资料、不改权限、不绕过验证码或签名算法。
- 采集账号与发布账号分离；高风险平台（抖音）建议使用无实名的独立小号。

## 账号真源
- 登录凭据统一来自 `../data/sau/cookies/*.json`，**不得另建第二套登录通道**。
- 不承诺永久登录：平台 Cookie 会失效，过期须重新扫码。
- 每次运行结束回写刷新后的 cookie（`persist_cred`），延长登录时限。

## 频率与安全
- 单并发；B站基础间隔 ≥1.5s + 抖动；每 300 请求强制休息 45–90s。
- 连续限流按 120s→300s→600s 退避，三轮仍失败则**主动停机**并保留进度。
- 每轮请求上限（默认 500–550），到点优雅退出，由计划任务续跑。
- 断点续传：每完成一个视频即写 state，中断零损失。
- 禁止并发运行两个采集实例（防重入锁 + PID 检测）。

## 数据与真实性
- 产出落在 `../1AMdata/`，不写根目录。
- 报告必须标注采样时间与覆盖范围；抽样不得宣称穷尽。
- 失败项必须可见（`[incomplete]` / `account error`），不得静默丢弃。
- 拿不到的数据写「不可得」，不编造。

## B站特化（已验证）
- WBI 签名本地实现；`arc/search` 必须带 `dm_img_list/dm_img_str/dm_cover_img_str`，否则稳定 -352。
- 匿名只能拿 3 条热评、字幕列表为空；评论全量与字幕均需登录。
- 字幕语言过滤：`--sub-langs zh` 只保留中文。
- 标题以 `...` 结尾会导致 Windows 去点、写文件 Errno 2 —— `safe_name()` 已处理。

## 抖音特化（验证阶段，未验收）
- 无公开 API，只能浏览器自动化（patchright 反检测 + 独立 profile + 有头模式）。
- 抖音对自动化容忍度远低于 B站，封号是常态手段：限流→禁言→临时封号→永久封号→设备封禁。
- **必须设备/profile 隔离**，不得与主号共用 profile；上线前先做 3 天隔离验证。
- 逐字稿需自行 ASR（下载音频 + 本地转写），平台无字幕接口。
""", encoding="utf-8")

# ---- 7) 采集管线 进度.md ----
(SK / "进度.md").write_text(
    f"# 采集管线 进度\n\n> {stamp} 从项目根 `进度.md` 拆出（第 118 行起）。"
    f"工作台进度见 `../小绿工作台/进度.md`。\n\n" + sk_prog_body + "\n",
    encoding="utf-8")

# ---- 8) 采集管线 备份（空占位，后续按检查点轮换）----
(SK / "备份.md").write_text(
    f"# 采集管线 备份\n\n> {stamp} 建立。仅保留上一版本规则/进度，不是代码备份。\n",
    encoding="utf-8")

# ---- 9) 根 AGENTS.md 改为路由 ----
(PROJ / "AGENTS.md").write_text(f"""# AP-AutoMedia 项目总入口

本仓库包含**两个并列子项目**，文档各自独立维护：

| 子项目 | 目录 | 入口文档 |
|---|---|---|
| **小绿工作台**（Alien 小绿桌面产品）| `小绿工作台/` | `小绿工作台/AGENTS.md` → `小绿工作台/进度.md` |
| **采集管线**（B站 + 抖音，只读采集/监听/分析）| `skills/` | `skills/AGENTS.md` → `skills/规则.md`、`skills/进度.md` |

## 工作方式

- 开工先读**对应子项目**的 AGENTS.md 与进度，再核对真实代码与状态。
- 全局规则见 `规则.md`（两个子项目共用：安全、权限、验收标准）。
- 重要实现/修复/验收后更新**对应子项目**的进度；更新前把旧的规则+进度存入该子项目的 `备份.md`。
- 文档与文件冲突时先调查再修正，保留其他人的修改。

## 硬约束

- 所有代码、运行时、数据、凭证、输出必须留在本项目内；不改全局配置或其他项目。
- `data/sau/cookies/*.json` 是三平台登录真源，两套子系统**只读复用**，不要移动/复制。
- `1AMdata/` 是 B站采集产出，由采集管线写入，工作台不得改动。
- 两套子系统代码零交叉引用；唯一共享点是 `data/`。

## 目录

```
AP-AutoMedia/
  AGENTS.md  规则.md  进度.md  备份.md      ← 本文件：路由 + 全局规则 + 总索引
  小绿工作台/                                ← 产品本体（AGENTS.md 进度.md docs/ …）
  skills/                                    ← 采集管线（AGENTS.md 规则.md 进度.md bilibili-auto/ douyin-auto/）
  1AMdata/                                   ← B站采集产出
  data/                                      ← 三平台凭据与浏览器 profile
  .dsh/  .agents/                            ← agent/技能配置
```
""", encoding="utf-8")

# ---- 10) 根 进度.md 改为索引 ----
(PROJ / "进度.md").write_text(f"""# 项目总进度索引

> {stamp} 拆分：明细已移入各子项目，本文件只保留索引与最近状态。

## 子项目进度

| 子项目 | 进度文档 | 当前状态 |
|---|---|---|
| 小绿工作台 | `小绿工作台/进度.md` | 桌面工作台 v1.2；三平台写操作真实回执仍 unverified |
| 采集管线 · B站 | `skills/进度.md` | **BiliDeepCollect 运行中**，深度采集 151/420 账号 |
| 采集管线 · 抖音 | `skills/进度.md` | 验证阶段：环境就绪（patchright + Chromium），未开始隔离验证 |

## 最近变更

- {stamp}：项目文档按子项目拆分；根目录只留路由与全局规则。
- 2026-11-02 20:01：目录整理，产品本体归并入 `小绿工作台/`。
- 2026-11-01 18:35：B站采集管线 v0.1 落地（`AutoMedia/bilibili-auto`）。

## 历史

拆分前的完整项目文档见 `备份.md`。
""", encoding="utf-8")

# ---- 11) 根 规则.md 加适用范围说明 ----
if "## 适用范围" not in old_rules:
    (PROJ / "规则.md").write_text(
        old_rules.rstrip() +
        f"\n\n## 适用范围（{stamp}）\n\n"
        "- 本文件是**两个子项目共用的全局规则**：安全边界、权限、验收标准、故障记录方式。\n"
        "- 工作台专属规则见 `小绿工作台/AGENTS.md`；采集管线专属规则见 `skills/规则.md`。\n"
        "- 冲突时以更严格者为准。\n",
        encoding="utf-8")
    print("规则.md 已加适用范围")
else:
    print("规则.md 已有适用范围，跳过")

print(f"完成：工作台进度 {len(wk_prog_body.splitlines())} 行 / "
      f"采集进度 {len(sk_prog_body.splitlines())} 行")
