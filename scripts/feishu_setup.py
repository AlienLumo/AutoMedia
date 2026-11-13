#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""feishu_setup.py — 飞书配置向导 / 校验 / 测试消息。

纯标准库实现（urllib.request / hmac / base64 / hashlib / getpass / pathlib）。

两种接入模式（二选一）：
  a) 自定义机器人（最快，个人群够用）：
       --webhook "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx" [--secret 签名密钥]
     飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人 → 复制 Webhook。
  b) 自建应用（可发指定群/人、可 @ 人）：
       --app-id cli_xxx --app-secret xxx --chat-id oc_xxx
     飞书开放平台 https://open.feishu.cn/app → 创建企业自建应用 → 凭证与基础信息。

写入：<数据根>/data/secrets/feishu.env
      键：FEISHU_WEBHOOK / FEISHU_SECRET / FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_CHAT_ID
      数据根 = 环境变量 AUTOMEDIA_ROOT，缺省 = 本仓库根；data/ 已被 .gitignore 忽略。
      文件权限尽量收紧为 600。

用法：
  python scripts/feishu_setup.py                          # 交互式向导
  python scripts/feishu_setup.py --webhook URL [--secret S] [--test]
  python scripts/feishu_setup.py --app-id ID --app-secret S --chat-id C [--test]
  python scripts/feishu_setup.py --check                  # 只读校验现有配置
  python scripts/feishu_setup.py --dry-run --webhook URL  # 只打印将写入的键（值打码）

安全：屏幕/日志只显示打码后的值；--dry-run 不落盘。退出码：0 成功 / 1 失败 / 2 参数错误。
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.environ.get("AUTOMEDIA_ROOT") or ROOT)
ENV_FILE = DATA_ROOT / "data" / "secrets" / "feishu.env"

KEYS = ["FEISHU_WEBHOOK", "FEISHU_SECRET",
        "FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_CHAT_ID"]
WEBHOOK_KEYS = ("FEISHU_WEBHOOK", "FEISHU_SECRET")
APP_KEYS = ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_CHAT_ID")
MODE_WEBHOOK = "webhook"
MODE_APP = "app"

API = "https://open.feishu.cn/open-apis"
TIMEOUT = 20


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def _setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _mask(value: str) -> str:
    """打码：cli_xxxxxxxx -> cli_****xxxx。屏幕与日志里永不出现完整密钥。"""
    text = str(value or "")
    if not text:
        return "(空)"
    if len(text) >= 9:
        return text[:4] + "****" + text[-4:]
    if len(text) >= 5:
        return text[:2] + "****" + text[-2:]
    return "****"


def _rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(DATA_ROOT.resolve()))
    except (ValueError, OSError):
        return str(path)


def _redact(text: str, secrets) -> str:
    """把输出里可能出现的完整密钥替换成打码形式（按长度从长到短）。"""
    text = str(text)
    for secret in sorted({str(s) for s in secrets if s and len(str(s)) >= 3},
                         key=len, reverse=True):
        text = text.replace(secret, _mask(secret))
    return text


