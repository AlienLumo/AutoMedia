# collect.ps1 - 抖音单账号采集：一条命令完成 解析链接 -> 采集 -> 出报告
#
# 用法：
#   .\collect.ps1 -Link "https://v.douyin.com/xxxx/"
#   .\collect.ps1 -Link "https://www.douyin.com/user/MS4wLjABAAAA..."
#   .\collect.ps1 -Link "<链接>" -SaveVideo yes      # 额外保存视频
#   .\collect.ps1 -Link "<链接>" -Comments 30 -TopPlay 10 -Latest 5
#
# 设计原则（省 token）：
#   1. 全部详细输出重定向到 logs\collect-*.log，屏幕只留极简摘要
#   2. 采集脚本自己写 meta/comments/transcript 到磁盘，数据不进对话
#   3. 报告由 report.py 生成到 1AMdata\douyin\_report_*.md，按需再读
param(
    [Parameter(Mandatory = $true)][string]$Link,
    [ValidateSet('auto', 'yes', 'no')][string]$SaveVideo = 'no',
    [int]$Comments = 20,
    [int]$TopPlay = 10,
    [int]$Latest = 5,
    [string]$AsrModel = 'large-v3',
    [int]$Gap = 25,
    [ValidateSet('batch','next')][string]$Mode = 'batch',
    [int]$Count = 15,
    [int]$Scroll = 3
)

$ErrorActionPreference = 'Stop'
$Skill = Split-Path -Parent $PSScriptRoot
$Proj = Split-Path -Parent (Split-Path -Parent $Skill)
$Py = Join-Path $Proj 'runtime\python\python.exe'`r`n$env:HF_HOME = (Join-Path $Proj 'runtime\models\huggingface')
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_ENDPOINT = 'https://hf-mirror.com'
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("collect-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Step($msg) { Write-Host ">> $msg" }

# 1) 短链 -> 主页
$ProfileUrl = $Link
if ($Link -match 'v\.douyin\.com') {
    Step "解析分享短链…"
    $out = & $Py (Join-Path $PSScriptRoot 'resolve_share.py') $Link 2>> $Log
    $line = ($out | Select-String -Pattern '"profile_url"').Line
    if ($line -match '"profile_url":\s*"([^"]+)"') {
        $ProfileUrl = $Matches[1]
    } else {
        Write-Host "!! 短链解析失败，详见 $Log"
        exit 4
    }
    Write-Host "   主页: $ProfileUrl"
}

# 2) 采集
Step "开始采集（save-video=$SaveVideo, 评论=$Comments, 模型=$AsrModel）"
Step "详细日志: $Log"
& $Py (Join-Path $PSScriptRoot 'douyin_collect.py') --url $ProfileUrl --top-play $TopPlay --latest $Latest --comments $Comments --save-video $SaveVideo --asr-model $AsrModel --gap $Gap --mode $Mode --count $Count --scroll $Scroll *>> $Log
$code = $LASTEXITCODE

# 3) 报告
if ($code -eq 0) {
    $rep = & $Py (Join-Path $PSScriptRoot 'report.py') 2>> $Log
    foreach ($l in $rep) { Write-Host $l }
    Write-Host ""
    Write-Host "完成。详细日志: $Log"
} else {
    Write-Host "!! 采集返回码 $code，详见 $Log"
    Get-Content $Log -Tail 15 | ForEach-Object { Write-Host "   $_" }
}
exit $code


