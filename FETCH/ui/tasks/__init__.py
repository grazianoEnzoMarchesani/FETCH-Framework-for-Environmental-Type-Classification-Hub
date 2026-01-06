# -*- coding: utf-8 -*-
"""
FETCH Dashboard - Background Tasks

This package contains all QgsTask subclasses for background processing.
"""

from .download_task import DownloadTask
from .unify_task import UnifyTask
from .dsm_task import DSMTask
from .svf_task import SVFTask
from .grid_task import GridTask
from .parameter_task import LCZParameterTask
from .classification_task import ClassificationTask

__all__ = [
    'DownloadTask',
    'UnifyTask', 
    'DSMTask',
    'SVFTask',
    'GridTask',
    'LCZParameterTask',
    'ClassificationTask'
]
