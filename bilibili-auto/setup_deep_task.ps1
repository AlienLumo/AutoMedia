# BiliDeepCollect scheduled task (ASCII-only: Windows PowerShell 5.1 breaks
# on UTF-8 .ps1 files without BOM, so keep this file English-only).
# Usage:
#   powershell -ExecutionPolicy Bypass -File setup_deep_task.ps1
#   powershell -ExecutionPolicy Bypass -File setup_deep_task.ps1 -Remove
param([switch]$Remove, [switch]$Silent)

$TaskName = "BiliDeepCollect"
$Cmd = Join-Path $PSScriptRoot "collect_run.cmd"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "Removed scheduled task: $TaskName"
    return
}

if (-not (Test-Path $Cmd)) { Write-Error "Missing $Cmd"; return }

if ($Silent) {
    $vbs = Join-Path (Split-Path $Cmd) "collect_hidden.vbs"
    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "//nologo `"$vbs`""
} else {
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Cmd`""
}
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 25) `
    -RepetitionDuration (New-TimeSpan -Days 5)
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 22) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Bilibili deep collect (safe pacing, resumable)" -Force | Out-Null

$info = Get-ScheduledTask -TaskName $TaskName
$ti = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Output "Registered: $($info.TaskName)  State=$($info.State)"
Write-Output "Trigger   : every 25 min for 5 days"
Write-Output "NextRun   : $($ti.NextRunTime)"
Write-Output "Log       : $(Join-Path $PSScriptRoot 'logs\deep_run.log')"
Write-Output ""
Write-Output "Run one chunk now : cmd /c `"$Cmd`""
Write-Output "Check progress    : python scripts\show_state.py"
Write-Output "Remove task       : powershell -ExecutionPolicy Bypass -File setup_deep_task.ps1 -Remove"
