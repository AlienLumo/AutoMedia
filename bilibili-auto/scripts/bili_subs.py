#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_subs.py — collect Bilibili video subtitles for a set of UP masters.

Pipeline per UP: arc/search (video list) -> player/pagelist (cid)
-> player/wbi/v2 (subtitle list) -> download subtitle JSON -> .srt + .txt

Resumable: every subtitle file is written individually, and an index.jsonl
records progress, so a killed run can be restarted with the same command.

Usage
  python bili_subs.py --mids 14097567 --max-videos 5 --outdir subs
  python bili_subs.py --roster data/known_ai_ups.tsv --outdir subs --budget 300
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path
from _paths import PROJECT, SKILL

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEAD = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
MIXIN_TAB = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43,
             5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16,
             24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59,
             6, 63, 57, 62, 11, 36, 20, 34, 44, 52]
PROJECT_ROOT = Path(os.environ.get("BILI_PROJECT_ROOT") or str(PROJECT))
CACHE = Path(os.environ.get("BILI_CACHE") or (SKILL / "cache"))
CACHE.mkdir(parents=True, exist_ok=True)
THROTTLE_CODES = {-352, -412, -509, -799}

# 空间投稿接口有额外反爬校验：不带这三项参数，匿名请求稳定返回 -352。
DM_PARAMS = {
    "dm_img_list": "[]",
    "dm_img_str": "V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ",
    "dm_cover_img_str": ("QU5HTEUgKE5WSURJQSwgTlZJRElBIEdlRm9yY2UgUlRYIDMwNjAg"
                         "KDB4MDAwMDI1MDIpIERpcmVjdDNEMTEgdnNfNV8wIHBzXzVfMCBE"
                         "M0QxMSksIG9yIHRvIGJldHRlcg"),
}

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class Throttled(Exception):
    pass


class Budget(Exception):
    pass


class NotLoggedIn(Exception):
    pass


CRED_FILE = Path(os.environ.get("BILI_CRED_FILE")
                 or (SKILL / "credentials" / "bili_cookie.txt"))


# 项目账号真源（biliup TV 扫码）：优先使用，避免另建第二套登录通道
BILIUP_CRED = PROJECT_ROOT / "data" / "sau" / "cookies" / "bilibili_alien.json"


def read_biliup_cred(path=None):
    """从 biliup 凭据 JSON 里取出 cookie_info.cookies -> dict。"""
    p = Path(path or BILIUP_CRED)
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception as e:
        print(f"  ! biliup cred parse failed: {e}", file=sys.stderr)
        return {}
    out = {}
    for item in ((d.get("cookie_info") or {}).get("cookies") or []):
        if isinstance(item, dict) and item.get("name"):
            out[item["name"]] = item.get("value", "")
    return out


def parse_cookie_string(s):
    """'SESSDATA=x; buvid3=y; ...' -> dict"""
    out = {}
    for part in s.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _read_cred_file(p):
    """Read one credential file (formats: full cookie string / two raw lines)."""
    try:
        lines = [l.strip().lstrip("\ufeff")
                 for l in p.read_text(encoding="utf-8-sig").splitlines()
                 if l.strip() and not l.strip().startswith("#")]
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"  ! cannot read {p}: {e}", file=sys.stderr)
        return {}
    if not lines:
        return {}
    first = lines[0]
    if "SESSDATA=" in first or ";" in first:
        return parse_cookie_string(first)
    d = {"SESSDATA": first}
    if len(lines) > 1:
        d["buvid3"] = lines[1]
    return d


def read_cred(explicit=None):
    """凭据优先级：环境变量 -> 显式文件 -> 项目 biliup 真源 -> 手动 cookie 文件。

    biliup 真源优先于手动文件，符合项目「账号真源独占」的约束：项目重新扫码
    后采集器自动用上新凭据，不需要再手工复制 cookie。
    """
    if os.environ.get("BILI_COOKIE"):
        return parse_cookie_string(os.environ["BILI_COOKIE"])
    if os.environ.get("BILI_SESSDATA"):
        d = {"SESSDATA": os.environ["BILI_SESSDATA"].strip()}
        if os.environ.get("BILI_BUVID3"):
            d["buvid3"] = os.environ["BILI_BUVID3"]
        return d

    if explicit:
        got = _read_cred_file(Path(explicit))
        if got:
            return got
    up = read_biliup_cred()
    if up.get("SESSDATA"):
        return up
    return _read_cred_file(CRED_FILE)


def mask(s):
    if not s:
        return "(empty)"
    return f"{s[:4]}...{s[-4:]} (len={len(s)})"


