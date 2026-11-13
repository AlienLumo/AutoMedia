# -*- coding: utf-8 -*-
"""build_talk_queue.py — 生成「口播/字幕密集型」主题的采集队列。

目标主题：名人访谈 / 前沿资讯 / 科技前沿 / 创业
筛选：≥10万粉、排除已采完的、按粉丝降序，拆两份供双账号并行。
"""
import argparse
import json
import re
from pathlib import Path
from _paths import DATA as _DATA, SKILL

CFG = SKILL / "config"
DATA = _DATA / "douyin"

ap = argparse.ArgumentParser()
ap.add_argument("--themes", default="名人访谈,前沿资讯,科技前沿,创业")
ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
ap.add_argument("--per-theme", type=int, default=0, help="每主题最多取多少个（0=不限）")
ap.add_argument("--split", type=int, default=2)
ap.add_argument("--skip-done", type=int, default=25, dest="skip_done",
                help="已有 >=N 个作品视为已采完，跳过")
a = ap.parse_args()

WANT = [t.strip() for t in a.themes.split(",") if t.strip()]

st = json.loads((CFG / "video_search_state.json").read_text(encoding="utf-8"))
authors = st.get("authors") or []

# 已采完的 sec_uid
collected = {}
for d in DATA.iterdir() if DATA.exists() else []:
    if not d.is_dir():
        continue
    ap_f = d / "_account.json"
    if not ap_f.exists():
        continue
    try:
        acc = json.loads(ap_f.read_text(encoding="utf-8"))
    except Exception:
        continue
    m = re.search(r"/user/([A-Za-z0-9_\-]{20,})", acc.get("url") or "")
    if m:
        n = len([x for x in d.iterdir() if x.is_dir()])
        collected[m.group(1)] = (acc.get("nickname") or d.name, n)

# ===== 机构号排除（只要个人自媒体，与 B站 口径一致）=====
HARD_INST = [
    # 官方媒体
    "央视", "中央电视", "CCTV", "CNTV", "人民日报", "人民网", "新华社", "新华网",
    "共青团", "观察者网", "环球时报", "澎湃", "界面新闻", "财新", "第一财经",
    "中国网", "中国日报", "光明网", "经济日报", "参考消息", "环球网",
    "新闻网", "新闻", "报道", "日报", "晚报", "晨报", "周刊",
    "卫视", "广电", "广播电台", "电视台", "融媒体", "传媒",
    # 政府/机构
    "政府", "国务院", "外交部", "国防部", "卫健委", "教育部", "央行", "证监会",
    "全国妇联", "科协", "红十字会", "研究院", "研究所", "实验室",
    "清华", "北大", "大学", "学院", "中学", "小学",
    # 品牌/公司（抖音官方号）
    "华为", "小米", "苹果", "腾讯", "阿里", "百度", "字节", "京东", "美团",
    "特斯拉", "比亚迪", "蔚来", "理想汽车", "小鹏", "荣耀", "OPPO", "vivo",
    "三星", "英特尔", "英伟达", "联想", "戴尔", "微软", "谷歌", "Meta",
    "爱奇艺", "优酷", "芒果", "哔哩哔哩", "快手", "微博",
    "中国移动", "中国电信", "中国联通", "国家电网", "中石油", "中石化",
]
SOFT_INST = ["集团", "公司", "商城", "官方", "频道", "文化传播",
             "协会", "基金会", "科技有限", "出版社", "杂志", "报社",
             "影业", "娱乐", "文化", "工作室", "团队"]
PERSONAL_HINT = ["老师", "哥", "姐", "叔", "阿姨", "同学",
                 "先生", "博士", "教授", "UP主", "君", "叔", "爷", "妈", "爸"]


def is_personal(name):
    """判定是否个人自媒体。"""
    n = name or ""
    if any(w in n for w in HARD_INST):
        return False
    if any(w in n for w in SOFT_INST):
        return any(w in n for w in PERSONAL_HINT)
    return True


