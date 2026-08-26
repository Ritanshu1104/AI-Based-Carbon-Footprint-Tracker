from flask import Flask, request, jsonify
from flask_cors import CORS
from nlp_extractor import ActivityExtractor
from carbon_calculator import CarbonCalculator

app = Flask(__name__)
CORS(app)

extractor = ActivityExtractor()
calculator = CarbonCalculator()

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
        
    activities = extractor.extract_activities(text)
    result = calculator.calculate_footprint(activities)
    result['extracted_activities'] = activities
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)