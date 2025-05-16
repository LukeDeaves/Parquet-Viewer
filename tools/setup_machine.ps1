# setup_machine.ps1

# Get current directory
$currentDir = Get-Location
$requirementsFile = "requirements.txt"
$requirementsPath = Join-Path -Path $currentDir -ChildPath $requirementsFile

# Check if requirements.txt exists
if (-not (Test-Path $requirementsPath)) {
    Write-Error "requirements.txt not found in current directory: $currentDir"
    exit 1
}

# Confirm Python is installed
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed or not in PATH."
    exit 1
}

# Install dependencies using Python's pip
Write-Output "Installing packages from requirements.txt..."
python -m pip install -r "$requirementsPath"

if ($LASTEXITCODE -eq 0) {
    Write-Output "Environment setup complete."
} else {
    Write-Error "Package installation failed."
}