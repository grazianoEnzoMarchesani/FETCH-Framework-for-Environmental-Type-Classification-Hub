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
"""
