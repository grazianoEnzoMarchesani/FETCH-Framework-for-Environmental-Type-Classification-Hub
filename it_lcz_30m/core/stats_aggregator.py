# -*- coding: utf-8 -*-
"""
Stats Aggregator for FETCH Plugin
Processes the grid layer attributes to provide aggregated metrics for statistics.
"""

import numpy as np
from qgis.core import QgsProject, QgsMessageLog, Qgis
from .constants import LCZMappings, FieldNames

class StatsAggregator:
    @staticmethod
    def get_layer_stats(layer):
        """
        Aggregates statistics from the grid layer.
        Returns a dict with:
        - lcz_counts: {class: count}
        - rmsep_stats: {class: mean_rmsep}
        - match_stats: {class: mean_matches}
        - param_means: {class: {param: mean_val}}
        - esa_correction: {count_corrected, count_total}
        """
        if not layer or not layer.isValid():
            return None

        # Fields we care about
        lcz_field = 'lcz_class'
        rmsep_field = 'lcz_rmsep'
        matches_field = 'lcz_matches'
        esa_fix_field = 'lcz_esa_fix'
        
        # Mapping for parameters
        param_fields = LCZMappings.FIELD_TO_PARAM # {field_name: param_internal_name}

        lcz_counts = {}
        rmsep_data = {} # {class: [values]}
        matches_data = {} # {class: [values]}
        esa_transitions = {} # {original: {new: count}}
        param_data = {} # {class: {param: [values]}}
        param_data_pre = {} # {original_class: {param: [values]}}
        esa_corrected_count = 0
        total_valid_count = 0

        for feat in layer.getFeatures():
            lcz = feat.attribute(lcz_field)
            if lcz is None or str(lcz) == 'NULL' or lcz == 'ERRORE':
                continue
            
            total_valid_count += 1
            lcz = str(lcz)
            lcz_counts[lcz] = lcz_counts.get(lcz, 0) + 1
            
            # ESA Fix
            esa_fix = feat.attribute(esa_fix_field)
            if esa_fix not in (None, 'NULL', '-', 'ERRORE'):
                esa_corrected_count += 1
                if ' → ' in str(esa_fix):
                    try:
                        orig, new = str(esa_fix).split(' → ')
                        lcz_pre = orig
                        if orig not in esa_transitions: esa_transitions[orig] = {}
                        esa_transitions[orig][new] = esa_transitions[orig].get(new, 0) + 1
                    except Exception:
                        lcz_pre = lcz
                else:
                    lcz_pre = lcz
            else:
                lcz_pre = lcz
                
            # RMSEP
            r_val = feat.attribute(rmsep_field)
            if r_val not in (None, 'NULL'):
                if lcz not in rmsep_data: rmsep_data[lcz] = []
                rmsep_data[lcz].append(float(r_val))
                
            # Matches
            m_val = feat.attribute(matches_field)
            if m_val not in (None, 'NULL'):
                if lcz not in matches_data: matches_data[lcz] = []
                matches_data[lcz].append(int(m_val))
                
            # Parameter means (Post-ESA)
            if lcz not in param_data: param_data[lcz] = {}
            if lcz_pre not in param_data_pre: param_data_pre[lcz_pre] = {}
            
            for f_name, p_name in param_fields.items():
                val = feat.attribute(f_name)
                if val not in (None, 'NULL'):
                    f_val = float(val)
                    # Post-ESA mapping
                    if p_name not in param_data[lcz]: param_data[lcz][p_name] = []
                    param_data[lcz][p_name].append(f_val)
                    # Pre-ESA mapping
                    if p_name not in param_data_pre[lcz_pre]: param_data_pre[lcz_pre][p_name] = []
                    param_data_pre[lcz_pre][p_name].append(f_val)

        # Calculate averages
        rmsep_stats = {lcz: np.mean(vals) for lcz, vals in rmsep_data.items() if vals}
        match_stats = {lcz: np.mean(vals) for lcz, vals in matches_data.items() if vals}
        
        param_means = {}
        for l_orig, params in param_data.items():
            param_means[l_orig] = {p: np.mean(vals) for p, vals in params.items() if vals}

        param_means_pre = {}
        for l_orig, params in param_data_pre.items():
            param_means_pre[l_orig] = {p: np.mean(vals) for p, vals in params.items() if vals}

        return {
            'lcz_counts': lcz_counts,
            'rmsep_stats': rmsep_stats,
            'match_stats': match_stats,
            'param_means': param_means,
            'param_means_pre': param_means_pre,
            'esa_correction': {
                'corrected': esa_corrected_count,
                'total': total_valid_count,
                'transitions': esa_transitions # {original: {new: count}}
            }
        }
