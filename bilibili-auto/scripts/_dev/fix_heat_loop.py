# -*- coding: utf-8 -*-
"""修复 B站深度采集的「listed 阶段死循环」：
  1) heat() 复用已存在的 meta.json，不重复 view 请求
  2) 失败的 bvid 记入 heat_failed，下轮跳过
  3) 每 50 条保存一次进度
  4) pool 上限（默认 120），避免超大账号无限打分
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "bili_deep_collect.py"
t = f.read_text(encoding="utf-8")

# ---- 1) 替换 heat() ----
old = '''    def heat(self, pool, acct_dir):
        """对候选池查详情打分，顺手把 meta.json 落盘（避免采集阶段再查一次）。"""
        scored = []
        for v in pool:
            try:
                m = collect_meta(self.b, v)'''
new = '''    def heat(self, pool, acct_dir, acct=None):
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
                s = (existing.get("like") or 0) * 1.0 + \\
                    (existing.get("favorite") or 0) * 1.5 + \\
                    (existing.get("coin") or 0) * 2.0
                scored.append({"bvid": bvid, "heat": round(s, 1),
                               "play": existing.get("view") or 0,
                               "dir": f'{bvid}_{safe_name(existing.get("title", ""), 40)}'})
                reuse += 1
                continue
            try:
                m = collect_meta(self.b, v)'''
assert old in t, "heat 开头未匹配"
t = t.replace(old, new, 1)

# ---- 2) 失败记录 + 定期存盘 ----
old2 = '''            except Exception as e:
                print(f"    ! view {v.get('bvid')}: {str(e)[:45]}", file=sys.stderr)
            self._sleep(self.base_pace)
        scored.sort(key=lambda x: -x["heat"])
        return scored[:self.a.top_n]'''
new2 = '''            except Throttled:
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
        return scored[:self.a.top_n]'''
assert old2 in t, "heat 结尾未匹配"
t = t.replace(old2, new2, 1)

# ---- 3) 调用处传 acct ----
t = t.replace('scored = self.heat(pool, acct_dir)',
              'scored = self.heat(pool, acct_dir, acct)', 1)

# ---- 4) pool 上限 ----
old4 = '''                    pool = self.select(videos)
                    acct["pool"] = [v["bvid"] for v in pool]'''
new4 = '''                    pool = self.select(videos)
                    cap = getattr(self.a, "pool_cap", 120) or 120
                    if len(pool) > cap:
                        print(f"    候选池 {len(pool)} 条超过上限 {cap}，按发布倒序截断",
                              file=sys.stderr)
                        pool = pool[:cap]
                    acct["pool"] = [v["bvid"] for v in pool]'''
assert old4 in t, "pool 赋值未匹配"
t = t.replace(old4, new4, 1)

# ---- 5) 新增 --pool-cap 参数 ----
t = t.replace('    ap.add_argument("--top-n", type=int, default=20, dest="top_n")',
              '    ap.add_argument("--top-n", type=int, default=20, dest="top_n")\n'
              '    ap.add_argument("--pool-cap", type=int, default=120, dest="pool_cap")', 1)

f.write_text(t, encoding="utf-8")
print("已修复：meta 复用 + 失败跳过 + 定期存盘 + pool 上限")
