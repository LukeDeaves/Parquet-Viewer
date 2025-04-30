import sys
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QPushButton, QFileDialog, QTableWidget, QTableWidgetItem)
from PyQt5.QtCore import Qt

class ParquetViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parquet File Viewer")
        self.setGeometry(100, 100, 800, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create button to open file
        self.open_button = QPushButton("Open Parquet File")
        self.open_button.clicked.connect(self.open_file)
        layout.addWidget(self.open_button)
        
        # Create table widget to display data
        self.table = QTableWidget()
        layout.addWidget(self.table)
        
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
                print(f"Error reading file: {e}")

def main():
    app = QApplication(sys.argv)
    window = ParquetViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 