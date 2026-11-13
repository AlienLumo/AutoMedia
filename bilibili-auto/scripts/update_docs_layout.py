# 已停用（2026-11-09 解耦）：本脚本会写入 小绿工作台/ 文档，仅作历史参考，不要运行。
# -*- coding: utf-8 -*-
"""目录整理后：更新 AGENTS.md 布局说明 + 进度.md 检查点 + 备份。"""
import shutil
from datetime import datetime
from pathlib import Path
from _paths import PROJECT

PROJ = PROJECT
AG = PROJ / "AGENTS.md"
进度 = PROJ / "进度.md"
备份 = PROJ / "备份.md"
stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

# ---- 1) AGENTS.md 追加目录布局 ----
layout = f"""
## 目录布局（{stamp} 整理）

```
<项目根>/
  小绿工作台/        ← 产品本体：桌面工作台代码、运行时、依赖、数据、输出、文档
    Start.ps1  Stop.ps1  Setup.ps1  Bootstrap.ps1  启动小绿.cmd  停止小绿.cmd
    app/ public/ desktop/ scripts/ pythonbridge/ tests/ docs/
    .runtime/  vendor/  assets/  work/  archives/  outputs/  logs/
    package.json  requirements-lock.txt  PACKAGE-MANIFEST.json  README.md
  skills/            ← B站采集/监听全流程（独立技能，勿与工作台混淆）
     bilibili-auto/  （SKILL.md scripts/ config/ credentials/ cache/ data/ logs/）
  1AMdata/           ← B站采集产出（bilibili/<前缀>_<UP>_<粉丝量>/<bvid>_<标题>/）
  data/              ← 三平台共享凭据与浏览器 profile（含 B站登录态，勿移动）
  .dsh/  .agents/    ← 本项目的 agent/技能配置
  AGENTS.md  规则.md  进度.md  备份.md
```

**硬约束**：
- `data/sau/cookies/*.json` 是三平台登录真源，`AutoMedia/bilibili-auto` 按
  `PROJECT_ROOT/data/sau/cookies/` 读取，**不要移动 data/**。
- 桌面工作台的启动脚本全部使用 `$PSScriptRoot` 相对路径，移动时必须整个目录一起动。
"""
txt = AG.read_text(encoding="utf-8")
if "## 目录布局" not in txt:
    AG.write_text(txt.rstrip() + "\n" + layout, encoding="utf-8")
    print("AGENTS.md 已追加目录布局")
else:
    print("AGENTS.md 已有目录布局，跳过")

# ---- 2) 备份旧进度 ----
old = 进度.read_text(encoding="utf-8")
rules = (PROJ / "规则.md").read_text(encoding="utf-8")
已存在 = 备份.read_text(encoding="utf-8") if 备份.exists() else ""
备份.write_text(
    f"# 备份（{stamp} 检查点前）\n\n> 仅保留上一份快照，不是代码备份。\n\n"
    f"## 规则.md（快照）\n\n{rules}\n\n## 进度.md（快照）\n\n{old}\n",
    encoding="utf-8")
print(f"备份.md 已更新（旧进度 {len(old)} 字符）")

# ---- 3) 追加检查点 ----
ck = f"""

## {stamp} 目录整理（小绿工作台归并为单一目录）

**变更**：把散落在项目根目录的产品相关文件整体移入 `小绿工作台/`，根目录只保留
B站链路（`skills/`、`1AMdata/`、`data/`）、agent 配置（`.dsh/`、`.agents/`）与四份过程文档。

- 移入 `小绿工作台/`：app、public、pythonbridge、desktop、tests、docs、scripts、
  .runtime、vendor、assets、work、archives、outputs、logs 共 14 个目录，以及
  Start/Stop/Setup/Bootstrap.ps1、启动小绿.cmd、停止小绿.cmd、package.json、
  requirements-lock.txt、PACKAGE-MANIFEST.json、README.md 共 10 个文件。
- **未动**：`AutoMedia/bilibili-auto`（B站采集全流程）、`1AMdata`（采集产出）、
  `data/`（三平台凭据，含 B站登录真源）、`.dsh/`、`.agents/`。

**验证**（本地，verified）：
- 启动链关键文件齐全：`.runtime/node/node.exe`、`desktop/workstation.ps1`、
  WebView2 SDK、`Start.ps1`、`启动小绿.cmd`、`package.json` 全部 ✅。
- 搬迁前已确认：所有启动脚本使用 `$PSScriptRoot` 相对路径；app/scripts/pythonbridge/
  desktop/tests 内无硬编码绝对路径；仅 docs/*.md 有 8 处路径引用（纯文档，无功能影响）。
- 搬迁前确认小绿未运行（最近启动日志 11-01 10:57，无关联 WebView2/进程）。
- B站链路复验：`AutoMedia/bilibili-auto/collect_run.cmd`、`data/sau/cookies/bilibili_alien.json`、
  `1AMdata/bilibili`、`.dsh/AutoMedia/bilibili-auto` 联结均存在；计划任务 BiliDeepCollect 仍在 Running。

**未验证**：搬迁后尚未实际启动桌面工作台（避免干扰正在运行的采集）；下次启动时需复验原生窗口。

**B站采集现状**：BiliDeepCollect 运行中，已完成 151/420 个账号。
"""
with 进度.open("a", encoding="utf-8") as f:
    f.write(ck)
print("进度.md 已追加检查点")
