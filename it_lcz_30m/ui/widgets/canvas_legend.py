# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Canvas Legend Widget

A floating widget that overlays on the QGIS Map Canvas to show layer legends.
"""

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QPushButton, QFrame
)
from qgis.PyQt.QtGui import QColor, QPalette

class CanvasLegend(QFrame):
    """Floating legend widget for the QGIS Map Canvas."""
    
    def __init__(self, parent_canvas):
        # We set parent to the canvas to stay on top and move with it
        super().__init__(parent_canvas)
        self.canvas = parent_canvas
        self._setup_ui()
        self.hide()
        
        # Position in bottom right (initially)
        self.setFixedWidth(200)
        self.setObjectName("CanvasLegend")
        self.setStyleSheet("""
            QFrame#CanvasLegend {
                background-color: rgba(255, 255, 255, 230);
                border: 1px solid #dcdde1;
                border-radius: 8px;
            }
            QLabel#LegendTitle {
                font-weight: bold;
                font-size: 11px;
                color: #2c3e50;
                padding: 2px;
            }
            QLabel#LegendItemLabel {
                font-size: 10px;
                color: #34495e;
            }
            QPushButton#CloseButton {
                border: none;
                background-color: transparent;
                color: #7f8c8d;
                font-weight: bold;
                font-size: 14px;
                padding: 0 5px;
            }
            QPushButton#CloseButton:hover {
                color: #e74c3c;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QWidget#ScrollContent {
                background-color: transparent;
            }
        """)

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 10)
        self.main_layout.setSpacing(5)
        
        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_title = QLabel("Legenda")
        self.lbl_title.setObjectName("LegendTitle")
        self.lbl_title.setWordWrap(True)
        header_layout.addWidget(self.lbl_title)
        
        btn_close = QPushButton("×")
        btn_close.setObjectName("CloseButton")
        btn_close.setFixedSize(20, 20)
        btn_close.clicked.connect(self.hide)
        header_layout.addWidget(btn_close)
        
        self.main_layout.addWidget(header)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #f0f0f0; margin: 2px 0;")
        self.main_layout.addWidget(line)
        
        # Content Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ScrollContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        
        self.scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll)

    def update_legend(self, title, items):
        """
        Update the legend content.
        items: list of (color_hex, label)
        """
        self.lbl_title.setText(title)
        
        # Clear previous items
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for color_hex, label in items:
            item_row = QWidget()
            row_layout = QHBoxLayout(item_row)
            row_layout.setContentsMargins(2, 2, 2, 2)
            row_layout.setSpacing(8)
            
            # Color patch
            patch = QFrame()
            patch.setFixedSize(14, 14)
            patch.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #bdc3c7; border-radius: 2px;")
            row_layout.addWidget(patch)
            
            # Label
            lbl = QLabel(label)
            lbl.setObjectName("LegendItemLabel")
            lbl.setWordWrap(True)
            row_layout.addWidget(lbl)
            
            row_layout.addStretch()
            self.content_layout.addWidget(item_row)
            
        self.content_layout.addStretch()
        
        # Ensure layout is processed
        self.content_widget.adjustSize()
        self.show()
        
        # Short delay to allow QGIS/Qt to settle the layout for accurate size hint
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(10, self._reposition)

    def _reposition(self):
        """Anchor the widget to the bottom right of the canvas."""
        if not self.canvas or self.isHidden():
            return
        
        canvas_width = self.canvas.width()
        canvas_height = self.canvas.height()
        
        # Force redraw of content to get accurate height
        self.content_widget.adjustSize()
        content_h = self.content_widget.sizeHint().height()
        
        # Calculate required height precisely
        # Header + Line + Layout Spacing + Margins
        # We can use the main layout's size hint if we temporarily disable fixed height
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        
        header_h = self.lbl_title.parent().sizeHint().height() if self.lbl_title.parent() else 30
        line_h = 5
        margins_h = self.main_layout.contentsMargins().top() + self.main_layout.contentsMargins().bottom()
        spacing_h = self.main_layout.spacing() * 3 # approx sections
        
        required_h = content_h + header_h + line_h + margins_h + spacing_h + 10
        
        # Max available height on canvas (with margins)
        margin = 15
        max_h = canvas_height - (margin * 2) - 40 # extra buffer for UI bars
        
        h = min(required_h, max_h)
        w = self.width()
        
        self.setFixedHeight(int(h))
        
        # Bottom-right corner
        self.move(canvas_width - w - margin, canvas_height - h - margin)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Repositioning is usually handled by the parent's resize event 
        # but we can force it here too if needed.
        pass

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition()
