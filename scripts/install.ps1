# install.ps1 - AutoMedia installer / environment checker (Windows PowerShell 5.1+)
#
# Creates the data directories, checks the runtime (Python / patchright / Chromium /
# ffmpeg / faster-whisper), and can install Python deps or link the four skills into
# a DSH workspace.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1 -DryRun
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1 -InstallDeps
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1 -ProjectRoot D:\my-dsh-workspace
#
# Keep this file pure ASCII: PowerShell 5.1 may parse UTF-8 without BOM as GBK and
# the console codepage may be GBK too. Paths that contain non-ASCII characters are
# printed as \uXXXX escapes. The news-source data directory name is built from code
# points for the same reason.

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$InstallDeps,
    [switch]$SkipChecks,
    [string]$ProjectRoot = ''
)

$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'

# ---------------------------------------------------------------------------
# Output helpers (ASCII only)
# ---------------------------------------------------------------------------
function ConvertTo-AsciiText([string]$text) {
    if ([string]::IsNullOrEmpty($text)) { return '' }
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $text.ToCharArray()) {
        if ([int][char]$ch -lt 128) { [void]$sb.Append($ch) }
        else { [void]$sb.Append(('\u{0:X4}' -f [int][char]$ch)) }
    }
    return $sb.ToString()
}

function Write-Pass([string]$text) { Write-Host ('[ok] ' + $text) }
function Write-Note([string]$text) { Write-Host ('[!]  ' + $text) }
function Write-Miss([string]$text) { Write-Host ('[x]  ' + $text) }
function Write-Do([string]$text)   { Write-Host ('[..] ' + $text) }
function Write-Plan([string]$text) { if ($DryRun) { Write-Host ('[dry-run] ' + $text) } }

$script:Fatal = 0
$script:Issues = 0

function Report-Check([string]$label, [string]$detail, [string]$status) {
    switch ($status) {
        'ok'   { Write-Pass ($label + ' - ' + $detail) }
        'warn' { $script:Issues++; Write-Note ($label + ' - ' + $detail) }
        default { $script:Fatal++;  Write-Miss ($label + ' - ' + $detail) }
    }
}

