# -*- coding: utf-8 -*-
"""
FETCH Dashboard - UI Section Widgets

This package contains modular UI section widgets for the FETCH Dashboard.
"""

from .project_setup import ProjectSetupSection
from .data_acquisition import DataAcquisitionSection
from .processing import ProcessingSection
from .grid_definition import GridDefinitionSection
from .parameters import ParametersSection
from .progress_info import ProgressInfoSection

__all__ = [
    'ProjectSetupSection',
    'DataAcquisitionSection',
    'ProcessingSection',
    'GridDefinitionSection',
    'ParametersSection',
    'ProgressInfoSection'
]
