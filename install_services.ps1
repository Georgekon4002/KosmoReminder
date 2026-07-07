$ErrorActionPreference = "Stop"

# Ensure running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Please run this script as Administrator!" -ForegroundColor Red
    Exit
}

$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$nssmZip = "$PSScriptRoot\nssm.zip"
$nssmDir = "$PSScriptRoot\nssm-2.24"
$nssmExe = "$nssmDir\win64\nssm.exe"

# Download and extract NSSM if not present
if (-not (Test-Path $nssmExe)) {
    Write-Host "Downloading NSSM from $nssmUrl..."
    Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip
    Write-Host "Extracting NSSM..."
    Expand-Archive -Path $nssmZip -DestinationPath $PSScriptRoot -Force
    Remove-Item $nssmZip
}

$pythonExe = (python -c "import sys; print(sys.executable)")
if (-not $pythonExe) {
    Write-Host "Python not found in PATH. Please install Python and add it to PATH." -ForegroundColor Red
    Exit
}

# 1. Reminder Service
$service1 = "KosmoSMS_ReminderService"
Write-Host "Installing $service1..."
& $nssmExe stop $service1
& $nssmExe remove $service1 confirm

& $nssmExe install $service1 "$pythonExe" "$PSScriptRoot\src\reminder_service.py"
& $nssmExe set $service1 AppDirectory "$PSScriptRoot"
& $nssmExe set $service1 Description "KosmoSMS Background Reminder Engine"
& $nssmExe set $service1 AppStdout "$PSScriptRoot\logs\reminder-service-nssm.log"
& $nssmExe set $service1 AppStderr "$PSScriptRoot\logs\reminder-service-nssm.log"
& $nssmExe start $service1

# 2. Callback Receiver
$service2 = "KosmoSMS_CallbackReceiver"
Write-Host "Installing $service2..."
& $nssmExe stop $service2
& $nssmExe remove $service2 confirm

& $nssmExe install $service2 "$pythonExe" "$PSScriptRoot\src\callback_receiver.py"
& $nssmExe set $service2 AppDirectory "$PSScriptRoot"
& $nssmExe set $service2 Description "KosmoSMS Webhook Receiver & API"
& $nssmExe set $service2 AppStdout "$PSScriptRoot\logs\callback-receiver-nssm.log"
& $nssmExe set $service2 AppStderr "$PSScriptRoot\logs\callback-receiver-nssm.log"
& $nssmExe start $service2

# 3. Email Reminder Service
$service3 = "KosmoSMS_EmailReminderService"
Write-Host "Installing $service3..."
& $nssmExe stop $service3
& $nssmExe remove $service3 confirm

& $nssmExe install $service3 "$pythonExe" "$PSScriptRoot\src\email_reminder_service.py"
& $nssmExe set $service3 AppDirectory "$PSScriptRoot"
& $nssmExe set $service3 Description "KosmoSMS Background Email Reminder Engine"
& $nssmExe set $service3 AppStdout "$PSScriptRoot\logs\email-reminder-service-nssm.log"
& $nssmExe set $service3 AppStderr "$PSScriptRoot\logs\email-reminder-service-nssm.log"
& $nssmExe start $service3

Write-Host "Services installed and started successfully!" -ForegroundColor Green
