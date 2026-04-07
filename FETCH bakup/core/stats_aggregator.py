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

        # Fields we care about (Dynamic lookup)
        lcz_idx = layer.fields().lookupField('lcz_class')
        
        # Support both 'lcz_rmsep' (v1-v4) and 'lcz_score' (v5-v6)
        rmsep_idx = layer.fields().lookupField('lcz_rmsep')
        if rmsep_idx == -1:
            rmsep_idx = layer.fields().lookupField('lcz_score')
            
        conf_idx = layer.fields().lookupField('lcz_confidence')
        class2_idx = layer.fields().lookupField('lcz_class_2nd')
        score2_idx = layer.fields().lookupField('lcz_score_2nd')
        matches_idx = layer.fields().lookupField('lcz_matches')
        esa_fix_idx = layer.fields().lookupField('lcz_esa_fix')
        
        # Mapping for parameters
        param_fields = LCZMappings.FIELD_TO_PARAM # {field_name: param_internal_name}

        lcz_counts = {}
        rmsep_data = {} # {class: [values]}
        matches_data = {} # {class: [values]}
        reliability_data = {} # {class: {'scores': [], 'confidences': []}}
        ambiguity_data = {} # {class: {'scores1': [], 'scores2': [], 'classes2': []}}
        sensitivity_data = {} # {class: {param: {'values': [], 'confidences': []}}}
        esa_transitions = {} # {original: {new: count}}
        param_data = {} # {class: {param: [values]}}
        param_data_pre = {} # {original_class: {param: [values]}}
        
        # Coherence tracking: {class: {param: [compliant_count, total_count]}}
        coherence_pre = {}
        coherence_post = {}
        
        esa_corrected_count = 0
        total_valid_count = 0

        for feat in layer.getFeatures():
            # Mandatory check for LCZ class
            if lcz_idx == -1: break
            
            lcz = feat.attribute(lcz_idx)
            if lcz in (None, 'NULL', 'ERRORE', ''):
                continue
            
            total_valid_count += 1
            lcz = str(lcz)
            lcz_counts[lcz] = lcz_counts.get(lcz, 0) + 1
            
            # ESA Fix
            lcz_pre = lcz
            if esa_fix_idx != -1:
                esa_fix = feat.attribute(esa_fix_idx)
                if esa_fix not in (None, 'NULL', '-', 'ERRORE', ''):
                    esa_corrected_count += 1
                    if ' → ' in str(esa_fix):
                        try:
                            orig, new = str(esa_fix).split(' → ')
                            lcz_pre = orig
                            if orig not in esa_transitions: esa_transitions[orig] = {}
                            esa_transitions[orig][new] = esa_transitions[orig].get(new, 0) + 1
                        except Exception:
                            pass
            
            # RMSEP / Score
            r_val = None
            if rmsep_idx != -1:
                attr_val = feat.attribute(rmsep_idx)
                if attr_val not in (None, 'NULL', ''):
                    try: 
                        r_val = float(attr_val)
                        if lcz not in rmsep_data: rmsep_data[lcz] = []
                        rmsep_data[lcz].append(r_val)
                    except: pass
            
            # Confidence
            c_val = None
            if conf_idx != -1:
                attr_val = feat.attribute(conf_idx)
                if attr_val not in (None, 'NULL', ''):
                    try: c_val = float(attr_val)
                    except: pass

            # Reliability (Score vs Confidence) - Keep for backward compatibility/reference
            if r_val is not None and c_val is not None:
                if lcz not in reliability_data:
                    reliability_data[lcz] = {'scores': [], 'confidences': []}
                reliability_data[lcz]['scores'].append(r_val)
                reliability_data[lcz]['confidences'].append(c_val)

            # Ambiguity (Score 1 vs Score 2)
            if class2_idx != -1 and score2_idx != -1:
                s2_val = feat.attribute(score2_idx)
                c2_val = feat.attribute(class2_idx)
                if s2_val not in (None, 'NULL', '') and r_val is not None:
                    if lcz not in ambiguity_data:
                        ambiguity_data[lcz] = {'scores1': [], 'scores2': [], 'classes2': []}
                    ambiguity_data[lcz]['scores1'].append(r_val)
                    ambiguity_data[lcz]['scores2'].append(float(s2_val))
                    ambiguity_data[lcz]['classes2'].append(str(c2_val) if c2_val else 'N/D')
                
            # Matches
            if matches_idx != -1:
                m_val = feat.attribute(matches_idx)
                if m_val not in (None, 'NULL', ''):
                    if lcz not in matches_data: matches_data[lcz] = []
                    try: matches_data[lcz].append(int(m_val))
                    except: pass
                
            # Parameter means & Sensitivity
            if lcz not in param_data: param_data[lcz] = {}
            if lcz_pre not in param_data_pre: param_data_pre[lcz_pre] = {}
            if lcz not in sensitivity_data: sensitivity_data[lcz] = {}
            
            for f_name, p_name in param_fields.items():
                val = feat.attribute(f_name)
                if val not in (None, 'NULL'):
                    f_val = float(val)
                    # Post-ESA mapping
                    if p_name not in param_data[lcz]: param_data[lcz][p_name] = []
                    param_data[lcz][p_name].append(f_val)

                    # Sensitivity
                    if c_val is not None:
                        if p_name not in sensitivity_data[lcz]:
                            sensitivity_data[lcz][p_name] = {'values': [], 'confidences': []}
                        sensitivity_data[lcz][p_name]['values'].append(f_val)
                        sensitivity_data[lcz][p_name]['confidences'].append(c_val)
                    
                    # Pre-ESA mapping
                    if p_name not in param_data_pre[lcz_pre]: param_data_pre[lcz_pre][p_name] = []
                    param_data_pre[lcz_pre][p_name].append(f_val)
                    
                    # Coherence check (Stewart & Oke Ranges)
                    # Pre
                    if lcz_pre not in coherence_pre: coherence_pre[lcz_pre] = {}
                    if p_name not in coherence_pre[lcz_pre]: coherence_pre[lcz_pre][p_name] = [0, 0]
                    
                    ref_range_pre = LCZMappings.PARAMETERS.get(lcz_pre, {}).get(p_name)
                    if ref_range_pre:
                        p_min, p_max = ref_range_pre
                        coherence_pre[lcz_pre][p_name][1] += 1
                        if p_min <= f_val <= p_max:
                            coherence_pre[lcz_pre][p_name][0] += 1
                    
                    # Post
                    if lcz not in coherence_post: coherence_post[lcz] = {}
                    if p_name not in coherence_post[lcz]: coherence_post[lcz][p_name] = [0, 0]
                    
                    ref_range_post = LCZMappings.PARAMETERS.get(lcz, {}).get(p_name)
                    if ref_range_post:
                        p_min, p_max = ref_range_post
                        coherence_post[lcz][p_name][1] += 1
                        if p_min <= f_val <= p_max:
                            coherence_post[lcz][p_name][0] += 1

        # Calculate averages
        rmsep_stats = {lcz: np.mean(vals) for lcz, vals in rmsep_data.items() if vals}
        match_stats = {lcz: np.mean(vals) for lcz, vals in matches_data.items() if vals}
        
        param_means = {}
        for l_post, params in param_data.items():
            param_means[l_post] = {p: np.mean(vals) for p, vals in params.items() if vals}

        param_means_pre = {}
        for l_pre, params in param_data_pre.items():
            param_means_pre[l_pre] = {p: np.mean(vals) for p, vals in params.items() if vals}

        # Calculate coherence percentages
        coherence_stats_pre = {}
        for lcz, params in coherence_pre.items():
            coherence_stats_pre[lcz] = {p: (vals[0] / vals[1] * 100) if vals[1] > 0 else 0 for p, vals in params.items()}
            
        coherence_stats_post = {}
        for lcz, params in coherence_post.items():
            coherence_stats_post[lcz] = {p: (vals[0] / vals[1] * 100) if vals[1] > 0 else 0 for p, vals in params.items()}

        return {
            'lcz_counts': lcz_counts,
            'rmsep_stats': rmsep_stats,
            'match_stats': match_stats,
            'param_means': param_means,
            'param_means_pre': param_means_pre,
            'coherence_stats_pre': coherence_stats_pre,
            'coherence_stats_post': coherence_stats_post,
            'reliability_data': reliability_data,
            'ambiguity_data': ambiguity_data,
            'sensitivity_data': sensitivity_data,
            'esa_correction': {
                'corrected': esa_corrected_count,
                'total': total_valid_count,
                'transitions': esa_transitions # {original: {new: count}}
            }
        }
