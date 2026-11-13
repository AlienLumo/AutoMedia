# -*- coding: utf-8 -*-
"""一次性：标记历史脚本停用、写 runtime/README、更新根 AGENTS.md 目录表。"""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT

PROJ = PROJECT

# 1) 历史脚本加停用头
for rel in ["AutoMedia/bilibili-auto/scripts/split_project_docs.py",
            "AutoMedia/bilibili-auto/scripts/update_docs_layout.py"]:
    p = PROJ / rel
    if not p.exists():
        continue
    c = p.read_text(encoding="utf-8")
    if "已停用" in c:
        continue
    head = "# 已停用（2026-11-09 解耦）：本脚本会写入 小绿工作台/ 文档，仅作历史参考，不要运行。\n"
    p.write_text(head + c, encoding="utf-8")
    print("archived", rel)

# 2) runtime/README.md
readme = """# runtime/ —— 采集管线的独立运行时（2026-11-09 从小绿工作台解耦）

内容：
- python/      独立 Python 3.12 发行版（patchright / faster-whisper / imageio-ffmpeg / CUDA 库）
- browsers/    Chromium 1208（patchright 使用）
- models/      faster-whisper 模型（large-v3 / small / tiny，HF 缓存格式）

规则：
- 这是采集管线自己的运行时，不要删除；升级依赖直接在本目录内进行。
- 不再读写 `小绿工作台/.runtime`。
- 唯一共享点：`../data/`（cookies、浏览器 profile）。
"""
(PROJ / "runtime" / "README.md").write_text(readme, encoding="utf-8")
print("runtime README ok")

# 3) 根 AGENTS.md 目录表补 runtime
p = PROJ / "AGENTS.md"
c = p.read_text(encoding="utf-8")
if "runtime/" not in c:
    old = "  data/                                      ← 三平台凭据与浏览器 profile"
    new = old + "\n  runtime/                                   ← 采集管线独立运行时（Python/Chromium/ASR 模型，已与工作台解耦）"
    if old in c:
        c = c.replace(old, new)
        p.write_text(c, encoding="utf-8")
        print("AGENTS.md updated")
    else:
        print("AGENTS.md anchor not found")
else:
    print("AGENTS.md already has runtime/")
