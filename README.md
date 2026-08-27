# 🌍 AI-Based Personal Carbon Footprint Tracker

An intelligent web application that estimates a user's daily carbon footprint by analyzing natural language text descriptions of their daily activities. Instead of tedious manual form-filling or category-picking, users simply type what they did in plain English (e.g., *"I drove my car 25 km to the office and ate chicken for lunch"*), and the system automatically extracts the activities, maps them to realistic emission factors, and calculates the total CO₂e emissions.

## ✨ Key Features

- **Natural Language Input**: No tedious dropdowns or forms. The NLP engine understands free-form text.
- **Realistic Emission Mapping**: Uses a custom dataset of 300+ realistic emission factors, accounting for variations like vehicle/meal sizes (Small, Medium, Large).
- **Demographic Benchmarking**: Compares the user's daily footprint against a real-world demographic dataset to provide context.
- **100% Free & Offline**: Uses custom/public datasets and open-source Python libraries. No paid APIs or cloud dependencies.
- **Instant Feedback**: Real-time calculation and breakdown of emissions by category (Transport, Food, etc.).

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **Data Processing**: Pandas
- **NLP**: Regex-based pattern extraction (easily extensible to spaCy or HuggingFace Transformers)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## 📊 Datasets Used

This project leverages three custom datasets to provide a highly realistic and data-driven experience:

1. **`Realistic_Emission_Factors_300.csv`**: Contains 300 emission factors for Transport and Food categories. It averages out variations (Small, Medium, Large) to provide accurate baseline factors for activities like driving, flying, or eating specific meals.
2. **`Daily_Activity_Text_Dataset.csv`**: A 1,000-row dataset of text descriptions mapped to specific activities and quantities. This dataset informs the NLP extraction patterns to ensure the app understands how real users describe their days.
3. **`Carbon Emission.csv`**: A demographic dataset containing lifestyle choices and total annual carbon emissions. This is used to calculate the baseline daily average to compare the user's footprint against.

## 📁 Project Structure

```text
carbon-tracker/
├── data/
│   ├── Carbon Emission.csv                 # Demographic benchmark dataset
│   ├── Daily_Activity_Text_Dataset.csv     # NLP text patterns dataset
│   └── Realistic_Emission_Factors_300.csv  # Emission factors dataset
├── backend/
│   ├── app.py                              # Flask API server
│   ├── nlp_extractor.py                    # NLP/Regex extraction logic
│   └── carbon_calculator.py                # Calculation & benchmarking logic
├── frontend/
│   ├── index.html                          # UI Layout
│   ├── style.css                           # Styling
│   └── script.js                           # Frontend API calls
└── README.md                               # Project documentation

🚀 Installation & Setup
This project uses Conda for environment management.
1. Clone or navigate to the project directory:
    bash
   cd carbon-tracker

2. Create and activate the Conda environment:
    bash
    conda create -n carbon-tracker python=3.10 -y
   conda activate carbon-tracker

3. Install dependencies:
    bash
   conda install -c conda-forge flask flask-cors pandas -y

💻 Running the Application
1.Start the Backend Server:
    bash
       cd backend
   python app.py

(The Flask server will start on http://localhost:5000)
Open the Frontend:
Open the frontend/index.html file in any modern web browser (Chrome, Firefox, Edge).

📝 Example Inputs
Try typing these into the text box to see the NLP engine in action:
"I drove my car 25 km to the office."
"I flew 800 km today for a meeting."
"I ate chicken for lunch and watched TV for 4 hours."
"I travelled 15 km by bus and cycled 10 km."
"I took a train for 300 km and had a vegetarian meal."

🧠 How It Works
Text Input: The user enters a natural language description of their day.
NLP Extraction: The nlp_extractor.py module uses pattern matching (trained on the Daily_Activity_Text_Dataset.csv) to identify activities (e.g., Car, Flight, Chicken) and quantities (e.g., 25 km, 1 meal).
Factor Lookup: The carbon_calculator.py module cleans the Realistic_Emission_Factors_300.csv data, stripping out size variations (Small/Medium/Large) to calculate the mathematical average emission factor for each base activity.
Calculation & Benchmarking: It multiplies the extracted quantity by the average emission factor. Finally, it compares the total daily CO₂e against the average daily emission derived from the Carbon Emission.csv demographic dataset.
🔮 Future Enhancements
Advanced NLP: Integrate spaCy or HuggingFace Transformers (like BERT) to handle more complex, varied, and ambiguous sentence structures.
User Accounts & History: Add a lightweight SQLite database to allow users to track their carbon footprint over weeks or months.
Expanded Categories: Add more food items, electricity usage metrics, and international shipping/travel factors.
Gamification: Introduce a "Green Score" or show equivalent environmental impacts (e.g., "Your choices today saved the equivalent of 2 trees!").
