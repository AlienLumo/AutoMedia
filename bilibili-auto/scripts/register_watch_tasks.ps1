# register_watch_tasks.ps1 - register/remove Windows scheduled tasks for Bili watch.
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File register_watch_tasks.ps1
#   ... -Remove    ... -Query
param([switch]$Remove, [switch]$Query)

$ErrorActionPreference = "Stop"
$S = $PSScriptRoot
$PYW = Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))) 'runtime\python\pythonw.exe'
if (-not (Test-Path $PYW)) {
    $PYW = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
}
if (-not $PYW) { $PYW = (Get-Command python.exe).Source }

# start times are deliberately staggered so that network-heavy runs do not overlap
$tasks = @(
    @{ Name = "BiliWatch-Inbox";  Script = "bili_inbox_collect.py"; Args = "--max-items 20"; ST = "08:00"; RI = 30;  DU = "14:30"; Desc = "inbox collect: subtitles/comments/meta" },
    @{ Name = "BiliWatch-UpsS";   Script = "bili_ups_watch.py";     Args = "--tier S";      ST = "08:03"; RI = 60;  DU = "14:55"; Desc = "S-tier UP polling (core AI/tutorial/robot/science)" },
    @{ Name = "BiliWatch-KW";     Script = "bili_kw_watch.py";      Args = "--pages 1";     ST = "08:22"; RI = 180; DU = "13:00"; Desc = "keyword polling (publish-time order)" },
    @{ Name = "BiliWatch-UpsA";   Script = "bili_ups_watch.py";     Args = "--tier A";      ST = "08:12"; RI = 240; DU = "13:00"; Desc = "A-tier UP polling (tech/maker/security)" },
    @{ Name = "BiliWatch-UpsB";   Script = "bili_ups_watch.py";     Args = "--tier B";      ST = "08:35"; RI = 240; DU = "13:00"; Desc = "B-tier UP polling (business/stock/geopolitics)" },
    @{ Name = "BiliWatch-Digest"; Script = "bili_digest.py";        Args = "";             ST = "21:00"; RI = 0;   DU = "";     Desc = "daily digest -> Feishu" }
)

if ($Query) {
    foreach ($t in $tasks) {
        Write-Output "== $($t.Name) =="
        schtasks /Query /TN $t.Name /FO LIST /V 2>$null | Select-String "Status|Next Run Time|Last Run Time|Task To Run" | ForEach-Object { $_.Line }
    }
    exit 0
}

if ($Remove) {
    foreach ($t in $tasks) { schtasks /Delete /TN $t.Name /F 2>$null | Out-Null }
    Write-Output "removed $($tasks.Count) tasks"
    exit 0
}

foreach ($t in $tasks) {
    $tr = "`"$PYW`" `"$S\$($t.Script)`" $($t.Args)"
    if ($t.RI -gt 0) {
        $out = schtasks /Create /TN $t.Name /SC DAILY /ST $t.ST /RI $t.RI /DU $t.DU /TR $tr /F 2>&1
    } else {
        $out = schtasks /Create /TN $t.Name /SC DAILY /ST $t.ST /TR $tr /F 2>&1
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Output "[FAIL] $($t.Name): $out"
        continue
    }
    # harden: no 72h hang, no battery stop; IgnoreNew keeps same-task runs serial
    try {
        $st = Get-ScheduledTask -TaskName $t.Name
        $set = $st.Settings
        $set.DisallowStartIfOnBatteries = $false
        $set.StopIfGoingOnBatteries = $false
        $set.ExecutionTimeLimit = "PT30M"
        $set.StartWhenAvailable = $true
        $set.MultipleInstances = "IgnoreNew"
        Set-ScheduledTask -TaskName $t.Name -Settings $set | Out-Null
        Write-Output "[OK] $($t.Name) - $($t.Desc) (timeout 30m, battery allowed, staggered)"
    } catch {
        Write-Output "[OK] $($t.Name) - $($t.Desc) (settings hardening failed: $($_.Exception.Message))"
    }
}





