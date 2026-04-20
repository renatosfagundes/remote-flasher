# setup_serialterm_janitor.ps1
# Installs a scheduled task that kills orphaned serialterm.py processes.
# Any python.exe running serialterm.py longer than MAX_MINUTES is terminated,
# releasing the COM port it was holding.
#
# Runs every 5 minutes as SYSTEM (needs admin to kill any user's process).
#
# Run once on each lab PC (requires Administrator):
#   powershell -ExecutionPolicy Bypass -File setup_serialterm_janitor.ps1

$TaskName   = "Serialterm + Avrdude Janitor"
$LogDir     = "C:\2026"
$ScriptPath = Join-Path $LogDir "serialterm_janitor.ps1"
$LogPath    = Join-Path $LogDir "serialterm_janitor.log"

# Maximum lifetime (minutes) for any serialterm.py instance. Raise if
# students regularly run serial sessions longer than this.
$MaxMinutes = 15

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Janitor body written to its own .ps1 so Task Scheduler invokes it with
# -File (a path), avoiding multi-line -Command escaping headaches.
$janitor = @"
`$ErrorActionPreference = "Continue"
`$LogPath    = "$LogPath"
`$MaxMinutes = $MaxMinutes
`$ts         = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Candidates: serialterm.py instances AND avrdude.exe instances. Both can
# orphan on COM ports after a failed flash / closed SSH session.
#
# The Python side must NOT filter by Name='python.exe' — Microsoft Store
# and per-user Python installs run as python3.11.exe / python3.12.exe /
# etc. A Name='python.exe' filter silently misses every orphan on those
# machines (observed in the lab: PID 7284 ran serialterm.py as
# python3.11.exe and was invisible to the old filter). Match on
# command-line content instead; the camera's pythonw.exe running
# camera1.py has no 'serialterm' in args so it's safely excluded.
`$procs = @(
    Get-CimInstance Win32_Process |
        Where-Object { `$_.CommandLine -like '*serialterm*' }
    Get-CimInstance Win32_Process -Filter "Name='avrdude.exe'"
)

if (-not `$procs) {
    Add-Content -Path `$LogPath -Value "`$ts - idle"
    return
}

foreach (`$p in `$procs) {
    `$ageMin = [int](New-TimeSpan -Start `$p.CreationDate -End (Get-Date)).TotalMinutes
    `$port   = "?"
    if (`$p.CommandLine -match '--port\s+(\S+)') { `$port = `$Matches[1] }
    elseif (`$p.CommandLine -match '-P\s+(\S+)')  { `$port = `$Matches[1] }

    # If the parent SSH session is gone, the child is orphaned and should
    # be killed regardless of age — the parent is what would have cleaned
    # it up on a normal exit, so its absence means the port will never be
    # released otherwise.
    #
    # Important: Windows does NOT reparent orphans to the init process
    # (unlike Linux). An orphan keeps its original ParentProcessId, and
    # that PID may have been recycled to an unrelated process. Get-Process
    # would then return that unrelated process and we'd treat the orphan
    # as live. Guard against that by also requiring the parent's
    # CreationDate to be earlier than the child's — if the parent appears
    # younger, its PID has been recycled and the child is truly orphaned.
    `$parent = Get-CimInstance Win32_Process -Filter "ProcessId=`$(`$p.ParentProcessId)" -ErrorAction SilentlyContinue
    `$parentAlive = (`$null -ne `$parent) -and (`$parent.CreationDate -le `$p.CreationDate)

    if (-not `$parentAlive -or `$ageMin -gt `$MaxMinutes) {
        `$reason = if (-not `$parentAlive) {
            if (`$null -eq `$parent) { "orphaned (no parent)" } else { "orphaned (PID recycled)" }
        } else { "age=`${ageMin}m > `$MaxMinutes" }
        Add-Content -Path `$LogPath -Value "`$ts - killing `$(`$p.Name) PID=`$(`$p.ProcessId) port=`$port (`$reason)"
        Stop-Process -Id `$p.ProcessId -Force -ErrorAction SilentlyContinue
    } else {
        Add-Content -Path `$LogPath -Value "`$ts - keeping `$(`$p.Name) PID=`$(`$p.ProcessId) port=`$port age=`${ageMin}m"
    }
}
"@

Set-Content -Path $ScriptPath -Value $janitor -Encoding UTF8

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""

# Start 1 minute from now and repeat every 5 minutes indefinitely.
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -User "SYSTEM" -RunLevel Highest -Force

Write-Host "Installed scheduled task '$TaskName' (runs every 5 minutes as SYSTEM)."
Write-Host "Kills serialterm.py older than $MaxMinutes minutes or whose parent SSH session died."
Write-Host "Janitor script: $ScriptPath"
Write-Host "Log file:       $LogPath"
Write-Host ""
Write-Host "To force a run now:   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To verify it ran:     Get-Content '$LogPath' -Tail 10"
