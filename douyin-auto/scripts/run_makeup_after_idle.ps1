# run_makeup_after_idle.ps1
# Wait until the current Douyin queue runs are idle, then launch the makeup
# queues (queue_makeup_p1/p2) on the two accounts.
# Keep this file pure ASCII: PowerShell 5.1 reads .ps1 as ANSI.
$ErrorActionPreference = 'Continue'

$Here = Split-Path -Parent $PSCommandPath
$Skill = Split-Path -Parent $Here
$Proj = Split-Path -Parent (Split-Path -Parent $Skill)
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'makeup-chain.log'
$Profile2 = Join-Path $Proj 'data\social\douyin-account2-profile'
$Q1 = Join-Path $Skill 'config\queue_makeup_p1.txt'
$Q2 = Join-Path $Skill 'config\queue_makeup_p2.txt'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path (Join-Path $LogDir 'makeup-status.txt') -Value $m -Encoding UTF8
}

function Get-Collectors {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*douyin_collect.py*' }
}

Note "chained makeup runner started, waiting for current queues to become idle"

# Require 3 consecutive idle checks (5 min apart) before starting.
$idle = 0
$deadline = (Get-Date).AddHours(36)
while ((Get-Date) -lt $deadline) {
    $run = Get-Collectors
    if ($run) {
        if ($idle -ne 0) { Note "collector is active again, idle counter reset" }
        $idle = 0
        Start-Sleep -Seconds 300
        continue
    }
    $idle++
    Note "idle check $idle/3 (no douyin_collect process)"
    if ($idle -ge 3) { break }
    Start-Sleep -Seconds 300
}

if ($idle -lt 3) {
    Note "gave up: still not idle after deadline"
    exit 1
}

if (-not (Test-Path $Q1) -or -not (Test-Path $Q2)) {
    Note "makeup queue files missing, abort"
    exit 2
}

$n1 = (Get-Content $Q1 -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
$n2 = (Get-Content $Q2 -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
Note "launching makeup queues: $n1 + $n2 accounts"

$rq = Join-Path $Here 'run_queue.ps1'
$common = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$rq`"",
            '-TopPlay','10','-Latest','5','-Comments','20','-Gap','55','-Scroll','4')

$args1 = $common + @('-LinksFile',"`"$Q1`"",'-StatusTag','makeup1')
$args2 = $common + @('-LinksFile',"`"$Q2`"",'-Profile',"`"$Profile2`"",'-StatusTag','makeup2')

$p1 = Start-Process powershell.exe -ArgumentList $args1 -WindowStyle Hidden -PassThru
Note "queue makeup1 started pid=$($p1.Id)"
Start-Sleep -Seconds 45
$p2 = Start-Process powershell.exe -ArgumentList $args2 -WindowStyle Hidden -PassThru
Note "queue makeup2 started pid=$($p2.Id)"

