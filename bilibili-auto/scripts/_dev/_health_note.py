# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL
p=SKILL.parent / "进度.md"
c=p.read_text(encoding="utf-8")
stamp=datetime.now().strftime("%Y-%m-%d %H:%M")
entry=f"""

### {stamp} 监听任务巡检
- 6 个计划任务全部 Ready，Last Result=0；今日 Inbox 13 轮、UP 11 轮、KW 2 轮，0 错误；飞书 11-08 21:00 推送成功。
- 今日 inbox 总量 1054（599 已采、455 标记 skipped/out_of_roster），pending 0；A/B 首轮补采已消化。
- 问题：网络锁冲突导致 08:04 UP-S、08:23 KW 等轮次被跳过（Inbox 20 条/轮约 4-5 分钟，与 :03/:22/:35 重叠）。
- 修复：ups/kw 的 NetLock 等待 90→300 秒；任务超时 25→30 分钟并重注册。
- 待确认：455 条 kw 结果被非当前脚本标记 skipped（11-08 21:06，mid 异常），若要池外发现需改回待处理。
"""
p.write_text(c+entry, encoding="utf-8")
print("progress updated")
