param([Parameter(Mandatory=$true)][string]$Port)
$p = New-Object System.IO.Ports.SerialPort $Port,19200,None,8,One
$p.Open()
$p.WriteLine("AT RT")
$p.Close()
