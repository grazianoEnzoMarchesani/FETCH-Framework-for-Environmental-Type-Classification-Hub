# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Help Mixin

Provides functionality to add help buttons and show help dialogs.
"""

from qgis.PyQt.QtWidgets import QPushButton, QMessageBox
from qgis.PyQt.QtCore import Qt

class HelpMixin:
    """Mixin to provide points of explanation for UI elements."""
    
    def create_help_button(self, help_key, content_dict):
        """
        Creates an elegant '?' button.
        
        Args:
            help_key: Key in the content_dict
            content_dict: Dictionary containing help data
        """
        btn = QPushButton("?")
        btn.setObjectName("HelpButton")
        btn.setFixedSize(18, 18)
        btn.setCursor(Qt.PointingHandCursor)
        
        # Connect to show help message
        btn.clicked.connect(lambda: self.show_help_message(help_key, content_dict))
        
        # Basic tooltip as preview
        if help_key in content_dict:
            btn.setToolTip(f"Clicca per spiegazione: {content_dict[help_key]['title']}")
            
        return btn

    def show_help_message(self, help_key, content_dict):
        """Displays a formatted help dialog."""
        if help_key not in content_dict:
            return
            
        data = content_dict[help_key]
        msg = QMessageBox(self)
        msg.setWindowTitle("Info Elemento")
        
        # Formatted text
        text = f"<h3>{data['title']}</h3>"
        text += f"<p>{data['content']}</p>"
        text += f"<hr><p style='font-size: 10px; color: #7f8c8d;'><i>Fonte: {data['source']}</i></p>"
        
        if 'url' in data and data['url']:
            text += f"<p><a href='{data['url']}'>🔗 Link al servizio/repository</a></p>"
        
        msg.setText(text)
        msg.setTextFormat(Qt.RichText)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
