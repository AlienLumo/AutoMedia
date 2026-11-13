# run_dual_after_search.ps1 - 搜索完成后：拆分创客队列，双账号并行采集
param(
    [int]$TopPlay = 10,
    [int]$Latest = 20,
    [int]$Comments = 20,
    [int]$Gap = 55,
    [int]$SearchGap = 420,
    [string]$Themes = '创客',
    [switch]$SkipSearch
)

$ErrorActionPreference = 'Continue'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Skill = Split-Path -Parent $Here
$Proj = Split-Path -Parent (Split-Path -Parent $Skill)
$Py = Join-Path $Proj 'runtime\python\python.exe'`r`n$env:HF_HOME = (Join-Path $Proj 'runtime\models\huggingface')
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir "dual-$Stamp.log"
$Status = Join-Path $LogDir 'dual-status.txt'
$Prof2 = Join-Path $Proj 'data\social\douyin-account2-profile'

$env:PYTHONIOENCODING = 'utf-8'
$env:HF_ENDPOINT = 'https://hf-mirror.com'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path $Status -Value ("$m" + "`n日志: $Log" + "`nUpdated: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -Encoding UTF8
}

if (-not $SkipSearch) {
    # 等其它抖音任务结束（搜索用的是默认 profile）
    $idle = 0
    while ($idle -lt 2) {
        $running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*douyin_collect.py*' -or $_.CommandLine -like '*douyin_find_by_video.py*' }
        if ($running) { $idle = 0; Note "等待其它抖音任务…"; Start-Sleep -Seconds 60 }
        else { $idle++; Start-Sleep -Seconds 15 }
    }
    Note "补扫剩余关键词…"
    & $Py (Join-Path $Here 'douyin_find_by_video.py') --gap $SearchGap --min-fans 100000 --scroll 2 --themes '$Themes' 2>&1 |
        Tee-Object -FilePath $Log -Append
    Note "搜索结束 exit=$LASTEXITCODE"
}

Note "生成创客队列并拆成 2 份…"
$out = & $Py (Join-Path $Here 'build_targets.py') --themes $Themes --split 2 2>&1
Add-Content -Path $Log -Value ($out | Out-String) -Encoding UTF8
foreach ($l in $out) { if ($l -match '^(QUEUE|SPLIT|TSV)=') { Note $l } }

$q1 = Join-Path $Skill 'config\queue_creators_p1.txt'
$q2 = Join-Path $Skill 'config\queue_creators_p2.txt'
if (-not (Test-Path $q1) -or -not (Test-Path $q2)) { Note "队列文件缺失，终止"; exit 5 }
$n1 = (Get-Content $q1 -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
$n2 = (Get-Content $q2 -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
Note "账号1 队列 $n1 个 / 账号2 队列 $n2 个（间隔 ${Gap}s）"

Note "启动两个并行采集队列…"
$args1 = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$Here\run_queue.ps1`"",
           '-LinksFile',"`"$q1`"",'-TopPlay',$TopPlay,'-Latest',$Latest,'-Comments',$Comments,
           '-Gap',$Gap,'-StatusTag','acct1')
$args2 = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$Here\run_queue.ps1`"",
           '-LinksFile',"`"$q2`"",'-TopPlay',$TopPlay,'-Latest',$Latest,'-Comments',$Comments,
           '-Gap',$Gap,'-Profile',"`"$Prof2`"",'-StatusTag','acct2')
$p1 = Start-Process powershell.exe -ArgumentList $args1 -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 60
$p2 = Start-Process powershell.exe -ArgumentList $args2 -WindowStyle Hidden -PassThru
Note "队列已启动：acct1 PID $($p1.Id) / acct2 PID $($p2.Id)"

$p1.WaitForExit(); Note "账号1 队列结束 exit=$($p1.ExitCode)"
$p2.WaitForExit(); Note "账号2 队列结束 exit=$($p2.ExitCode)"
Note "双账号全部结束"


