import sys
import os
import warnings
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                            QMenuBar, QMenu, QAction, QMessageBox, QFrame, QDialog, QLineEdit, QDialogButtonBox,
                            QLabel, QStatusBar, QTableWidgetSelectionRange, QComboBox, QScrollBar,
                            QAbstractItemView)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPalette, QColor, QCursor, QBrush
import configparser
from pathlib import Path
import numpy as np
from datetime import datetime
import shutil
from typing import List, Any, Tuple

# Suppress PyQt5 deprecation warning
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Command pattern for undo/redo
class EditCommand:
    def __init__(self, changes: List[Tuple[int, int, Any, Any]]):
        self.changes = changes  # List of (row, col, old_value, new_value)

    def undo(self, table: QTableWidget, df: pd.DataFrame):
        for row, col, old_value, _ in self.changes:
            # Update DataFrame
            df.iloc[row, col] = old_value
            # Update table
            item = table.item(row, col)
            if item:
                if pd.notna(old_value):
                    if isinstance(old_value, (int, float)):
                        item.setText(f"{old_value:,}")
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        item.setText(str(old_value))
                else:
                    item.setText('')

    def redo(self, table: QTableWidget, df: pd.DataFrame):
        for row, col, _, new_value in self.changes:
            # Update DataFrame
            df.iloc[row, col] = new_value
            # Update table
            item = table.item(row, col)
            if item:
                if pd.notna(new_value):
                    if isinstance(new_value, (int, float)):
                        item.setText(f"{new_value:,}")
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        item.setText(str(new_value))
                else:
                    item.setText('')

