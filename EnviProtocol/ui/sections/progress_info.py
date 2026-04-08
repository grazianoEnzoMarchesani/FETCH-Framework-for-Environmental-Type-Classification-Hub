# -*- coding: utf-8 -*-
"""
EnviProtocol Dashboard - Progress Info Section

Progress bar and status display for background operations.
"""

from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar


class ProgressInfoSection(QWidget):
    """Progress and status display section."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Status label
        self.status_label = QLabel("Pronto")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.main_layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                text-align: center;
                background-color: #f1f2f6;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        self.main_layout.addWidget(self.progress)
        
    def set_status(self, text, is_error=False, is_busy=False):
        """Set the status text and styling."""
        self.status_label.setText(text)
        if is_error:
            self.status_label.setStyleSheet("font-weight: bold; color: #c0392b;")
        elif is_busy:
            self.status_label.setStyleSheet("font-weight: bold; color: #c0392b;")
        else:
            self.status_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
            
    def set_progress(self, value, maximum=100):
        """Set the progress bar value."""
        self.progress.setMaximum(maximum)
        self.progress.setValue(value)
        
    def set_indeterminate(self, indeterminate=True):
        """Set progress bar to indeterminate mode."""
        if indeterminate:
            self.progress.setMaximum(0)
        else:
            self.progress.setMaximum(100)
            
    def reset(self):
        """Reset to ready state."""
        self.set_status("Pronto")
        self.set_progress(0)
