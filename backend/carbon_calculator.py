import pandas as pd
import os

class CarbonCalculator:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        factors_path = os.path.join(base_dir, 'data', 'Realistic_Emission_Factors_300.csv')
        demo_path = os.path.join(base_dir, 'data', 'Carbon Emission.csv')
        
        # 1. Load and process Emission Factors
        self.df_factors = pd.read_csv(factors_path)
        self._build_factor_lookup()
        
        # 2. Load Demographic Data for Benchmarking
        self.df_demo = pd.read_csv(demo_path)
        self.avg_emission = self.df_demo['CarbonEmission'].mean()
        
        # Fallback factors for items not explicitly in the 300 CSV (Electricity & Veg Meals)
        self.fallback_factors = {
            'Vegetarian Meal': 2.0,  # kgCO2e per meal
            'Electricity': 0.5       # kgCO2e per hour (estimated grid average)

        }
        
    def _build_factor_lookup(self):
        # Strip "Small 1", "Medium 2", etc., to get base categories like "Petrol Car"
        self.df_factors['base_activity'] = self.df_factors['Activity'].str.replace(
            r'\s+(Small|Medium|Large)\s+\d+', '', regex=True
        )
        
        # Calculate the average emission factor per base category
        self.lookup = self.df_factors.groupby('base_activity')['EmissionFactor_kgCO2e_per_unit'].mean().to_dict()
        
        # Map NLP extracted labels to the CSV base categories
        self.label_mapping = {
            'Flight': ['Domestic Flight', 'International Flight'], 
            'Bus': 'Bus',
            'Train': 'Train',
            'Car': ['Petrol Car', 'Diesel Car', 'Hybrid Car', 'Electric Car'], 
            'Petrol Car': 'Petrol Car',
            'Diesel Car': 'Diesel Car',
            'Hybrid Car': 'Hybrid Car',
            'Electric Car': 'Electric Car',
            'Bike': 'Bicycle',
            'Walking': 'Walking',
            'Chicken Meal': 'Chicken'
        }
        
    def get_factor(self, label):
        if label in self.fallback_factors:
            return self.fallback_factors[label]
            
        mapped = self.label_mapping.get(label)
        if not mapped:
            return 0.0
            
        if isinstance(mapped, list):
            valid_factors = [self.lookup.get(m) for m in mapped if self.lookup.get(m) is not None]
            return sum(valid_factors) / len(valid_factors) if valid_factors else 0.0
        else:
            return self.lookup.get(mapped, 0.0)

    def calculate_footprint(self, activities):
        total_co2 = 0
        breakdown = []
        
        for act in activities:
            label = act['label']
            qty = act['quantity']
            unit = act['unit']
            
            factor = self.get_factor(label)
            co2 = qty * factor
            total_co2 += co2
            
            # Determine category for UI grouping
            if label in ['Flight', 'Bus', 'Train', 'Car', 'Bike', 'Walking']:
                category = 'Transport'
            elif 'Meal' in label or 'Chicken' in label:
                category = 'Food'
            else:
                category = 'Energy'
                
            breakdown.append({
                'activity': f"{label} ({qty} {unit})",
                'co2_kg': round(co2, 2),
                'category': category,
                'factor_kg_co2e_per_unit': round(factor, 6),
                'source_text': act.get('source_text', '')
            })
            
        return {
            'total_co2_kg': round(total_co2, 2),
            'breakdown': breakdown,
            'benchmark': self._get_benchmark()
        }
        
    def _get_benchmark(self):
        daily_avg = self.avg_emission / 365.0
        return {
            'annual_avg_kg': round(self.avg_emission, 2),
            'daily_avg_kg': round(daily_avg, 2),
            'message': f"Based on our demographic dataset, the average annual emission is {round(self.avg_emission, 2)} kg CO2e."
        }
