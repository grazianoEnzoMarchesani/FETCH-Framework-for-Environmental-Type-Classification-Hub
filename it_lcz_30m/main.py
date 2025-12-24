# -*- coding: utf-8 -*-

import sys
import multiprocessing
import os.path

# MacOS Multiprocessing Fix for QGIS (prevents opening extra GUI instances)
if sys.platform == 'darwin':
    exe_dir = os.path.dirname(sys.executable)
    # Search for versioned python (e.g., python3.12) as priority
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    candidate_names = [f"python{py_ver}", "python3", "Python"]
    
    found_p = None
    for folder in [exe_dir, os.path.join(exe_dir, "bin")]:
        for name in candidate_names:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                found_p = p
                break
        if found_p: break
        
    if found_p:
        try:
            if not hasattr(sys, '_qgis_executable'):
                sys._qgis_executable = sys.executable
            sys.executable = found_p
            multiprocessing.set_executable(found_p)
        except: pass
    try:
        if multiprocessing.get_start_method(allow_none=True) != 'spawn':
            multiprocessing.set_start_method('spawn', force=True)
    except: pass


from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .ui.dashboard import ITLCZDashboard

class ITLCZ30m:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'FETCH'
        self.dock_widget = None

    def tr(self, message):
        return QCoreApplication.translate('FETCH', message)

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
            text=self.tr('FETCH Dashboard'),
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
            self.dock_widget = ITLCZDashboard(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        
        self.dock_widget.show()
        self.dock_widget.raise_()
