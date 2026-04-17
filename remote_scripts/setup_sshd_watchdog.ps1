# setup_sshd_watchdog.ps1
# Installs a scheduled task that checks SSHD health every 5 minutes.
# If port 22 is unresponsive, SSHD is restarted automatically.
#
# Run once on each lab PC (requires Administrator):
#   powershell -ExecutionPolicy Bypass -File setup_sshd_watchdog.ps1

$TaskName   = "SSHD Watchdog"
$LogDir     = "C:\2026"
$ScriptPath = Join-Path $LogDir "sshd_watchdog.ps1"
$LogPath    = Join-Path $LogDir "sshd_watchdog.log"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Watchdog body written to its own .ps1 so Task Scheduler invokes it with
# -File (a path), not -Command (a multi-line blob that gets mangled when
# stored in the task's single argument string).
$watchdog = @'
$ErrorActionPreference = "Continue"
$LogPath   = "C:\2026\sshd_watchdog.log"
$StateFile = "C:\2026\sshd_watchdog.state"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Test-SshBanner {
    param([int]$TimeoutMs = 15000)
    try {
        $tcp = New-Object Net.Sockets.TcpClient
        $tcp.ReceiveTimeout = $TimeoutMs
        $tcp.Connect("127.0.0.1", 22)   # force IPv4; avoid ::1 dual-stack slowness
        $stream = $tcp.GetStream()
        $buf = New-Object byte[] 256
        $n = $stream.Read($buf, 0, 256)
        $banner = [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
        $tcp.Close()
        return ($banner -like "SSH-*")
    } catch {
        return $false
    }
}

# Three preconditions have to fail before we restart — avoids thrash from a
# slow first-banner or a Defender scan stall on sshd-session.exe spawn.
$svcRunning = (Get-Service sshd -ErrorAction SilentlyContinue).Status -eq 'Running'
$listening  = [bool](Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
$banner     = Test-SshBanner -TimeoutMs 15000

if ($svcRunning -and $listening -and $banner) {
    Add-Content -Path $LogPath -Value "$ts - OK"
    Set-Content -Path $StateFile -Value "0"
    return
}

# Require TWO consecutive failures before restarting. Transient banner timeouts
# under SYSTEM + Defender scanning are normal and recover on their own.
$fails = 0
if (Test-Path $StateFile) { $fails = [int](Get-Content $StateFile -ErrorAction SilentlyContinue) }
$fails++
Set-Content -Path $StateFile -Value $fails

Add-Content -Path $LogPath -Value "$ts - unhealthy (svc=$svcRunning listen=$listening banner=$banner) fails=$fails"

if ($fails -lt 2) { return }

Add-Content -Path $LogPath -Value "$ts - restarting sshd after $fails consecutive failures..."
Restart-Service sshd -Force
Start-Sleep 3
Add-Content -Path $LogPath -Value "$ts - sshd status: $((Get-Service sshd).Status)"
Set-Content -Path $StateFile -Value "0"
'@

Set-Content -Path $ScriptPath -Value $watchdog -Encoding UTF8

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""

# Start 1 minute from now so the first run happens promptly after registration.
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -User "SYSTEM" -RunLevel Highest -Force

Write-Host "Installed scheduled task '$TaskName' (runs every 5 minutes as SYSTEM)."
Write-Host "Watchdog script: $ScriptPath"
Write-Host "Log file:        $LogPath"
Write-Host ""
Write-Host "To force a run now:   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To verify it ran:     Get-Content '$LogPath' -Tail 5"
