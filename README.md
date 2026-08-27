# 🌍 AI-Based Personal Carbon Footprint Tracker

An intelligent web application that estimates a user's daily carbon footprint by analyzing natural language descriptions of their activities. Rather than navigating tedious forms or dropdown menus, users simply type what they did in plain English (e.g., *"I drove my car 25 km to the office and ate chicken for lunch"*), and the system automatically extracts activities, maps them to emission factors, and calculates total CO₂e emissions.

---

## 📋 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Datasets](#-datasets-used)
- [Installation](#-installation--setup)
- [Usage](#-running-the-application)
- [How It Works](#-how-it-works)
- [Example Inputs](#-example-inputs)
- [Future Enhancements](#-future-enhancements)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

- **Natural Language Input** — No dropdowns or forms. The NLP engine understands free-form text descriptions.
- **Realistic Emission Mapping** — Uses a custom dataset of 300+ emission factors with variations (Small, Medium, Large) for vehicles and meals.
- **Demographic Benchmarking** — Compares the user's daily footprint against real-world demographic data for contextual insights.
- **100% Free & Offline** — Leverages custom and public datasets with open-source Python libraries. No paid APIs or cloud dependencies required.
- **Real-Time Feedback** — Instant calculation and breakdown of emissions by category (Transport, Food, etc.).

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, Flask |
| **Data Processing** | Pandas |
| **NLP** | Regex-based pattern extraction (extensible to spaCy or HuggingFace Transformers) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Environment** | Conda |

---

## 📁 Project Structure

```
carbon-tracker/
├── data/
│   ├── Carbon_Emission.csv                 # Demographic benchmark dataset
│   ├── Daily_Activity_Text_Dataset.csv     # NLP text patterns dataset
│   └── Realistic_Emission_Factors_300.csv  # Emission factors reference
├── backend/
│   ├── app.py                              # Flask API server
│   ├── nlp_extractor.py                    # NLP/Regex extraction logic
│   └── carbon_calculator.py                # Calculation & benchmarking logic
├── frontend/
│   ├── index.html                          # UI layout
│   ├── style.css                           # Styling
│   └── script.js                           # Frontend API calls
├── README.md                               # Project documentation
└── requirements.txt                        # Python dependencies
```

---

## 📊 Datasets Used

This project uses three custom datasets to deliver realistic, data-driven carbon footprint estimates:

1. **`Realistic_Emission_Factors_300.csv`**  
   Contains 300 emission factors for Transport and Food categories. Emission factors are averaged across variations (Small, Medium, Large) to provide accurate baseline values for activities like driving, flying, or eating specific meals.

2. **`Daily_Activity_Text_Dataset.csv`**  
   A 1,000-row dataset mapping natural language text descriptions to specific activities and quantities. Informs the NLP extraction patterns to ensure the app understands how users naturally describe their daily activities.

3. **`Carbon_Emission.csv`**  
   A demographic dataset containing lifestyle choices and annual carbon emissions. Used to calculate baseline daily averages for demographic benchmarking.

---

## 🚀 Installation & Setup

### Prerequisites

- **Python 3.10** or higher
- **Conda** (download from [Anaconda](https://www.anaconda.com/))

### Step 1: Clone the Repository

```bash
git clone https://github.com/[USERNAME]/carbon-tracker.git
cd carbon-tracker
```

### Step 2: Create and Activate the Conda Environment

```bash
conda create -n carbon-tracker python=3.10 -y
conda activate carbon-tracker
```

### Step 3: Install Dependencies

```bash
conda install -c conda-forge flask flask-cors pandas -y
```

Alternatively, if using `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## 💻 Running the Application

### Start the Backend Server

```bash
cd backend
python app.py
```

The Flask server will start on `http://localhost:5000`.

### Open the Frontend

Open `frontend/index.html` in any modern web browser (Chrome, Firefox, Edge, Safari).

The application is now ready to use.

---

## 📝 Example Inputs

Test the NLP engine with these sample inputs:

- `"I drove my car 25 km to the office."`
- `"I flew 800 km today for a meeting."`
- `"I ate chicken for lunch and watched TV for 4 hours."`
- `"I travelled 15 km by bus and cycled 10 km."`
- `"I took a train for 300 km and had a vegetarian meal."`

---

## 🧠 How It Works

The application follows a four-step pipeline:

1. **Text Input**  
   User enters a natural language description of their daily activities.

2. **NLP Extraction**  
   The `nlp_extractor.py` module uses pattern matching (trained on `Daily_Activity_Text_Dataset.csv`) to identify activities (e.g., Car, Flight, Chicken) and quantities (e.g., 25 km, 1 meal).

3. **Factor Lookup**  
   The `carbon_calculator.py` module processes `Realistic_Emission_Factors_300.csv`, stripping size variations (Small/Medium/Large) to calculate the mathematical average emission factor for each base activity.

4. **Calculation & Benchmarking**  
   The system multiplies extracted quantity by the average emission factor and compares the total daily CO₂e against the average daily emission derived from `Carbon_Emission.csv` demographic data.

---

## 🔮 Future Enhancements

- **Advanced NLP**: Integrate spaCy or HuggingFace Transformers (e.g., BERT) to handle complex, varied, and ambiguous sentence structures.
- **User Accounts & History**: Add SQLite database to track carbon footprints over weeks or months.
- **Expanded Categories**: Include electricity usage, international shipping factors, and additional food items.
- **Gamification**: Introduce a "Green Score" or show equivalent environmental impacts (e.g., "Your choices saved the equivalent of 2 trees!").
- **Data Visualization**: Add charts and trends for historical footprint analysis.

---

## 🤝 Contributing

Contributions are welcome! To contribute:

1. **Fork** the repository on GitHub.
2. **Create a feature branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** and test them thoroughly.
4. **Commit** with clear, descriptive messages:
   ```bash
   git commit -m "Add feature: description of changes"
   ```
5. **Push** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
6. **Open a Pull Request** with a description of your changes.

### Guidelines

- Follow PEP 8 for Python code style.
- Update tests and documentation for new features.
- Keep commits atomic and descriptive.
- Reference any related issues in your PR description.

---



## 📧 Contact & Support

For questions, issues, or suggestions, please:

<!-- - Open an [issue](https://github.com/[USERNAME]/carbon-tracker/issues) on GitHub. -->
- Reach out via email: **[ritanshupm@gmail.com]**.

---

**Happy tracking! 🌱**
