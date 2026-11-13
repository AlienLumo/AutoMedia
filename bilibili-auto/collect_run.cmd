@echo off
chcp 65001 >nul
rem ============================================================
rem  BiliDeepCollect - one resumable chunk per invocation
rem  Registered by setup_deep_task.ps1 (repeats every 25 min)
rem  Tier1 speedup (2026-11-03): pace 1.3, rest-every 600, pool-cap 80
rem  2026-11-06: exit early once every account is finished, so the
rem              scheduled task no longer spins up the collector.
rem  NOTE: keep this file ASCII-only. cmd.exe reads .cmd in the ANSI
rem        codepage; non-ASCII comments break parsing.
rem ============================================================
cd /d "%~dp0"

set PY="%~dp0..\..\runtime\python\python.exe"
if not exist %PY% set PY=python
set LOG=logs\deep_run.log

if not exist logs mkdir logs

rem ---- skip when all accounts are finished -------------------
%PY% "scripts\deep_done_check.py"
if %ERRORLEVEL%==0 (
  echo [%date% %time%] [skip] all accounts finished, chunk skipped >> "%LOG%"
  exit /b 0
)

%PY% "scripts\bili_deep_collect.py" ^
  --max-requests 850 ^
  --pace 1.3 ^
  --rest-every 600 ^
  --cooldown 120 ^
  --comment-cap 100 ^
  --top-n 20 ^
  --pool-cap 80 ^
  --sub-langs zh >> "%LOG%" 2>&1

echo [%date% %time%] chunk exit=%ERRORLEVEL% >> "%LOG%"
