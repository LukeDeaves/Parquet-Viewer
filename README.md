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

1. Clone this repository
2. Run the setup script to install the required dependencies:
   ```
   .\tools\setup_machine.ps1
   ```

## Usage

1. Run the application:
   ```
   .\tools\run_application.ps1
   ```
2. Use File > Open to open a Parquet file
3. Navigate and edit data in the table view
4. Toggle edit mode to make changes to cells
5. Use the status bar to view statistics about selected data
6. Save your changes using File > Save or Save As

> [!TIP]
> To create a standalone executable for `Parquet Viewer.exe` in the `dist` directory, you can run the PowerShell script `.\tools\run_build.ps1`