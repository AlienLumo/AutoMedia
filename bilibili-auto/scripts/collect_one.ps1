# collect_one.ps1 - B站单个 UP 一键采集（元数据 + 评论 + 字幕）
# 用法：
#   .\collect_one.ps1 -Mid 385670211              # 采最近 30 条
#   .\collect_one.ps1 -Mid 385670211 -Limit 100   # 采最近 100 条
#   .\collect_one.ps1 -Mid 385670211 -Order click # 按播放量排序（成本翻倍）
param(
    [Parameter(Mandatory=$true)][int]$Mid,
    [int]$Limit = 30,
    [ValidateSet('pubdate','click')][string]$Order = 'pubdate',
    [int]$CommentCap = 200,
    [double]$Pace = 1.3,
    [string]$OutDir = ''
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Proj = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $Here))
$Py = Join-Path $Proj 'runtime\python\python.exe'
if (-not (Test-Path $Py)) { $Py = (Get-Command python.exe).Source }
$env:PYTHONIOENCODING = 'utf-8'
if (-not $OutDir) { $OutDir = Join-Path $Proj "1AMdata\bilibili\_single\$Mid" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ">> 采集 mid=$Mid  limit=$Limit  order=$Order"
& $Py (Join-Path $Here 'bili_collect.py') --mid $Mid --limit $Limit --order $Order `
    --outdir $OutDir --with-comments --comment-cap $CommentCap --with-subs --pace $Pace
$code = $LASTEXITCODE

$vids = (Get-ChildItem $OutDir -Directory -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName 'meta.json') }).Count
Write-Host ">> 完成 exit=$code  视频=$vids  输出=$OutDir"
exit $code

