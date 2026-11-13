# run_makeup2_when_free.ps1
# Start queue_makeup_p2.txt on WHICHEVER Douyin account becomes free first.
# Replaces the account2-only watcher so the second account does not idle.
# Keep this file pure ASCII.
$ErrorActionPreference = 'Continue'

$Here  = Split-Path -Parent $PSCommandPath            # ...\douyin-auto\scripts
$Skill = Split-Path -Parent $Here                     # ...\douyin-auto
$Proj  = Split-Path -Parent (Split-Path -Parent $Skill)
$LogDir = Join-Path $Skill 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'makeup2-chain.log'
$Lock = Join-Path $LogDir 'makeup2.lock'
$Q2 = Join-Path $Skill 'config\queue_makeup_p2.txt'
$Rq = Join-Path $Here 'run_queue.ps1'

function Note($m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Add-Content -Path $Log -Value $line -Encoding UTF8
    Set-Content -Path (Join-Path $LogDir 'makeup2-status.txt') -Value $m -Encoding UTF8
}

if (Test-Path $Lock) { Note "lock exists, another makeup2 starter already ran"; exit 0 }

# Resolve both profiles without hardcoding Chinese paths.
$Profiles = @()
foreach ($d in Get-ChildItem (Join-Path $Proj 'data\social') -Directory -ErrorAction SilentlyContinue) {
    if ($d.Name -like '*verify*')     { $Profiles += @{ Name = 'acct1'; Path = $d.FullName } }
    elseif ($d.Name -like '*account2*') { $Profiles += @{ Name = 'acct2'; Path = $d.FullName } }
}
if ($Profiles.Count -eq 0) { Note "no douyin profiles found"; exit 1 }

function Get-CollectorCount($path) {
    $leaf = Split-Path $path -Leaf
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*douyin_collect.py*' -and $_.CommandLine -like "*$leaf*" }).Count
}

Note ("watching profiles: " + (($Profiles | ForEach-Object { $_.Name }) -join ', '))
$idle = @{}
foreach ($p in $Profiles) { $idle[$p.Name] = 0 }

$deadline = (Get-Date).AddHours(36)
while ((Get-Date) -lt $deadline) {
    if (Test-Path $Lock) { Note "lock appeared, exit"; exit 0 }
    foreach ($p in $Profiles) {
        $n = Get-CollectorCount $p.Path
        if ($n -gt 0) { $idle[$p.Name] = 0; continue }
        $idle[$p.Name]++
        if ($idle[$p.Name] -ge 3) {
            if (-not (Test-Path $Q2)) { Note "queue_makeup_p2 missing"; exit 2 }
            $cnt = (Get-Content $Q2 -Encoding UTF8 | Where-Object { $_ -match '^https?://' }).Count
            Note ("account {0} is free; starting makeup2 ({1} accounts)" -f $p.Name, $cnt)
            New-Item -ItemType File -Path $Lock -Force | Out-Null
            $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$Rq`"",
                      '-LinksFile',"`"$Q2`"",'-TopPlay','10','-Latest','5','-Comments','20',
                      '-Gap','55','-Scroll','4','-Profile',"`"$($p.Path)`"",
                      '-StatusTag',("makeup2-" + $p.Name))
            $proc = Start-Process powershell.exe -ArgumentList $args -WindowStyle Hidden -PassThru
            Note ("makeup2 started on {0}, pid={1}" -f $p.Name, $proc.Id)
            exit 0
        }
    }
    Start-Sleep -Seconds 180
}
Note "deadline reached without a free account"

