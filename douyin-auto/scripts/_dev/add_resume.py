# -*- coding: utf-8 -*-
"""给 douyin_collect.py 增加「接力采集」模式：从上批最后一条继续往更早的方向采。

新增参数：
  --mode batch|next   batch=置顶+播放Top10+最新5（默认）；next=接着上次往更早采
  --count N           next 模式下本批采多少个（默认 15）
  --scroll N          主页滚动轮数（默认 3；深历史用 8-15）

游标：_account.json 记录
  works_order : 每次抓到的完整作品顺序（发布时间倒序）
  collected   : 已采 aweme_id
  cursor_last : 上次采到的最早一条 aweme_id
"""
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "douyin_collect.py"
t = f.read_text(encoding="utf-8")

# ---------- 1) list_works 支持滚动轮数 ----------
old = '''def list_works(page):
    """主页作品卡片：aweme_id / 是否置顶 / 卡片文本（含播放量）。"""
    try:
        page.wait_for_selector('a[href*="/video/"]', timeout=25000)
    except Exception:
        pass
    for _ in range(3):
        page.mouse.wheel(0, random.randint(700, 1100))
        pause(1.2, 2.2)'''
new = '''def list_works(page, rounds=3):
    """主页作品卡片：aweme_id / 是否置顶 / 卡片文本（含播放量）。

    rounds 控制滚动轮数：滚得越多，能加载到越早的历史作品。
    """
    try:
        page.wait_for_selector('a[href*="/video/"]', timeout=25000)
    except Exception:
        pass
    for _ in range(max(1, rounds)):
        page.mouse.wheel(0, random.randint(700, 1100))
        pause(1.2, 2.2)'''
assert old in t
t = t.replace(old, new, 1)

# ---------- 2) 新增命令行参数 ----------
old2 = '''    ap.add_argument("--headless", action="store_true")'''
new2 = '''    ap.add_argument("--mode", default="batch", choices=["batch", "next"],
                    help="batch=置顶+播放Top10+最新5；next=接着上次往更早采")
    ap.add_argument("--count", type=int, default=15, help="next 模式本批条数")
    ap.add_argument("--scroll", type=int, default=3,
                    help="主页滚动轮数（深历史建议 8-15）")
    ap.add_argument("--headless", action="store_true")'''
assert old2 in t
t = t.replace(old2, new2, 1)

# ---------- 3) 列表调用传入 scroll ----------
t = t.replace("        works = list_works(page)",
              "        works = list_works(page, rounds=a.scroll)", 1)

# ---------- 4) 选片逻辑：batch / next ----------
old3 = '''        for w in works:
            nums = re.findall(r"([\\d\\.]+\\s*[万亿]?)",
                              (w.get("card_text", "") + " " + w.get("inner", "")))
            w["play"] = max([play_num(x) for x in nums], default=0)
        pinned = [w for w in works if w.get("pinned")]
        rest = sorted([w for w in works if not w.get("pinned")], key=lambda x: -x["play"])
        chosen = (pinned + rest)[:max(a.top_play, len(pinned))]
        ids = {w["aweme_id"] for w in chosen}
        for w in works[:a.latest]:
            if w["aweme_id"] not in ids:
                chosen.append(w)
                ids.add(w["aweme_id"])
        print(f"   选片 {len(chosen)} 个（置顶 {len(pinned)} + 播放Top + 最新）")'''
new3 = '''        for w in works:
            nums = re.findall(r"([\\d\\.]+\\s*[万亿]?)",
                              (w.get("card_text", "") + " " + w.get("inner", "")))
            w["play"] = max([play_num(x) for x in nums], default=0)

        works_order = [w["aweme_id"] for w in works]

        # 读上次的游标
        ap_path = acct_dir / "_account.json"
        prev = {}
        if ap_path.exists():
            try:
                prev = json.loads(ap_path.read_text(encoding="utf-8"))
            except Exception:
                prev = {}
        prev_collected = [x for x in (prev.get("collected") or [])]

        if a.mode == "next":
            # 找到「最后一条已采作品」在时间轴上的位置，从它之后往更早的方向取
            pos = [i for i, aid in enumerate(works_order) if aid in prev_collected]
            start = (max(pos) + 1) if pos else 0
            chosen = [w for w in works[start:]
                      if w["aweme_id"] not in prev_collected][:a.count]
            if not pos:
                print(f"   ⚠ 未找到上次采集记录，从最新开始取 {len(chosen)} 个")
            elif not chosen:
                print(f"   ✓ 已到最早（当前能加载到 {len(works)} 个作品，"
                      f"更早的需要调大 --scroll）")
                (acct_dir / "_account.json").write_text(json.dumps({
                    **prev, "works_order": works_order, "works_seen": len(works),
                    "mode": "next", "ts": time.time(),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M")},
                    ensure_ascii=False, indent=1), encoding="utf-8")
                ctx.close()
                return 0
            print(f"   接力采集 {len(chosen)} 个（从已采 {len(prev_collected)} 个之后往更早）")
        else:
            pinned = [w for w in works if w.get("pinned")]
            rest = sorted([w for w in works if not w.get("pinned")],
                          key=lambda x: -x["play"])
            chosen = (pinned + rest)[:max(a.top_play, len(pinned))]
            ids = {w["aweme_id"] for w in chosen}
            for w in works[:a.latest]:
                if w["aweme_id"] not in ids:
                    chosen.append(w)
                    ids.add(w["aweme_id"])
            print(f"   选片 {len(chosen)} 个（置顶 {len(pinned)} + 播放Top + 最新）")'''
assert old3 in t
t = t.replace(old3, new3, 1)

# ---------- 5) 结束时累积 collected + 记录游标 ----------
old4 = '''        # 优先用 detail 接口的 author_fans（页面文本解析常不准）
        fans_final = fans'''
new4 = '''        # 累积已采列表（跨批次保留），并记录游标
        all_collected = list(dict.fromkeys(prev_collected + results))
        cursor_last = None
        for aid in works_order:
            if aid in all_collected:
                cursor_last = aid
        # 优先用 detail 接口的 author_fans（页面文本解析常不准）
        fans_final = fans'''
assert old4 in t
t = t.replace(old4, new4, 1)

t = t.replace('"works_found": len(works), "collected": results,',
              '"works_found": len(works), "collected": all_collected,\n'
              '            "works_order": works_order, "works_seen": len(works),\n'
              '            "cursor_last": cursor_last, "mode": a.mode,', 1)

f.write_text(t, encoding="utf-8")
print("已加入接力采集模式（--mode next / --count / --scroll）")
