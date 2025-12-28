# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Qt Stylesheet Definitions

This module contains all CSS/Qt stylesheet constants for the FETCH Dashboard UI.
"""

STYLESHEET = """
QWidget#DashboardRoot {
    background-color: #f5f6f7;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #dcdde1;
    border-radius: 6px;
    margin-top: 20px;
    padding: 15px 10px 10px 10px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: #2c3e50;
}
QPushButton {
    border: none;
    border-radius: 4px;
    padding: 8px 15px;
    font-size: 12px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: rgba(0,0,0,0.1);
}
#PrimaryButton {
    background-color: #3498db;
    color: white;
    font-weight: bold;
}
#PrimaryButton:hover {
    background-color: #2980b9;
}
#DarkButton {
    background-color: #2c3e50;
    color: white;
    font-weight: bold;
}
#DarkButton:hover {
    background-color: #1a252f;
}
#AccentButton {
    background-color: #9b59b6;
    color: white;
}
#AccentButton:hover {
    background-color: #8e44ad;
}
#SuccessButton {
    background-color: #27ae60;
    color: white;
    font-weight: bold;
}
#SuccessButton:hover {
    background-color: #219150;
}
#WarningLabel {
    color: #d35400; 
    font-weight: bold; 
    background-color: #fff3e0; 
    border: 1px solid #ffe0b2; 
    border-radius: 4px; 
    padding: 8px;
}
#ExtentLabel {
    font-family: 'Courier New', Courier, monospace;
    font-size: 11px;
    background-color: #f1f2f6;
    border: 1px solid #dfe4ea;
    border-radius: 3px;
    padding: 5px;
    color: #57606f;
}
#PrimaryButton:disabled, #DarkButton:disabled, #AccentButton:disabled, #SuccessButton:disabled {
    background-color: #e0e0e0;
    color: #a0a0a0;
}
QLabel:disabled, QCheckBox:disabled, QRadioButton:disabled {
    color: #b2bec3;
}
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #dcdde1;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 11px;
    color: #2c3e50;
}
QLineEdit:focus {
    border: 1px solid #3498db;
    background-color: #fdfdfd;
}
#IndicatorButton {
    background-color: #bdc3c7;
    border: none;
    border-radius: 8px;
    min-width: 16px;
    max-width: 16px;
    min-height: 16px;
    max-height: 16px;
    padding: 0;
    margin: 0 2px;
}
#IndicatorButton:enabled {
    background-color: #27ae60;
}
#IndicatorButton:enabled:hover {
    background-color: #2ecc71;
}
#IndicatorButton:disabled {
    background-color: #bdc3c7;
}
#ParamRow, #SourceRow {
    background-color: #ffffff;
    border-bottom: 1px solid #f0f0f0;
}
#ParamRow:hover, #SourceRow:hover {
    background-color: #fcfcfc;
}
#ResultsCard, #CredentialCard {
    background-color: #f1f2f6; 
    border: 1px solid #dcdde1; 
    border-radius: 6px;
}
#ResultsHeader, #CardHeader {
    font-size: 10px; 
    font-weight: bold; 
    color: #7f8c8d; 
    text-transform: uppercase;
}
#AuthLink {
    color: #3498db;
    text-decoration: underline;
}
#StatusText {
    font-size: 10px;
    font-weight: bold;
}
#CalculateButton {
    background-color: #f8f9fa;
    color: #2c3e50;
    border: 1px solid #dcdde1;
    font-weight: 600;
    font-size: 10px;
    padding: 4px 10px;
    min-width: 80px;
}
#CalculateButton:hover {
    background-color: #e9ecef;
    border-color: #bdc3c7;
}
#CalculateButton:pressed {
    background-color: #dee2e6;
}
#CalculateButton:disabled {
    background-color: #f1f2f6;
    color: #b2bec3;
}
#VisualButton {
    background-color: #f8f9fa; 
    border: 1px solid #dcdde1;
    border-radius: 9px;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    padding: 0;
}
#VisualButton:enabled {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2ecc71, stop:1 #27ae60);
    border: 1px solid #219150;
}
#VisualButton:enabled:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #34e883, stop:1 #2ecc71);
    border-color: #27ae60;
}
#VisualButton:disabled {
    background-color: #f8f9fa;
    border: 1px dashed #ced4da;
}
"""
