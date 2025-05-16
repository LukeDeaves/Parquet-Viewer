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

- Python 3.8 or higher
- Operating System:
    - Windows
    - macOS _[Untested]_
    - Linux _[Untested]_

## Installation

1. Clone this repository
2. Run the setup script to install the required dependencies:
   ```
   .\tools\setup_machine.ps1
   ```

## Usage

1. Run the application:
   ```
   python main.py
   ```
2. Use File > Open to open a Parquet file
3. Navigate and edit data in the table view
4. Toggle edit mode to make changes to cells
5. Use the status bar to view statistics about selected data
6. Save your changes using File > Save or Save As

To create a standalone executable for `Parquet Viewer.exe` in the `dist` directory, you can compile the project using one of the following methods:

**Using PyInstaller:**
   ```
   pyinstaller --onefile --windowed --name "Parquet Viewer" main.py
   ```
   - **File Size:** Larger executable size
   - **Summary:** PyInstaller offers a faster compilation process, but it produces larger executable files that are more susceptible to reverse engineering.

**Using Nuitka:**
   ```
   nuitka --standalone --onefile --windows-console-mode=disable --enable-plugin=pyqt5 main.py --output-filename="Parquet Viewer.exe" --output-dir=dist
   ```
   - **File Size:** Smaller executable size
   - **Summary:** Nuitka transforms Python code into optimized C++ code, producing more efficient executables with reduced file sizes and improved performance.
