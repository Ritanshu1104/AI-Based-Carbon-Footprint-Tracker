# 🌍 AI-Based Personal Carbon Footprint Tracker

An intelligent web application that estimates a user's daily carbon footprint from natural-language descriptions of daily activities.

Instead of filling out lengthy forms or selecting activities manually, users can simply describe their day in plain English, for example:

> "I drove my car 25 km to the office and ate chicken for lunch."

The application extracts activities and quantities from the text, maps them to emission factors, calculates estimated CO₂e emissions, and compares the result with a demographic-based daily benchmark.

## ✨ Features

- **Natural Language Input** — Enter daily activities using simple, free-form text.
- **Automatic Activity Extraction** — Identifies activities such as car travel, flights, food consumption, and other supported activities.
- **Emission Factor Mapping** — Uses a custom dataset containing **300+ emission factors** for Transport and Food categories.
- **Quantity-Based Calculation** — Uses quantities such as distance, duration, or number of meals when calculating emissions.
- **Category-Wise Breakdown** — Provides an emission breakdown across categories such as Transport and Food.
- **Demographic Benchmarking** — Compares the estimated daily footprint with a daily average derived from the demographic dataset.
- **Free and Local** — Uses open-source Python libraries and local/public datasets without paid APIs or cloud dependencies.

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Data Processing | Pandas |
| NLP / Text Extraction | Regex-based pattern matching |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Environment | Conda |

## 📊 Datasets

The project uses three datasets:

### 1. `Realistic_Emission_Factors_300.csv`

Contains 300 emission factors for Transport and Food categories. The application averages Small, Medium, and Large variations to obtain a baseline emission factor for supported activities.

### 2. `Daily_Activity_Text_Dataset.csv`

Contains 1,000 text descriptions mapped to activities and quantities. It supports the pattern-based NLP extraction logic used by the application.

### 3. `Carbon Emission.csv`

Contains demographic lifestyle information and annual carbon emissions. It is used to derive a daily benchmark for comparing the user's estimated footprint.

## 📁 Project Structure

```text
carbon-tracker/
├── data/
│   ├── Carbon Emission.csv
│   ├── Daily_Activity_Text_Dataset.csv
│   └── Realistic_Emission_Factors_300.csv
│
├── backend/
│   ├── app.py
│   ├── nlp_extractor.py
│   └── carbon_calculator.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
└── README.md
```

### File Overview

- `app.py` — Flask backend/API server.
- `nlp_extractor.py` — Extracts supported activities and quantities from natural-language text.
- `carbon_calculator.py` — Looks up emission factors, performs calculations, and handles benchmarking.
- `index.html` — Frontend interface.
- `style.css` — Frontend styling.
- `script.js` — Handles frontend interactions and backend API requests.
- `data/` — Contains the datasets required by the application.

## 🚀 Installation & Setup

### Prerequisites

Make sure the following are installed:

- Python 3.10
- Conda
- Git
- A modern web browser

### 1. Clone the Repository

```bash
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd carbon-tracker
```

Replace `<YOUR-GITHUB-REPOSITORY-URL>` with the URL of your GitHub repository.

### 2. Create the Conda Environment

```bash
conda create -n carbon-tracker python=3.10 -y
conda activate carbon-tracker
```

### 3. Install Dependencies

```bash
conda install -c conda-forge flask flask-cors pandas -y
```

## 💻 Running the Application

### Start the Backend

From the project root:

```bash
cd backend
python app.py
```

The Flask server should start at:

```text
http://localhost:5000
```

### Open the Frontend

Open:

```text
frontend/index.html
```

in a modern browser such as Chrome, Firefox, or Edge.

> **Note:** The backend must be running while using the frontend because the frontend communicates with the Flask API.

## 📝 Example Inputs

Try entering statements such as:

```text
I drove my car 25 km to the office.

I flew 800 km today for a meeting.

I ate chicken for lunch and watched TV for 4 hours.

I travelled 15 km by bus and cycled 10 km.

I took a train for 300 km and had a vegetarian meal.
```

The application extracts the supported activities and quantities and uses them to estimate the associated CO₂e emissions.

## 🧠 How It Works

The application follows a simple processing pipeline:

```text
Natural-Language Activity Description
                ↓
        NLP / Pattern Extraction
                ↓
       Activity + Quantity Extraction
                ↓
         Emission Factor Lookup
                ↓
          CO₂e Calculation
                ↓
       Category-Wise Breakdown
                ↓
      Demographic Benchmarking
```

### Step 1 — Text Input

The user enters a natural-language description of their daily activities.

### Step 2 — Activity Extraction

`nlp_extractor.py` uses pattern matching to identify supported activities and quantities, such as:

- Car → 25 km
- Flight → 800 km
- Chicken → 1 meal
- Bus → 15 km

### Step 3 — Emission Factor Lookup

`carbon_calculator.py` processes `Realistic_Emission_Factors_300.csv` and averages available size variations (Small, Medium, Large) to obtain a baseline factor for supported activities.

### Step 4 — CO₂e Calculation

The extracted quantity is combined with the corresponding emission factor to estimate the activity's CO₂e emissions.

### Step 5 — Benchmarking

The estimated total daily footprint is compared with a daily average derived from `Carbon Emission.csv`.

## 🔮 Future Enhancements

- **Advanced NLP** — Integrate spaCy or Hugging Face Transformers, such as BERT-based models, for more complex and ambiguous sentences.
- **User Accounts & History** — Add SQLite-based storage for tracking carbon footprints over weeks or months.
- **Expanded Categories** — Add electricity consumption, additional food items, shipping, and more travel activities.
- **Gamification** — Introduce a Green Score and environmental-impact comparisons.
- **Improved Activity Recognition** — Expand the supported vocabulary and quantity patterns.

## ⚠️ Limitations

- The current NLP component is **regex/pattern based**, so it may not understand every possible way of describing an activity.
- The accuracy of the estimate depends on the emission factors available in the provided datasets.
- The application currently focuses on the activity categories supported by the datasets and extraction logic.

## 🎯 Project Objective

The goal of this project is to make personal carbon-footprint estimation simpler and more accessible by allowing users to describe their everyday activities naturally instead of manually entering data into multiple forms.

---

⭐ **If you find this project useful, consider giving the repository a star!**