# 按主题分组
by_theme = {t: [] for t in WANT}
seen = set()
for x in authors:
    themes = x.get("themes") or []
    hit = [t for t in WANT if t in themes]
    if not hit:
        continue
    if (x.get("fans") or 0) < a.min_fans:
        continue
    uid = x.get("sec_uid")
    if not uid or uid in seen:
        continue
    if not is_personal(x.get("nickname")):
        continue
    seen.add(uid)
    rec = {"sec_uid": uid, "name": x.get("nickname"), "fans": x.get("fans") or 0,
           "themes": hit, "hits": x.get("videos_hit") or 0}
    for t in hit:
        by_theme[t].append(rec)

for t in WANT:
    by_theme[t].sort(key=lambda r: -r["fans"])

# 合并（去重，按粉丝降序），可选每主题限流
chosen, chosen_ids = [], set()
for t in WANT:
    lst = by_theme[t]
    if a.per_theme > 0:
        lst = lst[:a.per_theme]
    for r in lst:
        if r["sec_uid"] in chosen_ids:
            continue
        chosen_ids.add(r["sec_uid"])
        chosen.append(r)

# 排除已采完的
before = len(chosen)
chosen = [r for r in chosen
          if collected.get(r["sec_uid"], ("", 0))[1] < a.skip_done]
chosen.sort(key=lambda r: -r["fans"])

print(f"主题: {', '.join(WANT)}")
print(f"各主题 ≥{a.min_fans}粉 人数: " +
      " / ".join(f"{t} {len(by_theme[t])}" for t in WANT))
print(f"合并去重 {before} → 排除已采完后 {len(chosen)}")

# 输出被排除的机构号供复核
inst_out = CFG / "excluded_institutions_douyin.tsv"
with inst_out.open("w", encoding="utf-8", newline="") as fh:
    fh.write("昵称\t粉丝\t主题\n")
    for x in authors:
        th = [t2 for t2 in WANT if t2 in (x.get("themes") or [])]
        if not th or (x.get("fans") or 0) < a.min_fans:
            continue
        if not is_personal(x.get("nickname")):
            fh.write(f'{x.get("nickname")}\t{x.get("fans")}\t{",".join(th)}\n')
print(f"排除的机构号清单: {inst_out}")
print(f"其中已在采过的账号: {sum(1 for r in chosen if r['sec_uid'] in collected)}")

# 拆两份（交替分配，保证两边都从高粉开始）
if a.split > 1:
    for p in range(a.split):
        sub = [r for i, r in enumerate(chosen) if i % a.split == p]
        f = CFG / f"queue_talk_p{p+1}.txt"
        f.write_text("\n".join(f'https://www.douyin.com/user/{r["sec_uid"]}'
                               for r in sub) + "\n", encoding="utf-8")
        print(f"SPLIT={f}  count={len(sub)}")
else:
    f = CFG / "queue_talk.txt"
    f.write_text("\n".join(f'https://www.douyin.com/user/{r["sec_uid"]}'
                           for r in chosen) + "\n", encoding="utf-8")
    print(f"QUEUE={f}  count={len(chosen)}")

tsv = CFG / "queue_talk.tsv"
with tsv.open("w", encoding="utf-8", newline="") as fh:
    fh.write("序号\t昵称\t粉丝\t主题\t命中视频\t已采作品\n")
    for i, r in enumerate(chosen, 1):
        n = collected.get(r["sec_uid"], ("", 0))[1]
        fh.write(f'{i}\t{r["name"]}\t{r["fans"]}\t{",".join(r["themes"])}\t'
                 f'{r["hits"]}\t{n}\n')
print(f"TSV={tsv}")
print("\n前 25 个（按粉丝降序）：")
for i, r in enumerate(chosen[:25], 1):
    n = collected.get(r["sec_uid"], ("", 0))[1]
    tag = f" [已采{n}]" if n else ""
    print(f'  {i:>2}. {r["fans"]/1e4:>7.1f}万  [{",".join(r["themes"])[:14]}]  '
          f'{r["name"]}{tag}')

# 预估
per = 30
minutes = len(chosen) * per * 1.95
print(f"\n预估：{len(chosen)} 个 × {per} 视频 × 1.95 分 ÷ 2 账号 "
      f"= {minutes/2/60:.1f} 小时")
