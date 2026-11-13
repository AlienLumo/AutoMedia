# run_phase2.ps1 - 两阶段自动流水线
#   阶段1：补扫剩余关键词（自动跳过已完成的）
#   阶段2：按粉丝降序采集「创客/创业」博主，每号 30 个视频（最火10 + 最新20）
# 独立后台运行，全程不占对话。
param(
    [int]$TopPlay = 10,
    [int]$Latest = 20,
    [int]$Comments = 20,
    [int]$Gap = 90,
    [int]$SearchGap = 420
)

$ErrorActionPreference = 'Continue'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Skill = Split-Path -Parent $Here
$Proj = Split-Path -Parent (Split-Path -Parent $Skill)
$Py = Join-Path $Proj 'runtime\python\python.exe'`r`n$env:HF_HOME = (Join-Path $Proj 'runtime\models\huggingface')
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir "phase2-$Stamp.log"
$Status = Join-Path $LogDir 'phase2-status.txt'

$env:PYTHONIOENCODING = 'utf-8'
$env:HF_ENDPOINT = 'https://hf-mirror.com'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path $Status -Value ("$m" + "`n日志: $Log" + "`nUpdated: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -Encoding UTF8
}

function Wait-Idle {
    $idle = 0
    while ($idle -lt 2) {
        $running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*douyin_collect.py*' -or
                           $_.CommandLine -like '*douyin_find_by_video.py*' -or
                           $_.CommandLine -like '*douyin_find_bloggers.py*' }
        if ($running) {
            $idle = 0
            Note "等待其它抖音任务结束（PID $(($running | ForEach-Object { $_.ProcessId }) -join ',')）…"
            Start-Sleep -Seconds 60
        } else {
            $idle++
            Start-Sleep -Seconds 15
        }
    }
}

Note "========== 阶段1：补扫剩余关键词 =========="
Wait-Idle
# 不带 --themes 即全部 7 个领域；脚本内部会跳过已完成关键词
& $Py (Join-Path $Here 'douyin_find_by_video.py') --gap $SearchGap --min-fans 100000 --scroll 2 2>&1 |
    Tee-Object -FilePath $Log -Append
Note "阶段1结束 exit=$LASTEXITCODE"

Note "========== 生成创客/创业采集队列 =========="
$out = & $Py (Join-Path $Here 'build_targets.py') 2>&1
Add-Content -Path $Log -Value ($out | Out-String) -Encoding UTF8
foreach ($l in $out) { if ($l -match '^(QUEUE|TSV)=|count=') { Note $l } }
$queueFile = Join-Path $Skill 'config\queue_creators.txt'
if (-not (Test-Path $queueFile)) {
    Note "队列文件未生成，终止"
    exit 5
}
$n = (Get-Content $queueFile -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
Note "待采博主 $n 个（按粉丝降序）"

Note "========== 阶段2：串行采集 =========="
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Here 'run_queue.ps1') `
    -LinksFile $queueFile -TopPlay $TopPlay -Latest $Latest -Comments $Comments -Gap $Gap 2>&1 |
    Tee-Object -FilePath $Log -Append
Note "阶段2结束 exit=$LASTEXITCODE"
Note "全部完成"


