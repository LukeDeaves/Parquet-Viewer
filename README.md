# Parquet File Viewer

A desktop application for viewing, editing, and creating Parquet files.

## Features

- Open, view, and edit Parquet files
- Display data in a customizable table format
- Edit cell values with type validation
- Calculate statistics on selected data
- Column totals for numerical data
- Undo/redo functionality for all edits
- Save changes back to Parquet format
- _[Future]_ Export data to CSV and Excel formats
- Search and filter capabilities
- Sort data by columns
- Dark mode support

## Requirements

- Operating System:
   - Windows 11 or later
   - Windows 10 or earlier _(functionality not guaranteed)_

## Installation

1. Download the latest release from [GitHub Releases](https://github.com/LukeDeaves/Parquet-Viewer/tags).
2. Extract the zip asset file and run the `Parquet Viewer.exe` file. Note that this method may trigger the [⚠️ Windows Defender/SmartScreen Warning](#%EF%B8%8F-windows-defendersmartscreen-warning).

## Usage

1. Use File > Open to open a Parquet file.
2. Navigate and edit data in the table view.
3. Toggle edit mode to make changes to cells.
4. Use the status bar to view statistics about selected data.
5. Save your changes using File > Save or Save As.

## Advanced Users

### Additional Requirements

- Python 3.8 or higher

### Advanced Installation
1. Clone this repository.
2. Run the setup script to install the required dependencies:
   ```
   .\tools\setup_machine.ps1
   ```
3. Run the application using:
   ```
   .\tools\run_application.ps1
   ```
   Or build it using:
   ```
   .\tools\run_build.ps1
   ```

## ⚠️ Windows Defender/SmartScreen Warning

This app is not code-signed due to the high cost for indie developers. As a result, Windows may warn you that the file is unrecognised or potentially unsafe.  
If you downloaded this app from our official GitHub releases, it is safe to use.  
If you see a warning, you can right-click the file, select "Properties", and check "Unblock", or allow it in Windows Defender.

The source code is open and available for review here: [GitHub Repo Link](https://github.com/LukeDeaves/Parquet-Viewer)