# Ensure script runs with elevated privileges
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    echo "This script requires administrator privileges. Restarting as administrator..."
    Start-Process powershell "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# --- Check if winget is available ---
while (!(Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "The 'winget' command is unavailable." -ForegroundColor Red
    Write-Host "Please update 'App Installer' through Microsoft Store. Opening Store in 5 seconds..."
    Start-Sleep -Seconds 5
    Start-Process "ms-windows-store://pdp?hl=en-us&gl=us&productid=9nblggh4nns1"
    Write-Host "Press any key after update is complete..."
    $null = $host.UI.RawUI.ReadKey()
}

# --- Update winget sources and install packages ---
Write-Host "Updating winget sources..." -ForegroundColor Cyan
& winget source update

$packages = @(
    "akeo.ie.Zadig",
    "Git.Git",
    "Python.Python.3.9"
)

foreach ($package in $packages) {
    Write-Host "Installing $package..." -ForegroundColor Cyan
    & winget install --id=$package --accept-package-agreements --accept-source-agreements --disable-interactivity --scope machine
}

# --- Check for Git location ---
Write-Host "Checking for Git..." -ForegroundColor Cyan
$gitcmd = ""
if (Test-Path "${env:ProgramFiles}\Git\cmd\git.exe") {
    Write-Host "Git found in local Program Files."
    $gitcmd = "${env:ProgramFiles}\Git\cmd\git.exe"
} elseif (Get-Command "git" -ErrorAction SilentlyContinue) {
    Write-Host "Git Command found in PATH."
    $gitcmd = "git"
} else {
    Write-Host "Git not found, Aborting..." -ForegroundColor Red
    exit
}

# --- Clone the edl repository ---
$edlFolder = Join-Path $env:ProgramFiles "edl"

if (-not (Test-Path $edlFolder)) {
    Write-Host "Cloning edl repository into $edlFolder..." -ForegroundColor Cyan
    # Using the Call Operator & as requested
    & $gitcmd clone --recurse-submodules https://github.com/bkerler/edl.git $edlFolder
} else {
    Write-Host "EDL folder already exists. Skipping clone." -ForegroundColor Yellow
}

# --- Install Python dependencies ---
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
# Using 'python -m pip' is safer than hardcoding the pip3 path
& python -m pip install -r "$edlFolder\requirements.txt"

# --- Add edl to the system PATH ---
Write-Host "Updating system PATH..." -ForegroundColor Cyan
$currentPath = [Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::Machine)
$edlPath = Resolve-Path $edlFolder

if ($currentPath -split ';' -notcontains $edlPath) {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$edlPath", [System.EnvironmentVariableTarget]::Machine)
    Write-Host "Successfully added $edlPath to the system PATH." -ForegroundColor Green
} else {
    Write-Host "$edlPath is already in the system PATH." -ForegroundColor Yellow
}

# --- Final Instructions ---
Write-Host "`nSetup completed successfully!" -ForegroundColor Green
Write-Host "1. Run 'zadig' to install the WinUSB driver for QHSUSB_BULK devices."
Write-Host "2. Restart your terminal to use the 'edl' command."
Write-Host "`nPress any key to exit..."
$null = $host.UI.RawUI.ReadKey()
