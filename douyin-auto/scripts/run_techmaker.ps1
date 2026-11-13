# run_techmaker.ps1 — 科技创客专用流水线（硬编码主题，避免引号传参问题）
#   阶段1：搜索「科技创客」主题剩余关键词
#   阶段2：按粉丝降序生成队列并拆 2 份
#   阶段3：双账号并行采集（30 视频/博主）
param(
    [int]$TopPlay = 10,
    [int]$Latest = 20,
    [int]$Comments = 20,
    [int]$Gap = 55,
    [int]$SearchGap = 360
)

$ErrorActionPreference = 'Continue'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Skill = Split-Path -Parent $Here
$Proj = Split-Path -Parent (Split-Path -Parent $Skill)
$Py = Join-Path $Proj 'runtime\python\python.exe'`r`n$env:HF_HOME = (Join-Path $Proj 'runtime\models\huggingface')
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir "techmaker-$Stamp.log"
$Status = Join-Path $LogDir 'techmaker-status.txt'
$Prof2 = Join-Path $Proj 'data\social\douyin-account2-profile'
$THEME = '科技创客'

$env:PYTHONIOENCODING = 'utf-8'
$env:HF_ENDPOINT = 'https://hf-mirror.com'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path $Status -Value ("$m" + "`n日志: $Log" + "`nUpdated: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -Encoding UTF8
}

# ---------- 阶段1：搜索 ----------
Note "阶段1：搜索科技创客关键词"
$idle = 0
while ($idle -lt 2) {
    $run = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*douyin_collect.py*' -or $_.CommandLine -like '*douyin_find_by_video.py*' }
    if ($run) { $idle = 0; Note "等待其它任务…"; Start-Sleep -Seconds 45 }
    else { $idle++; Start-Sleep -Seconds 10 }
}
& $Py (Join-Path $Here 'douyin_find_by_video.py') --themes 科技创客 --gap $SearchGap --min-fans 100000 --scroll 2 2>&1 |
    Tee-Object -FilePath $Log -Append
Note "阶段1结束 exit=$LASTEXITCODE"

# ---------- 阶段2：生成队列 ----------
Note "阶段2：生成队列"
$out = & $Py (Join-Path $Here 'build_targets.py') --themes 科技创客 --split 2 2>&1
Add-Content -Path $Log -Value ($out | Out-String) -Encoding UTF8
foreach ($l in $out) { if ($l -match '^(QUEUE|SPLIT|TSV)=') { Note $l } }

$q1 = Join-Path $Skill 'config\queue_techmaker_p1.txt'
$q2 = Join-Path $Skill 'config\queue_techmaker_p2.txt'
# build_targets 输出固定名 queue_creators_pN.txt，这里改名避免和旧文件混
$b1 = Join-Path $Skill 'config\queue_creators_p1.txt'
$b2 = Join-Path $Skill 'config\queue_creators_p2.txt'
Copy-Item $b1 $q1 -Force -ErrorAction SilentlyContinue
Copy-Item $b2 $q2 -Force -ErrorAction SilentlyContinue

$n1 = (Get-Content $q1 -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
$n2 = (Get-Content $q2 -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
Note "科技创客队列：账号1 $n1 个 / 账号2 $n2 个"
if ($n1 -eq 0 -and $n2 -eq 0) { Note "队列为空，终止"; exit 5 }

# ---------- 阶段3：双账号并行 ----------
Note "阶段3：双账号并行采集（间隔 ${Gap}s）"
$a1 = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$Here\run_queue.ps1`"",
        '-LinksFile',"`"$q1`"",'-TopPlay',$TopPlay,'-Latest',$Latest,'-Comments',$Comments,
        '-Gap',$Gap,'-StatusTag','tm1')
$a2 = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$Here\run_queue.ps1`"",
        '-LinksFile',"`"$q2`"",'-TopPlay',$TopPlay,'-Latest',$Latest,'-Comments',$Comments,
        '-Gap',$Gap,'-Profile',"`"$Prof2`"",'-StatusTag','tm2')
$p1 = Start-Process powershell.exe -ArgumentList $a1 -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 60
$p2 = Start-Process powershell.exe -ArgumentList $a2 -WindowStyle Hidden -PassThru
Note "已启动：tm1 PID $($p1.Id) / tm2 PID $($p2.Id)"

$p1.WaitForExit(); Note "账号1 结束 exit=$($p1.ExitCode)"
$p2.WaitForExit(); Note "账号2 结束 exit=$($p2.ExitCode)"
Note "科技创客采集全部结束"


