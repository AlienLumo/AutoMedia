# -*- coding: utf-8 -*-
"""news_paths.py — 信息源 skill 统一路径解析（所有脚本共用）。

默认按 skill 位置推导项目根：发布仓布局 `<项目根>/news-source/scripts/`；
源码布局 `<项目根>/skills/news-source/scripts/` 自动退到 `SKILL.parents[1]`。
全部可用环境变量覆盖：
  AUTOMEDIA_ROOT  项目根（默认按上述布局推导）
  NEWS_DATA_ROOT  素材库根目录（默认 <项目根>/1信息源）
  NEWS_DATE       日期目录名，6 位数字（默认 261111，即 2026-11-11）
  NEWS_POOL       资讯池 items.jsonl（默认 <项目根>/1AMdata/news/pool/items.jsonl）
  NEWS_RUNTIME    运行时根目录（默认 <项目根>/runtime）
"""
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent                      # <项目根>/news-source 或 skills/news-source
# 发布仓：<项目根>/news-source/scripts/；源码仓：<项目根>/skills/news-source/scripts/
_DEFAULT_PROJECT = SKILL.parents[1] if SKILL.parent.name == "skills" else SKILL.parent
PROJECT = Path(os.environ.get("AUTOMEDIA_ROOT") or _DEFAULT_PROJECT)   # 项目根

DATA_ROOT = Path(os.environ.get("NEWS_DATA_ROOT") or (PROJECT / "1信息源"))
DATE = os.environ.get("NEWS_DATE") or "261111"
POOL = Path(os.environ.get("NEWS_POOL") or (PROJECT / "1AMdata" / "news" / "pool" / "items.jsonl"))
RUNTIME = Path(os.environ.get("NEWS_RUNTIME") or (PROJECT / "runtime"))
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
FFMPEG = (RUNTIME / "python" / "Lib" / "site-packages" / "imageio_ffmpeg"
          / "binaries" / "ffmpeg-win-x86_64-v7.1.exe")

CONFIG = SKILL / "config"


def day_dir(date=None):
    """素材库中某一天的目录：1信息源/<date>/"""
    return DATA_ROOT / (date or DATE)


def day_iso(date=None):
    """6 位日期 → 2026-11-11；非法格式原样返回。"""
    d = str(date or DATE)
    return f"20{d[0:2]}-{d[2:4]}-{d[4:6]}" if (len(d) == 6 and d.isdigit()) else d


def events_config(date=None):
    """当日事件配置：config/events/<date>.json"""
    return CONFIG / "events" / f"{date or DATE}.json"


def buckets_config():
    """事件分桶关键词：config/buckets.json"""
    return CONFIG / "buckets.json"
