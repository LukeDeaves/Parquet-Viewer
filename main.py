import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                            QMenuBar, QMenu, QAction, QMessageBox, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
import configparser
from pathlib import Path

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
        layout.addWidget(self.table)
        
        # Apply initial theme
        self.apply_theme()
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open Parquet File", self)
        open_action.setShortcut("Ctrl+O")  # Add keyboard shortcut
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        # Dark mode action
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        settings_menu.addAction(self.dark_mode_action)
    
    def load_settings(self):
        """Load settings from config file"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            self.dark_mode = self.config.getboolean('Settings', 'dark_mode', fallback=False)
        else:
            self.dark_mode = False
            self.save_settings()
        
        # Sync the menu toggle state with the loaded setting
        if hasattr(self, 'dark_mode_action'):
            self.dark_mode_action.setChecked(self.dark_mode)

    def save_settings(self):
        """Save current settings to config file"""
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.config.set('Settings', 'dark_mode', str(self.dark_mode))
        
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def toggle_dark_mode(self):
        self.dark_mode = self.dark_mode_action.isChecked()
        self.apply_theme()
        self.save_settings()  # Save settings when dark mode is toggled
    
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
        
    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Parquet File",
            "",
            "Parquet Files (*.parquet);;All Files (*)"
        )
        
        if file_name:
            try:
                # Read the parquet file
                df = pd.read_parquet(file_name)
                
                # Update window title with file name
                base_name = os.path.basename(file_name)
                name_without_ext = os.path.splitext(base_name)[0]
                self.setWindowTitle(f"{name_without_ext} - Parquet File Viewer")
                
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
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error reading file: {e}")

def main():
    app = QApplication(sys.argv)
    window = ParquetViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()