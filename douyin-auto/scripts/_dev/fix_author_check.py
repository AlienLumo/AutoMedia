# -*- coding: utf-8 -*-
"""修数据完整性：主页混入的推荐视频按 author_sec_uid 过滤；昵称不被覆盖。"""
import json
import re
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import DATA, SKILL

f = SKILL / "scripts" / "douyin_collect.py"
t = f.read_text(encoding="utf-8")

# 1) 解析目标账号 sec_uid
old = '        print(f"[1] 打开主页 {a.url}")'
new = ('        m_uid = re.search(r"/user/([A-Za-z0-9_\\-]{20,})", a.url)\n'
       '        target_uid = m_uid.group(1) if m_uid else None\n'
       '        print(f"[1] 打开主页 {a.url}")\n'
       '        if target_uid:\n'
       '            print(f"   目标 sec_uid: {target_uid[:24]}…")')
assert old in t
t = t.replace(old, new, 1)

# 2) 采到作品后校验作者归属，不匹配则丢弃
old2 = '''            meta = parse_detail(cap)
            if not meta.get("aweme_id"):
                meta["aweme_id"] = vid'''
new2 = '''            meta = parse_detail(cap)
            if not meta.get("aweme_id"):
                meta["aweme_id"] = vid
            # 校验：必须是目标账号的作品（主页滚动会混入推荐/相关视频）
            au_uid = meta.get("author_sec_uid")
            if target_uid and au_uid and au_uid != target_uid:
                print(f"      ✗ 非本账号作品（作者={meta.get('author')}），丢弃")
                cap.close()
                try:
                    vdir.rmdir()
                except OSError:
                    shutil.rmtree(vdir, ignore_errors=True)
                time.sleep(random.uniform(3, 6))
                continue'''
assert old2 in t
t = t.replace(old2, new2, 1)

# 3) 昵称不被 meta 覆盖；fans 只在作者匹配时采用
old3 = '''                    if _m.get("author_fans"):
                        fans_final = _m["author_fans"]
                        nickname = _m.get("author") or nickname
                        break'''
new3 = '''                    if _m.get("author_fans") and (
                            not target_uid or _m.get("author_sec_uid") == target_uid):
                        fans_final = _m["author_fans"]
                        break'''
assert old3 in t
t = t.replace(old3, new3, 1)

# 4) 需要 shutil
if "import shutil" not in t:
    t = t.replace("import subprocess", "import shutil\nimport subprocess", 1)

f.write_text(t, encoding="utf-8")
print("已加入作者归属校验")

# 5) 清理误采的视频目录
acct = DATA / "douyin" / "蓝星智人_2.2万"
target = "MS4wLjABAAAAJYj2fv-pXXsny4g1SUpcplIiESTbPZjcl5uv2ql2fWHVFWW5xJuwGGAgjYUqAqQg"
removed = 0
for v in list(acct.iterdir()):
    if not v.is_dir():
        continue
    mp = v / "meta.json"
    if not mp.exists():
        continue
    try:
        m = json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        continue
    if m.get("author_sec_uid") and m["author_sec_uid"] != target:
        shutil.rmtree(v)
        removed += 1
        print(f"  删除误采: {v.name}  作者={m.get('author')}")
print(f"清理 {removed} 个误采目录；剩余 {len([x for x in acct.iterdir() if x.is_dir()])} 个")

# 6) 修正 _account.json
ap = acct / "_account.json"
if ap.exists():
    d = json.loads(ap.read_text(encoding="utf-8"))
    d["nickname"] = "蓝星智人"
    d["fans"] = 22110
    d["collected"] = [x.name for x in acct.iterdir() if x.is_dir()]
    ap.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("_account.json 已修正")
