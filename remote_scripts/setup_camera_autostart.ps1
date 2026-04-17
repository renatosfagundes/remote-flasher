# setup_camera_autostart.ps1
# Installs a scheduled task that starts the MJPEG camera server on boot/logon.
# Also creates a helper script (start_camera.ps1) for manual restarts.
#
# Run once on the camera PC (requires Administrator):
#   powershell -ExecutionPolicy Bypass -File setup_camera_autostart.ps1

$CameraDir   = "C:\dev\camera"
$PythonExe   = "$CameraDir\venv\Scripts\python.exe"
$CameraScript = "$CameraDir\camera1.py"
$TaskName     = "Camera MJPEG Server"
$HelperScript = "$CameraDir\start_camera.ps1"

# Verify paths exist
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: $PythonExe not found. Is the venv set up?" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $CameraScript)) {
    Write-Host "ERROR: $CameraScript not found." -ForegroundColor Red
    exit 1
}

# Create a helper script for manual starts (no venv activation needed —
# we call the venv's python.exe directly).
$helperContent = @"
# start_camera.ps1 — Start the MJPEG camera server.
# Uses the venv python directly, no activation needed.
Set-Location "$CameraDir"
& "$PythonExe" "$CameraScript"
"@
Set-Content -Path $HelperScript -Value $helperContent -Encoding UTF8
Write-Host "Created helper: $HelperScript"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# The task calls venv python directly (no Activate.ps1 needed).
$action  = New-ScheduledTaskAction -Execute $PythonExe `
    -Argument "`"$CameraScript`"" -WorkingDirectory $CameraDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd `
    -ExecutionTimeLimit ([TimeSpan]::Zero)  # run indefinitely

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -User "SYSTEM" -RunLevel Highest -Force

Write-Host ""
Write-Host "Installed scheduled task '$TaskName' (runs at startup as SYSTEM)."
Write-Host "The camera server will start automatically on next boot."
Write-Host ""
Write-Host "To start it NOW without rebooting:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
