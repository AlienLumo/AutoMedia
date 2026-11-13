# -*- coding: utf-8 -*-
"""_paths.py — creator-distill 统一路径解析（adapters / scripts 共用）。

默认按 skill 位置推导项目根：发布仓布局 `<项目根>/creator-distill/scripts/`；
源码布局 `<项目根>/skills/creator-distill/scripts/` 自动退到 `SKILL.parents[1]`。
全部可用环境变量覆盖：
  AUTOMEDIA_ROOT  项目根（默认按上述布局推导）
  CREATOR_RUNTIME 运行时根目录（默认 <项目根>/runtime）
  CREATOR_PROFILE 小红书登录 profile 目录（默认 <项目根>/data/accounts/xiaohongshu/profile）
  CREATOR_OUT_ROOT 蒸馏输出根目录（默认 <项目根>/1AMdata/distill）
"""
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent

# 发布仓：<项目根>/<skill>/scripts/；源码仓：<项目根>/skills/<skill>/scripts/
_DEFAULT_PROJECT = SKILL.parents[1] if SKILL.parent.name == "skills" else SKILL.parent
PROJECT = Path(os.environ.get("AUTOMEDIA_ROOT") or _DEFAULT_PROJECT)

RUNTIME = Path(os.environ.get("CREATOR_RUNTIME") or (PROJECT / "runtime"))
PROFILE = Path(os.environ.get("CREATOR_PROFILE")
               or (PROJECT / "data" / "accounts" / "xiaohongshu" / "profile"))
OUT_ROOT = Path(os.environ.get("CREATOR_OUT_ROOT") or (PROJECT / "1AMdata" / "distill"))

CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
FFMPEG = (RUNTIME / "python" / "Lib" / "site-packages" / "imageio_ffmpeg"
          / "binaries" / "ffmpeg-win-x86_64-v7.1.exe")
