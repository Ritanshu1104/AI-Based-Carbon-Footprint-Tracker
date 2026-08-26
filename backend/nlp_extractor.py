import re

class ActivityExtractor:
    def __init__(self):
        # Regex patterns mapped to your dataset's labels and units
        self.patterns = [
            # Transport
            (r'flew\s+(\d+\.?\d*)\s*km', 'Flight', 'km'),
            (r'took a flight covering\s+(\d+\.?\d*)\s*km', 'Flight', 'km'),
            (r'(?:travelled|commuted)\s+(\d+\.?\d*)\s*km\s+(?:by\s+)?(?:bus|using the bus)', 'Bus', 'km'),
            (r'took a bus for\s+(\d+\.?\d*)\s*km', 'Bus', 'km'),
            (r'(?:travelled|took a train for)\s+(\d+\.?\d*)\s*km\s*(?:by\s+)?train', 'Train', 'km'),
            (r'(?:travelled|used my car|drove my car)\s+(\d+\.?\d*)\s*km', 'Car', 'km'),
            (r'(?:rode my bike|cycled)\s+(\d+\.?\d*)\s*km', 'Bike', 'km'),
            (r'(?:went for a|walked)\s+(\d+\.?\d*)\s*km\s*walk', 'Walking', 'km'),
            # Electricity
            (r'(?:watched TV|used my computer|used the air conditioner)\s+for\s+(\d+\.?\d*)\s*hours?', 'Electricity', 'hour')
        ]

    def extract_activities(self, text):
        extracted = []
        text_lower = text.lower()
        
        # 1. Extract quantities using Regex
        for pattern, label, unit in self.patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                extracted.append({
                    'label': label,
                    'quantity': float(match),
                    'unit': unit
                })
                
        # 2. Extract implicit "1 meal" activities (since your dataset uses "I ate chicken...")
        if ('vegetarian meal' in text_lower or 'veg lunch' in text_lower) and not any(e['label'] == 'Vegetarian Meal' for e in extracted):
            extracted.append({'label': 'Vegetarian Meal', 'quantity': 1.0, 'unit': 'meal'})
            
        if 'chicken' in text_lower and not any(e['label'] == 'Chicken Meal' for e in extracted):
            extracted.append({'label': 'Chicken Meal', 'quantity': 1.0, 'unit': 'meal'})
            
        return extracted