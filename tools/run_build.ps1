# run_build.ps1

# Get current directory
$currentDir = Get-Location
$script = "main.py"
$outputName = "Parquet Viewer.exe"
$outputDir = "dist"
$outputFolder = "build_output"  # Define the output folder for the .exe

# Set required environment variable
$env:MPLBACKEND = "TkAgg"
Write-Output "Set MPLBACKEND to TkAgg"

# Check if Nuitka is installed
if (-not (Get-Command "nuitka" -ErrorAction SilentlyContinue)) {
    Write-Error "Nuitka is not installed or not in PATH."
    exit 1
}

# Check if the main script exists
$scriptPath = Join-Path -Path $currentDir -ChildPath $script
if (-not (Test-Path $scriptPath)) {
    Write-Error "Could not find $script in the current directory."
    exit 1
}

# Ensure output folder exists
$outputPath = Join-Path -Path $currentDir -ChildPath $outputDir
if (-not (Test-Path $outputPath)) {
    New-Item -ItemType Directory -Path $outputPath | Out-Null
    Write-Output "Created output directory: $outputDir"
}

# Ensure build_output folder exists and is emptied
$outputFolderPath = Join-Path -Path $currentDir -ChildPath $outputFolder
if (-not (Test-Path $outputFolderPath)) {
    New-Item -ItemType Directory -Path $outputFolderPath | Out-Null
    Write-Output "Created output directory: $outputFolder"
} else {
    # Empty the build_output folder
    Remove-Item -Path "$outputFolderPath\*" -Recurse -Force
    Write-Output "Emptied output directory: $outputFolder"
}

# Run the build with Nuitka
Write-Output "Building project with Nuitka..."
nuitka --standalone --onefile --windows-console-mode=disable --enable-plugin=pyqt5 `
       "$script" --output-filename="$outputName" --output-dir="$outputDir"
# pyinstaller --onefile --windowed --name "Parquet Viewer" main.py
Write-Output "Build finished. Output: $outputDir\$outputName"

# Move the .exe to the build_output folder
$exeSource = Join-Path -Path $outputPath -ChildPath $outputName
$exeDestination = Join-Path -Path $outputFolderPath -ChildPath $outputName
if (Test-Path $exeSource) {
    Move-Item -Path $exeSource -Destination $exeDestination -Force
    Write-Output "Moved $outputName to $outputFolder"
    
    # Run clean_build.ps1 if the .exe was successfully moved
    $cleanBuildScript = Join-Path -Path $currentDir -ChildPath "tools\clean_build.ps1"
    if (Test-Path $cleanBuildScript) {
        & $cleanBuildScript
    } else {
        Write-Error "clean_build.ps1 not found in the current directory."
    }
} else {
    Write-Output "$outputName not found in $outputDir"
}