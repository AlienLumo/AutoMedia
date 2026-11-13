# run_queue.ps1 - 串行采集队列（安全优先）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File run_queue.ps1 -LinksFile "<config\queue_links.txt>"
param(
    [string]$LinksFile = '',
    [string[]]$Links = @(),
    [int]$TopPlay = 15,
    [int]$Latest = 15,
    [int]$Comments = 20,
    [int]$Gap = 90,
    [int]$Scroll = 4,
    [int]$MaxWaitMinutes = 360,
    [string]$Profile = '',
    [string]$StatusTag = ''
)

$ErrorActionPreference = 'Continue'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Skill = Split-Path -Parent $Here
$Proj = Split-Path -Parent (Split-Path -Parent $Skill)
$Py = Join-Path $Proj 'runtime\python\python.exe'`r`n$env:HF_HOME = (Join-Path $Proj 'runtime\models\huggingface')
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir "queue-$Stamp.log"
$Status = Join-Path $LogDir ("queue-status" + $(if($StatusTag){"-$StatusTag"}else{""}) + ".txt")
$ProfArg = @()
if ($Profile) { $ProfArg = @('--profile', $Profile) }

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$env:HF_ENDPOINT = 'https://hf-mirror.com'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path $Status -Value ("$m" + "`n" + "日志: $Log" + "`n" + "Updated: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -Encoding UTF8
}

function Wait-Idle {
    if ($Profile) { return $true }
    $deadline = (Get-Date).AddMinutes($MaxWaitMinutes)
    $idle = 0
    while ((Get-Date) -lt $deadline) {
        $running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*douyin_collect.py*' -or $_.CommandLine -like '*douyin_find_by_video.py*' }
        if ($running) {
            $idle = 0
            $ids = ($running | ForEach-Object { $_.ProcessId }) -join ','
            Note "等待前一个采集结束（PID $ids）…"
            Start-Sleep -Seconds 60
        } else {
            $idle++
            if ($idle -ge 2) { return $true }
            Start-Sleep -Seconds 20
        }
    }
    return $false
}

$all = @()
if ($Links) { $all += $Links }
if ($LinksFile -and (Test-Path $LinksFile)) {
    $all += (Get-Content $LinksFile -Encoding UTF8 | Where-Object { $_ -match '^https?://' })
}
$all = @($all | Where-Object { $_ -match '^https?://' } | Select-Object -Unique)

Note "队列启动，共 $($all.Count) 个博主"
Note "参数: TopPlay=$TopPlay Latest=$Latest Comments=$Comments Gap=${Gap}s Scroll=$Scroll"

$idx = 0
foreach ($link in $all) {
    $idx++
    Note "========== 第 $idx/$($all.Count) 个 =========="
    if (-not (Wait-Idle)) { Note "等待超时，终止队列"; break }

    $profile = $link
    if ($link -match 'v\.douyin\.com') {
        Note "解析短链: $link"
        $out = & $Py (Join-Path $Here 'resolve_share.py') $link 2>&1
        Add-Content -Path $Log -Value ($out | Out-String) -Encoding UTF8
        $line = ($out | Select-String -Pattern '"profile_url"').Line
        if ($line -match '"profile_url":\s*"([^"]+)"') {
            $profile = $Matches[1]
            Note "主页: $profile"
        } else {
            Note "解析失败，跳过"
            continue
        }
    }

    Note "开始采集…"
    & $Py (Join-Path $Here 'douyin_collect.py') --url $profile --top-play $TopPlay --latest $Latest --comments $Comments --save-video no --asr-model large-v3 --gap $Gap --scroll $Scroll --mode batch @ProfArg 2>&1 | Out-File -FilePath $Log -Append -Encoding utf8
    $code = $LASTEXITCODE
    Note "采集结束 exit=$code"

    if ($code -eq 0) {
        $rep = & $Py (Join-Path $Here 'report.py') 2>&1
        Add-Content -Path $Log -Value ($rep | Out-String) -Encoding UTF8
        foreach ($l in $rep) { Note "REPORT $l" }
    } else {
        Note "非 0 退出（可能验证码中断），继续下一个"
    }
    Note "休息 120s"
    Start-Sleep -Seconds 120
}

Note "队列全部结束"


