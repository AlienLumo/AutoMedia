# -*- coding: utf-8 -*-
"""修正 douyin_collect.py 的账号目录命名与复用匹配。"""
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import DATA, SKILL

f = SKILL / "scripts" / "douyin_collect.py"
t = f.read_text(encoding="utf-8")

# 1) 归一化昵称：去掉页面标题后缀「的抖音」
old1 = '        nickname = (page.title() or "").split("-")[0].strip()[:30]'
new1 = ('        nickname = (page.title() or "").split("-")[0].strip()\n'
        '        nickname = re.sub(r"的抖音$", "", nickname).strip()[:30]  '
        '# 页面标题常带「的抖音」后缀\n')
assert old1 in t, "nickname 行未找到"
t = t.replace(old1, new1)

# 2) 复用匹配放宽：去掉非字母数字后比前 4 个字符
old2 = '''        nick_key = safe_name(nickname, 30)
        acct_dir = None
        for cand in sorted(outroot.iterdir(), key=lambda p: -p.stat().st_mtime):
            if cand.is_dir() and cand.name.startswith(nick_key):
                acct_dir = cand
                print(f"   复用已有目录: {cand.name}")
                break
        if acct_dir is None:
            acct_dir = outroot / f"{nick_key}_{fans_tag}"
'''
new2 = '''        nick_key = safe_name(nickname, 30)

        def _norm(s):
            return re.sub(r"[^0-9A-Za-z\\u4e00-\\u9fff]", "", s)

        acct_dir = None
        nk = _norm(nick_key)
        for cand in sorted(outroot.iterdir(), key=lambda p: -p.stat().st_mtime):
            if not cand.is_dir():
                continue
            if _norm(cand.name).startswith(nk[:4]) and nk:
                acct_dir = cand
                print(f"   复用已有目录: {cand.name}")
                break
        if acct_dir is None:
            acct_dir = outroot / f"{nick_key}_{fans_tag}"
'''
assert old2 in t, "复用块未找到"
t = t.replace(old2, new2)
f.write_text(t, encoding="utf-8")
print("已修正昵称归一化 + 复用匹配")

# 3) 清理重复目录
import shutil
base = DATA / "douyin"
for d in list(base.iterdir()):
    if not d.is_dir():
        continue
    if d.name.startswith("蓝星智人的抖音"):
        n = len([x for x in d.iterdir() if x.is_dir()])
        shutil.rmtree(d)
        print(f"删除重复目录 {d.name}（{n} 个作品）")
print("剩余账号目录:", [p.name for p in base.iterdir() if p.is_dir()])
