# -*- coding: utf-8 -*-
"""给 build_talk_queue.py 加机构号过滤（用 Python 改，避免 PS 中文匹配问题）。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "build_talk_queue.py"
t = f.read_text(encoding="utf-8")

INST = '''
# ===== 机构号排除（只要个人自媒体，与 B站 口径一致）=====
HARD_INST = ["央视", "中央电视", "CCTV", "CNTV", "人民日报", "人民网", "新华社",
             "新华网", "共青团", "观察者网", "环球时报", "澎湃", "界面新闻",
             "财新", "第一财经", "中国网", "中国日报", "光明网", "经济日报",
             "参考消息", "环球网", "政府", "国务院", "外交部", "国防部",
             "卫健委", "教育部", "央行", "证监会", "卫视", "广电", "广播电台",
             "电视台", "日报", "晚报", "晨报", "新闻网", "全国妇联", "科协",
             "红十字会", "清华大学", "北京大学", "大学", "学院", "研究院", "研究所",
             "电影报道", "新闻"]
SOFT_INST = ["集团", "公司", "商城", "官方", "频道", "传媒", "文化传播",
             "协会", "基金会", "科技有限", "爱奇艺", "腾讯", "优酷", "芒果",
             "哔哩哔哩", "出版社", "杂志", "周刊", "报社", "实验室", "车场", "影院"]
PERSONAL_HINT = ["老师", "哥", "姐", "叔", "阿姨", "同学", "小明",
                 "阿", "小", "先生", "博士", "教授", "UP主"]


def is_personal(name):
    n = name or ""
    if any(w in n for w in HARD_INST):
        return False
    if any(w in n for w in SOFT_INST):
        return any(w in n for w in PERSONAL_HINT)
    return True
'''

if "def is_personal" not in t:
    t = t.replace("# 按主题分组", INST + "\n\n# 按主题分组", 1)

# 在主循环里加过滤
old = '''    uid = x.get("sec_uid")
    if not uid or uid in seen:
        continue
    seen.add(uid)'''
new = '''    uid = x.get("sec_uid")
    if not uid or uid in seen:
        continue
    if not is_personal(x.get("nickname")):
        continue
    seen.add(uid)'''
if old in t:
    t = t.replace(old, new, 1)
else:
    print("WARN: 主循环锚点未匹配")

f.write_text(t, encoding="utf-8")
print("已加机构号过滤" if "def is_personal" in t else "失败")
