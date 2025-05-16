# run_application.ps1

# Get current directory
$currentDir = Get-Location
$mainScript = "main.py"
$mainScriptPath = Join-Path -Path $currentDir -ChildPath $mainScript

# Check if main.py exists
if (-not (Test-Path $mainScriptPath)) {
    Write-Error "main.py not found in current directory: $currentDir"
    exit 1
}

# Confirm Python is installed
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed or not in PATH."
    exit 1
}

# Run the application
Write-Output "Starting application..."
python main.py

if ($LASTEXITCODE -eq 0) {
    Write-Output "Application completed successfully."
} else {
    Write-Error "Application failed to run."
} 