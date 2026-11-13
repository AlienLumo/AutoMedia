# -*- coding: utf-8 -*-
"""一次性：按项目规则备份旧规则+进度，再追加解耦进度。"""
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

SK = SKILL.parent
bak = SK / "备份.md"
rule = (SK / "规则.md").read_text(encoding="utf-8")
prog = (SK / "进度.md").read_text(encoding="utf-8")
stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
bak.write_text(
    bak.read_text(encoding="utf-8")
    + f"\n\n## {stamp} 变更前快照（规则 + 进度）\n\n### 规则.md\n\n{rule}\n\n### 进度.md\n\n{prog}\n",
    encoding="utf-8")

entry = f"""

---

## {stamp} 采集管线与「小绿工作台」解耦

**背景**：采集侧以后不再修改/依赖工作台项目。

**事实核查**
- bilibili-auto：基本独立（直接调 B 站 API，凭据 `data/sau/cookies`），仅 3 处软依赖：`collect_one.ps1` / `run_bili_continuous.ps1` 使用工作台 python，`feishu_push.py` 读工作台 `.runtime/feishu.env`。
- douyin-auto：**深度依赖**工作台运行时（Python 环境含 patchright/faster-whisper/CUDA、Chromium 1208、ffmpeg、ASR 模型），21 个脚本硬编码 `小绿工作台` 路径。

**已完成**
1. 复制独立运行时到项目根 `runtime/`（6.36GB）：`python/`（2.6GB）、`browsers/chromium-1208`（393MB）、`models/huggingface`（3.5GB，large-v3/small/tiny）。
2. 批量替换 28 个抖音脚本的 `WK`/路径为 `RUNTIME`；B 站两个 ps1 改用 `runtime/python`。
3. `feishu_push.py` 改读 `data/secrets/feishu.env`（已从工作台复制一份，只复制不改）。
4. ASR 脚本注入 `HF_HOME` 指向 `runtime/models/huggingface`；ps1 运行器同步设置。
5. 6 个计划任务改用 `runtime/python/pythonw.exe` 并重注册。
6. 文档更新：`skills/AGENTS.md`、根 `AGENTS.md` 目录表、`runtime/README.md`；`split_project_docs.py`/`update_docs_layout.py` 标记停用（会写工作台文档）。
7. 验证：独立 python 导入 patchright/faster_whisper/imageio_ffmpeg 通过；`douyin_probe.py --help`、`bili_ups_watch.py --help`、`bili_collect.py --help` 正常；飞书 dry-run 读到凭证。

**边界**
- 唯一共享：`data/`（cookies、浏览器 profile）；运行时/代码/模型全部在 `skills/` 与 `runtime/`。
- 工作台侧浏览器自动化（social-operator）不属于采集管线，不再使用。
- `runtime/` 不要删除；依赖升级在 runtime 内进行。
"""
(SK / "进度.md").write_text(prog + entry, encoding="utf-8")
print("backup + progress updated")
