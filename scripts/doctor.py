#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoMedia doctor.py — 环境 / 登录态 / 飞书 / 输出目录自检。

纯标准库实现：不需要 pip 依赖，也不要求项目内 runtime/ 存在（CI 可直接跑）。

用法：
    python scripts/doctor.py            # 人类可读的自检表
    python scripts/doctor.py --json     # 机器可读（CI / 上层脚本）
    python scripts/doctor.py --ci       # CI 模式：缺运行时只告警，退出码恒为 0

路径规则（与各 skill 的 _paths.py 保持一致）：
    仓库根 = 本文件上两级
    数据根 = 环境变量 AUTOMEDIA_ROOT，缺省 = 仓库根
    运行时 = <数据根>/runtime（项目内的 Python / Chromium / ffmpeg / ASR 模型）

退出码：0 = 无致命问题（--ci 恒为 0）；1 = 存在致命问题。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.environ.get("AUTOMEDIA_ROOT") or ROOT)
RUNTIME = DATA_ROOT / "runtime"

MARKS = {"ok": "✓", "warn": "!", "fail": "✗"}

# runtime/ 里由 install.ps1 或用户放置的可执行文件
CHROMIUM_PATTERNS = [
    "browsers/chromium-*/chrome-win64/chrome.exe",
    "browsers/chromium-*/chrome-linux/chrome",
    "browsers/chromium-*/chrome-linux64/chrome",
    "browsers/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    "browsers/chrome-*/chrome-win64/chrome.exe",
]
CHROMIUM_CACHE_PATTERNS = [
    "chromium-*/chrome-win64/chrome.exe",
    "chromium-*/chrome-linux/chrome",
    "chromium-*/chrome-linux64/chrome",
]
FFMPEG_PATTERNS = [
    "python/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg*.exe",
    "python/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg*",
    "python/lib/site-packages/imageio_ffmpeg/binaries/ffmpeg*",
    "python/Scripts/ffmpeg.exe",
    "ffmpeg/bin/ffmpeg.exe",
    "ffmpeg/bin/ffmpeg",
]

