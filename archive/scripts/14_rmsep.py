import sys
print(f"Python path: {sys.executable}")

try:
    import numpy as np
    print(f"NumPy version: {np.__version__}")
except ImportError:
    print("Errore: NumPy non è installato")
    raise

try:
    import statsmodels
    import statsmodels.tools.eval_measures as em
    print(f"Statsmodels version: {statsmodels.__version__}")
except ImportError:
    print("Errore: Statsmodels non è installato")
    print("Per installarlo, esegui questo comando nel terminale:")
    print("/Applications/QGIS.app/Contents/MacOS/bin/python3 -m pip install statsmodels")
    raise

class LCZClassifier:
    def __init__(self, parameters):
        self.parameters = parameters
        
        # Definizione delle classi LCZ e relative descrizioni
        self.lcz_classes = {
            '1': 'Compact highrise',
            '2': 'Compact midrise',
            '3': 'Compact lowrise',
            '4': 'Open highrise',
            '5': 'Open midrise',
            '6': 'Open lowrise',
            '7': 'Lightweight lowrise',
            '8': 'Large lowrise',
            '9': 'Sparsely built',
            '10': 'Heavy industry',
            'A': 'Dense trees',
            'B': 'Scattered trees',
            'C': 'Bush, scrub',
            'D': 'Low plants',
            'E': 'Bare rock or paved',
            'F': 'Bare soil or sand',
            'G': 'Water'
        }
        
        # Definizione dei range di parametri per ogni classe LCZ
        self.lcz_parameters = {
            '1': {
                'sky_view_factor': (0.2, 0.4),
                'aspect_ratio': (2, float('inf')),
                'building_surface_fraction': (40, 60),
                'impervious_surface_fraction': (40, 60),
                'pervious_surface_fraction': (0, 10),
                'height_roughness': (25, float('inf')),
                'terrain_roughness': (8, 8),
                'surface_admittance': (1500, 1800),
                'surface_albedo': (0.1, 0.2),
                'anthropogenic_heat': (50, 300)
            },
            '2': {
                'sky_view_factor': (0.3, 0.6),
                'aspect_ratio': (0.75, 2),
                'building_surface_fraction': (40, 70),
                'impervious_surface_fraction': (30, 50),
                'pervious_surface_fraction': (0, 20),
                'height_roughness': (10, 25),
                'terrain_roughness': (6, 7),
                'surface_admittance': (1500, 2200),
                'surface_albedo': (0.1, 0.2),
                'anthropogenic_heat': (0, 75)
            },
            '3': {
                'sky_view_factor': (0.2, 0.6),
                'aspect_ratio': (0.75, 1.5),
                'building_surface_fraction': (40, 70),
                'impervious_surface_fraction': (20, 50),
                'pervious_surface_fraction': (0, 30),
                'height_roughness': (3, 10),
                'terrain_roughness': (6, 6),
                'surface_admittance': (1200, 1800),
                'surface_albedo': (0.1, 0.2),
                'anthropogenic_heat': (0, 75)
            },
            '4': {
                'sky_view_factor': (0.5, 0.7),
                'aspect_ratio': (0.75, 1.25),
                'building_surface_fraction': (20, 40),
                'impervious_surface_fraction': (30, 40),
                'pervious_surface_fraction': (30, 40),
                'height_roughness': (25, float('inf')),
                'terrain_roughness': (7, 8),
                'surface_admittance': (1400, 1800),
                'surface_albedo': (0.12, 0.25),
                'anthropogenic_heat': (0, 50)
            },
            '5': {
                'sky_view_factor': (0.5, 0.8),
                'aspect_ratio': (0.3, 0.75),
                'building_surface_fraction': (20, 40),
                'impervious_surface_fraction': (30, 50),
                'pervious_surface_fraction': (20, 40),
                'height_roughness': (10, 25),
                'terrain_roughness': (5, 6),
                'surface_admittance': (1400, 2000),
                'surface_albedo': (0.12, 0.25),
                'anthropogenic_heat': (0, 25)
            },
            '6': {
                'sky_view_factor': (0.6, 0.9),
                'aspect_ratio': (0.3, 0.75),
                'building_surface_fraction': (20, 40),
                'impervious_surface_fraction': (20, 50),
                'pervious_surface_fraction': (30, 60),
                'height_roughness': (3, 10),
                'terrain_roughness': (5, 6),
                'surface_admittance': (1200, 1800),
                'surface_albedo': (0.12, 0.25),
                'anthropogenic_heat': (0, 25)
            },
            '7': {
                'sky_view_factor': (0.2, 0.5),
                'aspect_ratio': (1, 2),
                'building_surface_fraction': (60, 90),
                'impervious_surface_fraction': (0, 20),
                'pervious_surface_fraction': (0, 30),
                'height_roughness': (2, 4),
                'terrain_roughness': (4, 5),
                'surface_admittance': (800, 1500),
                'surface_albedo': (0.15, 0.35),
                'anthropogenic_heat': (0, 35)
            },
            '8': {
                'sky_view_factor': (0.7, float('inf')),
                'aspect_ratio': (0.1, 0.3),
                'building_surface_fraction': (30, 50),
                'impervious_surface_fraction': (40, 50),
                'pervious_surface_fraction': (0, 20),
                'height_roughness': (3, 10),
                'terrain_roughness': (5, 5),
                'surface_admittance': (1200, 1800),
                'surface_albedo': (0.15, 0.25),
                'anthropogenic_heat': (0, 50)
            },
            '9': {
                'sky_view_factor': (0.8, 1),
                'aspect_ratio': (0.1, 0.25),
                'building_surface_fraction': (10, 20),
                'impervious_surface_fraction': (0, 20),
                'pervious_surface_fraction': (60, 80),
                'height_roughness': (3, 10),
                'terrain_roughness': (5, 6),
                'surface_admittance': (1000, 1800),
                'surface_albedo': (0.12, 0.25),
                'anthropogenic_heat': (0, 10)
            },
            '10': {
                'sky_view_factor': (0.6, 0.9),
                'aspect_ratio': (0.2, 0.5),
                'building_surface_fraction': (20, 30),
                'impervious_surface_fraction': (20, 40),
                'pervious_surface_fraction': (40, 50),
                'height_roughness': (5, 15),
                'terrain_roughness': (5, 6),
                'surface_admittance': (1000, 2500),
                'surface_albedo': (0.12, 0.2),
                'anthropogenic_heat': (300, float('inf'))
            },
            'A': {
                'sky_view_factor': (0, 0.4),
                'aspect_ratio': (1, float('inf')),
                'building_surface_fraction': (0, 10),
                'impervious_surface_fraction': (0, 10),
                'pervious_surface_fraction': (90, 100),
                'height_roughness': (3, 30),
                'terrain_roughness': (8, 8),
                'surface_admittance': (1000, 1800),
                'surface_albedo': (0.12, 0.2),
                'anthropogenic_heat': (0, 0)
            },
            'B': {
                'sky_view_factor': (0.5, 0.8),
                'aspect_ratio': (0.25, 0.75),
                'building_surface_fraction': (0, 10),
                'impervious_surface_fraction': (0, 10),
                'pervious_surface_fraction': (90, 100),
                'height_roughness': (3, 15),
                'terrain_roughness': (5, 6),
                'surface_admittance': (1200, 1800),
                'surface_albedo': (0.15, 0.25),
                'anthropogenic_heat': (0, 0)
            },
            'C': {
                'sky_view_factor': (0.7, 0.9),
                'aspect_ratio': (0.25, 1),
                'building_surface_fraction': (0, 10),
                'impervious_surface_fraction': (0, 10),
                'pervious_surface_fraction': (90, 100),
                'height_roughness': (0, 2),
                'terrain_roughness': (4, 5),
                'surface_admittance': (700, 1500),
                'surface_albedo': (0.15, 0.30),
                'anthropogenic_heat': (0, 0)
            },
            'D': {
                'sky_view_factor': (0.9, 1),
                'aspect_ratio': (0, 0.1),
                'building_surface_fraction': (0, 10),
                'impervious_surface_fraction': (0, 10),
                'pervious_surface_fraction': (90, 100),
                'height_roughness': (0, 1),
                'terrain_roughness': (3, 4),
                'surface_admittance': (1200, 1600),
                'surface_albedo': (0.15, 0.25),
                'anthropogenic_heat': (0, 0)
            },
            'E': {
                'sky_view_factor': (0.9, 1),
                'aspect_ratio': (0, 0.1),
                'building_surface_fraction': (0, 10),
                'impervious_surface_fraction': (90, 100),
                'pervious_surface_fraction': (0, 10),
                'height_roughness': (0, 0.25),
                'terrain_roughness': (1, 2),
                'surface_admittance': (1200, 2500),
                'surface_albedo': (0.15, 0.3),
                'anthropogenic_heat': (0, 0)
            },
            'F': {
                'sky_view_factor': (0.9, 1),
                'aspect_ratio': (0, 0.1),
                'building_surface_fraction': (0, 10),
                'impervious_surface_fraction': (0, 10),
                'pervious_surface_fraction': (90, 100),
                'height_roughness': (0, 0.25),
                'terrain_roughness': (1, 2),
                'surface_admittance': (600, 1400),
                'surface_albedo': (0.2, 0.35),
                'anthropogenic_heat': (0, 0)
            },
            'G': {
                'sky_view_factor': (0.9, 1),
                'aspect_ratio': (0, 0.1),
                'building_surface_fraction': (0, 10),
                'impervious_surface_fraction': (0, 10),
                'pervious_surface_fraction': (90, 100),
                'height_roughness': (0, 0.25),
                'terrain_roughness': (1, 1),
                'surface_admittance': (1500, 1500),
                'surface_albedo': (0.02, 0.10),
                'anthropogenic_heat': (0, 0)
            }
        }

    def calculate_rmsep(self, lcz_class):
        """
        Calcola il RMSEP usando statsmodels per una maggiore accuratezza statistica
        e restituisce i contributi di errore per ogni parametro.
        """
        if not self._is_valid_for_class(lcz_class):
            return float('inf'), 0, {}
        
        params = self.lcz_parameters[lcz_class]
        valid_params = []
        target_values = []
        error_contributions = {}
        perfect_matches = 0
        total_valid_params = 0
        
        for param_name, (min_val, max_val) in params.items():
            current_val = self.parameters.get(param_name)
            
            if current_val is None:
                continue
                
            total_valid_params += 1
            
            if min_val <= current_val <= max_val:
                perfect_matches += 1
                error_contributions[param_name] = 0
                continue
                
            target_val = min_val if max_val == float('inf') else (min_val + max_val) / 2
            
            if target_val == 0:
                error_contributions[param_name] = float('inf')
                continue
            
            valid_params.append(current_val)
            target_values.append(target_val)
            
            # Calcola l'errore percentuale
            percentage_error = (current_val - target_val) / target_val
            error_contributions[param_name] = percentage_error ** 2
            
      
        if total_valid_params == 0:
            return float('inf'), 0, {}
            
        if not valid_params:
            return 0, perfect_matches, error_contributions
            
        valid_params = np.array(valid_params)
        target_values = np.array(target_values)
        
        # Calcola il RMSEP
        rmsep = em.rmspe(valid_params, target_values)/100
   
        
        # Calcola la media dei contributi di errore
        mean_error_contribution = np.sqrt(np.mean(list(error_contributions.values())) * 100)
   
        return rmsep, perfect_matches, error_contributions

    def _is_valid_for_class(self, lcz_class):
        """
        Verifica se i parametri sono validi per una determinata classe LCZ
        """
        # building_surface_fraction threshold
        building_surface_fraction_threshold = 0
        # Regole specifiche per verificare la validità
        if lcz_class in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
            return self.parameters['building_surface_fraction'] <= building_surface_fraction_threshold
        return self.parameters['building_surface_fraction'] > building_surface_fraction_threshold 

    def classify(self):
        """
        Classifica la zona calcolando il RMSEP per tutte le classi
        """
        # Verifica che 'building_surface_fraction' non sia None
        if self.parameters.get('building_surface_fraction') is None:
            raise ValueError("Il parametro 'building_surface_fraction' è fondamentale e non può essere None.")
        
        # Verifica che la somma delle frazioni sia 100
        building_fraction = self.parameters.get('building_surface_fraction', 0)
        impervious_fraction = self.parameters.get('impervious_surface_fraction', 0)
        pervious_fraction = self.parameters.get('pervious_surface_fraction', 0)
        
        total_fraction = building_fraction + impervious_fraction + pervious_fraction
        if total_fraction != 100:
            raise ValueError(
                f"La somma di 'building_surface_fraction', 'impervious_surface_fraction' e 'pervious_surface_fraction' deve essere 100. "
                f"Valori attuali: building_surface_fraction={building_fraction}, "
                f"impervious_surface_fraction={impervious_fraction}, "
                f"pervious_surface_fraction={pervious_fraction}."
            )
        
        results = {}
        available_params = sum(1 for val in self.parameters.values() if val is not None)
        
        for lcz in self.lcz_classes.keys():
            rmsep, perfect_matches, error_contributions = self.calculate_rmsep(lcz)
            results[lcz] = {
                'rmsep': rmsep,
                'perfect_matches': perfect_matches,
                'available_params': available_params,
                'error_contributions': error_contributions
            }
        
        # Trova il numero massimo di match perfetti tra tutte le classi
        max_perfect_matches = max(data['perfect_matches'] for data in results.values())
        
        # Filtra le classi che hanno il numero massimo di match perfetti
        best_matches = {
            lcz: data 
            for lcz, data in results.items() 
            if data['perfect_matches'] == max_perfect_matches
        }
        
        # Tra queste, trova quella con il RMSEP minimo
        best_class = min(best_matches.items(), key=lambda x: x[1]['rmsep'])
        
        classification_result = {
            'lcz_class': best_class[0],
            'rmsep': best_class[1]['rmsep'],
            'perfect_matches': best_class[1]['perfect_matches'],
            'available_params': available_params,
            'all_results': results
        }

        # Stampa i risultati
        print("\nRisultati della classificazione LCZ:")
        print("\n" + "°." * 30 + "\n")
        print(f"Classe LCZ assegnata: {classification_result['lcz_class']}")
        print(f"RMSEP: {classification_result['rmsep']:.4f}")
        print(f"Parametri perfettamente nel range: {classification_result['perfect_matches']}/{classification_result['available_params']}")
        print(f"Parametri disponibili: {classification_result['available_params']}/10")
        print("\nValori per tutte le classi:")
        print("\n" + "°." * 30 + "\n")

        # Filtra e ordina solo i risultati con il massimo numero di match perfetti
        max_matches_results = {
            lcz: data 
            for lcz, data in classification_result['all_results'].items()
            if data['perfect_matches'] == max_perfect_matches
        }
        
        sorted_results = dict(sorted(max_matches_results.items(),
                                   key=lambda x: x[1]['rmsep']))
        
        for lcz_class, values in sorted_results.items():
            if values['rmsep'] != float('inf'):
                print(f"LCZ {lcz_class}: RMSEP={values['rmsep']:.4f}, "
                      f"Match perfetti={values['perfect_matches']}/{values['available_params']}")
                
                for param, error in values['error_contributions'].items():
                    param_range = self.lcz_parameters[lcz_class][param]
                    current_val = self.parameters.get(param)
                    
                    if error == 0:
                        print(f"  {param}: nessun errore ---> match perfetto")
                    else:
                        if param_range[1] == float('inf'):
                            range_str = f">{param_range[0]}"
                        else:
                            range_str = f"({param_range[0]}, {param_range[1]})"
                        print(f"  {param}: {range_str} ---> valore inserito: {current_val}")
                
                print("-" * 60)

        return classification_result

    def get_lcz_description(self, lcz_class):
        """
        Restituisce la descrizione di una classe LCZ
        """
        return self.lcz_classes.get(lcz_class, "Classe non trovata")

# Esempio di utilizzo

test_parameters = {
    'sky_view_factor': 0.736596167,
    'aspect_ratio': 0.072062784,
    'building_surface_fraction': 5,
    'impervious_surface_fraction': 85,
    'pervious_surface_fraction': 10,
    'height_roughness': 9.564424038,
    'terrain_roughness': 1.703751326,
    'surface_admittance': None,
    'surface_albedo': 0.26990354,
    'anthropogenic_heat': 999999999999999
}

classifier = LCZClassifier(test_parameters)
result = classifier.classify()

LCZ=result['lcz_class']
print(f"LCZ: {LCZ}")



