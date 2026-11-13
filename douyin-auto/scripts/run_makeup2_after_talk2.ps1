# run_makeup2_after_talk2.ps1
# Account 2 (douyin-account2-profile) finishes queue_talk_p2_resume5.txt first;
# when that queue ends (or crashes), immediately run queue_makeup_p2.txt on the
# same account so both Douyin accounts stay busy until all queues are done.
# Keep this file pure ASCII.
$ErrorActionPreference = 'Continue'

$Here  = Split-Path -Parent $PSCommandPath            # ...\douyin-auto\scripts
$Skill = Split-Path -Parent $Here                     # ...\douyin-auto
$Proj  = Split-Path -Parent (Split-Path -Parent $Skill)
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'makeup2-chain.log'
$Status = Join-Path $LogDir 'queue-status-talk2-resume2.txt'
$Profile2 = $null
foreach ($d in Get-ChildItem (Join-Path $Proj 'data\social') -Directory -ErrorAction SilentlyContinue) {
    if ($d.Name -like '*account2*') { $Profile2 = $d.FullName; break }
}
$Q2 = Join-Path $Skill 'config\queue_makeup_p2.txt'
$Rq = Join-Path $Here 'run_queue.ps1'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path (Join-Path $LogDir 'makeup2-status.txt') -Value $m -Encoding UTF8
}

function Get-Acc2Collector {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*douyin_collect.py*' -and $_.CommandLine -like '*account2*' }
}

Note "watching talk2-resume2; will start makeup2 on account2 when it ends"
$idle = 0
$deadline = (Get-Date).AddHours(36)
while ((Get-Date) -lt $deadline) {
    $done = $false
    if (Test-Path $Status) {
        $txt = [System.IO.File]::ReadAllText($Status, [System.Text.Encoding]::UTF8)
        if ($txt -match '队列全部结束') { $done = $true }
    }
    if (-not $done) {
        $run = Get-Acc2Collector
        if ($run) { $idle = 0 }
        else {
            $idle++
            if ($idle -ge 4) { $done = $true; Note "account2 collector gone for 20min, treating queue as ended" }
        }
    }
    if ($done) { break }
    Start-Sleep -Seconds 300
}

if (-not (Test-Path $Q2)) { Note "makeup2 queue file missing"; exit 2 }
$n = (Get-Content $Q2 -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
Note "starting makeup2 on account2: $n accounts"
$common = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$Rq`"",
            '-LinksFile',"`"$Q2`"",'-TopPlay','10','-Latest','5','-Comments','20',
            '-Gap','55','-Scroll','4','-StatusTag','makeup2')
if ($Profile2) { $common += @('-Profile',"`"$Profile2`"") }
$p = Start-Process powershell.exe -ArgumentList $common -WindowStyle Hidden -PassThru
Note "makeup2 started pid=$($p.Id)"