def _read_env(path: Path = ENV_FILE) -> dict:
    values = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def _env_text(values: dict) -> str:
    lines = ["# AutoMedia / 飞书配置（由 scripts/feishu_setup.py 生成；不要提交到 git）"]
    if values.get("FEISHU_WEBHOOK") or values.get("FEISHU_SECRET"):
        lines.append("# 自定义机器人")
    if any(values.get(k) for k in APP_KEYS):
        lines.append("# 自建应用")
    for key in KEYS:
        value = str(values.get(key) or "").strip()
        if value:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def _restrict_permissions(path: Path) -> None:
    """尽力设为 600（Windows 上 chmod 只映射只读位，做不到严格 ACL）。"""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".feishu-", suffix=".env", dir=str(path.parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _restrict_permissions(tmp_path)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    _restrict_permissions(path)


# --------------------------------------------------------------------------- #
# 飞书 API
# --------------------------------------------------------------------------- #
def _post_json(url: str, payload: dict, headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "AutoMedia-feishu-setup/1.0",
                 **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except OSError:
            pass
        return exc.code, detail
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络请求失败：{exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"网络请求失败：{exc}") from exc


def _parse_json(body: str) -> dict:
    try:
        data = json.loads(body)
    except ValueError:
        return {"_raw": body[:300]}
    return data if isinstance(data, dict) else {"_raw": body[:300]}


def _error_summary(status: int, data: dict) -> str:
    code = data.get("code", data.get("StatusCode", data.get("status_code")))
    message = data.get("msg") or data.get("message") or data.get("_raw") or ""
    parts = [f"HTTP {status}"]
    if code is not None:
        parts.append(f"code={code}")
    if message:
        parts.append(str(message)[:200])
    return " / ".join(parts)


def _send_webhook(webhook: str, secret: str, text: str):
    payload = {"msg_type": "text", "content": {"text": text}}
    if secret:
        timestamp = str(int(time.time()))
        key = f"{timestamp}\n{secret}".encode("utf-8")
        sign = base64.b64encode(hmac.new(key, b"", hashlib.sha256).digest()).decode()
        payload["timestamp"] = timestamp
        payload["sign"] = sign
    status, body = _post_json(webhook, payload)
    data = _parse_json(body)
    code = data.get("code", data.get("StatusCode", data.get("status_code")))
    if status >= 400 or code not in (0, None):
        return False, _error_summary(status, data)
    return True, "自定义机器人测试消息已发送"


def _send_app(app_id: str, app_secret: str, chat_id: str, text: str):
    status, body = _post_json(
        f"{API}/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret})
    data = _parse_json(body)
    token = data.get("tenant_access_token")
    if not token:
        return False, "拿不到 tenant_access_token：" + _error_summary(status, data)
    status, body = _post_json(
        f"{API}/im/v1/messages?receive_id_type=chat_id",
        {"receive_id": chat_id, "msg_type": "text",
         "content": json.dumps({"text": text}, ensure_ascii=False)},
        headers={"Authorization": f"Bearer {token}"})
    data = _parse_json(body)
    if status >= 400 or data.get("code") != 0:
        return False, _error_summary(status, data)
    return True, "应用凭证测试消息已发送"


def _test_message() -> str:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"AutoMedia 测试消息：飞书配置成功。\n{stamp}\n（来自 scripts/feishu_setup.py）"


# --------------------------------------------------------------------------- #
# 配置状态
# --------------------------------------------------------------------------- #
def _detect_mode(values: dict):
    """返回 (模式, 缺失键列表)。模式为 None 表示配置不完整。"""
    webhook = str(values.get("FEISHU_WEBHOOK") or "").strip()
    if webhook:
        return MODE_WEBHOOK, []
    missing = [key for key in APP_KEYS if not str(values.get(key) or "").strip()]
    if not missing:
        return MODE_APP, []
    if any(str(values.get(key) or "").strip() for key in APP_KEYS):
        return None, missing
    return None, list(APP_KEYS)


def _validate(values: dict, mode: str, existing: dict):
    """返回错误文本；没问题返回 None。"""
    webhook = str(values.get("FEISHU_WEBHOOK") or "").strip()
    if mode == MODE_WEBHOOK:
        if not webhook:
            return "使用自定义机器人模式需要 --webhook（或已有配置里包含 FEISHU_WEBHOOK）"
        scheme = urllib.parse.urlsplit(webhook).scheme.lower()
        if scheme != "https" or not urllib.parse.urlsplit(webhook).netloc:
            return "Webhook 必须是完整的 https:// 地址（在飞书群机器人设置里复制）"
    if mode == MODE_APP:
        missing = [key for key in APP_KEYS if not str(values.get(key) or "").strip()]
        if missing:
            names = {"FEISHU_APP_ID": "--app-id", "FEISHU_APP_SECRET": "--app-secret",
                     "FEISHU_CHAT_ID": "--chat-id"}
            return "应用模式缺少参数：" + "、".join(names.get(k, k) for k in missing)
        app_id = str(values.get("FEISHU_APP_ID") or "")
        if not app_id.startswith("cli_"):
            print(f"! 提示：App ID 通常以 cli_ 开头（当前 {_mask(app_id)}），请确认没复制错")
    secret = str(values.get("FEISHU_SECRET") or "").strip()
    if secret and not existing.get("FEISHU_WEBHOOK") and not webhook:
        return "签名密钥需要配合 --webhook 使用（自定义机器人开启签名校验时才有）"
    return None


def _merge(existing: dict, updates: dict, mode: str) -> dict:
    values = {key: str(value) for key, value in existing.items()}
    values.update({key: str(value) for key, value in updates.items() if str(value)})
    if mode == MODE_WEBHOOK:
        for key in APP_KEYS:
            values.pop(key, None)
    elif mode == MODE_APP:
        for key in WEBHOOK_KEYS:
            values.pop(key, None)
    return values


# --------------------------------------------------------------------------- #
# 子命令
# --------------------------------------------------------------------------- #
def cmd_check() -> int:
    if not ENV_FILE.is_file():
        print(f"✗ 未找到配置文件：{_rel(ENV_FILE)}")
        print("  运行 python scripts\\feishu_setup.py 进入交互式配置，"
              "或用 --webhook / --app-id 参数配置")
        return 1
    values = _read_env()
    mode, missing = _detect_mode(values)
    print(f"配置文件：{_rel(ENV_FILE)}")
    for key in KEYS:
        if key in values:
            print(f"  {key} = {_mask(values[key])}")
    print()
    if mode == MODE_WEBHOOK:
        print("✓ 已配置：自定义机器人（FEISHU_WEBHOOK）")
        return 0
    if mode == MODE_APP:
        print("✓ 已配置：自建应用（FEISHU_APP_ID / SECRET / CHAT_ID）")
        return 0
    if any(values.get(key) for key in KEYS):
        print("✗ 配置不完整，缺少：" + "、".join(missing))
    else:
        print("✗ 配置文件里没有可用的飞书键")
    print("  修复：python scripts\\feishu_setup.py（交互式）或带参数重跑")
    return 1


def _print_plan(values: dict, mode: str, existing: dict) -> None:
    print(f"目标文件：{_rel(ENV_FILE)}")
    print(f"接入模式：{'自定义机器人' if mode == MODE_WEBHOOK else '自建应用'}")
    print("将写入的键（值已打码）：")
    for key in KEYS:
        if key not in values:
            continue
        action = "更新" if existing.get(key) and existing.get(key) != values[key] else "新增"
        if existing.get(key) == values.get(key):
            action = "不变"
        print(f"  {key} = {_mask(values[key])}  [{action}]")
    print("[dry-run] 未写入任何文件")


def _write(values: dict) -> int:
    try:
        _atomic_write(ENV_FILE, _env_text(values))
    except OSError as exc:
        print(f"✗ 写入失败：{_redact(str(exc), values.values())}")
        return 1
    print(f"✓ 已写入：{_rel(ENV_FILE)}")
    for key in KEYS:
        if values.get(key):
            print(f"  {key} = {_mask(values[key])}")
    print("  文件权限已尽量收紧为 600（data/ 不会入库）")
    return 0


def _run_test(values: dict) -> int:
    try:
        if values.get("FEISHU_WEBHOOK"):
            ok, detail = _send_webhook(values["FEISHU_WEBHOOK"],
                                       str(values.get("FEISHU_SECRET") or ""),
                                       _test_message())
        else:
            ok, detail = _send_app(str(values.get("FEISHU_APP_ID") or ""),
                                   str(values.get("FEISHU_APP_SECRET") or ""),
                                   str(values.get("FEISHU_CHAT_ID") or ""),
                                   _test_message())
    except (RuntimeError, OSError) as exc:
        print("✗ " + _redact(str(exc), values.values()))
        return 1
    detail = _redact(str(detail), values.values())
    print(("✓ " if ok else "✗ ") + detail)
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# 交互式向导
# --------------------------------------------------------------------------- #
def _ask(prompt: str, secret: bool = False) -> str:
    try:
        if secret:
            return getpass.getpass(prompt).strip()
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(1)


def interactive() -> int:
    print("飞书配置向导 — 不配也能用，只是没有日报/异常推送")
    print()
    print("方式一：自定义机器人（最快，适合个人群）")
    print("  1) 飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人")
    print("  2) 复制 Webhook 地址（https://open.feishu.cn/open-apis/bot/v2/hook/...）")
    print("  3) 若开启了「签名校验」，一并复制签名密钥")
    print()
    print("方式二：自建应用（适合团队，可发指定群/人）")
    print("  1) 打开 https://open.feishu.cn/app → 创建企业自建应用")
    print("  2) 「凭证与基础信息」→ 复制 App ID / App Secret")
    print("  3) 开通 im:message 权限，把应用拉进目标群，复制 Chat ID（oc_ 开头）")
    print()
    choice = _ask("选择 [1=自定义机器人 / 2=自建应用，回车默认 1]：") or "1"
    if choice not in ("1", "2"):
        print(f"✗ 无效选择：{choice}")
        return 2

    existing = _read_env() if ENV_FILE.is_file() else {}
    updates = {}
    if choice == "1":
        default = existing.get("FEISHU_WEBHOOK", "")
        hint = f"（已有配置，回车保留 {_mask(default)}）" if default else ""
        updates["FEISHU_WEBHOOK"] = _ask(f"粘贴 Webhook 地址{hint}：") or default
        if not updates["FEISHU_WEBHOOK"]:
            print("✗ Webhook 不能为空")
            return 2
        secret_default = existing.get("FEISHU_SECRET", "")
        secret_hint = "（回车保留已有密钥）" if secret_default else "（没有就回车跳过）"
        updates["FEISHU_SECRET"] = _ask(f"签名密钥{secret_hint}：", secret=True) or secret_default
        mode = MODE_WEBHOOK
    else:
        updates["FEISHU_APP_ID"] = _ask("App ID（cli_ 开头）：")
        updates["FEISHU_APP_SECRET"] = _ask("App Secret：", secret=True)
        updates["FEISHU_CHAT_ID"] = _ask("Chat ID（oc_ 开头）：")
        mode = MODE_APP

    values = _merge(existing, updates, mode)
    error = _validate(values, mode, existing)
    if error:
        print(f"✗ {error}")
        return 2

    print()
    print(f"将写入：{_rel(ENV_FILE)}")
    for key in KEYS:
        if values.get(key):
            print(f"  {key} = {_mask(values[key])}")
    code = _write(values)
    if code != 0:
        return code

    print()
    if (_ask("发送一条测试消息？[Y/n]：") or "y").lower() in ("y", "yes", "是"):
        code = _run_test(values)
    else:
        print("已跳过测试。之后可运行：python scripts\\feishu_setup.py --check")
    print()
    print("下一步：python bilibili-auto\\scripts\\bili_digest.py（日报会读这份配置并推送）")
    return code


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="飞书配置向导（自定义机器人 Webhook / 自建应用），可校验并发送测试消息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("用法：", 1)[-1])
    parser.add_argument("--webhook", metavar="URL",
                        help="自定义机器人 Webhook（https://open.feishu.cn/open-apis/bot/v2/hook/...）")
    parser.add_argument("--secret", metavar="KEY", help="自定义机器人签名密钥（开了签名校验才需要）")
    parser.add_argument("--app-id", dest="app_id", metavar="ID", help="自建应用 App ID（cli_ 开头）")
    parser.add_argument("--app-secret", dest="app_secret", metavar="SECRET",
                        help="自建应用 App Secret")
    parser.add_argument("--chat-id", dest="chat_id", metavar="CHAT",
                        help="目标群 Chat ID（oc_ 开头）")
    parser.add_argument("--check", action="store_true", help="只读校验已有 data/secrets/feishu.env")
    parser.add_argument("--test", action="store_true", help="发送一条测试消息（需要网络）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将写入的键（值打码），不落盘")
    return parser


def main(argv=None) -> int:
    _setup_stdout()
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args:
        if not sys.stdin.isatty():
            print("非交互环境：请使用参数模式，例如 "
                  "--webhook URL --test / --app-id ... --test（见 --help）")
            return 2
        try:
            return interactive()
        except SystemExit as exc:
            return int(exc.code or 0)

    parser = _arg_parser()
    args = parser.parse_args(raw_args)

    if args.check:
        return cmd_check()

    updates = {}
    for key, value in (("FEISHU_WEBHOOK", args.webhook),
                       ("FEISHU_SECRET", args.secret),
                       ("FEISHU_APP_ID", args.app_id),
                       ("FEISHU_APP_SECRET", args.app_secret),
                       ("FEISHU_CHAT_ID", args.chat_id)):
        if value is not None and str(value).strip():
            updates[key] = str(value).strip()

    if updates.get("FEISHU_WEBHOOK") and (updates.get("FEISHU_APP_ID")
                                          or updates.get("FEISHU_APP_SECRET")
                                          or updates.get("FEISHU_CHAT_ID")):
        print("✗ 两种模式二选一：--webhook 或 --app-id/--app-secret/--chat-id")
        return 2

    existing = _read_env() if ENV_FILE.is_file() else {}
    if updates.get("FEISHU_WEBHOOK") or updates.get("FEISHU_SECRET"):
        mode = MODE_WEBHOOK
    elif any(updates.get(key) for key in APP_KEYS):
        mode = MODE_APP
    else:
        mode = None

    if mode is None:
        if args.test:
            detected, missing = _detect_mode(existing)
            if detected is None:
                print("✗ 还没有可用配置，先运行：python scripts\\feishu_setup.py")
                if any(existing.get(key) for key in KEYS):
                    print("  缺少：" + "、".join(missing))
                return 2
            return _run_test(existing)
        if args.dry_run:
            detected, missing = _detect_mode(existing)
            if detected is None:
                print("✗ 没有可写入的配置：请带 --webhook 或 --app-id/--app-secret/--chat-id")
                return 2
            _print_plan(existing, detected, existing)
            return 0
        print("✗ 没有要写入的配置。用法：")
        print("    python scripts\\feishu_setup.py --webhook URL [--secret S] [--test]")
        print("    python scripts\\feishu_setup.py --app-id ID --app-secret S --chat-id C [--test]")
        print("    python scripts\\feishu_setup.py --check")
        return 2

    values = _merge(existing, updates, mode)
    error = _validate(values, mode, existing)
    if error:
        print(f"✗ {error}")
        return 2

    if args.dry_run:
        _print_plan(values, mode, existing)
        if args.test:
            print("[dry-run] 不发送测试消息")
        return 0

    code = _write(values)
    if code != 0:
        return code

    if args.test:
        code = _run_test(values)
    else:
        print()
        print("下一步：python scripts\\feishu_setup.py --test   （发送测试消息）")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
