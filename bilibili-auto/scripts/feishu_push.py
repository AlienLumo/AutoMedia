#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""feishu_push.py — 把文本推送到飞书机器人（项目内既有应用凭证，或自定义机器人）。

两种模式（自动选择）：
  1) 应用模式：读 `data/secrets/feishu.env` 的 FEISHU_APP_ID / FEISHU_APP_SECRET
     / FEISHU_CHAT_ID，取 tenant_access_token 后调 im/v1/messages 发到群。
  2) 自定义机器人模式：`AutoMedia/bilibili-auto/config/feishu.json` 里配 {"feishu_hook": "...",
     "secret": "..."}（飞书自定义机器人），自动处理签名。

用法：
  python feishu_push.py --text-file digest.md
  python feishu_push.py --text "测试" --dry-run
"""
import argparse
import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
ENV_FILE = PROJ / "data" / "secrets" / "feishu.env"
CONF_FILE = SKILL / "config" / "feishu.json"
API = "https://open.feishu.cn/open-apis"
MAX_CHARS = 3800


def _read_env(path=ENV_FILE):
    d = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            d[k.strip().strip("\ufeff")] = v.strip()
    return d


def _read_conf():
    try:
        return json.loads(CONF_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _post(url, body, headers=None, timeout=20):
    req = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "Mozilla/5.0", **(headers or {})},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _chunks(text, n=MAX_CHARS):
    """按段落切分，避免飞书单条消息过长。"""
    parts, cur = [], ""
    for line in text.splitlines(True):
        if len(cur) + len(line) > n and cur:
            parts.append(cur)
            cur = ""
        cur += line
    if cur:
        parts.append(cur)
    return parts or [""]


def send_text(text, dry_run=False):
    """返回 (ok, detail)。自动识别应用模式 / 自定义机器人模式。"""
    env = _read_env()
    conf = _read_conf()

    if conf.get("feishu_hook"):
        url = conf["feishu_hook"]
        for i, part in enumerate(_chunks(text)):
            body = {"msg_type": "text", "content": {"text": part}}
            secret = conf.get("secret") or ""
            if secret:
                ts = str(int(time.time()))
                key = f"{ts}\n{secret}".encode()
                sign = base64.b64encode(hmac.new(key, b"", hashlib.sha256).digest()).decode()
                body.update({"timestamp": ts, "sign": sign})
            if dry_run:
                print(f"[dry-run hook] {len(part)} chars, part {i+1}")
                continue
            data = _post(url, body)
            code = data.get("code", data.get("StatusCode", -1))
            if code not in (0, None):
                return False, f"自定义机器人发送失败: {data}"
        return True, "自定义机器人 ok"

    app_id = env.get("FEISHU_APP_ID") or conf.get("app_id")
    app_secret = env.get("FEISHU_APP_SECRET") or conf.get("app_secret")
    chat_id = env.get("FEISHU_CHAT_ID") or conf.get("chat_id")
    if not (app_id and app_secret and chat_id):
        return False, ("未找到飞书凭证：请配置 data/secrets/feishu.env "
                       "(FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_CHAT_ID) "
                       "或 config/feishu.json 的 feishu_hook")

    if dry_run:
        print(f"[dry-run app] app={app_id[:8]}*** chat={chat_id[:8]}*** "
              f"parts={len(_chunks(text))}")
        return True, "dry-run"

    tk = _post(f"{API}/auth/v3/tenant_access_token/internal",
               {"app_id": app_id, "app_secret": app_secret})
    token = tk.get("tenant_access_token")
    if not token:
        return False, f"拿不到 tenant_access_token: {tk}"
    headers = {"Authorization": f"Bearer {token}"}
    for part in _chunks(text):
        data = _post(f"{API}/im/v1/messages?receive_id_type=chat_id",
                     {"receive_id": chat_id, "msg_type": "text",
                      "content": json.dumps({"text": part}, ensure_ascii=False)},
                     headers=headers)
        if data.get("code") != 0:
            return False, f"发送失败: {data}"
    return True, "app ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file", default="", dest="text_file")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    text = a.text or (Path(a.text_file).read_text(encoding="utf-8")
                      if a.text_file else "")
    if not text.strip():
        print("empty text", file=sys.stderr)
        return 1
    ok, detail = send_text(text, dry_run=a.dry_run)
    print(("OK " if ok else "FAIL ") + detail)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

