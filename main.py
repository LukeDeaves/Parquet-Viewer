import sys
import os
import warnings
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                            QMenuBar, QMenu, QAction, QMessageBox, QFrame, QDialog, QLineEdit, QDialogButtonBox,
                            QLabel, QStatusBar, QTableWidgetSelectionRange)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPalette, QColor, QCursor
import configparser
from pathlib import Path
import numpy as np
from datetime import datetime
import shutil

# Suppress PyQt5 deprecation warning
warnings.filterwarnings("ignore", category=DeprecationWarning)

class ParquetViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parquet File Viewer")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumWidth(400)  # Set minimum window width
        
        # Initialize config
        self.config = configparser.ConfigParser()
        self.config_file = os.path.join(os.path.expanduser('~'), 'Documents', 'parquet_viewer.ini')
        
        # Initialize recent files list
        self.recent_files = []
        
        # Initialize editing state
        self.current_file = None
        self.original_df = None
        self.column_types = {}
        self.modified = False
        self.edit_mode = False
        self.modified_cells = set()  # Track modified cells (row, col)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.edit_mode_label = QLabel()
        self.modified_label = QLabel()
        self.status_bar.addPermanentWidget(self.edit_mode_label)
        self.status_bar.addPermanentWidget(self.modified_label)
        self.update_status_bar()
        
        # Load settings after menu creation
        self.load_settings()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create table widget to display data
        self.table = QTableWidget()
        self.table.setSortingEnabled(True)  # Enable sorting
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)  # Enable context menu
        self.table.customContextMenuRequested.connect(self.show_context_menu)  # Connect context menu signal
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)  # Enable multiple cell selection
        self.table.itemChanged.connect(self.on_cell_changed)  # Connect cell change signal
        
        # Configure header for right-click menu
        header = self.table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_filter_menu)
        header.setSectionsClickable(True)
        header.sectionResized.connect(self.on_column_resize)
        
        # Handle window resize events
        self.table.horizontalHeader().setStretchLastSection(True)  # Prevent horizontal scrollbar by default
        
        # Install event filter for keyboard shortcuts
        self.table.installEventFilter(self)
        
        layout.addWidget(self.table)
        
        # Store filter values
        self.filters = {}
        
        # Apply initial theme
        self.apply_theme()
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        self.file_menu = menubar.addMenu("File")
        open_action = QAction("Open Parquet File", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        self.file_menu.addAction(open_action)
        
        # Add Save actions
        self.save_action = QAction("Save", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_file)
        self.save_action.setEnabled(False)
        self.file_menu.addAction(self.save_action)
        
        self.save_as_action = QAction("Save As...", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_file_as)
        self.save_as_action.setEnabled(False)
        self.file_menu.addAction(self.save_as_action)
        
        self.file_menu.addSeparator()
        
        # Add recent files menu
        self.recent_menu = self.file_menu.addMenu("Recent Files")
        
        # Add global shortcut for Recent Files
        recent_shortcut = QAction("Recent Files", self)
        recent_shortcut.setShortcut("Ctrl+Shift+O")
        recent_shortcut.triggered.connect(self.show_recent_menu)
        self.addAction(recent_shortcut)
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        # Dark mode action
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        settings_menu.addAction(self.dark_mode_action)
        
        # Wrap text action
        self.wrap_text_action = QAction("Wrap Text", self)
        self.wrap_text_action.setCheckable(True)
        self.wrap_text_action.triggered.connect(self.toggle_wrap_text)
        settings_menu.addAction(self.wrap_text_action)
        
        # Edit mode action
        self.edit_mode_action = QAction("Enable Editing", self)
        self.edit_mode_action.setCheckable(True)
        self.edit_mode_action.setShortcut("Ctrl+E")
        self.edit_mode_action.triggered.connect(self.toggle_edit_mode)
        settings_menu.addAction(self.edit_mode_action)
        
        settings_menu.addSeparator()
        
        # Reset view action
        reset_view_action = QAction("Reset View", self)
        reset_view_action.triggered.connect(self.reset_view)
        settings_menu.addAction(reset_view_action)
    
    def load_settings(self):
        """Load settings from config file"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            self.dark_mode = self.config.getboolean('Settings', 'dark_mode', fallback=False)
            self.wrap_text = self.config.getboolean('Settings', 'wrap_text', fallback=False)
            self.edit_mode = self.config.getboolean('Settings', 'edit_mode', fallback=False)
            self.last_folder = self.config.get('Settings', 'last_folder', fallback=os.path.join(os.path.expanduser('~'), 'Documents'))
            # Load recent files
            self.recent_files = self.config.get('Settings', 'recent_files', fallback='').split('|')
            self.recent_files = [f for f in self.recent_files if f and os.path.exists(f)]  # Filter empty and non-existent files
        else:
            self.dark_mode = False
            self.wrap_text = False
            self.edit_mode = False
            self.last_folder = os.path.join(os.path.expanduser('~'), 'Documents')
            self.recent_files = []
            self.save_settings()
        
        # Update recent files menu
        self.update_recent_files_menu()
        
        # Sync the menu toggle states with the loaded settings
        if hasattr(self, 'dark_mode_action'):
            self.dark_mode_action.setChecked(self.dark_mode)
        if hasattr(self, 'wrap_text_action'):
            self.wrap_text_action.setChecked(self.wrap_text)
        if hasattr(self, 'edit_mode_action'):
            self.edit_mode_action.setChecked(self.edit_mode)
        
        self.update_status_bar()

    def save_settings(self):
        """Save current settings to config file"""
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.config.set('Settings', 'dark_mode', str(self.dark_mode))
        self.config.set('Settings', 'wrap_text', str(self.wrap_text))
        self.config.set('Settings', 'edit_mode', str(self.edit_mode))
        self.config.set('Settings', 'last_folder', self.last_folder)
        # Save recent files
        self.config.set('Settings', 'recent_files', '|'.join(self.recent_files))
        
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def toggle_dark_mode(self):
        self.dark_mode = self.dark_mode_action.isChecked()
        self.apply_theme()
        self.save_settings()  # Save settings when dark mode is toggled
    
    def toggle_wrap_text(self):
        """Toggle text wrapping for table cells"""
        self.wrap_text = self.wrap_text_action.isChecked()
        self.save_settings()
        self.update_table_wrapping()

    def toggle_edit_mode(self):
        """Toggle edit mode for the table"""
        if self.modified and self.edit_mode:
            # If trying to exit edit mode with unsaved changes
            reply = QMessageBox.question(
                self, "Save Changes?",
                "You have unsaved changes. What would you like to do?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                if not self.save_file():
                    # If save failed, don't exit edit mode
                    self.edit_mode_action.setChecked(True)
                    return
            elif reply == QMessageBox.Cancel:
                # Keep edit mode on
                self.edit_mode_action.setChecked(True)
                return
            # If Discard, continue with toggling edit mode off
            else:
                # Reset modified state when discarding changes
                self.modified = False
                self.modified_cells.clear()
        
        self.edit_mode = self.edit_mode_action.isChecked()
        self.save_settings()
        
        # Update cell flags based on edit mode
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    if self.edit_mode:
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        
        # Reset modified state when entering edit mode (treat like opening a new file)
        if self.edit_mode:
            self.modified = False
            self.modified_cells.clear()
        
        # Update UI elements - don't enable save until actual changes are made
        self.save_action.setEnabled(self.edit_mode and self.modified)
        self.save_as_action.setEnabled(self.edit_mode)
        self.update_status_bar()

    def on_cell_changed(self, item):
        """Handle cell content changes"""
        if not self.edit_mode:
            return
            
        row = item.row()
        col = item.column()
        new_value = item.text()
        
        try:
            # Get the column name and data type
            col_name = self.table.horizontalHeaderItem(col).text()
            dtype = self.column_types.get(col_name)
            
            if dtype:
                # Validate and convert the new value
                if pd.isna(new_value) or new_value == '':
                    converted_value = None
                elif dtype == 'int64':
                    converted_value = int(new_value)
                elif dtype == 'float64':
                    converted_value = float(new_value)
                elif dtype == 'bool':
                    converted_value = bool(new_value.lower() in ['true', '1', 'yes'])
                elif dtype == 'datetime64[ns]':
                    converted_value = pd.to_datetime(new_value)
                else:
                    converted_value = str(new_value)
                
                # Update the DataFrame
                self.original_df.iloc[row, col] = converted_value
                
                # Mark as modified
                self.modified = True
                self.modified_cells.add((row, col))
                self.save_action.setEnabled(True)
                
                # Update cell display
                if converted_value is not None:
                    item.setText(str(converted_value))
                else:
                    item.setText('')
                
                # Update status
                self.update_status_bar()
                
            else:
                # If no dtype found, treat as string
                self.original_df.iloc[row, col] = new_value
                self.modified = True
                self.modified_cells.add((row, col))
                self.save_action.setEnabled(True)
                self.update_status_bar()
                
        except (ValueError, TypeError) as e:
            # Restore the original value
            QMessageBox.warning(self, "Invalid Value", 
                              f"Could not convert '{new_value}' to required type: {str(e)}")
            original_value = str(self.original_df.iloc[row, col])
            item.setText(original_value)

    def update_status_bar(self):
        """Update status bar with current state"""
        # Update edit mode status
        self.edit_mode_label.setText("Edit Mode: ON" if self.edit_mode else "Edit Mode: OFF")
        
        # Update modified status
        if self.modified:
            self.modified_label.setText("Modified")
            self.modified_label.setStyleSheet("color: red;")
        else:
            self.modified_label.setText("")
            self.modified_label.setStyleSheet("")

    def save_file(self):
        """Save the current file"""
        if not self.current_file:
            return self.save_file_as()
            
        try:
            # Save the file
            self.original_df.to_parquet(self.current_file)
            
            # Reset modified state
            self.modified = False
            self.modified_cells.clear()
            self.save_action.setEnabled(False)
            self.update_status_bar()
            
            # Show success message
            self.status_bar.showMessage("File saved successfully", 3000)
            
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving file: {str(e)}")
            return False

    def save_file_as(self):
        """Save the current file with a new name"""
        if not self.original_df is not None:
            return False
            
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Parquet File",
            self.last_folder,
            "Parquet Files (*.parquet);;All Files (*)"
        )
        
        if file_name:
            # Update current file and save
            self.current_file = file_name
            self.last_folder = os.path.dirname(file_name)
            self.save_settings()
            return self.save_file()
            
        return False

    def closeEvent(self, event):
        """Handle application close event"""
        if self.modified:
            reply = QMessageBox.question(
                self, "Save Changes?",
                "The document has been modified. Do you want to save your changes?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                if not self.save_file():
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        
        event.accept()

    def show_context_menu(self, position):
        """Show context menu for copying cell contents"""
        menu = QMenu()
        copy_action = menu.addAction("Copy")
        
        # Get selected items
        selected_items = self.table.selectedItems()
        if selected_items:
            action = menu.exec_(self.table.viewport().mapToGlobal(position))
            if action == copy_action:
                self.show_context_menu_copy()

    def show_context_menu_copy(self):
        """Handle copying of selected cells"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        # Get unique rows and columns to maintain selection order
        rows = sorted(set(item.row() for item in selected_items))
        cols = sorted(set(item.column() for item in selected_items))
        
        # Create a list of lists to store the data
        data = []
        current_row = []
        last_row = -1
        
        for item in selected_items:
            if item.row() != last_row:
                if current_row:
                    data.append(current_row)
                current_row = []
                last_row = item.row()
            current_row.append(item.text())
        
        if current_row:
            data.append(current_row)
        
        # Convert to tab-separated string
        text_to_copy = '\n'.join('\t'.join(row) for row in data)
        QApplication.clipboard().setText(text_to_copy)

    def on_column_resize(self, logical_index, old_size, new_size):
        """Handle manual column resize"""
        try:
            # Only enforce maximum width on manual resize
            max_width = int(self.get_max_column_width())
            min_width = max(int(self.get_min_column_width(logical_index)), 50)
            
            if new_size > max_width:
                self.table.horizontalHeader().resizeSection(logical_index, max_width)
            elif new_size < min_width:
                self.table.horizontalHeader().resizeSection(logical_index, min_width)
        except Exception:
            # If resize fails, set to minimum width
            self.table.horizontalHeader().resizeSection(logical_index, 50)

    def get_max_column_width(self):
        """Get maximum allowed column width (50% of table width)"""
        viewport_width = max(self.table.viewport().width(), 100)  # Ensure minimum viewport width
        return int(viewport_width * 0.5)

    def get_min_column_width(self, column):
        """Get minimum width needed for header text and filter indicator"""
        header_item = self.table.horizontalHeaderItem(column)
        if not header_item:
            return 50  # Minimum default width
            
        text = header_item.text()
        if column in self.filters and not text.endswith(' 🔍'):
            text += ' 🔍'
            
        # Create a temporary label to measure text width
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        
        # Add padding and ensure minimum width
        return max(text_width + 20, 50)  # Minimum 50 pixels width

    def clear_column_sort(self, column):
        """Clear sorting for a specific column"""
        header = self.table.horizontalHeader()
        current_sort_column = header.sortIndicatorSection()
        
        # Only clear if this column is currently sorted
        if current_sort_column == column:
            # Temporarily disable sorting to prevent automatic resort
            self.table.setSortingEnabled(False)
            
            # Store the current data in original order
            data = []
            for row in range(self.table.rowCount()):
                row_data = []
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")
                data.append(row_data)
            
            # Clear the sort indicator
            header.setSortIndicator(-1, Qt.AscendingOrder)
            
            # Restore the data in original order
            for row in range(len(data)):
                for col in range(len(data[row])):
                    if data[row][col]:
                        item = QTableWidgetItem(data[row][col])
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        self.table.setItem(row, col, item)
            
            # Re-enable sorting
            self.table.setSortingEnabled(True)

    def show_filter_menu(self, pos):
        """Show filter menu for the clicked column"""
        header = self.table.horizontalHeader()
        column = header.logicalIndexAt(pos)
        
        menu = QMenu()
        
        # Get unique values in the column
        values = set()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, column)
            if item:
                values.add(item.text())
        
        # Add filter options
        filter_action = menu.addAction("Filter...")
        clear_action = menu.addAction("Clear Filter")
        clear_sort_column_action = menu.addAction("Clear Sorting")
        menu.addSeparator()
        clear_all_filters_action = menu.addAction("Clear All Filters")
        clear_all_sort_action = menu.addAction("Clear All Sorting")
        
        # Show current filter if exists
        current_filter = self.filters.get(column)
        if current_filter:
            menu.addSeparator()
            menu.addAction(f"Current filter: {current_filter}")
        
        # Calculate the position for the menu
        pos = header.mapToGlobal(pos)
        
        action = menu.exec_(pos)
        
        if action == filter_action:
            # Show filter dialog
            dialog = QDialog(self)
            dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)  # Remove help button
            dialog.setWindowTitle(f"Filter Column: {self.table.horizontalHeaderItem(column).text().replace(' 🔍', '')}")
            layout = QVBoxLayout(dialog)
            
            # Add filter input
            filter_input = QLineEdit()
            if current_filter:
                filter_input.setText(current_filter)
            layout.addWidget(filter_input)
            
            # Add buttons
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            
            if dialog.exec_() == QDialog.Accepted:
                filter_text = filter_input.text()
                if filter_text:
                    self.filters[column] = filter_text
                else:
                    self.filters.pop(column, None)
                self.apply_filters()
                self.update_header_style()
                
        elif action == clear_action:
            self.filters.pop(column, None)
            self.apply_filters()
            self.update_header_style()
        elif action == clear_sort_column_action:
            self.clear_column_sort(column)
        elif action == clear_all_filters_action:
            self.clear_all_filters()
        elif action == clear_all_sort_action:
            self.clear_sorting()

    def update_header_style(self):
        """Update header style to show filtered columns"""
        header = self.table.horizontalHeader()
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item:
                text = item.text()
                if col in self.filters:
                    # Add a filter indicator to the header text if not already present
                    if not text.endswith(' 🔍'):
                        item.setText(f"{text} 🔍")
                        # Ensure column is wide enough for the new text
                        min_width = self.get_min_column_width(col)
                        current_width = header.sectionSize(col)
                        if current_width < min_width:
                            header.resizeSection(col, min_width)
                    item.setToolTip(f"Filter: {self.filters[col]}")
                else:
                    # Remove filter indicator if exists
                    if text.endswith(' 🔍'):
                        item.setText(text[:-2])
                    item.setToolTip("")

    def apply_filters(self):
        """Apply all active filters to the table"""
        for row in range(self.table.rowCount()):
            show_row = True
            for column, filter_text in self.filters.items():
                item = self.table.item(row, column)
                if item and filter_text.lower() not in item.text().lower():
                    show_row = False
                    break
            self.table.setRowHidden(row, not show_row)

    def update_recent_files_menu(self):
        """Update the recent files menu with current list of files"""
        self.recent_menu.clear()
        
        if not self.recent_files:
            no_recent = QAction("No Recent Files", self)
            no_recent.setEnabled(False)
            self.recent_menu.addAction(no_recent)
            return
            
        for file_path in self.recent_files:
            action = QAction(os.path.basename(file_path), self)
            action.setStatusTip(file_path)
            # Use a lambda that also closes the parent menu
            action.triggered.connect(
                lambda checked, path=file_path: 
                (self.open_recent_file(path))
            )
            self.recent_menu.addAction(action)

    def add_to_recent_files(self, file_path):
        """Add a file to recent files list"""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:5]  # Keep only 5 most recent
        self.save_settings()
        self.update_recent_files_menu()

    def open_recent_file(self, file_path):
        """Open a file from the recent files menu"""
        if os.path.exists(file_path):
            # Close all menus before opening the file
            self.file_menu.hide()
            self.recent_menu.hide()
            # Load the file
            self.load_parquet_file(file_path)
        else:
            QMessageBox.warning(self, "File Not Found", 
                              f"The file {file_path} no longer exists.")
            self.recent_files.remove(file_path)
            self.save_settings()
            self.update_recent_files_menu()

    def load_parquet_file(self, file_name):
        """Load and display a parquet file"""
        try:
            # Read the parquet file
            df = pd.read_parquet(file_name)
            
            # Store the original DataFrame and file info
            self.original_df = df.copy()  # Make a copy to track changes
            self.current_file = file_name
            self.modified = False  # Start as unmodified
            self.modified_cells.clear()
            
            # Store column types
            self.column_types = dict(df.dtypes)
            
            # Update window title with file name
            base_name = os.path.basename(file_name)
            name_without_ext = os.path.splitext(base_name)[0]
            self.setWindowTitle(f"{name_without_ext} - Parquet File Viewer")
            
            # Clear existing filters
            self.filters.clear()
            
            # Set up the table
            self.table.setRowCount(len(df))
            self.table.setColumnCount(len(df.columns))
            self.table.setHorizontalHeaderLabels(df.columns)
            
            # Populate the table
            for i in range(len(df)):
                for j in range(len(df.columns)):
                    value = df.iloc[i, j]
                    item = QTableWidgetItem(str(value) if pd.notna(value) else '')
                    
                    # Set flags based on edit mode
                    if self.edit_mode:
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    
                    if self.wrap_text:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                        item.setFlags(item.flags() | Qt.TextWordWrap)
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        item.setFlags(item.flags() & ~Qt.TextWordWrap)
                    
                    self.table.setItem(i, j, item)
            
            # Enable sorting after data is loaded
            self.table.setSortingEnabled(True)
            
            # First adjust column widths
            self.adjust_all_columns()
            
            # Then set appropriate row heights based on wrap setting and adjusted columns
            if self.wrap_text:
                # Process events to ensure column adjustments are applied
                QApplication.processEvents()
                self.table.resizeRowsToContents()
            else:
                header_height = self.table.horizontalHeader().height()
                for row in range(self.table.rowCount()):
                    self.table.setRowHeight(row, header_height)
            
            # Update UI state - ensure modified is False when loading new file
            self.modified = False
            self.modified_cells.clear()
            self.save_action.setEnabled(False)
            self.save_as_action.setEnabled(self.edit_mode)
            self.update_status_bar()
            
            # Add to recent files
            self.add_to_recent_files(file_name)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error reading file: {e}")

    def open_file(self):
        # Check if last folder exists, if not use Documents
        if not os.path.exists(self.last_folder):
            self.last_folder = os.path.join(os.path.expanduser('~'), 'Documents')
            
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Parquet File",
            self.last_folder,
            "Parquet Files (*.parquet);;All Files (*)"
        )
        
        if file_name:
            # Update last folder to the directory of the opened file
            self.last_folder = os.path.dirname(file_name)
            self.save_settings()  # Save the new last folder
            
            self.load_parquet_file(file_name)

    def apply_theme(self):
        if self.dark_mode:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QTableWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    gridline-color: #444444;
                    border: 1px solid #444444;
                }
                QTableWidget::item {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QTableWidget::item:selected {
                    background-color: #3b3b3b;
                }
                QHeaderView::section {
                    background-color: #3b3b3b;
                    color: #ffffff;
                    border: 1px solid #444444;
                }
                QPushButton {
                    background-color: #3b3b3b;
                    color: #ffffff;
                    border: 1px solid #444444;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #4b4b4b;
                }
                QMenuBar {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QMenuBar::item {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QMenuBar::item:selected {
                    background-color: #3b3b3b;
                }
                QMenu {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #444444;
                }
                QMenu::item:selected {
                    background-color: #3b3b3b;
                }
                QFrame[frameShape="4"] {
                    color: #444444;
                }
            """)
            # Set dark palette for better contrast
            dark_palette = QPalette()
            dark_palette.setColor(QPalette.Window, QColor(45, 45, 45))
            dark_palette.setColor(QPalette.WindowText, Qt.white)
            dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
            dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
            dark_palette.setColor(QPalette.ToolTipText, Qt.white)
            dark_palette.setColor(QPalette.Text, Qt.white)
            dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ButtonText, Qt.white)
            dark_palette.setColor(QPalette.BrightText, Qt.red)
            dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.HighlightedText, Qt.black)
            self.setPalette(dark_palette)
        else:
            self.setStyleSheet("")  # Reset to default light theme
            self.setPalette(self.style().standardPalette())  # Reset to default palette
        
    def eventFilter(self, source, event):
        """Handle keyboard shortcuts for the table"""
        if source is self.table and event.type() == event.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            
            # Handle Escape (clear selection)
            if key == Qt.Key_Escape:
                self.table.clearSelection()
                return True
            
            # Handle Ctrl+C
            if modifiers & Qt.ControlModifier and key == Qt.Key_C:
                self.show_context_menu_copy()
                return True
                
            # Handle Ctrl+E
            elif modifiers & Qt.ControlModifier and key == Qt.Key_E:
                self.edit_mode_action.trigger()
                return True
                
            # Handle Shift+Space (select row)
            elif modifiers & Qt.ShiftModifier and key == Qt.Key_Space:
                if self.table.currentItem():
                    current_row = self.table.currentRow()
                    # Select the entire row
                    self.table.setRangeSelected(
                        QTableWidgetSelectionRange(
                            current_row, 0,
                            current_row, self.table.columnCount() - 1
                        ),
                        True
                    )
                return True
                
            # Handle Ctrl+Space (select column)
            elif modifiers & Qt.ControlModifier and key == Qt.Key_Space:
                if self.table.currentItem():
                    current_col = self.table.currentColumn()
                    # Select the entire column without moving the current cell
                    self.table.setRangeSelected(
                        QTableWidgetSelectionRange(
                            0, current_col,
                            self.table.rowCount() - 1, current_col
                        ),
                        True
                    )
                return True
                
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                # If we're not in edit mode, ignore
                if not self.edit_mode:
                    return False
                    
                current = self.table.currentItem()
                if not current:
                    return False
                    
                # If cell is already in edit mode, this will trigger the editor to close and accept
                if self.table.state() == QTableWidget.EditingState:
                    return False
                    
                # Start editing the current cell
                self.table.editItem(current)
                return True
                
            elif key == Qt.Key_Delete:
                # If we're not in edit mode, ignore
                if not self.edit_mode:
                    return False
                    
                # Get all selected items
                selected_items = self.table.selectedItems()
                if not selected_items:
                    return False
                    
                # Clear the contents of all selected cells
                for item in selected_items:
                    row = item.row()
                    col = item.column()
                    
                    # Update the DataFrame
                    self.original_df.iloc[row, col] = None
                    
                    # Update the table item
                    item.setText('')
                    
                    # Mark as modified
                    self.modified = True
                    self.modified_cells.add((row, col))
                
                # Update UI
                self.save_action.setEnabled(True)
                self.update_status_bar()
                return True
                
        return super().eventFilter(source, event)

    def reset_view(self):
        """Reset the view by clearing filters and sorting"""
        self.clear_all_filters()
        self.clear_sorting()

    def clear_sorting(self):
        """Clear all column sorting"""
        self.table.sortItems(-1)  # -1 removes sorting from all columns

    def clear_all_filters(self):
        """Clear all active filters"""
        self.filters.clear()
        self.apply_filters()
        self.update_header_style()

    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        # Update column widths when window is resized
        self.adjust_all_columns()
        # Update row heights if text wrapping is enabled
        if self.wrap_text:
            self.table.resizeRowsToContents()

    def adjust_all_columns(self):
        """Adjust all column widths based on content and window size"""
        if self.table.columnCount() == 0:
            return
            
        viewport_width = self.table.viewport().width()
        if viewport_width <= 0:
            return  # Skip adjustment if viewport is not visible
            
        # First pass: get content widths
        content_widths = []
        total_content_width = 0
        for col in range(self.table.columnCount()):
            width = self.get_optimal_column_width(col)
            content_widths.append(width)
            total_content_width += width
        
        # Get available width
        available_width = max(viewport_width, 100)  # Ensure minimum available width
        max_column_width = int(available_width * 0.5)  # 50% of viewport width
        min_column_width = 50  # Minimum column width
        
        # Second pass: adjust widths if they exceed limits
        for col in range(self.table.columnCount()):
            optimal_width = content_widths[col]
            min_width = max(self.get_min_column_width(col), min_column_width)
            # Ensure width is between minimum required and maximum allowed
            final_width = int(min(max(optimal_width, min_width), max_column_width))
            try:
                self.table.setColumnWidth(col, final_width)
            except Exception:
                # If setting width fails, set to minimum width
                self.table.setColumnWidth(col, min_column_width)

    def get_optimal_column_width(self, column):
        """Calculate optimal width based on content and header"""
        font_metrics = self.fontMetrics()
        padding = 30  # Padding for better readability
        min_width = 50  # Minimum width
        
        # Get header width
        header_width = 0
        header_item = self.table.horizontalHeaderItem(column)
        if header_item:
            header_text = header_item.text()
            if column in self.filters and not header_text.endswith(' 🔍'):
                header_text += ' 🔍'  # Account for filter indicator
            header_width = font_metrics.horizontalAdvance(header_text)
        
        # Get maximum content width
        content_width = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, column)
            if item:
                try:
                    item_width = font_metrics.horizontalAdvance(item.text())
                    content_width = max(content_width, item_width)
                except Exception:
                    continue
        
        # Use the larger of header or content width
        optimal_width = max(header_width, content_width)
        
        # Add padding and ensure minimum width
        return max(optimal_width + padding, min_width)

    def update_table_wrapping(self):
        """Update text wrapping for all cells in the table"""
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    if self.wrap_text:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                        item.setFlags(item.flags() | Qt.TextWordWrap)
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        item.setFlags(item.flags() & ~Qt.TextWordWrap)
        
        # Update row heights based on wrap setting
        if self.wrap_text:
            self.table.resizeRowsToContents()
        else:
            # Reset all rows to default height when disabling wrap
            header_height = self.table.horizontalHeader().height()
            for row in range(self.table.rowCount()):
                self.table.setRowHeight(row, header_height)
        
        # Adjust columns to ensure proper layout
        self.adjust_all_columns()

    def show_recent_menu(self):
        """Show the File menu and Recent Files submenu as if clicked naturally"""
        # Get the File menu button in the menu bar
        menu_bar = self.menuBar()
        file_action = self.file_menu.menuAction()
        file_button_rect = menu_bar.actionGeometry(file_action)
        
        # Calculate the position for the File menu
        file_pos = menu_bar.mapToGlobal(file_button_rect.bottomLeft())
        
        # Show the File menu
        self.file_menu.popup(file_pos)
        
        # Find and highlight the Recent Files menu item
        for action in self.file_menu.actions():
            if action.menu() == self.recent_menu:
                # Use a timer to ensure menu is fully shown before highlighting
                QTimer.singleShot(50, lambda: self.file_menu.setActiveAction(action))
                break
        
        # Use a timer to delay showing the Recent Files submenu
        QTimer.singleShot(100, self.show_recent_submenu)

    def show_recent_submenu(self):
        """Show the Recent Files submenu"""
        # Find the Recent Files menu item
        for action in self.file_menu.actions():
            if action.menu() == self.recent_menu:
                # Get the action's geometry in the menu
                rect = self.file_menu.actionGeometry(action)
                # Calculate where the submenu should appear
                submenu_pos = self.file_menu.mapToGlobal(rect.topRight())
                # Show the submenu
                self.recent_menu.popup(submenu_pos)
                
                # Highlight the first item if there are recent files
                if self.recent_files:
                    first_action = self.recent_menu.actions()[0]
                    # Use a timer to ensure menu is fully shown before highlighting
                    QTimer.singleShot(50, lambda: self.recent_menu.setActiveAction(first_action))
                break

def main():
    app = QApplication(sys.argv)
    window = ParquetViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()