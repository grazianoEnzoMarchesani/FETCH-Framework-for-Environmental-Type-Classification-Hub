# -*- coding: utf-8 -*-
"""
EnviProtocol Dashboard - Background Tasks

This package contains all QgsTask subclasses for background processing.
"""

from .download_task import DownloadTask
from .envimet_task import ENVImetTask

__all__ = [
    'DownloadTask',
    'ENVImetTask'
]
