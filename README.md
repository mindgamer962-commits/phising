# AI-Powered Phishing Detector

A hybrid phishing detection system that combines Machine Learning (Naive Bayes) with rule-based heuristics to identify phishing emails, malicious URLs, and suspicious file names.

## Features

- **Hybrid Detection**: Uses sklearn's `MultinomialNB` alongside advanced rule-based scanning.
- **Context-Aware Analysis**: Distinguishes between explicit phishing threats and safe educational content.
- **Emotional Deception Scoring (EDS)**: Analyzes the use of Fear, Urgency, Authority, Trust, and Greed in email content.
- **Scalable Architecture**: Modular logic for URL, Email, and File analysis.
- **Retrainable**: Easily update the AI models with new datasets.

## Directory Structure

```text
├── app.py              # Flask Web Application
├── logic/
│   ├── detector.py     # Main detection engine (Hybrid)
│   ├── ml_logic.py     # ML pipeline and data loading
│   └── database.py     # Database integration
├── models/             # Trained joblib models
├── datasets/           # Raw training data (.txt, .eml)
└── tests/              # Automated test suite
```

## Setup and Installation

1. Install dependencies:
   ```bash
   pip install flask pandas scikit-learn joblib mysql-connector-python
   ```
2. Configure environment variables in `.env`.
3. Train the models:
   ```bash
   python train_model.py
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## Running Tests

Execute the standardized test suite:
```bash
python tests/test_suite.py
```

## How it Works

The system calculates a risk score (0-100).
- **AI Prediction**: ML models provide a baseline probability based on trained patterns.
- **Heuristics**: Specific rules analyze metadata, keywords, and structural anomalies.
- **EDS**: Social engineering tactics are weighted to determine the emotional manipulation level.
