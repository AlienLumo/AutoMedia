# run_bili_continuous.ps1 - B站连续采集（不依赖计划任务的 5 天期限）
# 循环调用 bili_deep_collect.py，一轮跑完立刻接下一轮（无 25 分钟空档）
# 与计划任务共存：靠采集器自己的 PID 锁避免并发（对方会因锁立即退出）
$ErrorActionPreference = 'Continue'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Skill = Split-Path -Parent $Here
$Proj = Split-Path -Parent (Split-Path -Parent $Skill)
$Py = Join-Path $Proj 'runtime\python\python.exe'
$Log = Join-Path $Here 'logs\deep_run.log'
$Status = Join-Path $Here 'logs\continuous-status.txt'

$env:PYTHONIOENCODING = 'utf-8'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path $Status -Value ("$m" + "`nUpdated: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -Encoding UTF8
}

Note "连续采集启动"
$cycle = 0
while ($cycle -lt 2000) {
    $cycle++
    Note "第 $cycle 轮开始"
    & $Py (Join-Path $Here 'bili_deep_collect.py') `
        --max-requests 850 --pace 1.3 --rest-every 600 --cooldown 120 `
        --comment-cap 100 --top-n 20 --pool-cap 80 --sub-langs zh 2>&1 |
        Add-Content -Path $Log -Encoding UTF8
    $code = $LASTEXITCODE
    Note "第 $cycle 轮结束 exit=$code"

    # 检查是否全部完成
    $py2 = @"
import json
from pathlib import Path
d = json.loads(Path(r'$Proj\1AMdata\_state\deep_collect.json').read_text(encoding='utf-8'))
a = d.get('accounts') or {}
fin = sum(1 for x in a.values() if x.get('stage')=='finished')
print(f'{fin}/{len(a)}')
"@
    $stat = & $Py -c $py2 2>$null
    Note "进度 $stat"
    if ($stat -match '^(\d+)/(\d+)$') {
        if ($Matches[1] -eq $Matches[2]) {
            Note "全部账号已采完，停止"
            break
        }
    }
    Start-Sleep -Seconds 30
}
Note "连续采集结束"

