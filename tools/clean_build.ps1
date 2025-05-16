# clean_build.ps1

# Get current directory
$currentDir = Get-Location

# Define paths
$distFolder = Join-Path -Path $currentDir -ChildPath "dist"

# Remove 'build' folder
$buildPath = Join-Path -Path $currentDir -ChildPath "build"
if (Test-Path $buildPath) {
    Remove-Item -Path $buildPath -Recurse -Force
    Write-Output "Deleted folder: build"
} else {
    Write-Output "Folder not found: build"
}

# Remove 'dist' folder
if (Test-Path $distFolder) {
    Remove-Item -Path $distFolder -Recurse -Force
    Write-Output "Deleted folder: dist"
} else {
    Write-Output "Folder not found: dist"
}

# Delete the .spec file
$specFile = Join-Path -Path $currentDir -ChildPath "Parquet Viewer.spec"
if (Test-Path $specFile) {
    Remove-Item -Path $specFile -Force
    Write-Output "Deleted file: Parquet Viewer.spec"
} else {
    Write-Output "File not found: Parquet Viewer.spec"
}

# Delete the nuitka-crash-report.xml file
$crashReportFile = Join-Path -Path $currentDir -ChildPath "nuitka-crash-report.xml"
if (Test-Path $crashReportFile) {
    Remove-Item -Path $crashReportFile -Force
    Write-Output "Deleted file: nuitka-crash-report.xml"
} else {
    Write-Output "File not found: nuitka-crash-report.xml"
}