function Find-FirstFile([string]$base, [string[]]$patterns) {
    if (-not (Test-Path $base)) { return $null }
    foreach ($pattern in $patterns) {
        try {
            $hit = Get-ChildItem -Path (Join-Path $base $pattern) -ErrorAction SilentlyContinue |
                Select-Object -First 1
        } catch {
            $hit = $null
        }
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Find-CommandPath([string[]]$names) {
    foreach ($name in $names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

# Native commands write warnings/tracebacks to stderr. Redirecting stderr while
# $ErrorActionPreference = 'Stop' turns that into a terminating error in PS 5.1,
# so redirected native calls below run with a temporarily relaxed preference.
function Invoke-PyCheck([string]$python, [string]$code) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $exitCode = 1
    try {
        & $python -c $code 2>&1 | Out-Null
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return $exitCode
}

function Invoke-PyOutput([string]$python, [string]$code) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $exitCode = 1
    $text = ''
    try {
        $output = & $python -c $code 2>&1
        $exitCode = $LASTEXITCODE
        $text = (@($output) | ForEach-Object { [string]$_ }) -join "`n"
    } finally {
        $ErrorActionPreference = $previous
    }
    return [pscustomobject]@{ ExitCode = $exitCode; Text = $text }
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir

if ([string]::IsNullOrWhiteSpace($env:AUTOMEDIA_ROOT)) {
    $DataRoot = $Root
    $DataRootLabel = 'repo root (default)'
} else {
    $DataRoot = [System.IO.Path]::GetFullPath($env:AUTOMEDIA_ROOT)
    $DataRootLabel = 'AUTOMEDIA_ROOT'
}
$Runtime = Join-Path $DataRoot 'runtime'

Write-Host ''
Write-Host 'AutoMedia install'
Write-Host ('  repo root : ' + (ConvertTo-AsciiText $Root))
Write-Host ('  data root : ' + (ConvertTo-AsciiText $DataRoot) + '  (' + $DataRootLabel + ')')
if ($DryRun) { Write-Host '  mode      : DRY RUN - nothing will be written' }
else { Write-Host '  mode      : apply' }
Write-Host ''

# ---------------------------------------------------------------------------
# Find a Python interpreter: project runtime first, then PATH
# ---------------------------------------------------------------------------
$Py = $null
$PyOrigin = ''
if (Test-Path $Runtime) {
    foreach ($candidate in @(
            (Join-Path $Runtime 'python\python.exe'),
            (Join-Path $Runtime 'python\bin\python3'),
            (Join-Path $Runtime 'python\python'))) {
        if (-not $Py -and (Test-Path $candidate)) {
            $Py = $candidate
            $PyOrigin = 'runtime/python'
        }
    }
}
if (-not $Py) {
    $Py = Find-CommandPath @('python', 'python3', 'py')
    if ($Py) { $PyOrigin = 'system python' }
}

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
if ($SkipChecks) {
    Write-Host '[checks] skipped (-SkipChecks)'
} else {
    Write-Host '[checks]'

    if (-not $Py) {
        Report-Check 'Python' 'not found - install Python 3.11+ (or put runtime/python under the data root)' 'fail'
    } else {
        $verResult = Invoke-PyOutput $Py "import sys;print('%d.%d' % sys.version_info[:2])"
        $verText = ([string]$verResult.Text).Trim()
        if ($verResult.ExitCode -ne 0 -or -not $verText) {
            Report-Check 'Python' ('cannot execute: ' + (ConvertTo-AsciiText $Py)) 'fail'
        } else {
            $verText = ([string]$verText).Trim()
            $parts = $verText.Split('.')
            $versionOk = $false
            if ($parts.Length -ge 2) {
                $major = 0
                $minor = 0
                [void][int]::TryParse($parts[0], [ref]$major)
                [void][int]::TryParse($parts[1], [ref]$minor)
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 11)) { $versionOk = $true }
            }
            $detail = 'Python ' + $verText + ' (' + $PyOrigin + ')'
            if ($versionOk) { Report-Check 'Python' $detail 'ok' }
            else { Report-Check 'Python' ($detail + ' - need >= 3.11') 'fail' }
        }
    }

    if ($Py) {
        if ((Invoke-PyCheck $Py 'import patchright') -eq 0) {
            Report-Check 'patchright' 'import ok' 'ok'
        } else {
            Report-Check 'patchright' 'not importable - pip install patchright (or use runtime/python)' 'fail'
        }
    } else {
        Report-Check 'patchright' 'skipped (no Python)' 'warn'
    }

    $chrome = $null
    if ($env:CHROMIUM_PATH -and (Test-Path $env:CHROMIUM_PATH)) { $chrome = $env:CHROMIUM_PATH }
    if (-not $chrome -and $env:CHROME_PATH -and (Test-Path $env:CHROME_PATH)) { $chrome = $env:CHROME_PATH }
    if (-not $chrome) {
        $chrome = Find-FirstFile $Runtime @(
            'browsers\chromium-*\chrome-win64\chrome.exe',
            'browsers\chromium-*\chrome-linux\chrome',
            'browsers\chromium-*\chrome-linux64\chrome',
            'browsers\chrome-*\chrome-win64\chrome.exe')
    }
    if (-not $chrome -and $env:LOCALAPPDATA) {
        $chrome = Find-FirstFile (Join-Path $env:LOCALAPPDATA 'ms-playwright') @(
            'chromium-*\chrome-win64\chrome.exe',
            'chromium-*\chrome-linux\chrome')
    }
    if (-not $chrome) {
        $chrome = Find-CommandPath @('chrome.exe', 'chromium', 'chrome')
    }
    if ($chrome) { Report-Check 'Chromium' (ConvertTo-AsciiText $chrome) 'ok' }
    else { Report-Check 'Chromium' 'not found - put it in runtime/browsers/ or run: patchright install chromium' 'fail' }

    $ffmpeg = $null
    if ($env:FFMPEG_PATH -and (Test-Path $env:FFMPEG_PATH)) { $ffmpeg = $env:FFMPEG_PATH }
    if (-not $ffmpeg) {
        $ffmpeg = Find-FirstFile $Runtime @(
            'python\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg*.exe',
            'python\lib\site-packages\imageio_ffmpeg\binaries\ffmpeg*',
            'python\Scripts\ffmpeg.exe',
            'ffmpeg\bin\ffmpeg.exe',
            'ffmpeg\bin\ffmpeg')
    }
    if (-not $ffmpeg) { $ffmpeg = Find-CommandPath @('ffmpeg', 'ffmpeg.exe') }
    if ($ffmpeg) { Report-Check 'ffmpeg' (ConvertTo-AsciiText $ffmpeg) 'ok' }
    else { Report-Check 'ffmpeg' 'not found - put ffmpeg under runtime/ or add it to PATH' 'fail' }

    if ($Py) {
        if ((Invoke-PyCheck $Py 'import faster_whisper') -eq 0) {
            Report-Check 'faster-whisper' 'import ok' 'ok'
        } else {
            Report-Check 'faster-whisper' 'not installed (optional, ASR only) - warn only' 'warn'
        }
    } else {
        Report-Check 'faster-whisper' 'skipped (no Python)' 'warn'
    }
}
Write-Host ''

# ---------------------------------------------------------------------------
# Actions: data directories
# ---------------------------------------------------------------------------
$InfoSourceName = '1' + [char]0x4FE1 + [char]0x606F + [char]0x6E90
$dirs = @(
    @{ Rel = 'data\secrets'; Label = 'login state + secrets' },
    @{ Rel = '1AMdata'; Label = 'collection / distill output' },
    @{ Rel = $InfoSourceName; Label = 'news-source materials' },
    @{ Rel = '.cache'; Label = 'cache / temp' }
)

Write-Host '[actions]'
foreach ($item in $dirs) {
    $path = Join-Path $DataRoot $item.Rel
    if (Test-Path $path) {
        Write-Pass ('exists  : ' + (ConvertTo-AsciiText $path) + '  (' + $item.Label + ')')
    } elseif ($DryRun) {
        Write-Plan ('mkdir   : ' + (ConvertTo-AsciiText $path) + '  (' + $item.Label + ')')
    } else {
        try {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
            Write-Pass ('created : ' + (ConvertTo-AsciiText $path) + '  (' + $item.Label + ')')
        } catch {
            $script:Fatal++
            Write-Miss ('mkdir failed: ' + (ConvertTo-AsciiText $path) + ' - ' + (ConvertTo-AsciiText $_.Exception.Message))
        }
    }
}

# ---------------------------------------------------------------------------
# Actions: link the four skills into a DSH workspace (<ProjectRoot>\skills\)
# ---------------------------------------------------------------------------
if ($ProjectRoot) {
    Write-Host ''
    Write-Host '[dsh links]'
    $projectPath = [System.IO.Path]::GetFullPath($ProjectRoot)
    if (-not (Test-Path $projectPath)) {
        $script:Fatal++
        Write-Miss ('ProjectRoot not found: ' + (ConvertTo-AsciiText $projectPath))
    } else {
        $skillsDir = Join-Path $projectPath 'skills'
        foreach ($skill in @('bilibili-auto', 'douyin-auto', 'creator-distill', 'news-source')) {
            $src = Join-Path $Root $skill
            $dst = Join-Path $skillsDir $skill
            if (-not (Test-Path $src)) {
                $script:Fatal++
                Write-Miss ('missing skill directory in repo: ' + $skill)
                continue
            }
            if (Test-Path $dst) {
                $existing = Get-Item $dst -Force
                $currentTarget = ''
                if ($existing.LinkType) { $currentTarget = [string](@($existing.Target)[0]) }
                if ($currentTarget -and
                    ($currentTarget.TrimEnd('\', '/') -ieq ([string]$src).TrimEnd('\', '/'))) {
                    Write-Pass ('link ok : ' + (ConvertTo-AsciiText $dst))
                } else {
                    Write-Note ('exists, left untouched: ' + (ConvertTo-AsciiText $dst))
                }
            } elseif ($DryRun) {
                Write-Plan ('junction: ' + (ConvertTo-AsciiText $dst) + ' -> ' + (ConvertTo-AsciiText $src))
            } else {
                $linked = $false
                try {
                    if (-not (Test-Path $skillsDir)) {
                        New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
                    }
                    New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
                    $linked = Test-Path $dst
                } catch {
                    $linked = $false
                }
                if (-not $linked) {
                    $previous = $ErrorActionPreference
                    $ErrorActionPreference = 'Continue'
                    try {
                        & cmd.exe /c ('mklink /J "' + $dst + '" "' + $src + '"') 2>&1 | Out-Null
                    } finally {
                        $ErrorActionPreference = $previous
                    }
                    $linked = Test-Path $dst
                }
                if ($linked) {
                    Write-Pass ('linked  : ' + (ConvertTo-AsciiText $dst) + ' -> ' + (ConvertTo-AsciiText $src))
                } else {
                    $script:Fatal++
                    Write-Miss ('link failed: ' + (ConvertTo-AsciiText $dst))
                }
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Actions: install Python dependencies
# ---------------------------------------------------------------------------
if ($InstallDeps) {
    Write-Host ''
    Write-Host '[python deps]'
    $requirements = Join-Path $Root 'requirements.txt'
    if (-not $Py) {
        $script:Fatal++
        Write-Miss 'cannot install deps: Python not found'
    } elseif (-not (Test-Path $requirements)) {
        $script:Fatal++
        Write-Miss ('requirements.txt not found: ' + (ConvertTo-AsciiText $requirements))
    } elseif ($DryRun) {
        Write-Plan ('run: "' + (ConvertTo-AsciiText $Py) + '" -m pip install -r "' +
            (ConvertTo-AsciiText $requirements) + '"')
    } else {
        Write-Do ('pip install -r requirements.txt (' + $PyOrigin + ')')
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & $Py -m pip install -r $requirements
            $pipCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previous
        }
        if ($pipCode -ne 0) {
            $script:Fatal++
            Write-Miss ('pip install failed (exit ' + $pipCode + ')')
        } else {
            Write-Pass 'dependencies installed'
        }
    }
}

# ---------------------------------------------------------------------------
# Summary + next steps
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '[summary]'
if ($SkipChecks) {
    Write-Host '  checks : skipped (-SkipChecks)'
    Write-Host ('  actions: ' + $script:Fatal + ' fatal, ' + $script:Issues + ' warning')
} elseif ($script:Fatal -gt 0) {
    Write-Host ('  result : ' + $script:Fatal + ' fatal issue(s), ' + $script:Issues + ' warning(s)')
} elseif ($script:Issues -gt 0) {
    Write-Host ('  result : ok, ' + $script:Issues + ' warning(s)')
} else {
    Write-Host '  result : all checks passed'
}
Write-Host ''
Write-Host 'Next steps:'
Write-Host '  1) Log in to the platforms you need (login state stays on this machine):'
Write-Host '     - Bilibili : put data\sau\cookies\bilibili_*.json (exported by biliup)'
Write-Host '     - Douyin   : python douyin-auto\scripts\douyin_login.py --profile data\social\douyin-verify-profile --timeout 600'
Write-Host '     - Xiaohongshu: scan the QR code in the profile at data\accounts\xiaohongshu\profile'
Write-Host '  2) Self-check : python scripts\doctor.py'
Write-Host '  3) Feishu     : python scripts\feishu_setup.py   (optional, for notifications)'
Write-Host ''

if ($DryRun) {
    Write-Host 'Dry run complete: nothing was created or modified.'
    exit 0
}
if ($script:Fatal -gt 0) {
    Write-Host ('Install finished with ' + $script:Fatal + ' problem(s). Fix the [x] lines above, then rerun.')
    exit 1
}
Write-Host 'Install complete.'
exit 0