def cred_summary(cred):
    """Never print cookie values; only which keys are present."""
    if not cred:
        return "cred=(none)"
    keys = ["SESSDATA", "buvid3", "buvid4", "bili_jct", "DedeUserID", "b_nut"]
    parts = [f"{k}={'Y' if cred.get(k) else 'N'}" for k in keys if k in cred]
    extra = [k for k in cred if k not in keys]
    return (f"cred=SESSDATA:{mask(cred.get('SESSDATA'))} " + " ".join(parts) +
            (f" +{len(extra)}more" if extra else ""))


class Bili:
    def __init__(self, pace=1.0, cooldown=60, time_budget=0, sessdata=None,
                 buvid3=None, cookies=None):
        self.pace = pace
        self.cooldown = cooldown
        self.time_budget = time_budget
        self.started = time.time()
        self.hits = 0
        self.logged_in = False
        self.uname = None
        self.cred = dict(cookies or {})
        if sessdata:
            self.cred.setdefault("SESSDATA", sessdata)
        if buvid3:
            self.cred.setdefault("buvid3", buvid3)
        self.cj = http.cookiejar.CookieJar()
        for k, v in self.cred.items():
            if not v:
                continue
            self.cj.set_cookie(http.cookiejar.Cookie(
                0, k, v, None, False, ".bilibili.com", False, False,
                "/", True, False, None, False, None, None, {}))
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj))
        self.mixin = self._bootstrap()

    def persist_cred(self, path=None):
        """把 cookie jar 里最新的 bilibili cookie 写回凭据文件。

        B 站会在响应里刷新 SESSDATA/bili_ticket 等，每次运行回写可以让
        登录态延续，而不是拿到一份越来越旧的快照。
        """
        p = Path(path or CRED_FILE)
        items = [f"{c.name}={c.value}" for c in self.cj
                 if "bilibili" in (c.domain or "")]
        if not any(i.startswith("SESSDATA=") for i in items):
            return False
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("; ".join(items) + "\n", encoding="utf-8")
            return True
        except Exception as e:
            print(f"  ! persist cred failed: {e}", file=sys.stderr)
            return False

    def preflight(self):
        """Fail fast if the cookie is missing/expired, instead of silently
        collecting zero subtitles for hours."""
        r = self._raw("https://api.bilibili.com/x/web-interface/nav")
        d = r.get("data") or {}
        self.logged_in = bool(d.get("isLogin"))
        self.uname = d.get("uname")
        if not self.logged_in:
            raise NotLoggedIn(
                "SESSDATA 无效或已过期（nav 返回 isLogin=false）；"
                "请重新从浏览器复制后覆盖凭据文件")
        print(f"[login] ok as {self.uname}", file=sys.stderr)
        return True

    def check_budget(self):
        if self.time_budget and time.time() - self.started > self.time_budget:
            raise Budget(f"budget {self.time_budget}s exceeded")

    def _raw(self, url):
        req = urllib.request.Request(url, headers=HEAD)
        with self.opener.open(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def _sign(self, params):
        p = dict(params)
        p["wts"] = int(time.time())
        q = "&".join(f"{k}={urllib.parse.quote('' if p[k] is None else str(p[k]), safe='')}"
                     for k in sorted(p))
        return q + "&w_rid=" + hashlib.md5((q + self.mixin).encode()).hexdigest()

    def _bootstrap(self):
        wbi = CACHE / "wbi.json"
        try:
            c = json.loads(wbi.read_text(encoding="utf-8"))
            if time.time() - c.get("ts", 0) < 1800 and c.get("mixin"):
                for k, v in c.get("cookies", {}).items():
                    self.cj.set_cookie(http.cookiejar.Cookie(
                        0, k, v, None, False, ".bilibili.com", False, False,
                        "/", True, False, None, False, None, None, {}))
                return c["mixin"]
        except Exception:
            pass
        cookies = {}
        try:
            spi = self._raw("https://api.bilibili.com/x/frontend/finger/spi")
            for k, v in (("buvid3", spi["data"].get("b_3")),
                         ("buvid4", spi["data"].get("b_4"))):
                if v:
                    cookies[k] = v
        except Exception:
            pass
        nav = self._raw("https://api.bilibili.com/x/web-interface/nav")
        w = nav["data"]["wbi_img"]
        ik = w["img_url"].rsplit("/", 1)[-1].split(".")[0]
        sk = w["sub_url"].rsplit("/", 1)[-1].split(".")[0]
        raw = ik + sk
        mixin = "".join(raw[i] for i in MIXIN_TAB if i < len(raw))[:32]
        try:
            wbi.write_text(json.dumps({"ts": time.time(), "mixin": mixin,
                                       "cookies": cookies}), encoding="utf-8")
        except Exception:
            pass
        return mixin

    def get(self, path, params=None, tries=4):
        last = None
        throttled = False
        for i in range(tries):
            self.check_budget()
            q = self._sign(params or {})
            try:
                r = self._raw(f"https://api.bilibili.com/{path}?{q}")
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (412, 403):
                    throttled = True
                    time.sleep(self.cooldown)
                else:
                    time.sleep(1.5 * (i + 1))
                continue
            except Exception as e:
                last = e
                time.sleep(1.5 * (i + 1))
                continue
            code = r.get("code")
            if code == 0:
                return r
            if code == -101:
                raise NotLoggedIn(f"{path}: 账号未登录 (-101)")
            last = RuntimeError(f"{path} code={code} {r.get('message')}")
            if code in THROTTLE_CODES:
                throttled = True
                time.sleep(self.cooldown)
                continue
            raise last
        if throttled:
            raise Throttled(f"{path} throttled after {tries} tries")
        raise last

    def videos(self, mid, max_videos=0, order="click"):
        out, pn = [], 1
        while True:
            r = self.get("x/space/wbi/arc/search",
                         {"mid": mid, "ps": 30, "pn": pn, "order": order,
                          "platform": "web", "web_location": 1550101,
                          **DM_PARAMS}, tries=2)
            vl = ((r.get("data") or {}).get("list") or {}).get("vlist") or []
            if not vl:
                break
            for v in vl:
                out.append({"bvid": v["bvid"], "aid": v["aid"], "title": v["title"],
                            "play": v["play"], "created": v["created"],
                            "length": v.get("length")})
                if max_videos and len(out) >= max_videos:
                    return out
            pn += 1
            time.sleep(self.pace)
        return out

    def cid(self, bvid):
        r = self.get("x/player/pagelist", {"bvid": bvid})
        d = (r.get("data") or [])
        return d[0]["cid"] if d else None

    def subtitle_meta(self, aid, cid):
        for path in ("x/player/wbi/v2", "x/player/v2"):
            try:
                r = self.get(path, {"aid": aid, "cid": cid})
            except Exception:
                continue
            st = ((r.get("data") or {}).get("subtitle") or {})
            subs = st.get("subtitles") or []
            if subs:
                return subs
        return []


def srt_time(sec):
    ms = int(round(float(sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(body):
    out = []
    for i, line in enumerate(body, 1):
        out.append(str(i))
        out.append(f'{srt_time(line.get("from", 0))} --> {srt_time(line.get("to", 0))}')
        out.append((line.get("content") or "").strip())
        out.append("")
    return "\n".join(out)


def safe_name(s, n=60):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Windows 会静默去掉目录名结尾的点和空格：若不清掉，mkdir 建出的名字与
    # 后续写入用的名字不一致，表现为「目录存在但写入报 Errno 2」。
    s = s.rstrip(". ")[:n].rstrip(". ").strip()
    if s.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", "COM1", "COM2",
                                   "COM3", "LPT1", "LPT2", "LPT3"}:
        s = "_" + s
    return s or "untitled"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mids")
    ap.add_argument("--roster")
    ap.add_argument("--outdir", default="subs")
    ap.add_argument("--max-videos", type=int, default=0, dest="max_videos",
                    help="cap videos per UP (0 = all)")
    ap.add_argument("--order", default="click", help="click|pubdate")
    ap.add_argument("--budget", type=int, default=0, help="seconds (0=off)")
    ap.add_argument("--pace", type=float, default=1.0)
    ap.add_argument("--cooldown", type=int, default=60)
    ap.add_argument("--sessdata", default=None,
                    help="override; prefer the credential file")
    ap.add_argument("--cred-file", default=None, dest="cred_file",
                    help="default ~/.dsh/bili_sessdata.txt (line1 SESSDATA, "
                         "line2 optional buvid3)")
    ap.add_argument("--check-login", action="store_true", dest="check_login",
                    help="only verify the cookie and exit")
    ap.add_argument("--allow-anon", action="store_true", dest="allow_anon",
                    help="continue even if not logged in (subs will be empty)")
    a = ap.parse_args()

    cred = read_cred(a.cred_file)
    if a.sessdata:
        cred['SESSDATA'] = a.sessdata
    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=cred)
    print(f"[cred] {cred_summary(cred)} "
          f"file={a.cred_file or CRED_FILE}", file=sys.stderr)
    try:
        b.preflight()
    except NotLoggedIn as e:
        print(f"\n[NO-LOGIN] {e}", file=sys.stderr)
        if a.check_login or not a.allow_anon:
            raise SystemExit(3)
        print("[warn] continuing anonymously: subtitle lists will be empty",
              file=sys.stderr)
    if a.check_login:
        print("login check passed", file=sys.stderr)
        return

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    index = outdir / "index.jsonl"
    done = set()
    if index.exists():
        for line in index.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["bvid"])
            except Exception:
                pass

    mids = []
    names = {}
    if a.mids:
        mids = [int(x) for x in a.mids.split(",") if x.strip()]
    if a.roster:
        for line in Path(a.roster).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            c = line.split("\t")
            try:
                mids.append(int(c[0]))
                names[int(c[0])] = c[1] if len(c) > 1 else str(c[0])
            except ValueError:
                pass

    stats = {"ups": 0, "videos": 0, "with_subs": 0, "files": 0, "no_subs": 0,
             "errors": 0, "skipped": 0}
    try:
        for mid in mids:
            try:
                card = b.get("x/web-interface/card", {"mid": mid}).get("data") or {}
                uname = card.get("card", {}).get("name") or names.get(mid, str(mid))
            except (Throttled, Budget):
                raise
            except Exception:
                uname = names.get(mid, str(mid))
            updir = outdir / f"{mid}_{safe_name(uname, 30)}"
            updir.mkdir(parents=True, exist_ok=True)
            print(f"\n=== {uname} ({mid}) -> {updir}", file=sys.stderr)
            try:
                vids = b.videos(mid, a.max_videos, a.order)
            except (Throttled, Budget):
                raise
            except Exception as e:
                print(f"  video list failed: {e}", file=sys.stderr)
                stats["errors"] += 1
                continue
            stats["ups"] += 1
            print(f"  {len(vids)} videos", file=sys.stderr)
            for v in vids:
                stats["videos"] += 1
                if v["bvid"] in done:
                    stats["skipped"] += 1
                    continue
                try:
                    cid = b.cid(v["bvid"])
                    subs = b.subtitle_meta(v["aid"], cid) if cid else []
                except (Throttled, Budget):
                    raise
                except Exception as e:
                    print(f"  ! {v['bvid']}: {e}", file=sys.stderr)
                    stats["errors"] += 1
                    time.sleep(b.pace)
                    continue
                if not subs:
                    stats["no_subs"] += 1
                    with index.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({"bvid": v["bvid"], "mid": mid,
                                            "title": v["title"], "subs": 0,
                                            "ts": time.time()}, ensure_ascii=False) + "\n")
                    done.add(v["bvid"])
                    time.sleep(b.pace)
                    continue
                stats["with_subs"] += 1
                for s in subs:
                    url = s.get("subtitle_url") or ""
                    if url.startswith("//"):
                        url = "https:" + url
                    if not url:
                        continue
                    try:
                        data = b._raw(url)
                    except Exception as e:
                        print(f"  ! subtitle dl {v['bvid']}: {e}", file=sys.stderr)
                        continue
                    body = data.get("body") or []
                    if not body:
                        continue
                    base = f"{v['bvid']}_{safe_name(v['title'])}"
                    lan = (s.get("lan") or "zh").replace("/", "_")
                    (updir / f"{base}.{lan}.srt").write_text(to_srt(body),
                                                             encoding="utf-8")
                    txt = "\n".join((x.get("content") or "").strip() for x in body)
                    (updir / f"{base}.{lan}.txt").write_text(txt, encoding="utf-8")
                    stats["files"] += 2
                    time.sleep(b.pace)
                with index.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"bvid": v["bvid"], "mid": mid,
                                        "title": v["title"], "subs": len(subs),
                                        "ts": time.time()}, ensure_ascii=False) + "\n")
                done.add(v["bvid"])
                if stats["with_subs"] % 10 == 0:
                    print(f"  ... {stats}", file=sys.stderr)
    except (Throttled, Budget) as e:
        print(f"\n[STOPPED] {e}", file=sys.stderr)
        print(f"[stats] {stats}", file=sys.stderr)
        raise SystemExit(2)
    except NotLoggedIn as e:
        print(f"\n[NO-LOGIN] {e}", file=sys.stderr)
        print(f"[stats] {stats}", file=sys.stderr)
        raise SystemExit(3)
    print(f"\n[stats] {stats}", file=sys.stderr)


if __name__ == "__main__":
    main()
