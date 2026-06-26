import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from logic.database import log_model_performance
from logic.ml_logic import load_raw_datasets, get_email_pipeline, get_file_pipeline

def train_email_model(dataset_path='datasets'):
    print(f"Loading raw email datasets from {dataset_path}...")
    df = load_raw_datasets(dataset_path)
    
    if df.empty:
        print("Warning: No email data found in datasets folder. Falling back to data/emails.csv if available.")
        if os.path.exists('data/emails.csv'):
            df = pd.read_csv('data/emails.csv')
        else:
            print("Error: No training data available.")
            return 0, 0

    # Preprocessing
    X = df['text']
    y = df['label']
    
    # Split data
    # If we have very little data (like the current 6 files), use a smaller test size or avoid split
    test_size = 0.2 if len(df) > 5 else 0.1
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
    
    # Build pipeline
    pipeline = get_email_pipeline()
    
    # Train
    print(f"Training email model with {len(df)} samples...")
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    predictions = pipeline.predict(X_test)
    acc = accuracy_score(y_test, predictions)
    f1 = f1_score(y_test, predictions, average='weighted')
    
    print(f"Email Model Trained. Accuracy: {acc:.2f}, F1: {f1:.2f}")
    
    # Save
    if not os.path.exists('models'):
        os.makedirs('models')
    joblib.dump(pipeline, 'models/email_model.joblib')
    
    # Log to DB
    log_model_performance("Email Detector", "3.0.0", float(acc), float(f1))
    
    return acc, f1

def train_file_model(data_path='data/files.csv'):
    print(f"Loading file data from {data_path}...")
    if not os.path.exists(data_path):
        print(f"Warning: {data_path} not found.")
        return 0, 0
        
    df = pd.read_csv(data_path)
    
    X = df['filename']
    y = df['label']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    pipeline = get_file_pipeline()
    
    print("Training file model...")
    pipeline.fit(X_train, y_train)
    
    predictions = pipeline.predict(X_test)
    acc = accuracy_score(y_test, predictions)
    f1 = f1_score(y_test, predictions, average='weighted')
    
    print(f"File Model Trained. Accuracy: {acc:.2f}, F1: {f1:.2f}")
    
    joblib.dump(pipeline, 'models/file_model.joblib')
    
    # Log to DB
    log_model_performance("File Detector", "3.0.0", float(acc), float(f1))
    
    return acc, f1

if __name__ == "__main__":
    train_email_model()
    train_file_model()
    print("AI Retraining Complete!")
