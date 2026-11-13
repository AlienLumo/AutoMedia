# -*- coding: utf-8 -*-
"""统一路径入口（脱敏 + 可移植版）。

SCRIPTS : 本脚本目录（<仓库根>/<skill>/scripts）
SKILL   : 本 skill 目录
PROJECT : 项目根（含 1AMdata/、data/、runtime/）
          发布仓布局默认 = 仓库根；源码布局 <仓库根>/skills/<skill>/ 默认为仓库根；
          可用 AUTOMEDIA_ROOT 覆盖
DATA    : PROJECT/1AMdata
"""
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
# 发布仓：<仓库根>/<skill>/scripts；源码仓：<仓库根>/skills/<skill>/scripts
_DEFAULT_PROJECT = SKILL.parents[1] if SKILL.parent.name == "skills" else SKILL.parent
PROJECT = Path(os.environ.get("AUTOMEDIA_ROOT") or _DEFAULT_PROJECT)
DATA = PROJECT / "1AMdata"