class CommandStack:
    def __init__(self):
        self.undo_stack: List[EditCommand] = []
        self.redo_stack: List[EditCommand] = []

    def push(self, command: EditCommand):
        self.undo_stack.append(command)
        self.redo_stack.clear()  # Clear redo stack when new command is pushed

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def undo(self, table: QTableWidget, df: pd.DataFrame) -> bool:
        if not self.can_undo():
            return False
        command = self.undo_stack.pop()
        command.undo(table, df)
        self.redo_stack.append(command)
        return True

    def redo(self, table: QTableWidget, df: pd.DataFrame) -> bool:
        if not self.can_redo():
            return False
        command = self.redo_stack.pop()
        command.redo(table, df)
        self.undo_stack.append(command)
        return True

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()

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
        
        # Initialize command stack for undo/redo
        self.command_stack = CommandStack()
        
        # Initialize actions before creating menu
        self.init_actions()
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Create labels for status bar
        self.stats_label = QLabel()  # New label for stats
        self.stats_label.setTextFormat(Qt.RichText) # Use rich text
        self.edit_mode_label = QLabel()
        self.modified_label = QLabel()
        
        # Add widgets to status bar using addPermanentWidget (adds right-to-left)
        # Order: Stats, Edit Mode, Modified (to get desired left-to-right display)
        self.status_bar.addPermanentWidget(self.stats_label)
        self.status_bar.addPermanentWidget(self.edit_mode_label)
        self.status_bar.addPermanentWidget(self.modified_label)
        
        self.update_status_bar() # Initial update triggers text formatting
        
        # Load settings after menu creation
        self.load_settings()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create table widget to display data
        self.table = QTableWidget()
        self.table.setSortingEnabled(False)  # Disable automatic sorting
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.itemChanged.connect(self.on_cell_changed)
        self.table.itemSelectionChanged.connect(self.calculate_selection_stats) # Connect selection change to stats update
        
        # Configure headers for right-click menu
        header = self.table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_filter_menu)
        header.setSectionsClickable(True)
        header.sectionResized.connect(self.on_column_resize)
        header.sectionClicked.connect(self.on_header_click)
        
        # Configure vertical header (row numbers) for right-click menu
        v_header = self.table.verticalHeader()
        v_header.setContextMenuPolicy(Qt.CustomContextMenu)
        v_header.customContextMenuRequested.connect(self.show_row_menu)
        
        # Create totals widget
        self.totals_widget = QTableWidget()
        self.totals_widget.setMaximumHeight(25)  # Fixed height for totals
        self.totals_widget.horizontalHeader().hide()
        self.totals_widget.verticalHeader().hide()
        self.totals_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.totals_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.totals_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.totals_widget.customContextMenuRequested.connect(self.show_totals_context_menu)
        
        # Create a container widget for the table and totals
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addWidget(self.table)
        # Add scrollbar between table and totals
        h_scrollbar = QScrollBar(Qt.Horizontal)
        self.table.setHorizontalScrollBar(h_scrollbar)
        self.totals_widget.setHorizontalScrollBar(h_scrollbar)
        table_layout.addWidget(h_scrollbar)
        table_layout.addWidget(self.totals_widget)
        
        layout.addWidget(table_container)
        
        # Store filter values
        self.filters = {}
        
        # Apply initial theme
        self.apply_theme()
        
        # Add clipboard data storage
        self.clipboard_data = None
        self.clipboard_cells = set()  # Store coordinates of copied cells
        
        # Add timer for selection animation
        self.selection_timer = QTimer(self)
        self.selection_timer.timeout.connect(self.toggle_selection_highlight)
        self.selection_visible = True
        
        # Add flag to prevent recursive updates
        self.updating_totals = False
        self.applying_delete = False  # Add flag for delete operation
        
        # Store column sort states
        self.column_sort_states = {}  # {column_index: is_ascending}
        self.populating_new_column = False # Flag for adding new column

    def init_actions(self):
        """Initialize all actions"""
        # Undo/Redo actions
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_edit)
        self.undo_action.setEnabled(False)
        
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.redo_edit)
        self.redo_action.setEnabled(False)
        
        # Cut/Copy/Paste actions
        self.cut_action = QAction("Cut", self)
        self.cut_action.setShortcut("Ctrl+X")
        self.cut_action.triggered.connect(self.cut_cells)
        
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut("Ctrl+C")
        self.copy_action.triggered.connect(self.copy_cells)
        
        self.paste_action = QAction("Paste", self)
        self.paste_action.setShortcut("Ctrl+V")
        self.paste_action.triggered.connect(self.paste_cells)
        
        # Recent files shortcut
        self.recent_files_action = QAction("Recent Files", self)
        self.recent_files_action.setShortcut("Ctrl+Shift+O")
        self.recent_files_action.triggered.connect(self.show_recent_menu)

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        self.file_menu = menubar.addMenu("File")
        
        # New file action
        new_action = QAction("New Parquet File", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.create_new_file)
        self.file_menu.addAction(new_action)
        
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
        self.save_as_action.setEnabled(True) # Keep Save As enabled
        self.file_menu.addAction(self.save_as_action)
        
        self.file_menu.addSeparator()
        
        # Add recent files menu
        self.recent_menu = self.file_menu.addMenu("Recent Files")
        # Add the recent files shortcut to the application
        self.addAction(self.recent_files_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        
        # Add Row/Column actions
        edit_menu.addSeparator()
        add_row_action = QAction("Add Row", self)
        add_row_action.triggered.connect(lambda: self.insert_row(self.table.rowCount()))
        edit_menu.addAction(add_row_action)
        
        add_column_action = QAction("Add Column...", self)
        add_column_action.triggered.connect(self.add_new_column)
        edit_menu.addAction(add_column_action)
        
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
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Save Changes?")
            msg_box.setText("The document has been modified. Do you want to save your changes?")
            
            save_btn = msg_box.addButton("&Save", QMessageBox.AcceptRole)
            no_btn = msg_box.addButton("&No", QMessageBox.RejectRole)
            cancel_btn = msg_box.addButton("&Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(save_btn)
            msg_box.setEscapeButton(cancel_btn)
            
            msg_box.exec_()
            clicked_button = msg_box.clickedButton()
            
            if clicked_button == save_btn:
                if not self.save_file():
                    # If save failed, don't exit edit mode
                    self.edit_mode_action.setChecked(True)
                    return
            elif clicked_button == no_btn:
                # If No, revert all changes
                self.revert_all_changes()
            else:  # Cancel or Escape
                # Keep edit mode on
                self.edit_mode_action.setChecked(True)
                return
        
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
        
        # Reset modified state when entering edit mode
        if self.edit_mode:
            self.modified = False
            self.modified_cells.clear()
            self.command_stack.clear()
        
        # Update UI elements
        self.save_action.setEnabled(False)
        self.save_as_action.setEnabled(True)
        self.update_undo_redo_state()
        self.update_status_bar()

    def on_cell_changed(self, item):
        """Handle cell content changes"""
        if not self.edit_mode or self.updating_totals or self.applying_delete or self.populating_new_column: # Check the new flag
            return
            
        row = item.row()
        col = item.column()
        new_value = item.text().strip()
        
        try:
            # Get the column name and data type
            col_name = self.table.horizontalHeaderItem(col).text()
            dtype = self.column_types.get(col_name)
            
            # Store the old value before making changes
            old_value = self.original_df.iloc[row, col]
            
            # Skip if the value hasn't actually changed
            if pd.isna(new_value) and pd.isna(old_value):
                return
            elif str(old_value).strip() == new_value:
                return
            
            if dtype:
                # Validate and convert the new value
                if pd.isna(new_value) or new_value == '':
                    converted_value = None
                elif dtype == 'int64':
                    # Remove commas for integer conversion
                    clean_value = new_value.replace(',', '')
                    converted_value = int(float(clean_value))
                elif dtype == 'float64':
                    # Remove commas for float conversion
                    clean_value = new_value.replace(',', '')
                    converted_value = float(clean_value)
                elif dtype == 'bool':
                    converted_value = bool(new_value.lower() in ['true', '1', 'yes'])
                elif dtype == 'datetime64[ns]':
                    converted_value = pd.to_datetime(new_value)
                else:
                    converted_value = str(new_value)
                
                # Skip if the converted value hasn't changed
                if pd.isna(converted_value) and pd.isna(old_value):
                    return
                elif converted_value == old_value:
                    return
                
                # Create and push the edit command
                command = EditCommand([(row, col, old_value, converted_value)])
                self.command_stack.push(command)
                
                # Update the DataFrame
                self.original_df.iloc[row, col] = converted_value
                
                # Update the display format
                if converted_value is not None:
                    if isinstance(converted_value, (int, float)):
                        item.setText(f"{converted_value:,}")
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        item.setText(str(converted_value))
                else:
                    item.setText('')
                
                # Mark as modified
                self.modified = True
                self.modified_cells.add((row, col))
                self.save_action.setEnabled(True)
                
                # Update UI state
                self.update_undo_redo_state()
                self.update_status_bar()
                
                # Update statistics after cell change
                self.calculate_selection_stats()
                
                # Update column totals
                self.update_column_totals()
                
            else:
                # Skip if the string value hasn't changed
                if new_value == str(old_value).strip():
                    return
                
                # If no dtype found, treat as string
                command = EditCommand([(row, col, old_value, new_value)])
                self.command_stack.push(command)
                
                self.original_df.iloc[row, col] = new_value
                self.modified = True
                self.modified_cells.add((row, col))
                self.save_action.setEnabled(True)
                
                # Update UI state
                self.update_undo_redo_state()
                self.update_status_bar()
                
                # Update statistics after cell change
                self.calculate_selection_stats()
                
                # Update column totals
                self.update_column_totals()
                
        except (ValueError, TypeError) as e:
            # Restore the original value
            QMessageBox.warning(self, "Invalid Value", 
                              f"Could not convert '{new_value}' to required type: {str(e)}")
            if pd.notna(old_value):
                if isinstance(old_value, (int, float)):
                    item.setText(f"{old_value:,}")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setText(str(old_value))
            else:
                item.setText('')

    def update_status_bar(self):
        """Update status bar with current state and consistent separators"""
        # --- Get Raw Texts --- 
        # Stats text is set by calculate_selection_stats, read it
        stats_text = self.stats_label.text() 
        edit_mode_raw_text = "Edit Mode: ON" if self.edit_mode else "Edit Mode: OFF"
        modified_raw_text = "Modified" if self.modified else ""

        # --- Set Label Texts with Separators --- 

        # 1. Stats Label (no prefix)
        self.stats_label.setText(stats_text)

        # 2. Edit Mode Label
        # Add separator *only* if stats_text is not empty
        self.edit_mode_label.setText(edit_mode_raw_text)

        # 3. Modified Label
        # Add separator *only* if modified_raw_text is not empty (i.e., self.modified is True)
        # The Edit Mode label is always visible, so we don't need to check it.
        self.modified_label.setText(modified_raw_text)

        # Apply style for modified text
        if self.modified:
            self.modified_label.setStyleSheet("color: red;")
        else:
            self.modified_label.setStyleSheet("")

        # --- Update window title --- 
        title_prefix = "*" if self.modified else ""
        file_display_name = os.path.basename(self.current_file) if self.current_file else "Untitled"
        if self.current_file:
            name_without_ext = os.path.splitext(file_display_name)[0]
            self.setWindowTitle(f"{title_prefix}{name_without_ext} - Parquet File Viewer")
        else:
            self.setWindowTitle(f"{title_prefix}Untitled - Parquet File Viewer")

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
            self.command_stack.clear()  # Clear command stack after successful save
            self.save_action.setEnabled(False)
            self.update_undo_redo_state()
            self.update_status_bar()
            
            # Show success message
            self.status_bar.showMessage("File saved successfully", 3000)
            
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving file: {str(e)}")
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
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Save Changes?")
            msg_box.setText("The document has been modified. Do you want to save your changes?")
            
            save_btn = msg_box.addButton("&Save", QMessageBox.AcceptRole)
            no_btn = msg_box.addButton("&No", QMessageBox.RejectRole)
            cancel_btn = msg_box.addButton("&Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(save_btn)
            msg_box.setEscapeButton(cancel_btn)
            
            msg_box.exec_()
            clicked_button = msg_box.clickedButton()
            
            if clicked_button == save_btn:
                if not self.save_file():
                    event.ignore()
                    return
            elif clicked_button == cancel_btn:  # Cancel or Escape
                event.ignore()
                return
            # If No, just continue with close
        
        event.accept()

    def show_context_menu(self, position):
        """Show context menu for table cells"""
        menu = QMenu()
        
        copy_action = menu.addAction("Copy")
        if self.edit_mode:
            menu.addSeparator()
            cut_action = menu.addAction("Cut")
            paste_action = menu.addAction("Paste")
            menu.addSeparator()
            delete_action = menu.addAction("Delete")
        
        action = menu.exec_(self.table.viewport().mapToGlobal(position))
        
        if action == copy_action:
            self.show_context_menu_copy()
        elif self.edit_mode:
            if action == cut_action:
                self.cut_cells()
            elif action == paste_action:
                self.paste_cells()
            elif action == delete_action:
                self.delete_selected_cell_contents()

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
                new_size = max_width
                self.table.horizontalHeader().resizeSection(logical_index, new_size)
            elif new_size < min_width:
                new_size = min_width
                self.table.horizontalHeader().resizeSection(logical_index, new_size)
            
            # Update totals column width
            self.totals_widget.setColumnWidth(logical_index, new_size)
            
        except Exception:
            # If resize fails, set to minimum width
            new_size = 50
            self.table.horizontalHeader().resizeSection(logical_index, new_size)
            self.totals_widget.setColumnWidth(logical_index, new_size)

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
        
        # If clicked beyond the last column, show add column menu
        if column == -1:
            menu = QMenu()
            add_column_action = menu.addAction("Add Column")
            action = menu.exec_(header.mapToGlobal(pos))
            if action == add_column_action:
                self.add_new_column()
            return
        
        menu = QMenu()
        
        # Add column operations
        insert_left_action = menu.addAction("Insert Column Left")
        insert_right_action = menu.addAction("Insert Column Right")
        menu.addSeparator()
        delete_column_action = menu.addAction("Delete Column")
        delete_column_action.setEnabled(self.edit_mode)
        
        menu.addSeparator()
        
        # Add sort option
        sort_action = menu.addAction("Sort")
        if column in self.column_sort_states:
            sort_action.setText("Sort (Z to A)" if self.column_sort_states[column] else "Sort (A to Z)")
        else:
            sort_action.setText("Sort (A to Z)")
        
        menu.addSeparator()
        
        # Add filter options
        filter_action = menu.addAction("Filter...")
        clear_action = menu.addAction("Clear Filter")
        menu.addSeparator()
        clear_all_filters_action = menu.addAction("Clear All Filters")
        
        # Show current filter if exists
        current_filter = self.filters.get(column)
        if current_filter:
            menu.addSeparator()
            menu.addAction(f"Current filter: {current_filter}")
        
        # Calculate the position for the menu
        pos = header.mapToGlobal(pos)
        
        action = menu.exec_(pos)
        
        if action == insert_left_action:
            self.add_new_column(column)
        elif action == insert_right_action:
            self.add_new_column(column + 1)
        elif action == delete_column_action:
            self.delete_column(column)
        elif action == sort_action:
            self.toggle_column_sort(column)
        elif action == filter_action:
            self.show_filter_dialog(column)
        elif action == clear_action:
            self.filters.pop(column, None)
            self.apply_filters()
            self.update_header_style()
        elif action == clear_all_filters_action:
            self.clear_all_filters()

    def toggle_column_sort(self, column):
        """Toggle sort order for a column"""
        if column in self.column_sort_states:
            # Toggle sort order
            self.column_sort_states[column] = not self.column_sort_states[column]
            order = Qt.AscendingOrder if self.column_sort_states[column] else Qt.DescendingOrder
        else:
            # First sort - ascending
            self.column_sort_states[column] = True
            order = Qt.AscendingOrder
        
        self.table.sortItems(column, order)

    def show_row_menu(self, pos):
        """Show context menu for row operations"""
        if not self.edit_mode:
            return
            
        v_header = self.table.verticalHeader()
        row = v_header.logicalIndexAt(pos)
        
        # If clicked beyond the last row, show add row menu
        if row == -1:
            menu = QMenu()
            add_row_action = menu.addAction("Add Row")
            action = menu.exec_(v_header.mapToGlobal(pos))
            if action == add_row_action:
                self.insert_row(self.table.rowCount())
            return
        
        menu = QMenu()
        
        # Add row options
        insert_above_action = menu.addAction("Insert Row Above")
        insert_below_action = menu.addAction("Insert Row Below")
        menu.addSeparator()
        delete_row_action = menu.addAction("Delete Row")
        
        # Calculate menu position
        pos = v_header.mapToGlobal(pos)
        
        action = menu.exec_(pos)
        
        if action == insert_above_action:
            self.insert_row(row)
        elif action == insert_below_action:
            self.insert_row(row + 1)
        elif action == delete_row_action:
            self.delete_row(row)

    def show_filter_dialog(self, column):
        """Show filter dialog for a column"""
        dialog = QDialog(self)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.setWindowTitle(f"Filter Column: {self.table.horizontalHeaderItem(column).text().replace(' 🔍', '')}")
        layout = QVBoxLayout(dialog)
        
        # Add filter input
        filter_input = QLineEdit()
        current_filter = self.filters.get(column)
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

        # Update column totals after filtering
        self.update_column_totals()

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
        # Check for unsaved changes first
        if not self.check_unsaved_changes():
            return
            
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
        try:
            # Load the parquet file
            self.df = pd.read_parquet(file_name)
            self.original_df = self.df.copy()
            
            # Store column types
            self.column_types = self.df.dtypes.to_dict()
            
            # Reset the table
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            
            # Set column headers
            self.table.setColumnCount(len(self.df.columns))
            self.table.setHorizontalHeaderLabels(self.df.columns.astype(str))
            
            # Set row count
            self.table.setRowCount(len(self.df))
            
            # Populate the table
            for i, col in enumerate(self.df.columns):
                for j in range(len(self.df)):
                    val = self.df.iloc[j, i]
                    item = QTableWidgetItem()
                    if pd.isna(val):
                        item.setText('')
                    else:
                        if isinstance(val, (int, float)):
                            item.setText(f"{val:,}")
                            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        else:
                            item.setText(str(val))
                    # Ensure item editability matches current edit mode
                    if self.edit_mode:
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(j, i, item)
            
            # Update window title
            self.setWindowTitle(f"Parquet File Viewer - {os.path.basename(file_name)}")
            self.current_file = file_name
            
            # Reset modified state
            self.modified = False
            self.modified_cells.clear()
            self.command_stack.clear()
            self.update_status_bar()
            
            # Add to recent files
            self.add_to_recent_files(file_name)
            
            # Apply initial column widths
            self.adjust_all_columns()
            
            # Update the recent files menu
            self.update_recent_files_menu()
            
            # Clear filters
            self.filters.clear()
            
            # Enable sorting
            self.table.setSortingEnabled(True)
            
            # Update totals
            self.update_column_totals()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load parquet file: {str(e)}")
            return False
        return True

    def update_column_totals(self):
        """Update the totals row at the bottom of the table"""
        if self.table.rowCount() == 0:
            return
            
        self.updating_totals = True
        try:
            # Update totals widget
            self.totals_widget.setColumnCount(self.table.columnCount())
            self.totals_widget.setRowCount(1)
            
            # Create "Total" label for the first column
            total_label = QTableWidgetItem("Total")
            total_label.setBackground(QBrush(QColor("#f0f0f0")))
            total_label.setFlags(Qt.ItemIsEnabled)  # Make it read-only
            self.totals_widget.setItem(0, 0, total_label)
            
            # Calculate totals for each column
            for col in range(self.table.columnCount()):
                if col == 0:  # Skip first column as it has the "Total" label
                    continue
                    
                numeric_values = []
                for row in range(self.table.rowCount()):
                    item = self.table.item(row, col)
                    if item:
                        try:
                            value = float(item.text().replace(',', ''))
                            numeric_values.append(value)
                        except (ValueError, TypeError):
                            continue
                
                # Create total item
                total_item = QTableWidgetItem()
                total_item.setBackground(QBrush(QColor("#f0f0f0")))
                total_item.setFlags(Qt.ItemIsEnabled)  # Make it read-only
                
                if numeric_values:
                    total = sum(numeric_values)
                    total_item.setText(f"{total:,.2f}")
                    total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    total_item.setText("")
                    
                self.totals_widget.setItem(0, col, total_item)
            
            # Sync column widths with main table
            for col in range(self.table.columnCount()):
                self.totals_widget.setColumnWidth(col, self.table.columnWidth(col))
                
        finally:
            self.updating_totals = False

    def open_file(self):
        # Check for unsaved changes first
        if not self.check_unsaved_changes():
            return
            
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
                /* Unified Scrollbar Style - Refined */
                QScrollBar:horizontal {
                    border: none;
                    background: #3a3a3a; /* Dark track background */
                    height: 14px; /* Total height including padding */
                    margin: 0px 0px 0 0px; /* No margin on the scrollbar itself */
                }
                QScrollBar::handle:horizontal {
                    background: #606060; /* Handle color */
                    min-width: 20px;
                    border-radius: 3px; /* Slightly less rounded */
                    height: 6px; /* Actual handle height */
                    margin: 4px 18px; /* Top/bottom margin for padding, left/right for button space */
                }
                QScrollBar::handle:horizontal:hover {
                    background: #707070;
                }
                QScrollBar::add-line:horizontal,
                QScrollBar::sub-line:horizontal {
                    /* Explicitly hide arrows */
                    border: none;
                    background: none;
                    width: 0px;
                    height: 0px;
                }
                QScrollBar::add-page:horizontal,
                QScrollBar::sub-page:horizontal {
                    background: none; /* Track area */
                }
                QScrollBar:vertical {
                    border: none;
                    background: #3a3a3a;
                    width: 14px; /* Total width including padding */
                    margin: 0 0px 0 0px;
                }
                QScrollBar::handle:vertical {
                    background: #606060;
                    min-height: 20px;
                    border-radius: 3px;
                    width: 6px; /* Actual handle width */
                    margin: 0px 4px; /* Adjusted margin: No top/bottom needed, just left/right for padding */
                }
                QScrollBar::handle:vertical:hover {
                    background: #707070;
                }
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {
                    /* Explicitly hide arrows */
                    border: none;
                    background: none;
                    width: 0px;
                    height: 0px;
                }
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {
                    background: none;
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
            # Apply the *same* refined scrollbar style structure for light mode
            self.setStyleSheet("""
                /* Unified Scrollbar Style - Refined, No Arrows */
                QScrollBar:horizontal {
                    border: none;
                    background: #e0e0e0; /* Light track */
                    height: 14px; /* Total height */
                    margin: 0px 0px 0 0px;
                }
                QScrollBar::handle:horizontal {
                    background: #a0a0a0; /* Medium gray handle */
                    min-width: 20px;
                    border-radius: 3px;
                    height: 6px; /* Actual handle height */
                    margin: 4px 0px; /* Adjusted margin: No left/right needed, just top/bottom for padding */
                }
                QScrollBar::handle:horizontal:hover {
                    background: #888888;
                }
                QScrollBar::add-line:horizontal,
                QScrollBar::sub-line:horizontal {
                    /* Explicitly hide arrows */
                    border: none;
                    background: none;
                    width: 0px;
                    height: 0px;
                }
                QScrollBar::add-page:horizontal,
                QScrollBar::sub-page:horizontal {
                    background: none;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #e0e0e0; /* Light track */
                    width: 14px; /* Total width */
                    margin: 0 0px 0 0px;
                }
                QScrollBar::handle:vertical {
                    background: #a0a0a0;
                    min-height: 20px;
                    border-radius: 3px;
                    width: 6px; /* Actual handle width */
                    margin: 0px 4px; /* Adjusted margin: No top/bottom needed, just left/right for padding */
                }
                QScrollBar::handle:vertical:hover {
                    background: #888888;
                }
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {
                     /* Explicitly hide arrows */
                    border: none;
                    background: none;
                    width: 0px;
                    height: 0px;
                }
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {
                    background: none;
                }
            """)
            # Reset palette but keep custom scrollbar style
            self.setPalette(self.style().standardPalette())  
        
    def eventFilter(self, source, event):
        """Handle keyboard shortcuts for the table"""
        if source is self.table and event.type() == event.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            
            # Handle Escape (clear selection and copy highlighting)
            if key == Qt.Key_Escape:
                self.clear_copy_highlighting()
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
                
            elif key == Qt.Key_F2:
                current = self.table.currentItem()
                if current and self.edit_mode:
                    self.table.editItem(current)
                    return True # Consume the event, F2 edit works differently
                
            # We no longer need the specific Delete/Backspace handling here
            # elif key in (Qt.Key_Delete, Qt.Key_Backspace):
            #     ...

        elif source == self.table and event.type() == event.MouseButtonDblClick:
            if self.edit_mode and self.table.currentItem():
                self.table.editItem(self.table.currentItem())
                return True
                
        return super().eventFilter(source, event)

    def delete_selected_cell_contents(self):
        """Delete contents of selected cells"""
        if not self.edit_mode:
            return
            
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        changes = []
        for item in selected_items:
            row = item.row()
            col = item.column()
            old_value = self.original_df.iloc[row, col]
            if pd.notna(old_value):  # Only record changes for non-empty cells
                changes.append((row, col, old_value, None))
        
        if changes:
            # Create and push single command for all changes
            command = EditCommand(changes)
            self.command_stack.push(command)
            
            # Apply all changes
            self.applying_delete = True  # Set flag before UI updates
            try:
                for row, col, _, _ in changes:
                    self.original_df.iloc[row, col] = None
                    item = self.table.item(row, col)
                    if item:
                        item.setText('')
                    self.modified_cells.add((row, col))
            finally:
                self.applying_delete = False # Ensure flag is reset
            
            self.modified = True
            self.save_action.setEnabled(True)
            self.update_undo_redo_state()
            self.update_status_bar()
            self.update_column_totals()

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

        # Update column totals after clearing filters
        self.update_column_totals()

    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        # Update column widths when window is resized
        self.adjust_all_columns()
        # Update row heights if text wrapping is enabled
        if self.wrap_text:
            self.table.resizeRowsToContents()
        # Sync totals widget column widths
        for col in range(self.table.columnCount()):
            self.totals_widget.setColumnWidth(col, self.table.columnWidth(col))

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
                self.totals_widget.setColumnWidth(col, final_width)
            except Exception:
                # If setting width fails, set to minimum width
                self.table.setColumnWidth(col, min_column_width)
                self.totals_widget.setColumnWidth(col, min_column_width)

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

    def undo_edit(self):
        """Handle undo action"""
        if not self.edit_mode:
            return
            
        if self.command_stack.undo(self.table, self.original_df):
            # Update modified state based on remaining undo stack
            self.modified = len(self.command_stack.undo_stack) > 0
            self.modified_cells = set()  # Reset modified cells
            
            # If there are still undo commands, rebuild modified cells set
            if self.modified:
                for command in self.command_stack.undo_stack:
                    for row, col, _, _ in command.changes:
                        self.modified_cells.add((row, col))
            
            self.save_action.setEnabled(self.modified)
            self.update_undo_redo_state()
            self.update_status_bar()
            self.update_column_totals()  # Update totals after undo

    def redo_edit(self):
        """Handle redo action"""
        if not self.edit_mode:
            return
            
        if self.command_stack.redo(self.table, self.original_df):
            self.modified = True
            
            # Update modified cells from the last redone command
            if self.command_stack.undo_stack:
                last_command = self.command_stack.undo_stack[-1]
                for row, col, _, _ in last_command.changes:
                    self.modified_cells.add((row, col))
            
            self.save_action.setEnabled(True)
            self.update_undo_redo_state()
            self.update_status_bar()
            self.update_column_totals()  # Update totals after redo

    def update_undo_redo_state(self):
        """Update the enabled state of undo/redo actions"""
        self.undo_action.setEnabled(self.command_stack.can_undo())
        self.redo_action.setEnabled(self.command_stack.can_redo())

    def revert_all_changes(self):
        """Revert all changes to the original state"""
        if self.current_file and os.path.exists(self.current_file):
            # Reload the file from disk
            self.load_parquet_file(self.current_file)
        else:
            QMessageBox.warning(self, "Error", "Cannot revert changes: original file not found.")

    def toggle_selection_highlight(self):
        """Toggle the highlight of copied cells"""
        if not self.clipboard_cells:
            self.selection_timer.stop()
            return
            
        self.selection_visible = not self.selection_visible
        brush = QBrush(QColor(230, 230, 230) if self.selection_visible else QColor(255, 255, 255))
        
        for row, col in self.clipboard_cells:
            item = self.table.item(row, col)
            if item:
                item.setBackground(brush)
                # Add a distinctive border style
                if self.selection_visible:
                    item.setData(Qt.UserRole, "copied")  # Mark as copied
                else:
                    item.setData(Qt.UserRole, None)  # Clear mark

    def clear_copy_highlighting(self):
        """Clear any copy/cut highlighting"""
        if self.clipboard_cells:
            for row, col in self.clipboard_cells:
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QBrush())  # Clear background
                    item.setData(Qt.UserRole, None)  # Clear mark
            self.clipboard_cells.clear()
            self.selection_timer.stop()

    def cut_cells(self):
        """Cut selected cells"""
        self.copy_cells(cut=True)
        if self.edit_mode:
            # Clear the contents of cut cells
            selected_items = self.table.selectedItems()
            for item in selected_items:
                row = item.row()
                col = item.column()
                old_value = self.original_df.iloc[row, col]
                
                # Create and push the edit command
                command = EditCommand([(row, col, old_value, None)])
                self.command_stack.push(command)
                
                # Update DataFrame and UI
                self.original_df.iloc[row, col] = None
                item.setText('')
                
                # Mark as modified
                self.modified = True
                self.modified_cells.add((row, col))
            
            # Update UI state
            self.save_action.setEnabled(True)
            self.update_undo_redo_state()
            self.update_status_bar()

    def copy_cells(self, cut=False):
        """Copy selected cells"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        # Get unique rows and columns to maintain selection order
        rows = sorted(set(item.row() for item in selected_items))
        cols = sorted(set(item.column() for item in selected_items))
        
        # Create a matrix to store the data
        data = []
        for row in rows:
            row_data = []
            for col in cols:
                item = None
                for selected_item in selected_items:
                    if selected_item.row() == row and selected_item.column() == col:
                        item = selected_item
                        break
                if item:
                    row_data.append(item.text())
                else:
                    row_data.append('')
            if row_data:  # Only add non-empty rows
                data.append(row_data)
        
        # Store both text and structured data
        text_to_copy = '\n'.join('\t'.join(str(cell) for cell in row) for row in data)
        self.clipboard_data = {
            'text': text_to_copy,
            'data': data,
            'cells': set((item.row(), item.column()) for item in selected_items)
        }
        
        # Set system clipboard
        QApplication.clipboard().setText(text_to_copy)
        
        # Start selection animation if not cutting
        if not cut:
            self.clipboard_cells = self.clipboard_data['cells']
            self.selection_timer.start(500)  # Blink every 500ms
        else:
            self.selection_timer.stop()
            self.clipboard_cells.clear()

    def paste_cells(self):
        """Paste cells from clipboard"""
        if not self.edit_mode:
            return
            
        # Get selected cells or current cell
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            current_item = self.table.currentItem()
            if not current_item:
                return
            # Create a range for single cell
            selected_ranges = [QTableWidgetSelectionRange(
                current_item.row(), current_item.column(),
                current_item.row(), current_item.column()
            )]
        
        # Try to get structured data from our clipboard
        if self.clipboard_data and 'data' in self.clipboard_data:
            data = self.clipboard_data['data']
        else:
            # Fall back to system clipboard
            clipboard_text = QApplication.clipboard().text()
            if not clipboard_text:
                return
            # Parse clipboard text (tab-separated values)
            data = [row.split('\t') for row in clipboard_text.strip().split('\n')]
        
        # If single value and multiple cells selected, repeat the value
        if len(data) == 1 and len(data[0]) == 1:
            value = data[0][0]
            changes = []
            
            for sel_range in selected_ranges:
                for row in range(sel_range.topRow(), sel_range.bottomRow() + 1):
                    for col in range(sel_range.leftColumn(), sel_range.rightColumn() + 1):
                        if row >= self.table.rowCount() - 1 or col >= self.table.columnCount():  # Skip totals row
                            continue
                        
                        try:
                            # Get column type
                            col_name = self.table.horizontalHeaderItem(col).text()
                            dtype = self.column_types.get(col_name)
                            
                            # Convert value based on column type
                            if dtype:
                                if pd.isna(value) or value == '':
                                    converted_value = None
                                elif dtype == 'int64':
                                    clean_value = value.replace(',', '')
                                    converted_value = int(float(clean_value))
                                elif dtype == 'float64':
                                    clean_value = value.replace(',', '')
                                    converted_value = float(clean_value)
                                elif dtype == 'bool':
                                    converted_value = bool(value.lower() in ['true', '1', 'yes'])
                                elif dtype == 'datetime64[ns]':
                                    converted_value = pd.to_datetime(value)
                                else:
                                    converted_value = str(value)
                            else:
                                converted_value = value
                            
                            old_value = self.original_df.iloc[row, col]
                            changes.append((row, col, old_value, converted_value))
                            
                        except (ValueError, TypeError):
                            continue  # Skip cells that can't be converted
            
            if changes:
                # Create and push single command for all changes
                command = EditCommand(changes)
                self.command_stack.push(command)
                
                # Apply all changes
                for row, col, _, value in changes:
                    self.original_df.iloc[row, col] = value
                    item = self.table.item(row, col)
                    if item:
                        if pd.notna(value):
                            if isinstance(value, (int, float)):
                                item.setText(f"{value:,}")
                                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                            else:
                                item.setText(str(value))
                        else:
                            item.setText('')
                    self.modified_cells.add((row, col))
                
                self.modified = True
                self.save_action.setEnabled(True)
                self.update_undo_redo_state()
                self.update_status_bar()
                self.update_column_totals()
        else:
            # Normal paste operation for multiple values
            changes = []
            for sel_range in selected_ranges:
                start_row = sel_range.topRow()
                start_col = sel_range.leftColumn()
                
                for i, row_data in enumerate(data):
                    for j, value in enumerate(row_data):
                        row = start_row + i
                        col = start_col + j
                        
                        if row >= self.table.rowCount() - 1 or col >= self.table.columnCount():  # Skip totals row
                            continue
                        
                        try:
                            # Get column type
                            col_name = self.table.horizontalHeaderItem(col).text()
                            dtype = self.column_types.get(col_name)
                            
                            # Convert value based on column type
                            if dtype:
                                if pd.isna(value) or value == '':
                                    converted_value = None
                                elif dtype == 'int64':
                                    clean_value = value.replace(',', '')
                                    converted_value = int(float(clean_value))
                                elif dtype == 'float64':
                                    clean_value = value.replace(',', '')
                                    converted_value = float(clean_value)
                                elif dtype == 'bool':
                                    converted_value = bool(value.lower() in ['true', '1', 'yes'])
                                elif dtype == 'datetime64[ns]':
                                    converted_value = pd.to_datetime(value)
                                else:
                                    converted_value = str(value)
                            else:
                                converted_value = value
                            
                            old_value = self.original_df.iloc[row, col]
                            changes.append((row, col, old_value, converted_value))
                            
                        except (ValueError, TypeError):
                            continue  # Skip cells that can't be converted
            
            if changes:
                # Create and push single command for all changes
                command = EditCommand(changes)
                self.command_stack.push(command)
                
                # Apply all changes
                for row, col, _, value in changes:
                    self.original_df.iloc[row, col] = value
                    item = self.table.item(row, col)
                    if item:
                        if pd.notna(value):
                            if isinstance(value, (int, float)):
                                item.setText(f"{value:,}")
                                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                            else:
                                item.setText(str(value))
                        else:
                            item.setText('')
                    self.modified_cells.add((row, col))
                
                self.modified = True
                self.save_action.setEnabled(True)
                self.update_undo_redo_state()
                self.update_status_bar()
                self.update_column_totals()

    def calculate_selection_stats(self):
        """Calculate statistics for the selected cells and update the status bar label"""
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            self.stats_label.setText("") # Clear the label
            return
            
        total_cells = 0
        numeric_values = []
        
        for range_ in selected_ranges:
            for row in range(range_.topRow(), range_.bottomRow() + 1):
                for col in range(range_.leftColumn(), range_.rightColumn() + 1):
                    total_cells += 1
                    item = self.table.item(row, col)
                    if item:
                        try:
                            # Attempt to convert cell text to float, removing commas
                            value = float(item.text().replace(',', ''))
                            numeric_values.append(value)
                        except (ValueError, TypeError):
                            # Ignore non-numeric cells for sum/average
                            continue
        
        # Format the statistics string
        separator = "  |  " # Use consistent separator
        stats_parts = []
        stats_parts.append(f"Count: {total_cells:,}")
        
        if numeric_values: # Only show sum/avg if there are numeric values
            sum_val = sum(numeric_values)
            avg = sum_val / len(numeric_values)
            stats_parts.append(f"Sum: {sum_val:,.2f}")
            stats_parts.append(f"Average: {avg:,.2f}")
            
        # Join parts with the separator
        stats_text = separator.join(stats_parts)
            
        # Update the status bar label
        self.stats_label.setText(stats_text)

    def check_unsaved_changes(self):
        """Check for unsaved changes and handle them
        Returns:
            bool: True if it's safe to proceed, False if operation should be cancelled
        """
        if self.modified:
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Save Changes?")
            msg_box.setText("The document has been modified. Do you want to save your changes?")
            
            save_btn = msg_box.addButton("&Save", QMessageBox.AcceptRole)
            no_btn = msg_box.addButton("&No", QMessageBox.RejectRole)
            cancel_btn = msg_box.addButton("&Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(save_btn)
            msg_box.setEscapeButton(cancel_btn)
            
            msg_box.exec_()
            clicked_button = msg_box.clickedButton()
            
            if clicked_button == save_btn:
                return self.save_file()
            elif clicked_button == no_btn:
                return True
            else:  # Cancel
                return False
        return True

    def delete_column(self, column):
        """Delete a column from the table and DataFrame"""
        if not self.edit_mode:
            return
            
        # Get all selected columns if any
        selected_ranges = self.table.selectedRanges()
        columns_to_delete = set()
        column_names = []
        
        if selected_ranges:
            for range_ in selected_ranges:
                for col in range(range_.leftColumn(), range_.rightColumn() + 1):
                    columns_to_delete.add(col)
                    column_names.append(self.table.horizontalHeaderItem(col).text())
        else:
            columns_to_delete.add(column)
            column_names.append(self.table.horizontalHeaderItem(column).text())
            
        if not columns_to_delete:
            return
            
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Confirm Column Deletion")
        msg_box.setText(f"Are you sure you want to delete {len(columns_to_delete)} column(s)?")
        
        yes_btn = msg_box.addButton("&Yes", QMessageBox.YesRole)
        no_btn = msg_box.addButton("&No", QMessageBox.NoRole)
        msg_box.setDefaultButton(no_btn)
        
        msg_box.exec_()
        if msg_box.clickedButton() == yes_btn:
            # Delete from DataFrame
            self.original_df = self.original_df.drop(columns=column_names)
            
            # Delete from table (in reverse order to maintain indices)
            for col in sorted(columns_to_delete, reverse=True):
                self.table.removeColumn(col)
            
            # Update modified state
            self.modified = True
            self.save_action.setEnabled(True)
            self.update_status_bar()
            
            # Update column totals
            self.update_column_totals()

    def insert_row(self, row_index):
        """Insert a new row at the specified index using pd.concat"""
        if not self.edit_mode:
            return
            
        # Create a DataFrame for the new row with None values
        # Use existing columns to ensure alignment
        new_row_data = {col: [None] for col in self.original_df.columns}
        new_row_df = pd.DataFrame(new_row_data, index=[row_index]) # Assign index for potential sorting later if needed

        # Ensure new row DataFrame dtypes match original where possible (especially for non-object types)
        # This helps pandas concat logic but None will likely still result in object/float types initially
        for col in self.original_df.columns:
            if self.original_df[col].dtype != 'object':
                try:
                    # Attempt conversion, fallback to object if None causes issues
                    new_row_df[col] = new_row_df[col].astype(self.original_df[col].dtype)
                except (TypeError, ValueError):
                     # If conversion fails (e.g., None to int), keep as default (likely object)
                     pass 

        # Split original DataFrame
        df_top = self.original_df.iloc[:row_index]
        df_bottom = self.original_df.iloc[row_index:]
        
        # Concatenate the parts
        self.original_df = pd.concat([df_top, new_row_df, df_bottom], ignore_index=True)
        
        # Insert row visually into the QTableWidget
        self.table.insertRow(row_index)
        
        # Add empty cells to the new row in the table
        for col in range(self.table.columnCount()):
            item = QTableWidgetItem("") # Start with empty string
            # Set flags based on edit mode
            item.setFlags(item.flags() & ~Qt.ItemIsEditable) # Start non-editable
            if self.edit_mode:
                item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.table.setItem(row_index, col, item)
        
        # Update state
        self.modified = True
        self.save_action.setEnabled(True)
        self.update_status_bar()
        self.update_column_totals() # Update totals after insertion

    def delete_row(self, row):
        """Delete a row from the table and DataFrame"""
        if not self.edit_mode:
            return
            
        # Get all selected rows if any
        selected_ranges = self.table.selectedRanges()
        rows_to_delete = set()
        
        if selected_ranges:
            for range_ in selected_ranges:
                for row in range(range_.topRow(), range_.bottomRow() + 1):
                    rows_to_delete.add(row)
        else:
            rows_to_delete.add(row)
            
        if not rows_to_delete:
            return
            
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Confirm Row Deletion")
        msg_box.setText(f"Are you sure you want to delete {len(rows_to_delete)} row(s)?")
        
        yes_btn = msg_box.addButton("&Yes", QMessageBox.YesRole)
        no_btn = msg_box.addButton("&No", QMessageBox.NoRole)
        msg_box.setDefaultButton(no_btn)
        
        msg_box.exec_()
        if msg_box.clickedButton() == yes_btn:
            # Delete from DataFrame
            self.original_df = self.original_df.drop(index=sorted(rows_to_delete))
            self.original_df.reset_index(drop=True, inplace=True)
            
            # Delete from table (in reverse order to maintain indices)
            for row in sorted(rows_to_delete, reverse=True):
                self.table.removeRow(row)
            
            # Update modified state
            self.modified = True
            self.save_action.setEnabled(True)
            self.update_status_bar()
            
            # Update column totals
            self.update_column_totals()

    def add_new_column(self, position=None):
        """Add a new column to the table and DataFrame at the specified position."""
        if not self.edit_mode:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Column")
        layout = QVBoxLayout(dialog)
        
        # Column name input
        name_label = QLabel("Column Name:")
        layout.addWidget(name_label)
        name_input = QLineEdit()
        layout.addWidget(name_input)
        
        # Data type selection
        type_label = QLabel("Data Type:")
        layout.addWidget(type_label)
        type_combo = QComboBox()
        type_combo.addItems(["Text", "Integer", "Float", "Boolean", "DateTime"])
        layout.addWidget(type_combo)
        
        # Default value input
        default_label = QLabel("Default Value (optional):")
        layout.addWidget(default_label)
        default_input = QLineEdit()
        layout.addWidget(default_input)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            column_name = name_input.text().strip()
            if not column_name:
                QMessageBox.warning(self, "Error", "Column name cannot be empty.")
                return
                
            # Check if column name already exists
            if column_name in self.original_df.columns:
                QMessageBox.warning(self, "Error", "Column name already exists.")
                return
                
            # Get data type
            dtype_map = {
                "Text": "object",
                "Integer": "int64",
                "Float": "float64",
                "Boolean": "bool",
                "DateTime": "datetime64[ns]"
            }
            dtype = dtype_map[type_combo.currentText()]
            
            # Get default value
            default_value_str = default_input.text().strip()
            default_value = None
            if default_value_str:
                try:
                    if dtype == "int64":
                        default_value = int(float(default_value_str.replace(',', '')))
                    elif dtype == "float64":
                        default_value = float(default_value_str.replace(',', ''))
                    elif dtype == "bool":
                        default_value = default_value_str.lower() in ['true', '1', 'yes']
                    elif dtype == "datetime64[ns]":
                        default_value = pd.to_datetime(default_value_str)
                    else: # Text
                        default_value = default_value_str
                except (ValueError, TypeError) as e:
                    QMessageBox.warning(self, "Error", f"Invalid default value for selected type: {str(e)}")
                    return
            
            # Determine insertion index
            # If position is None or out of bounds, insert at the end
            num_cols = self.table.columnCount()
            if position is None or not (0 <= position <= num_cols):
                col_idx = num_cols
            else:
                col_idx = position

            # Explicitly cast to int just in case
            loc_index = int(col_idx)

            # Insert into DataFrame at the correct position
            self.original_df.insert(loc=loc_index, column=column_name,
                                  value=pd.Series([default_value] * len(self.original_df), dtype=dtype))
            self.column_types[column_name] = dtype
            
            # Insert column into the table at the correct position
            self.table.insertColumn(col_idx)
            self.table.setHorizontalHeaderItem(col_idx, QTableWidgetItem(column_name))
            
            # Populate new column cells
            self.populating_new_column = True # Set flag
            try:
                for row in range(self.table.rowCount()): # Includes totals row if applicable
                    item = QTableWidgetItem()
                    if default_value is not None:
                        if isinstance(default_value, (int, float)):
                            item.setText(f"{default_value:,}")
                            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        else:
                            item.setText(str(default_value))
                    
                    # Ensure item editability matches current edit mode
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable) # Start as non-editable
                    if self.edit_mode:
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                        
                    self.table.setItem(row, col_idx, item)
            finally:
                self.populating_new_column = False # Reset flag
            
            # Update modified state
            self.modified = True
            self.save_action.setEnabled(True)
            self.update_status_bar()
            
            # Update column totals (which will also handle totals row formatting)
            self.update_column_totals()
            
            # Adjust column width
            self.adjust_all_columns()

    def create_new_file(self):
        """Create a new empty parquet file"""
        # Check for unsaved changes first
        if not self.check_unsaved_changes():
            return
            
        # Create an empty DataFrame
        self.original_df = pd.DataFrame()
        self.column_types = {}
        
        # Clear the table
        self.table.clear()
        self.table.setRowCount(1)  # Just the totals row
        self.table.setColumnCount(0)
        
        # Reset state
        self.current_file = None
        self.modified = False
        self.modified_cells.clear()
        self.command_stack.clear()
        self.filters.clear()
        
        # Update UI
        self.setWindowTitle("Untitled - Parquet File Viewer")
        self.save_action.setEnabled(False)
        self.update_status_bar()
        
        # Enable edit mode automatically for new files
        self.edit_mode = True
        self.edit_mode_action.setChecked(True)
        self.update_status_bar()
        
        # Add initial column
        self.add_new_column()

    def show_totals_context_menu(self, position):
        """Show context menu for totals row"""
        menu = QMenu()
        copy_action = menu.addAction("Copy")
        
        action = menu.exec_(self.totals_widget.viewport().mapToGlobal(position))
        
        if action == copy_action:
            self.copy_totals()

    def copy_totals(self):
        """Copy selected cells from totals row"""
        selected_items = self.totals_widget.selectedItems()
        if not selected_items:
            return
            
        # Create a list to store the data
        data = []
        current_row = []
        
        for item in selected_items:
            current_row.append(item.text())
        
        if current_row:
            data.append(current_row)
        
        # Convert to tab-separated string
        text_to_copy = '\n'.join('\t'.join(row) for row in data)
        QApplication.clipboard().setText(text_to_copy)

    def on_header_click(self, logical_index):
        """Handle column header click to select entire column"""
        # Select the entire column
        self.table.setRangeSelected(
            QTableWidgetSelectionRange(
                0, logical_index,
                self.table.rowCount() - 1, logical_index
            ),
            True
        )

def main():
    app = QApplication(sys.argv)
    window = ParquetViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()