HINTS = {
    "patchright": "pip install patchright（或使用 <数据根>/runtime/python 里已带的包）",
    "chromium": "Chromium 放到 <数据根>/runtime/browsers/chromium-*/chrome-win64/chrome.exe，"
                "或执行 patchright install chromium",
    "ffmpeg": "ffmpeg 放到 <数据根>/runtime/，或把 ffmpeg.exe 加入 PATH",
    "bili": "B站登录：把 biliup 导出的 cookie JSON 放到 data/sau/cookies/bilibili_*.json",
    "douyin": "抖音登录：python douyin-auto\\scripts\\douyin_login.py "
              "--profile data\\social\\douyin-verify-profile --timeout 600",
    "xhs": "小红书登录：用专用 Chromium profile 打开小红书扫码，保存到 "
           "data/accounts/xiaohongshu/profile/",
    "feishu": "配置飞书：python scripts\\feishu_setup.py（不配也能跑，只是没有推送）",
    "dirs": "创建输出目录：powershell -File scripts\\install.ps1（或手工新建 <数据根>/1AMdata 等）",
}


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def _setup_stdout() -> None:
    """管道/重定向下强制 UTF-8，避免 Windows GBK 控制台对 ✓ 等字符编码报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _rel(path) -> str:
    """尽量显示成相对数据根的路径，避免把本机绝对路径带回对话/日志。"""
    try:
        return str(Path(path).resolve().relative_to(DATA_ROOT.resolve()))
    except (ValueError, OSError):
        return str(path)


def _short(text, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _sub_env() -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _mask(value: str) -> str:
    """打码：cli_xxxxxxxx -> cli_****xxxx。"""
    s = str(value or "")
    if not s:
        return "(空)"
    if len(s) >= 9:
        return s[:4] + "****" + s[-4:]
    if len(s) >= 5:
        return s[:2] + "****" + s[-2:]
    return "****"


def _row(group, name, status, detail, fatal=False, hint="") -> dict:
    return {
        "group": group,
        "name": name,
        "status": status,
        "detail": detail,
        "fatal": bool(fatal),
        "hint": hint if status != "ok" else "",
    }


def _first_file(patterns, base: Path):
    if not base.is_dir():
        return None
    for pattern in patterns:
        try:
            hits = sorted(base.glob(pattern))
        except OSError:
            continue
        for hit in hits:
            try:
                if hit.is_file():
                    return hit
            except OSError:
                continue
    return None


def _can_write(dirpath: Path):
    try:
        fd, tmp = tempfile.mkstemp(prefix=".doctor-probe-", dir=str(dirpath))
        os.close(fd)
        os.remove(tmp)
        return True, ""
    except OSError as exc:
        return False, _short(exc)


def _read_env(path: Path) -> dict:
    env = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return env
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


# --------------------------------------------------------------------------- #
# 解释器 / 运行时
# --------------------------------------------------------------------------- #
def _pick_python():
    candidates = [
        RUNTIME / "python" / "python.exe",
        RUNTIME / "python" / "bin" / "python3",
        RUNTIME / "python" / "python",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand, "runtime"
    return Path(sys.executable), "system"


def _same_python(path: Path) -> bool:
    try:
        return path.resolve() == Path(sys.executable).resolve()
    except OSError:
        return False


def _python_version(py: Path):
    if _same_python(py):
        return tuple(sys.version_info[:3])
    try:
        proc = subprocess.run(
            [str(py), "-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"],
            capture_output=True, text=True, timeout=60, env=_sub_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        return tuple(int(part) for part in proc.stdout.strip().split("."))
    except ValueError:
        return None


def _has_module(py: Path, module: str):
    """只探测“能否找到”，不真的执行模块（避免 doctor 触发重型导入）。"""
    if _same_python(py):
        try:
            return importlib.util.find_spec(module) is not None, ""
        except (ImportError, ValueError) as exc:
            return False, _short(exc)
    code = ("import importlib.util,sys;"
            f"sys.exit(0 if importlib.util.find_spec({module!r}) else 1)")
    try:
        proc = subprocess.run([str(py), "-c", code], capture_output=True,
                              text=True, timeout=60, env=_sub_env())
    except (OSError, subprocess.SubprocessError) as exc:
        return False, _short(exc)
    if proc.returncode == 0:
        return True, ""
    lines = (proc.stderr or "").strip().splitlines()
    return False, _short(lines[-1] if lines else "未安装")


def _find_chromium():
    for key in ("CHROMIUM_PATH", "CHROME_PATH"):
        value = os.environ.get(key)
        if value and Path(value).is_file():
            return Path(value), "env"
    hit = _first_file(CHROMIUM_PATTERNS, RUNTIME)
    if hit:
        return hit, "runtime"

    caches = []
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        caches.append(Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]))
    caches.append(Path.home() / ".cache" / "ms-playwright")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        caches.append(Path(local) / "ms-playwright")
    for cache in caches:
        hit = _first_file(CHROMIUM_CACHE_PATTERNS, cache)
        if hit:
            return hit, "playwright cache"

    for name in ("chrome", "chrome.exe", "chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return Path(found), "PATH"
    return None, ""


def _find_ffmpeg():
    for key in ("FFMPEG_PATH",):
        value = os.environ.get(key)
        if value and Path(value).is_file():
            return Path(value), "env"
    hit = _first_file(FFMPEG_PATTERNS, RUNTIME)
    if hit:
        return hit, "runtime"
    found = shutil.which("ffmpeg")
    if found:
        return Path(found), "PATH"
    return None, ""


def _found_detail(path: Path, origin: str) -> str:
    text = _rel(path)
    if origin == "PATH":
        return f"{text}（PATH）"
    if origin == "playwright cache":
        return f"{text}（playwright cache）"
    if origin == "env":
        return f"{text}（环境变量）"
    return text


# --------------------------------------------------------------------------- #
# 登录态 / 飞书 / 输出目录
# --------------------------------------------------------------------------- #
def _check_bili():
    group = "登录态"
    base = DATA_ROOT / "data" / "sau" / "cookies"
    files = []
    if base.is_dir():
        try:
            files = sorted(f for f in base.glob("*.json") if f.is_file())
        except OSError:
            files = []
    parsed, shown = [], []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        names = []
        info = data.get("cookie_info") if isinstance(data, dict) else None
        for item in ((info or {}).get("cookies") or []):
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        parsed.append(path)
        head = "、".join(names[:3]) + (" 等" if len(names) > 3 else "")
        shown.append(f"{_rel(path)}（{head or '已解析'}）")
    if parsed:
        detail = f"{len(parsed)} 个 cookie 文件：" + "；".join(shown[:2])
        return _row(group, "B站 cookie", "ok", _short(detail, 180))
    if files:
        return _row(group, "B站 cookie", "warn",
                    f"找到 {len(files)} 个 JSON 但无法解析（可能是旧格式）",
                    hint=HINTS["bili"])
    cred_txt = DATA_ROOT / "credentials" / "bili_cookie.txt"
    if cred_txt.is_file():
        return _row(group, "B站 cookie", "warn",
                    "仅找到 credentials/bili_cookie.txt（txt 模式可用，推荐 JSON 真源）",
                    hint=HINTS["bili"])
    return _row(group, "B站 cookie", "warn", "未找到 data/sau/cookies/*.json", hint=HINTS["bili"])


def _profile_dirs(base: Path, keyword="profile"):
    found = []
    if not base.is_dir():
        return found
    try:
        children = list(base.iterdir())
    except OSError:
        return found
    for child in children:
        try:
            if child.is_dir() and keyword in child.name.lower():
                found.append(child)
        except OSError:
            continue
    return sorted(found)


def _nonempty_dir(path: Path) -> bool:
    try:
        next(iter(path.iterdir()))
        return True
    except (StopIteration, OSError):
        return False


def _check_douyin():
    group = "登录态"
    base = DATA_ROOT / "data" / "social"
    dirs = _profile_dirs(base)
    ready = [d for d in dirs if _nonempty_dir(d)]
    if ready:
        return _row(group, "抖音 profile", "ok",
                    f"{len(ready)} 个 profile：" + "、".join(_rel(d) for d in ready[:2]))
    if dirs:
        return _row(group, "抖音 profile", "warn", "profile 目录已存在但为空（可能未登录）",
                    hint=HINTS["douyin"])
    return _row(group, "抖音 profile", "warn",
                "未找到 data/social/*profile*/（需 headful 扫码登录）", hint=HINTS["douyin"])


def _check_xhs():
    group = "登录态"
    path = DATA_ROOT / "data" / "accounts" / "xiaohongshu" / "profile"
    if path.is_dir() and _nonempty_dir(path):
        return _row(group, "小红书 profile", "ok", f"已找到 {_rel(path)}")
    if path.is_dir():
        return _row(group, "小红书 profile", "warn", f"{_rel(path)} 为空（可能未登录）",
                    hint=HINTS["xhs"])
    return _row(group, "小红书 profile", "warn",
                "未找到 data/accounts/xiaohongshu/profile/", hint=HINTS["xhs"])


def _check_feishu():
    group = "通知与输出"
    envfile = DATA_ROOT / "data" / "secrets" / "feishu.env"
    creds = _read_env(envfile)
    webhook = creds.get("FEISHU_WEBHOOK", "")
    app_id = creds.get("FEISHU_APP_ID", "")
    app_secret = creds.get("FEISHU_APP_SECRET", "")
    chat_id = creds.get("FEISHU_CHAT_ID", "")
    if webhook:
        try:
            host = urllib.parse.urlsplit(webhook).netloc or "webhook"
        except ValueError:
            host = "webhook"
        return _row(group, "飞书配置", "ok", f"自定义机器人 Webhook 已配置（{host}）")
    if app_id and app_secret and chat_id:
        return _row(group, "飞书配置", "ok",
                    f"应用凭证已配置（app_id {_mask(app_id)}，chat_id {_mask(chat_id)}）")
    if creds:
        missing = [k for k, v in (
            ("FEISHU_APP_ID", app_id), ("FEISHU_APP_SECRET", app_secret),
            ("FEISHU_CHAT_ID", chat_id),
        ) if not v]
        return _row(group, "飞书配置", "warn",
                    "feishu.env 存在但配置不完整，缺：" + "、".join(missing),
                    hint=HINTS["feishu"])
    return _row(group, "飞书配置", "warn", "未配置（可选：通知/日报用）", hint=HINTS["feishu"])


def _check_outputs():
    group = "通知与输出"
    names = ["1AMdata", "1信息源", ".cache"]
    pieces, missing, unwritable, writable = [], [], [], []
    for name in names:
        path = DATA_ROOT / name
        if path.is_dir():
            ok, err = _can_write(path)
            if ok:
                writable.append(name)
                pieces.append(f"{name}=可写")
            else:
                unwritable.append(name)
                pieces.append(f"{name}=不可写（{err}）")
        else:
            missing.append(name)
            pieces.append(f"{name}=尚未创建")
    detail = "；".join(pieces)
    if unwritable:
        return _row(group, "输出目录可写", "fail", detail, fatal=True, hint=HINTS["dirs"])
    if not DATA_ROOT.is_dir():
        return _row(group, "输出目录可写", "warn",
                    f"数据根不存在：{DATA_ROOT}（设置 AUTOMEDIA_ROOT 或重跑 install.ps1）",
                    hint=HINTS["dirs"])
    if missing:
        return _row(group, "输出目录可写", "warn",
                    "数据根可写，但输出目录尚未创建：" + detail, hint=HINTS["dirs"])
    if writable:
        return _row(group, "输出目录可写", "ok", detail)
    return _row(group, "输出目录可写", "warn", detail, hint=HINTS["dirs"])


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
def collect() -> list:
    rows = []

    # 1) 运行环境 ------------------------------------------------------------
    group = "运行环境"
    py, origin = _pick_python()
    origin_text = "runtime/python" if origin == "runtime" else "system python"
    version = _python_version(py)
    if version is None:
        rows.append(_row(group, "Python 版本", "fail",
                         f"无法执行 {_rel(py)}（{origin_text}）", fatal=True,
                         hint="安装 Python 3.11+，或把项目内运行时放到 <数据根>/runtime/"))
    else:
        version_text = ".".join(str(p) for p in version)
        supported = version >= (3, 11)
        rows.append(_row(group, "Python 版本", "ok" if supported else "fail",
                         f"{version_text}（{origin_text}）", fatal=not supported,
                         hint="" if supported else "需要 Python 3.11+（推荐 3.12）"))

    if RUNTIME.is_dir():
        rows.append(_row(group, "运行时目录", "ok", f"已找到 {_rel(RUNTIME)}"))
    else:
        rows.append(_row(group, "运行时目录", "warn",
                         "未找到 <数据根>/runtime（可选：系统 Python + PATH 里的 Chromium/ffmpeg 也能跑）"))

    found, err = _has_module(py, "patchright")
    rows.append(_row(group, "patchright", "ok" if found else "fail",
                     "已安装" if found else f"未安装{('：' + err) if err else ''}",
                     fatal=not found, hint=HINTS["patchright"]))

    # 2) 浏览器与媒体 --------------------------------------------------------
    group = "浏览器与媒体"
    chrome, chrome_origin = _find_chromium()
    if chrome:
        rows.append(_row(group, "Chromium 可执行", "ok", _found_detail(chrome, chrome_origin)))
    else:
        rows.append(_row(group, "Chromium 可执行", "fail", "未找到 chrome.exe / chromium",
                         fatal=True, hint=HINTS["chromium"]))

    ffmpeg, ffmpeg_origin = _find_ffmpeg()
    if ffmpeg:
        rows.append(_row(group, "ffmpeg 可执行", "ok", _found_detail(ffmpeg, ffmpeg_origin)))
    else:
        rows.append(_row(group, "ffmpeg 可执行", "fail", "未找到 ffmpeg",
                         fatal=True, hint=HINTS["ffmpeg"]))

    whisper, _ = _has_module(py, "faster_whisper")
    rows.append(_row(group, "faster-whisper", "ok" if whisper else "warn",
                     "已安装" if whisper else "未安装（可选：ASR 用，不跑 ASR 可忽略）",
                     hint="pip install faster-whisper" if not whisper else ""))

    # 3) 登录态 --------------------------------------------------------------
    rows.append(_check_bili())
    rows.append(_check_douyin())
    rows.append(_check_xhs())

    # 4) 通知与输出 ----------------------------------------------------------
    rows.append(_check_feishu())
    rows.append(_check_outputs())
    return rows


def _demote_ci(rows) -> list:
    """CI 模式：把致命项降级成告警，保证没有运行时也能 exit 0。"""
    out = []
    for row in rows:
        if row["status"] == "fail":
            row = dict(row)
            row["status"] = "warn"
            row["fatal"] = False
            row["demoted"] = True
        out.append(row)
    return out


def _display_width(text: str) -> int:
    width = 0
    for ch in text:
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def print_table(rows, ci: bool) -> None:
    print("AutoMedia doctor · 环境自检")
    print(f"  仓库根 : {ROOT}")
    print(f"  数据根 : {DATA_ROOT}" + ("（AUTOMEDIA_ROOT）" if os.environ.get("AUTOMEDIA_ROOT") else ""))
    print(f"  运行时 : {RUNTIME}" + ("（未找到）" if not RUNTIME.is_dir() else ""))
    print()

    name_width = max(_display_width(r["name"]) for r in rows) + 2
    current_group = None
    for row in rows:
        if row["group"] != current_group:
            current_group = row["group"]
            print(f"  [{current_group}]")
        mark = MARKS[row["status"]]
        print(f"  {mark} {_pad(row['name'], name_width)}{row['detail']}")

    total = {"ok": 0, "warn": 0, "fail": 0}
    for row in rows:
        total[row["status"]] += 1
    print()
    print(f"  汇总：通过 {total['ok']} · 警告 {total['warn']} · 失败 {total['fail']}")
    if ci:
        print("  CI 模式：运行时缺失只告警，退出码恒为 0")

    hints = [r for r in rows if r["status"] != "ok" and r["hint"]]
    if hints:
        print()
        print("  建议：")
        for row in hints:
            print(f"    {MARKS[row['status']]} {row['name']}：{row['hint']}")

    print()
    if total["fail"]:
        print("  结论：存在致命问题，按上面建议处理后重跑 python scripts\\doctor.py")
    else:
        print("  结论：环境可用。未配置的登录态/飞书按 skill 文档补即可。")
        print("  飞书（可选）：python scripts\\feishu_setup.py")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="AutoMedia 环境自检（Python / patchright / Chromium / ffmpeg / "
                    "faster-whisper / 登录态 / 飞书 / 输出目录）")
    parser.add_argument("--json", action="store_true", help="输出 JSON（机器可读）")
    parser.add_argument("--ci", action="store_true",
                        help="CI 模式：缺运行时只告警，退出码恒为 0")
    args = parser.parse_args(argv)

    _setup_stdout()
    rows = collect()
    if args.ci:
        rows = _demote_ci(rows)

    total = {"ok": 0, "warn": 0, "fail": 0}
    for row in rows:
        total[row["status"]] += 1
    failed = total["fail"] > 0

    if args.json:
        payload = {
            "ok": not failed,
            "ci": args.ci,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "root": str(ROOT),
            "data_root": str(DATA_ROOT),
            "runtime": str(RUNTIME),
            "runtime_found": RUNTIME.is_dir(),
            "summary": total,
            "checks": rows,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_table(rows, args.ci)

    if args.ci:
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
