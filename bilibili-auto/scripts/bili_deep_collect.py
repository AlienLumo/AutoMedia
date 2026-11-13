#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_deep_collect.py — 全名单深度采集（安全优先 / 断点续传 / 可无人值守）

选片规则（方案 B）
  候选池 = 近 90 天全部视频 ∪ 历史播放量 Top10
  对候选池逐个查详情 → 热度分 = 点赞*1.0 + 收藏*1.5 + 投币*2.0
  按热度取前 20，不足 20 全取
采集内容
  元数据 + 全语言字幕 + 高赞评论前 100 条
落盘
  1AMdata/bilibili/<前缀>_<UP名>_<粉丝量>/<bvid>_<标题>/

安全机制（这是本脚本的核心）
  1. 单并发、基础间隔 2.0s + 抖动 0.75~1.35 倍
  2. 每 300 次请求强制休息 45~90s
  3. 连续撞 -352/412：120s → 300s → 600s 退避；三轮仍失败则优雅退出
  4. 每轮最多 N 次请求（默认 1800）后主动退出，由计划任务下次续跑
  5. 断点续传：state 文件记录每号阶段与已完成视频，中断零损失
  6. 只读操作，不做任何点赞/投币/收藏/评论等写行为
"""
import argparse
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import (Bili, Throttled, Budget, NotLoggedIn, read_cred,   # noqa: E402
                       safe_name, to_srt, DM_PARAMS)
from bili_collect import collect_meta, collect_comments, collect_subs   # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"
DATA = PROJ / "1AMdata" / "bilibili"
STATE_DIR = PROJ / "1AMdata" / "_state"
STATE_FILE = STATE_DIR / "deep_collect.json"
LOG_DIR = SKILL / "logs"


def fmt_fans(n):
    return f"{n/10000:.1f}万" if n and n >= 10000 else str(n or 0)


def load_roster():
    rows = []
    for line in (CONF / "ups.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c = line.split("\t")
        try:
            rows.append((int(c[0]), c[1] if len(c) > 1 else "", ""))
        except ValueError:
            pass
    return rows


def load_pmap():
    m = {}
    for line in (CONF / "prefix_map.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c = line.split("\t")
        if len(c) < 4:
            continue
        try:
            m[int(c[0])] = {"name": c[1], "prefix": c[2], "fans": int(c[3] or 0)}
        except ValueError:
            pass
    return m


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"accounts": {}}


def save_state(st):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE_FILE)


class StopRun(Exception):
    pass


class Collector:
    def __init__(self, a):
        self.a = a
        self.max_req = a.max_requests
        self.req = 0
        self.rest_every = a.rest_every
        self.base_pace = a.pace
        self.consecutive_throttle = 0
        self.b = Bili(pace=a.pace, cooldown=a.cooldown, cookies=read_cred())
        self.b.preflight()
        self.st = load_state()
        self.quiet = a.quiet
        self.sub_langs = [x.strip() for x in (a.sub_langs or "").split(",") if x.strip()]
        self._patch_get()

    # ---------- 安全层 ----------
    def _in_quiet_hours(self):
        if not self.quiet:
            return False
        h = time.localtime().tm_hour
        return h >= 23 or h < 8

    def _sleep(self, s):
        t = s * random.uniform(0.75, 1.35)
        time.sleep(t)

    def _patch_get(self):
        orig = self.b.get

        def wrapped(path, params=None, tries=2):
            if self._in_quiet_hours():
                raise StopRun("quiet_hours 23:00-08:00")
            if self.req >= self.max_req:
                raise StopRun(f"本轮已达请求上限 {self.max_req}")
            if self.req and self.req % self.rest_every == 0:
                rest = random.uniform(45, 90)
                print(f"  [rest] 已发 {self.req} 请求，休息 {rest:.0f}s",
                      file=sys.stderr, flush=True)
                time.sleep(rest)
            self.req += 1
            try:
                r = orig(path, params, tries=tries)
                self.consecutive_throttle = 0
                return r
            except Throttled:
                self.consecutive_throttle += 1
                if self.consecutive_throttle >= 3:
                    raise StopRun(f"连续 {self.consecutive_throttle} 次限流，主动停机")
                back = {1: 120, 2: 300}.get(self.consecutive_throttle, 600)
                print(f"  [throttled x{self.consecutive_throttle}] 退避 {back}s",
                      file=sys.stderr, flush=True)
                time.sleep(back)
                raise Throttled("backoff then retry next run")

        self.b.get = wrapped

    # ---------- 主流程 ----------
    def list_all(self, mid):
        """拉该号全部投稿（分页，含播放量）。"""
        out, pn = [], 1
        while pn <= self.a.max_pages:
            r = self.b.get("x/space/wbi/arc/search",
                           {"mid": mid, "ps": 30, "pn": pn, "order": "pubdate",
                            "platform": "web", "web_location": 1550101,
                            **DM_PARAMS}, tries=2)
            vl = ((r.get("data") or {}).get("list") or {}).get("vlist") or []
            if not vl:
                break
            for v in vl:
                def _i(x):
                    try:
                        return int(x)
                    except (TypeError, ValueError):
                        return 0
                out.append({"bvid": v["bvid"], "title": v["title"],
                            "play": _i(v.get("play")),
                            "created": _i(v.get("created"))})
            pn += 1
            self._sleep(self.base_pace)
        return out

    def select(self, videos):
        cutoff = time.time() - 90 * 86400
        recent = [v for v in videos if v["created"] >= cutoff]
        top_hist = sorted(videos, key=lambda x: -x["play"])[:10]
        pool, seen = [], set()
        for v in recent + top_hist:
            if v["bvid"] in seen:
                continue
            seen.add(v["bvid"])
            pool.append(v)
        return pool

    def heat(self, pool, acct_dir, acct=None):
        """对候选池查详情打分；已存在的 meta.json 直接复用（断点续跑的关键）。

        之前每轮都从头打分，遇到几百条候选池的大账号会永远跑不完（死循环）。
        """
        scored = []
        reuse = 0
        failed = set((acct or {}).get("heat_failed") or [])
        for idx, v in enumerate(pool):
            bvid = v.get("bvid")
            if bvid in failed:
                continue
            # 复用已落盘的 meta.json
            existing = None
            try:
                for p in acct_dir.glob(f"{bvid}_*"):
                    if (p / "meta.json").exists():
                        import json as _json
                        existing = _json.loads((p / "meta.json").read_text(encoding="utf-8"))
                        break
            except Exception:
                existing = None
            if existing:
                s = (existing.get("like") or 0) * 1.0 + \
                    (existing.get("favorite") or 0) * 1.5 + \
                    (existing.get("coin") or 0) * 2.0
                scored.append({"bvid": bvid, "heat": round(s, 1),
                               "play": existing.get("view") or 0,
                               "dir": f'{bvid}_{safe_name(existing.get("title", ""), 40)}'})
                reuse += 1
                continue
            try:
                m = collect_meta(self.b, v)
                s = (m.get("like") or 0) * 1.0 + (m.get("favorite") or 0) * 1.5 \
                    + (m.get("coin") or 0) * 2.0
                vdir = acct_dir / f'{m["bvid"]}_{safe_name(m["title"], 40)}'
                vdir.mkdir(parents=True, exist_ok=True)
                m["heat"] = round(s, 1)
                (vdir / "meta.json").write_text(
                    json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
                scored.append({"bvid": m["bvid"], "heat": round(s, 1),
                               "play": m.get("view") or 0,
                               "dir": vdir.name})
            except (Throttled, StopRun):
                raise
            except Throttled:
                raise
            except Exception as e:
                print(f"    ! view {bvid}: {str(e)[:45]}", file=sys.stderr)
                if acct is not None:
                    failed.add(bvid)
                    acct["heat_failed"] = sorted(failed)[-800:]
            if (idx + 1) % 50 == 0:
                if acct is not None:
                    save_state(self.st)
                print(f"    打分进度 {idx+1}/{len(pool)}（复用 {reuse}）",
                      file=sys.stderr, flush=True)
            self._sleep(self.base_pace)
        scored.sort(key=lambda x: -x["heat"])
        print(f"    打分完成：复用 {reuse}，失败 {len(failed)}，有效 {len(scored)}",
              file=sys.stderr, flush=True)
        return scored[:self.a.top_n]

    def collect_one(self, vdir, langs=None):
        m = json.loads((vdir / "meta.json").read_text(encoding="utf-8"))
        n_cm = 0
        if self.a.with_comments and not (vdir / "comments.jsonl").exists():
            try:
                cms = collect_comments(self.b, m["aid"], self.a.comment_cap, 0)
                with (vdir / "comments.jsonl").open("w", encoding="utf-8") as f:
                    for c in cms:
                        f.write(json.dumps(c, ensure_ascii=False) + "\n")
                n_cm = len(cms)
            except (Throttled, StopRun):
                raise
            except Exception as e:
                print(f"    ! comments {m['bvid']}: {str(e)[:40]}", file=sys.stderr)
        n_sub = 0
        if self.a.with_subs:
            try:
                files, n = collect_subs(self.b, m["aid"], m["cid"], vdir, "subtitle",
                                          langs)
                n_sub = len(files)
            except (Throttled, StopRun):
                raise
            except Exception as e:
                print(f"    ! subs {m['bvid']}: {str(e)[:40]}", file=sys.stderr)
        return n_cm, n_sub

    def done_video(self, acct_dir, bvid):
        for p in acct_dir.glob(f"{bvid}_*"):
            if (p / "meta.json").exists():
                if not self.a.with_comments or (p / "comments.jsonl").exists():
                    return True
        return False

    def run(self):
        pmap = load_pmap()
        roster = load_roster()
        started = time.time()
        done_ups = 0
        self.current_mid = None
        try:
            for idx, (mid, name, _) in enumerate(roster):
                info = pmap.get(mid) or {}
                uname = info.get("name") or name or str(mid)
                pref = info.get("prefix") or "ai"
                fans = info.get("fans") or 0
                self.current_mid = mid
                acct = self.st["accounts"].setdefault(
                    str(mid), {"name": uname, "stage": "new", "done": [],
                               "total_cm": 0, "total_sub": 0})
                if acct.get("stage") == "finished":
                    continue
                if acct.get("stage") == "error" and acct.get("retries", 0) >= 3:
                    continue
                acct_dir = DATA / f"{pref}_{safe_name(uname, 30)}_{fmt_fans(fans)}"
                print(f'\n[{idx+1}/{len(roster)}] {uname} ({mid}) '
                      f'stage={acct.get("stage")} req={self.req}', file=sys.stderr,
                      flush=True)
                if acct.get("stage") == "new":
                    videos = self.list_all(mid)
                    if not videos:
                        acct["stage"] = "empty"
                        save_state(self.st)
                        continue
                    pool = self.select(videos)
                    cap = getattr(self.a, "pool_cap", 120) or 120
                    if len(pool) > cap:
                        print(f"    候选池 {len(pool)} 条超过上限 {cap}，按发布倒序截断",
                              file=sys.stderr)
                        pool = pool[:cap]
                    acct["pool"] = [v["bvid"] for v in pool]
                    acct["stage"] = "listed"
                    save_state(self.st)
                    print(f'  近90天 {sum(1 for v in videos if v["created"] >= time.time()-90*86400)} 条，'
                          f'历史Top10 已并入，候选池 {len(pool)} 条', file=sys.stderr)

                if acct.get("stage") == "listed":
                    acct_dir.mkdir(parents=True, exist_ok=True)
                    pool = [{"bvid": bv} for bv in (acct.get("pool") or [])]
                    scored = self.heat(pool, acct_dir, acct)
                    acct["selected"] = [x["bvid"] for x in scored]
                    acct["scores"] = {x["bvid"]: x["heat"] for x in scored}
                    acct["dir"] = acct_dir.name
                    # 候选池里未入选的视频移到 _pool/，主目录只留最终 20 条
                    sel = {x["dir"] for x in scored}
                    pdir = acct_dir / "_pool"
                    for d in list(acct_dir.iterdir()):
                        if (d.is_dir() and d.name.startswith("BV")
                                and d.name not in sel):
                            pdir.mkdir(exist_ok=True)
                            try:
                                d.rename(pdir / d.name)
                            except OSError:
                                pass
                    acct["stage"] = "scored"
                    save_state(self.st)
                    print(f'  选片完成 {len(scored)} 条（按热度排序）', file=sys.stderr)

                if acct.get("stage") == "scored":
                    acct["stage"] = "collecting"
                    save_state(self.st)

                if acct.get("stage") == "collecting":
                    acct_dir.mkdir(parents=True, exist_ok=True)
                    for x in (acct.get("selected") or []):
                        bv = x if isinstance(x, str) else x.get("bvid")
                        if bv in acct["done"]:
                            continue
                        vdir = None
                        for p in acct_dir.glob(f"{bv}_*"):
                            vdir = p
                            break
                        if vdir is None or not (vdir / "meta.json").exists():
                            # meta 缺失（上次中断），补一次
                            v = self.b.get("x/web-interface/view",
                                           {"bvid": bv})["data"]
                            st_ = v.get("stat") or {}
                            acct_dir.mkdir(parents=True, exist_ok=True)
                            vdir = acct_dir / f'{bv}_{safe_name(v["title"], 40)}'
                            vdir.mkdir(parents=True, exist_ok=True)
                            (vdir / "meta.json").write_text(json.dumps(
                                {"bvid": v["bvid"], "aid": v["aid"], "cid": v["cid"],
                                 "title": v["title"], "desc": v.get("desc") or "",
                                 "duration": v.get("duration"),
                                 "pubdate": v.get("pubdate"),
                                 "pubdate_str": time.strftime(
                                     "%Y-%m-%d %H:%M",
                                     time.localtime(v.get("pubdate") or 0)),
                                 "owner": (v.get("owner") or {}).get("name"),
                                 "view": st_.get("view"), "like": st_.get("like"),
                                 "coin": st_.get("coin"),
                                 "favorite": st_.get("favorite"),
                                 "share": st_.get("share"),
                                 "danmaku": st_.get("danmaku"),
                                 "reply": st_.get("reply"),
                                 "heat": (acct.get("scores") or {}).get(bv)},
                                ensure_ascii=False, indent=1), encoding="utf-8")
                        n_cm, n_sub = self.collect_one(vdir, self.sub_langs)
                        acct["done"].append(bv)
                        acct["total_cm"] = acct.get("total_cm", 0) + n_cm
                        acct["total_sub"] = acct.get("total_sub", 0) + n_sub
                        save_state(self.st)
                        self._sleep(self.base_pace)
                    acct["stage"] = "finished"
                    done_ups += 1
                    save_state(self.st)
                    print(f'  完成 {uname}: {len(acct["done"])} 个视频, '
                          f'{acct["total_cm"]} 评论', file=sys.stderr, flush=True)
        except StopRun as e:
            print(f"\n[STOP-RUN] {e}（已保存进度，下次续跑）", file=sys.stderr)
        except (Throttled, Budget) as e:
            print(f"\n[STOP] {e}", file=sys.stderr)
        except NotLoggedIn as e:
            print(f"\n[NO-LOGIN] {e}", file=sys.stderr)
        except Exception as e:
            mid = getattr(self, "current_mid", None)
            if mid is not None:
                acc = self.st["accounts"].setdefault(str(mid), {})
                acc["retries"] = acc.get("retries", 0) + 1
                acc["last_error"] = f"{type(e).__name__}: {e}"[:200]
                acc["stage"] = "error"
                # 重置该号的中间状态，下一轮重新从列表开始
                acc.pop("pool", None)
                acc.pop("selected", None)
                print(f"\n[ACCOUNT-ERROR] mid={mid} 第 {acc['retries']} 次失败: "
                      f"{type(e).__name__}: {str(e)[:120]}（已跳过，下轮重试）",
                      file=sys.stderr)
                import traceback as _tb
                _tb.print_exc()
            save_state(self.st)
        finally:
            save_state(self.st)
            if self.b.logged_in:
                self.b.persist_cred()
            accs = self.st.get("accounts", {})
            fin = sum(1 for v in accs.values() if v.get("stage") == "finished")
            print(f"\n[stats] 本轮请求 {self.req}，耗时 {time.time()-started:.0f}s，"
                  f"账号完成 {fin}/{len(roster)}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pace", type=float, default=2.0)
    ap.add_argument("--cooldown", type=int, default=120)
    ap.add_argument("--max-requests", type=int, default=1800, dest="max_requests",
                    help="本轮请求上限，达到即退出（由计划任务续跑）")
    ap.add_argument("--rest-every", type=int, default=300, dest="rest_every")
    ap.add_argument("--max-pages", type=int, default=40, dest="max_pages")
    ap.add_argument("--top-n", type=int, default=20, dest="top_n")
    ap.add_argument("--pool-cap", type=int, default=120, dest="pool_cap")
    ap.add_argument("--comment-cap", type=int, default=100, dest="comment_cap")
    ap.add_argument("--with-comments", action="store_true", default=True,
                    dest="with_comments")
    ap.add_argument("--no-comments", action="store_false", dest="with_comments")
    ap.add_argument("--sub-langs", default="", dest="sub_langs",
                    help="只下载指定语言的字幕，逗号分隔，如 zh 或 zh,en；空=全部")
    ap.add_argument("--with-subs", action="store_true", default=True,
                    dest="with_subs")
    ap.add_argument("--no-subs", action="store_false", dest="with_subs")
    ap.add_argument("--quiet", action="store_true",
                    help="23:00-08:00 不发请求")
    ap.add_argument("--max-accounts", type=int, default=0, dest="max_accounts",
                    help="只处理前 N 个账号（测试用）")
    ap.add_argument("--reset", type=int, dest="reset",
                    help="重置某个 mid 的进度")
    a = ap.parse_args()

    if a.reset:
        st = load_state()
        st["accounts"].pop(str(a.reset), None)
        save_state(st)
        print(f"已重置 {a.reset}")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lock = LOG_DIR / ".deepcollect.lock"

    def _pid_alive(pid):
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, 0, pid)
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        except Exception:
            return True   # 判断不了就当活着，保守

    if lock.exists():
        try:
            old_pid = int(lock.read_text(encoding="utf-8").strip() or 0)
            if old_pid and _pid_alive(old_pid):
                print(f"[skip] 实例 {old_pid} 仍在运行，退出")
                return
            print(f"[lock] 清理失效锁（pid={old_pid} 已不存在）")
        except Exception:
            pass
    lock.write_text(str(os.getpid()), encoding="utf-8")
    try:
        Collector(a).run()
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
