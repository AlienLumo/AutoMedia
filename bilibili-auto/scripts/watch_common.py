#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""watch_common.py — B站监听/轮询的公共层（状态、限速、锁、收件箱）。

设计约束（见 skills/规则.md）：
- 只读：不点赞/投币/收藏/评论/关注。
- 单并发：全局 PID 锁；同一时刻只允许一个监听实例。
- 限速：基础间隔 pace + 抖动；每 rest_every 次请求强制休息。
- 静默：23:00–08:00 不发起请求（可 --no-quiet 关闭，默认开）。
- 预算：每轮请求上限 / 时间上限，到点优雅退出，下次续跑。
"""
import json
import os
import random
import sys
import time
import ctypes
from datetime import datetime
from pathlib import Path
from _paths import PROJECT, SKILL as _SKILL

PROJ = PROJECT
SKILL = _SKILL
SCRIPTS = SKILL / "scripts"
CONF = SKILL / "config"
LOGS = SKILL / "logs"
STATE = PROJ / "1AMdata" / "_state" / "watch"
WATCH = PROJ / "1AMdata" / "watch"
VIDEOS = WATCH / "videos"
DIGESTS = WATCH / "digests"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:                      # Windows 控制台默认 GBK，统一成 UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

QUIET_START, QUIET_END = 23, 8


def ensure_dirs():
    for p in (STATE, VIDEOS, DIGESTS, LOGS):
        p.mkdir(parents=True, exist_ok=True)


def today():
    return datetime.now().strftime("%Y-%m-%d")


def now():
    return time.time()


def load_json(path, default):
    try:
        # utf-8-sig：兼容 PowerShell Set-Content -Encoding UTF8 写入的 BOM
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def emit(obj):
    """pythonw 下 stdout 可能不可用，安全打印。"""
    try:
        print(json.dumps(obj, ensure_ascii=False) if isinstance(obj, (dict, list)) else obj)
    except Exception:
        pass


def log(msg, tag="watch"):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:
        pass
    try:
        ensure_dirs()
        with (LOGS / f"{tag}_{today()}.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------- 配置 ----------------
def load_config():
    cfg = load_json(CONF / "watch.json", {})
    cfg.setdefault("pace_list", 1.5)
    cfg.setdefault("pace_search", 2.5)
    cfg.setdefault("rest_every", 300)
    cfg.setdefault("quiet", True)
    cfg.setdefault("ups", {"max_requests_per_run": 1200, "max_new_per_run": 300,
                           "ps": 5, "s_prefixes": ["ai", "教程", "机器人", "科研", "数码评测"]})
    cfg.setdefault("keywords", {"file": str(CONF / "watch_keywords.txt"), "pages": 2,
                                "days": 3, "max_requests_per_run": 1200,
                                "batch_keywords": 120})
    cfg.setdefault("inbox", {"comment_cap": 100, "max_requests_per_run": 800,
                             "max_items_per_run": 60, "sub_langs": ["zh"]})
    cfg.setdefault("digest", {"top": 12, "push": True})
    return cfg


# ---------------- 名单 ----------------
def _read_tsv(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        rows.append(line.split("\t"))
    return rows


def load_roster():
    """合并 ups.tsv / prefix_map.tsv / watch_tiers.tsv -> [{mid,name,prefix,fans,tier}]。"""
    cfg = load_config()
    pmap = {}
    for c in _read_tsv(CONF / "prefix_map.tsv"):
        if len(c) < 4:
            continue
        try:
            pmap[int(c[0])] = {"name": c[1], "prefix": c[2], "fans": int(c[3] or 0)}
        except ValueError:
            continue
    tiers = {}
    for c in _read_tsv(CONF / "watch_tiers.tsv"):
        if len(c) < 2:
            continue
        try:
            tiers[int(c[0])] = c[1].strip().upper()
        except ValueError:
            continue
    s_prefixes = set(cfg["ups"].get("s_prefixes") or [])
    out, seen = [], set()
    for c in _read_tsv(CONF / "ups.tsv"):
        try:
            mid = int(c[0])
        except (ValueError, IndexError):
            continue
        if mid in seen:
            continue
        seen.add(mid)
        info = pmap.get(mid) or {}
        prefix = info.get("prefix") or (c[2] if len(c) > 2 else "")
        tier = tiers.get(mid) or ("S" if prefix in s_prefixes else "A")
        out.append({"mid": mid,
                    "name": info.get("name") or (c[1] if len(c) > 1 else str(mid)),
                    "prefix": prefix or "other",
                    "fans": info.get("fans") or 0,
                    "tier": tier})
    return out


# ---------------- 锁 ----------------
def _pid_alive(pid):
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, 0, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259
    except Exception:
        return True


class Lock:
    def __init__(self, name="watch"):
        ensure_dirs()
        self.path = STATE / f".{name}.lock"

    def __enter__(self):
        if self.path.exists():
            try:
                pid = int(self.path.read_text(encoding="utf-8").strip() or 0)
            except Exception:
                pid = 0
            if pid and _pid_alive(pid):
                log(f"[skip] 已有实例 pid={pid} 在运行，退出")
                raise SystemExit(0)
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        return self

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except OSError:
            pass
        return False


NET_LOCK = STATE / ".bili_net.lock"


def _pid_alive_net(pid):
    return _pid_alive(pid)


class NetLock:
    """全局网络互斥：同一时刻只允许一个进程向 B 站发请求。

    不同计划任务（Inbox/UpsS/KW…）是不同进程，任务计划器不会互斥；
    两个进程同时按 1.5s 节奏跑会让实际速率翻倍、增加风控概率，也会并发
    回写同一份 cookie。这里用跨进程文件锁串行化，等不到就本轮跳过。
    """

    def __init__(self, wait=60, tag="net"):
        self.wait = wait
        self.tag = tag

    def _holder(self):
        try:
            return int(NET_LOCK.read_text(encoding="utf-8").strip() or 0)
        except Exception:
            return 0

    def _acquire(self):
        try:
            fd = os.open(str(NET_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            pid = self._holder()
            if pid and not _pid_alive(pid):
                try:
                    NET_LOCK.unlink()
                except OSError:
                    pass
                try:
                    fd = os.open(str(NET_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, str(os.getpid()).encode())
                    os.close(fd)
                    return True
                except FileExistsError:
                    return False
            return False

    def __enter__(self):
        ensure_dirs()
        deadline = time.time() + max(self.wait, 0)
        while True:
            if self._acquire():
                log("[net-lock] 已获得网络锁", self.tag)
                return self
            if time.time() >= deadline:
                log(f"[skip] 网络锁被 pid={self._holder()} 占用，等待 {self.wait}s 后跳过本轮",
                    self.tag)
                raise SystemExit(0)
            time.sleep(3)

    def __exit__(self, *exc):
        try:
            if self._holder() == os.getpid():
                NET_LOCK.unlink()
        except OSError:
            pass
        return False


# ---------------- 客户端 ----------------
class Stop(Exception):
    """本轮主动停止（预算/静默/连续限流）。"""


class Client:
    """在 bili_subs.Bili 外面套一层：预算、静默、休息、抖动。"""

    def __init__(self, pace=None, max_requests=1200, rest_every=None,
                 quiet=True, time_budget=0, cooldown=90, tag="watch"):
        from bili_subs import Bili, read_cred
        cfg = load_config()
        self.pace = pace if pace is not None else cfg["pace_list"]
        self.max_requests = max_requests
        self.rest_every = rest_every or cfg["rest_every"]
        self.quiet = quiet
        self.time_budget = time_budget
        self.started = time.time()
        self.req = 0
        self.tag = tag
        self.throttle_streak = 0
        self.b = Bili(pace=self.pace, cooldown=cooldown, cookies=read_cred())
        self.b.preflight()
        self._patch()

    def _patch(self):
        """把预算/静默/休息/节奏套在底层 b.get 上，这样 collect_meta/collect_subs
        等复用函数发出的请求也会被计数和限速。"""
        from bili_subs import NotLoggedIn, Throttled
        orig = self.b.get

        def wrapped(path, params=None, tries=4):
            self.check()
            if self.req and self.rest_every and self.req % self.rest_every == 0:
                rest = random.uniform(45, 90)
                log(f"[rest] 已发 {self.req} 请求，休息 {rest:.0f}s", self.tag)
                time.sleep(rest)
            self.req += 1
            try:
                r = orig(path, params, tries=tries)
                self.throttle_streak = 0
                return r
            except NotLoggedIn:
                raise
            except Throttled:
                self.throttle_streak += 1
                if self.throttle_streak >= 3:
                    raise Stop(f"连续 {self.throttle_streak} 次限流，主动停机")
                back = {1: 120, 2: 300}.get(self.throttle_streak, 600)
                log(f"[throttled x{self.throttle_streak}] 退避 {back}s", self.tag)
                time.sleep(back)
                raise
            finally:
                time.sleep(self.pace * random.uniform(0.75, 1.35))

        self.b.get = wrapped

    def check(self):
        if self.quiet and (time.localtime().tm_hour >= QUIET_START
                           or time.localtime().tm_hour < QUIET_END):
            raise Stop("quiet_hours 23:00-08:00")
        if self.max_requests and self.req >= self.max_requests:
            raise Stop(f"达到本轮请求上限 {self.max_requests}")
        if self.time_budget and time.time() - self.started > self.time_budget:
            raise Stop(f"达到本轮时间上限 {self.time_budget}s")

    def get(self, path, params=None):
        return self.b.get(path, params)

    def close(self):
        try:
            if getattr(self.b, "logged_in", False):
                self.b.persist_cred()
        except Exception:
            pass


def pace_sleep(client, pace=None):
    time.sleep((pace or client.pace) * random.uniform(0.75, 1.35))


# ---------------- 收件箱 ----------------
INBOX = WATCH / "inbox.jsonl"
INBOX_INDEX = WATCH / "inbox_index.json"


def load_index():
    return load_json(INBOX_INDEX, {})


KNOWN_FILE = STATE / "known_bvids.json"
KNOWN_TTL = 86400


def load_known(force=False):
    """主采集库里已有的 bvid 集合（避免监听重复入库）。每天重建一次。"""
    data = load_json(KNOWN_FILE, {})
    if (not force and data.get("built_at")
            and time.time() - data["built_at"] < KNOWN_TTL):
        return set(data.get("bvids") or [])
    base = PROJ / "1AMdata" / "bilibili"
    bvids = set()
    try:
        for up in base.iterdir():
            if not up.is_dir():
                continue
            for v in up.iterdir():
                if v.is_dir() and v.name[:2] == "BV":
                    bvids.add(v.name.split("_")[0])
            pool = up / "_pool"
            if pool.is_dir():
                for v in pool.iterdir():
                    if v.is_dir() and v.name[:2] == "BV":
                        bvids.add(v.name.split("_")[0])
    except Exception as e:
        log(f"[known] 扫描主库失败: {e}", "watch")
    save_json(KNOWN_FILE, {"built_at": time.time(), "bvids": sorted(bvids)})
    log(f"[known] 主库已知 {len(bvids)} 个 bvid", "watch")
    return bvids


def add_inbox(items, known=None):
    """按 bvid 去重后追加到 inbox.jsonl，并更新索引。返回实际新增条数。"""
    ensure_dirs()
    idx = load_index()
    if known is None:
        try:
            known = load_known()
        except Exception:
            known = set()
    added, added_items, skipped_known = 0, [], 0
    with INBOX.open("a", encoding="utf-8") as f:
        for it in items:
            bvid = it.get("bvid")
            if not bvid or bvid in idx:
                continue
            if known and bvid in known:
                skipped_known += 1
                idx[bvid] = {"ts": int(time.time()), "source": "already_collected"}
                continue
            it.setdefault("discovered_at", time.strftime("%Y-%m-%d %H:%M:%S"))
            it.setdefault("discovered_ts", int(time.time()))
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
            idx[bvid] = {"ts": it["discovered_ts"], "source": it.get("source"),
                         "title": it.get("title")}
            added_items.append(it)
            added += 1
    if added:
        save_json(INBOX_INDEX, idx)
    return added, added_items


def read_inbox(date=None):
    ensure_dirs()
    out = []
    if not INBOX.exists():
        return out
    for line in INBOX.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            it = json.loads(line)
        except Exception:
            continue
        if date and not (it.get("discovered_at") or "").startswith(date):
            continue
        out.append(it)
    return out


# ---------------- 处理状态 / 内联采集 ----------------
PROC_FILE = STATE / "processed.json"


def load_proc():
    return load_json(PROC_FILE, {})


def save_proc(proc):
    save_json(PROC_FILE, proc)


def inline_collect(client, item, subs=True):
    """跟踪阶段内联采集：元数据 + 中文逐字稿（不采评论）。

    返回 {"status": "done"|"exists"|"error", "sub": n, "dir": name}。
    失败会写入 processed（status=error，收件箱会重试），不会中断发现流程。
    """
    from bili_collect import collect_meta, collect_subs
    bvid = item["bvid"]
    title = item.get("title") or bvid
    vdir = VIDEOS / f"{bvid}_{safe_name(title, 40)}"
    proc = load_proc()
    rec = proc.get(bvid) or {}
    try:
        if (vdir / "meta.json").exists():
            rec.update({"status": "done", "dir": vdir.name})
            proc[bvid] = rec
            save_proc(proc)
            return {"status": "exists", "sub": int(rec.get("sub") or 0), "dir": vdir.name}
        meta = collect_meta(client.b, {"bvid": bvid})
        vdir.mkdir(parents=True, exist_ok=True)
        meta.update({"source": item.get("source"), "kw": item.get("kw"),
                     "tier": item.get("tier"), "prefix": item.get("prefix"),
                     "discovered_at": item.get("discovered_at")})
        meta["heat"] = round((meta.get("like") or 0) * 1.0
                             + (meta.get("favorite") or 0) * 1.5
                             + (meta.get("coin") or 0) * 2.0, 1)
        (vdir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        nsub = 0
        if subs:
            try:
                files, _ = collect_subs(client.b, meta["aid"], meta["cid"], vdir,
                                        "subtitle", ["zh"])
                nsub = len(files)
            except Stop:
                raise
            except Exception as e:
                log(f"  ! inline subs {bvid}: {str(e)[:60]}", "inline")
        rec.update({"status": "done", "dir": vdir.name, "ts": int(time.time()),
                    "sub": nsub, "cm": 0, "source": "inline",
                    "pubdate": meta.get("pubdate"), "sub_retries": 0})
        proc[bvid] = rec
        save_proc(proc)
        return {"status": "done", "sub": nsub, "dir": vdir.name}
    except Stop:
        raise
    except Exception as e:
        rec.update({"status": "error", "ts": int(time.time()),
                    "err": f"{type(e).__name__}: {e}"[:160],
                    "tries": int(rec.get("tries") or 0) + 1})
        proc[bvid] = rec
        save_proc(proc)
        return {"status": "error", "sub": 0, "dir": ""}


# ---------------- 文本处理 ----------------
INSTITUTION = ("官方", "日报", "新闻", "电视", "央视", "新华", "人民", "共青团",
               "大学", "学院", "研究院", "集团", "公司", "频道", "传媒", "媒体")


def looks_institutional(name, extra=()):
    n = name or ""
    return any(k in n for k in INSTITUTION) or any(k in n for k in extra)


def safe_name(s, n=40):
    from bili_subs import safe_name as _sn
    return _sn(s, n)


def fmt_play(x):
    try:
        x = int(x)
    except (TypeError, ValueError):
        return "?"
    if x >= 10000:
        return f"{x/10000:.1f}万"
    return str(x)


