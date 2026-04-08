# -*- coding: utf-8 -*-

import os.path

# Apply platform-specific fixes (MacOS multiprocessing, PROJ_LIB)
from .core.utils import apply_plugin_fixes
from .core.qt_compat import apply_qt_compatibility

# Apply Qt6/QGIS 4 compatibility before anything else
apply_qt_compatibility()
apply_plugin_fixes()


from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .ui.dashboard import EnviProtocolDashboard

class EnviProtocol:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'EnviProtocol'
        self.dock_widget = None

    def tr(self, message):
        return QCoreApplication.translate('EnviProtocol', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip:
            action.setStatusTip(status_tip)
        if whats_this:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr('EnviProtocol Dashboard'),
            callback=self.run,
            parent=self.iface.mainWindow()
        )

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)

    def run(self):
        if not self.dock_widget:
            self.dock_widget = EnviProtocolDashboard(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        
        self.dock_widget.show()
        self.dock_widget.raise_()
