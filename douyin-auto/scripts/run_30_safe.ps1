# run_30_safe.ps1 — 安全优先的 30 视频采集（独立后台运行，不占对话）
# 用法：由 Start-Process 以隐藏窗口启动，日志落盘，脚本自行完成
param(
    [Parameter(Mandatory = $true)][string]$Link,
    [int]$TopPlay = 15,
    [int]$Latest = 15,
    [int]$Comments = 20,
    [int]$Gap = 90,
    [int]$Scroll = 4
)

$ErrorActionPreference = 'Continue'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Skill = Split-Path -Parent $Here
$Proj = Split-Path -Parent (Split-Path -Parent $Skill)
$Py = Join-Path $Proj 'runtime\python\python.exe'`r`n$env:HF_HOME = (Join-Path $Proj 'runtime\models\huggingface')
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir "safe30-$Stamp.log"
$Status = Join-Path $LogDir 'safe30-status.txt'

$env:PYTHONIOENCODING = 'utf-8'
$env:HF_ENDPOINT = 'https://hf-mirror.com'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path $Status -Value "$m`n日志: $Log`nUpdated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8
}

Note "任务开始 link=$Link"
Note "参数: TopPlay=$TopPlay Latest=$Latest Comments=$Comments Gap=${Gap}s Scroll=$Scroll"

# 1) 若是短链先解析
$ProfileUrl = $Link
if ($Link -match 'v\.douyin\.com') {
    Note "解析短链…"
    $out = & $Py (Join-Path $Here 'resolve_share.py') $Link 2>&1
    Add-Content -Path $Log -Value ($out | Out-String) -Encoding UTF8
    $line = ($out | Select-String -Pattern '"profile_url"').Line
    if ($line -match '"profile_url":\s*"([^"]+)"') {
        $ProfileUrl = $Matches[1]
    } else {
        Note "短链解析失败，退出"
        exit 4
    }
}
Note "目标主页: $ProfileUrl"

# 2) 采集（安全参数）
Note "开始采集（作品间 ${Gap}s 间隔，触发验证码会自动停止并保留进度）"
& $Py (Join-Path $Here 'douyin_collect.py') `
    --url $ProfileUrl --top-play $TopPlay --latest $Latest `
    --comments $Comments --save-video no --asr-model large-v3 `
    --gap $Gap --scroll $Scroll --mode batch 2>&1 |
    Tee-Object -FilePath $Log -Append
$code = $LASTEXITCODE
Note "采集进程结束 exit=$code"

# 3) 出报告
if ($code -eq 0) {
    Note "生成报告…"
    $rep = & $Py (Join-Path $Here 'report.py') 2>&1
    Add-Content -Path $Log -Value ($rep | Out-String) -Encoding UTF8
    foreach ($l in $rep) { Note "REPORT $l" }
} else {
    Note "非 0 退出，请检查日志（可能是验证码中断）"
}

# 4) 汇总作品数
$count = (Get-ChildItem (Join-Path $Proj '1AMdata\douyin') -Directory |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
          Get-ChildItem -Directory).Count
Note "当前账号作品目录数: $count"
Note "任务完成"


