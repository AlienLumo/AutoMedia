#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili.py — Bilibili UP-master research CLI (WBI signed, risk-control aware).

One-stop replacement for the ad-hoc probing that normally takes 10+ tool calls.
Everything is printed as a compact TSV so only the rows you need enter context;
full data always lands in a JSON file.

Commands
  discover  topic/keyword -> uploaders -> fan-verified table   (cold start)
  check     names or mids -> fan table                          (verify a list)
  detail    mids -> recent uploads table                        (classify)
  resolve   name list file -> mid + fans                        (name -> id)
  rank      read a saved JSON -> filtered top-N table           (re-slice cheaply)

Examples
  python bili.py discover --topics "AI Agent|Agent Skills|Claude Code" --min-fans 100000
  python bili.py check --names "图灵的猫,秋芝2046,花叔v"
  python bili.py detail --mids 371846699,385670211 --ps 6
  python bili.py rank --file bili_research.json --min-fans 100000 --limit 40
"""

import argparse
import hashlib
import http.cookiejar
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

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
CACHE = Path(os.environ.get("BILI_CACHE", Path.home() / ".cache" / "dsh-bili"))
CACHE.mkdir(parents=True, exist_ok=True)
WBI_CACHE = CACHE / "wbi.json"
WBI_TTL = 1800  # seconds; bilibili rotates keys daily but this is plenty
CARD_CACHE = CACHE / "cards.json"   # mid -> {ts, data}; kills repeat requests
THROTTLE_CODES = {-352, -412, -509, -799}   # risk-control / rate-limit codes

try:                              # keep Chinese readable on Windows pipes
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class Throttled(Exception):
    """Raised when bilibili keeps rate-limiting; caller saves partial results."""


class BudgetExceeded(Exception):
    """Raised when --time-budget runs out; caller saves partial results."""


class Bili:
    def __init__(self, pace=0.9, cooldown=45, throttle_limit=5, reset=2,
                 card_ttl=21600, fresh=False, time_budget=0):
        self.pace = pace
        self.cooldown = cooldown            # seconds to sleep on a throttle burst
        self.throttle_limit = throttle_limit  # failures per burst before cooldown
        self.reset = reset                  # cooldowns allowed before giving up
        self.card_ttl = card_ttl
        self.fresh = fresh
        self.time_budget = time_budget
        self.started = time.time()
        self._throttle_hits = 0
        self._cooldowns = 0
        self.cache_hits = 0
        self.failed = []            # mids we could not fetch -> report, never hide
        self.cache = self._load_card_cache()
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj))
        self.mixin = self._bootstrap()

    # ---------- guards ----------
    def check_budget(self):
        if self.time_budget and time.time() - self.started > self.time_budget:
            raise BudgetExceeded(
                f"time budget {self.time_budget}s exceeded")

    def _throttled(self, why):
        """One burst of failures -> a single long cooldown, not per-request sleeps."""
        self._throttle_hits += 1
        if self._throttle_hits % self.throttle_limit:
            return
        self._cooldowns += 1
        if self._cooldowns > self.reset:
            raise Throttled(
                f"rate-limited {self._throttle_hits} times, gave up after "
                f"{self._cooldowns - 1} cooldowns ({why})")
        print(f"  [throttled: {why}] cooling down {self.cooldown}s "
              f"(round {self._cooldowns}/{self.reset})", file=sys.stderr)
        time.sleep(self.cooldown)

    # ---------- low level ----------
    def _raw(self, url):
        """Single attempt. Retry policy lives in get() so delays don't nest."""
        req = urllib.request.Request(url, headers=HEAD)
        with self.opener.open(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))

    def get(self, path, params=None, tries=3):
        """GET with wbi signing; converts rate limiting into a bounded cooldown."""
        last = None
        saw_throttle = False
        for i in range(tries):
            self.check_budget()
            q = self._sign(params or {})
            try:
                r = self._raw(f"https://api.bilibili.com/{path}?{q}")
            except urllib.error.HTTPError as e:
                last = e
                if e.code == 412:
                    saw_throttle = True
                    self._throttled("http 412")
                else:
                    time.sleep(0.8 * (i + 1))
                continue
            except Exception as e:
                last = e
                time.sleep(0.8 * (i + 1))
                continue
            code = r.get("code")
            if code == 0:
                self._throttle_hits = 0      # success resets the burst counter
                return r
            last = RuntimeError(f"{path} code={code} {r.get('message')}")
            if code in THROTTLE_CODES:
                saw_throttle = True
                self._throttled(f"code {code}")
                continue
            raise last
        # exhausted retries: if the reason was throttling, say so instead of
        # letting the caller silently drop the account
        if saw_throttle:
            raise Throttled(f"{path} stayed throttled after {tries} tries")
        raise last

    def _sign(self, params):
        p = dict(params)
        p["wts"] = int(time.time())
        q = "&".join(f"{k}={urllib.parse.quote('' if p[k] is None else str(p[k]), safe='')}"
                     for k in sorted(p))
        rid = hashlib.md5((q + self.mixin).encode()).hexdigest()
        return q + "&w_rid=" + rid

    def _bootstrap(self):
        # reuse cached wbi keys to save 2 round-trips per run
        try:
            c = json.loads(WBI_CACHE.read_text(encoding="utf-8"))
            if time.time() - c.get("ts", 0) < WBI_TTL and c.get("mixin"):
                for name, val in c.get("cookies", {}).items():
                    self.cj.set_cookie(http.cookiejar.Cookie(
                        0, name, val, None, False, ".bilibili.com", False,
                        False, "/", True, False, None, False, None, None, {}))
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
                    self.cj.set_cookie(http.cookiejar.Cookie(
                        0, k, v, None, False, ".bilibili.com", False, False,
                        "/", True, False, None, False, None, None, {}))
        except Exception as e:
            print(f"warn spi: {e}", file=sys.stderr)

        nav = self._raw("https://api.bilibili.com/x/web-interface/nav")
        w = nav["data"]["wbi_img"]
        ik = w["img_url"].rsplit("/", 1)[-1].split(".")[0]
        sk = w["sub_url"].rsplit("/", 1)[-1].split(".")[0]
        raw = ik + sk
        mixin = "".join(raw[i] for i in MIXIN_TAB if i < len(raw))[:32]
        try:
            WBI_CACHE.write_text(json.dumps(
                {"ts": time.time(), "mixin": mixin, "cookies": cookies}),
                encoding="utf-8")
        except Exception:
            pass
        return mixin

    # ---------- domain ----------
    def search_users(self, kw, pages=2, order="fans"):
        out = []
        for page in range(1, pages + 1):
            r = self.get("x/web-interface/wbi/search/type",
                         {"search_type": "bili_user", "keyword": kw,
                          "page": page, "order": order})
            res = (r.get("data") or {}).get("result") or []
            for u in res:
                out.append({
                    "mid": u.get("mid"), "name": u.get("uname"),
                    "fans": u.get("fans"), "videos": u.get("videos"),
                    "sign": (u.get("usign") or "").replace("\n", " ")[:100],
                    "kw": kw, "src": "user",
                })
            print(f"  [user:{kw} p{page}] {len(res)} rows", file=sys.stderr)
            time.sleep(self.pace)
        return out

    def search_videos(self, kw, pages=2, order="click"):
        out = []
        for page in range(1, pages + 1):
            r = self.get("x/web-interface/wbi/search/type",
                         {"search_type": "video", "keyword": kw,
                          "page": page, "order": order})
            res = (r.get("data") or {}).get("result") or []
            for v in res:
                title = (v.get("title") or "")
                for tag in ('<em class="keyword">', "</em>"):
                    title = title.replace(tag, "")
                out.append({"mid": v.get("mid"), "name": v.get("author"),
                            "play": v.get("play"), "title": title[:70],
                            "kw": kw, "src": "video"})
            print(f"  [video:{kw} p{page}] {len(res)} rows", file=sys.stderr)
            time.sleep(self.pace)
        return out

    def _load_card_cache(self):
        try:
            return json.loads(CARD_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _flush_cache(self):
        try:
            CARD_CACHE.write_text(json.dumps(self.cache, ensure_ascii=False),
                                  encoding="utf-8")
        except Exception as e:
            print(f"  cache write failed: {e}", file=sys.stderr)

    def card(self, mid):
        """Cached card fetch: repeat runs cost zero requests for the TTL window."""
        key = str(mid)
        if not self.fresh and self.card_ttl:
            hit = self.cache.get(key)
            if hit and time.time() - hit.get("ts", 0) < self.card_ttl:
                self.cache_hits += 1
                return dict(hit["data"])
        try:
            r = self.get("x/web-interface/card", {"mid": mid, "photo": "false"})
            d = r["data"]
            data = {"mid": mid, "name": d["card"].get("name"),
                    "fans": d.get("follower"),
                    "sign": (d["card"].get("sign") or "").replace("\n", " ")[:100],
                    "archive": d.get("archive_count")}
            self.cache[key] = {"ts": time.time(), "data": data}
            if len(self.cache) % 20 == 0:
                self._flush_cache()
            return dict(data)
        except (Throttled, BudgetExceeded):
            raise
        except Exception as e:
            print(f"  card {mid} failed: {e}", file=sys.stderr)
            self.failed.append(mid)
            return None

    def recent(self, mid, ps=6):
        try:
            r = self.get("x/space/wbi/arc/search",
                         {"mid": mid, "ps": ps, "pn": 1, "order": "pubdate",
                          "platform": "web", "web_location": 1550101})
            vl = ((r.get("data") or {}).get("list") or {}).get("vlist") or []
            return [(v["title"][:70], v["play"],
                     time.strftime("%Y-%m", time.localtime(v["created"])))
                    for v in vl]
        except Exception as e:
            print(f"  recent {mid} failed: {e}", file=sys.stderr)
            return []

    def resolve_name(self, name):
        """Exact-match first, else best fuzzy hit (report it as fuzzy)."""
        r = self.get("x/web-interface/wbi/search/type",
                     {"search_type": "bili_user", "keyword": name, "page": 1})
        res = (r.get("data") or {}).get("result") or []
        norm = name.replace(" ", "")
        for u in res:
            if (u.get("uname") or "").replace(" ", "") == norm:
                return {"mid": u["mid"], "name": u["uname"], "fans": u.get("fans"),
                        "fuzzy": False}
        if res:
            u = res[0]
            return {"mid": u["mid"], "name": u["uname"], "fans": u.get("fans"),
                    "fuzzy": True}
        return None


# ---------------- output helpers ----------------
def fmt_fans(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


def print_table(rows, limit=None, show_sign=True):
    """Compact table: the ONLY thing that should enter the context."""
    has_cat = any(r.get("cat") for r in rows)
    print("fans\tname\tmid" + ("\tcat" if has_cat else "") + "\tsign")
    for i, r in enumerate(rows):
        if limit and i >= limit:
            break
        sign = (r.get("sign") or "")[:52] if show_sign else ""
        cat = f'\t{r["cat"]}' if has_cat else ""
        print(f'{fmt_fans(r.get("fans"))}\t{r.get("name")}\t{r.get("mid")}{cat}\t{sign}')


def save(rows, path):
    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[saved {len(rows)} rows -> {p}]", file=sys.stderr)


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        m = r.get("mid")
        if m in seen:
            continue
        seen.add(m)
        out.append(r)
    return out


# ---------------- commands ----------------
def _verify_all(b, mids, a, extra=None, pool=None):
    """Card-verify with budget/throttle guards, incremental saves, cache reuse.

    Returns (rows, done, total, aborted_reason). A throttle burst or an expired
    time budget yields PARTIAL results instead of a silent 10-minute hang.
    """
    rows, done, total, aborted = [], 0, len(mids), None
    for i, mid in enumerate(mids):
        hits_before = b.cache_hits
        try:
            c = b.card(mid)
        except (Throttled, BudgetExceeded) as e:
            aborted = str(e)
            break
        if c:
            if extra and mid in extra:
                c.update({k: v for k, v in extra[mid].items() if v})
            if pool:
                c["kws"] = sorted({r["kw"] for r in pool if r["mid"] == mid})
            rows.append(c)
        done = i + 1
        if done % 20 == 0:
            b._flush_cache()
            save(rows, a.out)                 # a kill loses at most 20 cards
            print(f"  ...{done}/{total} verified (cache hits {b.cache_hits})",
                  file=sys.stderr)
        if b.cache_hits == hits_before:       # pace REAL requests only
            time.sleep(a.card_pace)
    b._flush_cache()
    if b.failed:
        print(f"[incomplete] {len(b.failed)} accounts could not be fetched; "
              f"re-run to retry them (cached ones cost 0 requests): "
              f"{b.failed[:10]}", file=sys.stderr)
    if aborted:
        print(f"\n[STOPPED] {aborted}\n"
              f"[partial] {done}/{total} verified, results still written. "
              f"Re-run in a few minutes: cached accounts cost 0 requests.",
              file=sys.stderr)
    return rows, done, total, aborted


def _finish(rows, a, aborted):
    rows.sort(key=lambda x: -(x.get("fans") or 0))
    if a.min_fans:
        rows = [r for r in rows if (r.get("fans") or 0) >= a.min_fans]
    save(rows, a.out)
    print_table(rows, a.limit)
    if aborted:
        raise SystemExit(2)


def cmd_discover(b, a):
    topics = [t.strip() for t in a.topics.split("|") if t.strip()]
    pool = []
    try:
        for t in topics:
            if a.mode in ("video", "both"):
                pool += b.search_videos(t, a.pages, a.order)
            if a.mode in ("user", "both"):
                pool += b.search_users(t, a.pages, "fans")
    except BudgetExceeded as e:
        print(f"\n[STOPPED] {e} (during search phase)", file=sys.stderr)

    by_mid = {}
    for r in pool:
        if r.get("mid"):
            by_mid.setdefault(r["mid"], r)
    # pre-filter with search-returned fans where available; only survivors get a
    # card call (the expensive, risk-control-prone request)
    mids = []
    for mid, r in by_mid.items():
        f = r.get("fans")
        if f is not None and a.min_fans and f < a.min_fans * 0.95:
            continue
        mids.append(mid)
    if getattr(a, "max_verify", 0) and len(mids) > a.max_verify:
        print(f"[warning] capping card verifies {len(mids)} -> {a.max_verify}",
              file=sys.stderr)
        mids = mids[:a.max_verify]
    print(f"[{len(pool)} hits / {len(by_mid)} unique / {len(mids)} to verify]",
          file=sys.stderr)

    rows, done, total, aborted = _verify_all(b, mids, a, pool=pool)
    _finish(rows, a, aborted)


def cmd_check(b, a):
    mids = []
    extra = {}          # mid -> {name, cat} from a seed roster file
    if a.mids:
        mids += [int(x) for x in a.mids.split(",") if x.strip()]
    if getattr(a, "mids_file", None):
        for line in Path(a.mids_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            try:
                mid = int(cols[0])
            except ValueError:
                continue
            mids.append(mid)
            extra[mid] = {"name": cols[1] if len(cols) > 1 else "",
                          "cat": cols[2] if len(cols) > 2 else ""}
    if a.names:
        for nm in [x.strip() for x in a.names.split(",") if x.strip()]:
            r = b.resolve_name(nm)
            if r:
                if r["fuzzy"]:
                    print(f"  ! fuzzy match: {nm} -> {r['name']}",
                          file=sys.stderr)
                mids.append(r["mid"])
            else:
                print(f"  ! not found: {nm}", file=sys.stderr)
            time.sleep(b.pace)
    rows, done, total, aborted = _verify_all(b, list(dict.fromkeys(mids)), a,
                                             extra=extra)
    _finish(rows, a, aborted)


def cmd_detail(b, a):
    mids = [int(x) for x in a.mids.split(",") if x.strip()]
    for mid in mids:
        c = b.card(mid) or {"mid": mid, "name": f"mid={mid}"}
        print(f'\n## {c.get("name")} | {fmt_fans(c.get("fans"))} | {mid}')
        if c.get("sign"):
            print(f'   sign: {c["sign"][:80]}')
        for t in b.recent(mid, a.ps):
            print(f"   - [{t[2]}] {t[0]}  ({t[1]})")
        time.sleep(b.pace)


def cmd_resolve(b, a):
    names = []
    if a.file:
        names = [x.strip() for x in Path(a.file).read_text(encoding="utf-8").splitlines()
                 if x.strip()]
    elif a.names:
        names = [x.strip() for x in a.names.split(",") if x.strip()]
    rows = []
    for nm in names:
        r = b.resolve_name(nm)
        if r:
            r["query"] = nm
            rows.append(r)
            flag = " [FUZZY]" if r["fuzzy"] else ""
            print(f'{fmt_fans(r["fans"])}\t{r["name"]}\t{r["mid"]}{flag}')
        else:
            print(f'-\t{nm}\tNOT_FOUND')
        time.sleep(b.pace)
    save(rows, a.out)


def cmd_rank(b, a):
    rows = json.loads(Path(a.file).read_text(encoding="utf-8"))
    if a.min_fans:
        rows = [r for r in rows if (r.get("fans") or 0) >= a.min_fans]
    if a.grep:
        rows = [r for r in rows
                if any(a.grep in (r.get(k) or "") for k in ("name", "sign", "cat"))]
    rows.sort(key=lambda x: -(x.get("fans") or 0))
    print_table(rows, a.limit)


def main():
    ap = argparse.ArgumentParser(description="Bilibili UP-master research CLI")
    # shared options live on every subcommand so they can always be written last
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--out", default="bili_research.json", help="JSON output path")
    shared.add_argument("--pace", type=float, default=0.9, help="sleep between searches")
    shared.add_argument("--card-pace", type=float, default=0.5, dest="card_pace")
    shared.add_argument("--time-budget", type=int, default=0, dest="time_budget",
                        help="stop and keep partial results after N seconds (0=off)")
    shared.add_argument("--cache-ttl", type=int, default=21600, dest="cache_ttl",
                        help="reuse card results younger than N seconds (0=off)")
    shared.add_argument("--fresh", action="store_true",
                        help="ignore the card cache, always re-fetch fans")
    shared.add_argument("--cooldown", type=int, default=45,
                        help="seconds to wait when rate limited")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", parents=[shared], help="topic -> verified UP table")
    d.add_argument("--topics", required=True, help='pipe separated, e.g. "AI Agent|Skill"')
    d.add_argument("--mode", default="both", choices=["video", "user", "both"])
    d.add_argument("--pages", type=int, default=2)
    d.add_argument("--order", default="click", help="video order: click|pubdate|dm")
    d.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
    d.add_argument("--max-verify", type=int, default=120, dest="max_verify",
                   help="cap card calls per run (0 = no cap)")
    d.add_argument("--limit", type=int, default=60)
    d.set_defaults(func=cmd_discover)

    c = sub.add_parser("check", parents=[shared], help="names/mids -> fan table")
    c.add_argument("--mids")
    c.add_argument("--names")
    c.add_argument("--mids-file", dest="mids_file",
                   help="TSV: mid<tab>name<tab>cat (skips discovery)")
    c.add_argument("--min-fans", type=int, default=0, dest="min_fans")
    c.add_argument("--limit", type=int, default=100)
    c.set_defaults(func=cmd_check)

    t = sub.add_parser("detail", parents=[shared], help="mids -> recent uploads")
    t.add_argument("--mids", required=True)
    t.add_argument("--ps", type=int, default=6)
    t.set_defaults(func=cmd_detail)

    r = sub.add_parser("resolve", parents=[shared], help="names -> mids")
    r.add_argument("--names")
    r.add_argument("--file")
    r.set_defaults(func=cmd_resolve)

    k = sub.add_parser("rank", parents=[shared], help="re-slice a saved JSON")
    k.add_argument("--file", required=True)
    k.add_argument("--min-fans", type=int, default=0, dest="min_fans")
    k.add_argument("--grep", help="substring filter on sign/name")
    k.add_argument("--limit", type=int, default=50)
    k.set_defaults(func=cmd_rank)

    a = ap.parse_args()
    if a.cmd == "rank":            # no network needed
        cmd_rank(None, a)
        return
    b = Bili(pace=a.pace, cooldown=a.cooldown, card_ttl=a.cache_ttl,
             fresh=a.fresh, time_budget=a.time_budget)
    try:
        a.func(b, a)
    except (Throttled, BudgetExceeded) as e:
        print(f"\n[STOPPED] {e}", file=sys.stderr)
        raise SystemExit(2)
    finally:
        b._flush_cache()
        if b.cache_hits:
            print(f"[cache] {b.cache_hits} accounts served from cache "
                  f"(0 requests)", file=sys.stderr)


if __name__ == "__main__":
    main()
