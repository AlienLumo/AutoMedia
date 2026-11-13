# -*- coding: utf-8 -*-
"""把 _account.json 的 fans 改为优先取 detail 的 author_fans。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "douyin_collect.py"
lines = f.read_text(encoding="utf-8").splitlines(True)

# 找到写入 _account.json 的行号
idx = next(i for i, l in enumerate(lines) if '_account.json").write_text' in l)
indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()))

ins = [
    f"{indent}# 优先用 detail 接口的 author_fans（页面文本解析常不准）\n",
    f"{indent}fans_final = fans\n",
    f"{indent}for _v in sorted(acct_dir.iterdir()):\n",
    f"{indent}    _mp = _v / \"meta.json\"\n",
    f"{indent}    if _mp.exists():\n",
    f"{indent}        try:\n",
    f"{indent}            _m = json.loads(_mp.read_text(encoding=\"utf-8\"))\n",
    f"{indent}            if _m.get(\"author_fans\"):\n",
    f"{indent}                fans_final = _m[\"author_fans\"]\n",
    f"{indent}                nickname = _m.get(\"author\") or nickname\n",
    f"{indent}                break\n",
    f"{indent}        except Exception:\n",
    f"{indent}            pass\n",
]
out = lines[:idx] + ins + lines[idx:]
txt = "".join(out).replace('"nickname": nickname, "fans": fans,',
                           '"nickname": nickname, "fans": fans_final,')
f.write_text(txt, encoding="utf-8")
print("已插入 author_fans 优先逻辑")
