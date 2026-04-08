# -*- coding: utf-8 -*-
"""
Qt6/QGIS 4 Compatibility Shim for EnviProtocol Plugin.
Injects missing Qt5-style attributes into the Qt and Qgis namespaces.
"""

from qgis.PyQt.QtCore import Qt, QMetaType
from qgis.PyQt.QtWidgets import QLineEdit, QMessageBox
from qgis.core import Qgis, QgsVectorFileWriter

def apply_qt_compatibility():
    """
    Checks if we are running in a Qt6 environment (QGIS 4) 
    and injects missing constants for backward compatibility.
    """
    
    # --- Qt Namespace Injections ---
    
    # 1. DockWidgetArea
    if not hasattr(Qt, 'LeftDockWidgetArea'):
        Qt.LeftDockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea
        Qt.RightDockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea
        Qt.TopDockWidgetArea = Qt.DockWidgetArea.TopDockWidgetArea
        Qt.BottomDockWidgetArea = Qt.DockWidgetArea.BottomDockWidgetArea
        Qt.AllDockWidgetAreas = Qt.DockWidgetArea.AllDockWidgetAreas
    
    # 2. Alignment
    if not hasattr(Qt, 'AlignCenter'):
        Qt.AlignLeft = Qt.AlignmentFlag.AlignLeft
        Qt.AlignRight = Qt.AlignmentFlag.AlignRight
        Qt.AlignHCenter = Qt.AlignmentFlag.AlignHCenter
        Qt.AlignVCenter = Qt.AlignmentFlag.AlignVCenter
        Qt.AlignCenter = Qt.AlignmentFlag.AlignCenter
        Qt.AlignTop = Qt.AlignmentFlag.AlignTop
        Qt.AlignBottom = Qt.AlignmentFlag.AlignBottom
        Qt.AlignJustify = Qt.AlignmentFlag.AlignJustify

    # 3. CheckState
    if not hasattr(Qt, 'Checked'):
        Qt.Checked = Qt.CheckState.Checked
        Qt.Unchecked = Qt.CheckState.Unchecked
        Qt.PartiallyChecked = Qt.CheckState.PartiallyChecked

    # 4. CursorShape
    if not hasattr(Qt, 'PointingHandCursor'):
        Qt.PointingHandCursor = Qt.CursorShape.PointingHandCursor
        Qt.ArrowCursor = Qt.CursorShape.ArrowCursor
        Qt.WaitCursor = Qt.CursorShape.WaitCursor
        Qt.IBeamCursor = Qt.CursorShape.IBeamCursor
        Qt.SizeVerCursor = Qt.CursorShape.SizeVerCursor
        Qt.SizeHorCursor = Qt.CursorShape.SizeHorCursor
        Qt.SizeBDiagCursor = Qt.CursorShape.SizeBDiagCursor
        Qt.SizeFDiagCursor = Qt.CursorShape.SizeFDiagCursor
        Qt.SizeAllCursor = Qt.CursorShape.SizeAllCursor
        Qt.BlankCursor = Qt.CursorShape.BlankCursor
        Qt.SplitVCursor = Qt.CursorShape.SplitVCursor
        Qt.SplitHCursor = Qt.CursorShape.SplitHCursor
        Qt.PointingHandCursor = Qt.CursorShape.PointingHandCursor
        Qt.ForbiddenCursor = Qt.CursorShape.ForbiddenCursor
        Qt.OpenHandCursor = Qt.CursorShape.OpenHandCursor
        Qt.ClosedHandCursor = Qt.CursorShape.ClosedHandCursor
        Qt.WhatsThisCursor = Qt.CursorShape.WhatsThisCursor
        Qt.BusyCursor = Qt.CursorShape.BusyCursor

    # 5. TextFormat
    if not hasattr(Qt, 'RichText'):
        Qt.RichText = Qt.TextFormat.RichText
        Qt.PlainText = Qt.TextFormat.PlainText
        Qt.AutoText = Qt.TextFormat.AutoText
        Qt.MarkdownText = getattr(Qt.TextFormat, 'MarkdownText', Qt.TextFormat.RichText)

    # 6. Orientation
    if not hasattr(Qt, 'Horizontal'):
        Qt.Horizontal = Qt.Orientation.Horizontal
        Qt.Vertical = Qt.Orientation.Vertical

    # 7. ItemDataRole
    if not hasattr(Qt, 'DisplayRole'):
        Qt.DisplayRole = Qt.ItemDataRole.DisplayRole
        Qt.DecorationRole = Qt.ItemDataRole.DecorationRole
        Qt.EditRole = Qt.ItemDataRole.EditRole
        Qt.ToolTipRole = Qt.ItemDataRole.ToolTipRole
        Qt.StatusTipRole = Qt.ItemDataRole.StatusTipRole
        Qt.WhatsThisRole = Qt.ItemDataRole.WhatsThisRole
        Qt.FontRole = Qt.ItemDataRole.FontRole
        Qt.TextAlignmentRole = Qt.ItemDataRole.TextAlignmentRole
        Qt.BackgroundRole = Qt.ItemDataRole.BackgroundRole
        Qt.ForegroundRole = Qt.ItemDataRole.ForegroundRole
        Qt.CheckStateRole = Qt.ItemDataRole.CheckStateRole
        Qt.InitialSortOrderRole = Qt.ItemDataRole.InitialSortOrderRole
        Qt.UserRole = Qt.ItemDataRole.UserRole

    # --- QLineEdit Injections ---
    if not hasattr(QLineEdit, 'Password'):
        try:
            QLineEdit.Normal = QLineEdit.EchoMode.Normal
            QLineEdit.NoEcho = QLineEdit.EchoMode.NoEcho
            QLineEdit.Password = QLineEdit.EchoMode.Password
            QLineEdit.PasswordEchoOnEdit = QLineEdit.EchoMode.PasswordEchoOnEdit
        except AttributeError:
            pass

    # --- QMessageBox Injections ---
    if not hasattr(QMessageBox, 'Ok'):
        try:
            QMessageBox.Ok = QMessageBox.StandardButton.Ok
            QMessageBox.Save = QMessageBox.StandardButton.Save
            QMessageBox.SaveAll = QMessageBox.StandardButton.SaveAll
            QMessageBox.Open = QMessageBox.StandardButton.Open
            QMessageBox.Yes = QMessageBox.StandardButton.Yes
            QMessageBox.No = QMessageBox.StandardButton.No
            QMessageBox.Abort = QMessageBox.StandardButton.Abort
            QMessageBox.Retry = QMessageBox.StandardButton.Retry
            QMessageBox.Ignore = QMessageBox.StandardButton.Ignore
            QMessageBox.Cancel = QMessageBox.StandardButton.Cancel
            QMessageBox.Close = QMessageBox.StandardButton.Close
            
            QMessageBox.NoIcon = QMessageBox.Icon.NoIcon
            QMessageBox.Information = QMessageBox.Icon.Information
            QMessageBox.Warning = QMessageBox.Icon.Warning
            QMessageBox.Critical = QMessageBox.Icon.Critical
            QMessageBox.Question = QMessageBox.Icon.Question
        except AttributeError:
            pass

    # --- QgsVectorFileWriter Injections ---
    if not hasattr(QgsVectorFileWriter, 'NoError'):
        try:
            # QGIS 4 uses WriterError and ActionOnExistingFile enums
            QgsVectorFileWriter.NoError = QgsVectorFileWriter.WriterError.NoError
            QgsVectorFileWriter.CreateOrOverwriteFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
        except AttributeError:
            pass

    # --- Qgis Namespace Injections (QGIS 4 specific) ---
    if not hasattr(Qgis, 'Warning'):
        try:
            # Map legacy names to new MessageLevel enum
            Qgis.Info = Qgis.MessageLevel.Info
            Qgis.Warning = Qgis.MessageLevel.Warning
            Qgis.Critical = Qgis.MessageLevel.Critical
            Qgis.Success = Qgis.MessageLevel.Success
            Qgis.NoLevel = Qgis.MessageLevel.NoLevel
        except AttributeError:
            pass

    # --- QMetaType Injections ---
    if not hasattr(QMetaType, 'QString'):
        try:
            QMetaType.QString = QMetaType.Type.QString
            QMetaType.Int = QMetaType.Type.Int
            QMetaType.Double = QMetaType.Type.Double
            QMetaType.Bool = QMetaType.Type.Bool
        except AttributeError:
            pass
