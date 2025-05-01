import sys
import os
import warnings
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                            QMenuBar, QMenu, QAction, QMessageBox, QFrame, QDialog, QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QPalette, QColor
import configparser
from pathlib import Path

# Suppress PyQt5 deprecation warning
warnings.filterwarnings("ignore", category=DeprecationWarning)

class ParquetViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parquet File Viewer")
        self.setGeometry(100, 100, 800, 600)
        
        # Initialize config
        self.config = configparser.ConfigParser()
        self.config_file = os.path.join(os.path.expanduser('~'), 'Documents', 'parquet_viewer.ini')
        
        # Create menu bar
        self.create_menu_bar()
        
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
        
        # Configure header for right-click menu
        header = self.table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_filter_menu)
        header.setSectionsClickable(True)
        
        layout.addWidget(self.table)
        
        # Store filter values
        self.filters = {}
        
        # Apply initial theme
        self.apply_theme()
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open Parquet File", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        # Dark mode action
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        settings_menu.addAction(self.dark_mode_action)
        
        # Clear all filters action
        clear_filters_action = QAction("Clear All Filters", self)
        clear_filters_action.triggered.connect(self.clear_all_filters)
        settings_menu.addAction(clear_filters_action)
    
    def load_settings(self):
        """Load settings from config file"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            self.dark_mode = self.config.getboolean('Settings', 'dark_mode', fallback=False)
            self.last_folder = self.config.get('Settings', 'last_folder', fallback=os.path.join(os.path.expanduser('~'), 'Documents'))
        else:
            self.dark_mode = False
            self.last_folder = os.path.join(os.path.expanduser('~'), 'Documents')
            self.save_settings()
        
        # Sync the menu toggle state with the loaded setting
        if hasattr(self, 'dark_mode_action'):
            self.dark_mode_action.setChecked(self.dark_mode)

    def save_settings(self):
        """Save current settings to config file"""
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.config.set('Settings', 'dark_mode', str(self.dark_mode))
        self.config.set('Settings', 'last_folder', self.last_folder)
        
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def toggle_dark_mode(self):
        self.dark_mode = self.dark_mode_action.isChecked()
        self.apply_theme()
        self.save_settings()  # Save settings when dark mode is toggled
    
    def show_context_menu(self, position):
        """Show context menu for copying cell contents"""
        menu = QMenu()
        copy_action = menu.addAction("Copy")
        
        # Get selected items
        selected_items = self.table.selectedItems()
        if selected_items:
            action = menu.exec_(self.table.viewport().mapToGlobal(position))
            if action == copy_action:
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

    def update_header_style(self):
        """Update header style to show filtered columns"""
        header = self.table.horizontalHeader()
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item:
                text = item.text()
                if col in self.filters:
                    # Add a filter indicator to the header text
                    if not text.endswith(' 🔍'):
                        item.setText(f"{text} 🔍")
                    item.setToolTip(f"Filter: {self.filters[col]}")
                else:
                    # Remove filter indicator if exists
                    if text.endswith(' 🔍'):
                        item.setText(text[:-2])
                    item.setToolTip("")

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
        menu.addSeparator()
        clear_all_action = menu.addAction("Clear All Filters")
        
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
        elif action == clear_all_action:
            self.clear_all_filters()

    def clear_all_filters(self):
        """Clear all active filters"""
        self.filters.clear()
        self.apply_filters()
        self.update_header_style()

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
            
            try:
                # Read the parquet file
                df = pd.read_parquet(file_name)
                
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
                        item = QTableWidgetItem(str(df.iloc[i, j]))
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        self.table.setItem(i, j, item)
                
                # Resize columns to fit content
                self.table.resizeColumnsToContents()
                
                # Enable sorting after data is loaded
                self.table.setSortingEnabled(True)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error reading file: {e}")

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
        
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            self.table.clearSelection()
        super().keyPressEvent(event)

def main():
    app = QApplication(sys.argv)
    window = ParquetViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()