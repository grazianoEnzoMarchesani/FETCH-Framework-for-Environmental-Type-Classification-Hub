# -*- coding: utf-8 -*-
"""
EnviProtocol Dashboard - UI Section Widgets

This package contains modular UI section widgets for the EnviProtocol Dashboard.
"""

from .project_setup import ProjectSetupSection
from .data_acquisition import DataAcquisitionSection
from .envimet_export import ENVImetExportSection
from .progress_info import ProgressInfoSection

__all__ = [
    'ProjectSetupSection',
    'DataAcquisitionSection',
    'ENVImetExportSection',
    'ProgressInfoSection'
]
