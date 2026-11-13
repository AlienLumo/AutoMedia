# run_bili_sub_backfill_after_idle.ps1
# Wait until Douyin collection (including the makeup queues) is fully idle and
# enough RAM is free, then run the Bilibili subtitle ASR backfill.
#
# Why wait: two Douyin collectors hold ~4GB of browser + ASR memory; loading
# another Whisper model while they run fails with mkl_malloc out-of-memory.
#
# Keep this file pure ASCII (PowerShell 5.1 reads .ps1 as ANSI).
# $Proj is derived from this file's location, not a hard-coded path.

$ErrorActionPreference = 'Continue'

$Here  = Split-Path -Parent $PSCommandPath   # ...\AutoMedia\bilibili-auto
$Skill = $Here                                # this skill dir
$Proj  = Split-Path -Parent (Split-Path -Parent $Here)   # project root
$LogDir = Join-Path $Here 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log    = Join-Path $LogDir 'bili-sub-backfill.log'
$Status = Join-Path $LogDir 'bili-sub-backfill-status.txt'

# Resolve the Python that has faster-whisper + imageio-ffmpeg.
$Py = Join-Path $Proj 'runtime\python\python.exe'
if (-not (Test-Path $Py)) { "python with faster-whisper not found" | Set-Content $Status; exit 1 }

$Script = Join-Path $Here 'scripts\bili_sub_backfill.py'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path $Status -Value $m -Encoding UTF8
}

function Get-DouyinCollectors {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*douyin_collect.py*' }
}

function Get-FreeGb {
    $os = Get-CimInstance Win32_OperatingSystem
    [math]::Round($os.FreePhysicalMemory / 1MB, 2)
}

Note "waiting: douyin idle 30min AND free RAM > 4GB before Bilibili ASR backfill"

$idle = 0
$deadline = (Get-Date).AddHours(48)
while ((Get-Date) -lt $deadline) {
    $run = Get-DouyinCollectors
    $free = Get-FreeGb
    if ($run) {
        if ($idle -ne 0) { Note "douyin active again, idle reset" }
        $idle = 0
        Start-Sleep -Seconds 300
        continue
    }
    if ($free -lt 4) {
        Note ("douyin idle but RAM low ({0} GB free), waiting" -f $free)
        $idle = 0
        Start-Sleep -Seconds 300
        continue
    }
    $idle++
    Note ("idle {0}/6, free RAM {1} GB" -f $idle, $free)
    if ($idle -ge 6) { break }
    Start-Sleep -Seconds 300
}

if ($idle -lt 6) { Note "gave up waiting (deadline)"; exit 1 }

Note "starting Bilibili subtitle ASR backfill (large-v3)"
$args = @($Script)
& $Py @args *>> $Log
Note ("backfill finished, exit={0}" -f $LASTEXITCODE)
