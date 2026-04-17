# setup_sshd_watchdog.ps1
# Installs a scheduled task that checks SSHD health every 5 minutes.
# If port 22 is unresponsive, SSHD is restarted automatically.
#
# Run once on each lab PC (requires Administrator):
#   powershell -ExecutionPolicy Bypass -File setup_sshd_watchdog.ps1

$TaskName = "SSHD Watchdog"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# The check: TCP connect to port 22 and verify we get an SSH banner
# (e.g. "SSH-2.0-OpenSSH_..."). A hung SSHD can accept TCP connections
# but never send the banner — a bare TCP check misses that.
$script = @'
$healthy = $false
try {
    $tcp = New-Object Net.Sockets.TcpClient
    $tcp.Connect("localhost", 22)
    $tcp.ReceiveTimeout = 5000
    $stream = $tcp.GetStream()
    $buf = New-Object byte[] 256
    $n = $stream.Read($buf, 0, 256)
    $banner = [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
    if ($banner -like "SSH-*") { $healthy = $true }
    $tcp.Close()
} catch { }

if (-not $healthy) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path "C:\2026\sshd_watchdog.log" -Value "$ts - SSHD unhealthy (no SSH banner), restarting..."
    Restart-Service sshd -Force
    Start-Sleep 2
    Add-Content -Path "C:\2026\sshd_watchdog.log" -Value "$ts - SSHD restarted. Status: $((Get-Service sshd).Status)"
}
'@

$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command $script"
$trigger = New-ScheduledTaskTrigger -Once -At "00:00" `
    -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -User "SYSTEM" -RunLevel Highest -Force

Write-Host "Installed scheduled task '$TaskName' (runs every 5 minutes as SYSTEM)."
Write-Host "Log file: C:\2026\sshd_watchdog.log"
