import os
import pandas as pd
import email
import logging
from email import policy
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger("PhishingDetector.MLLogic")

def load_text_from_file(file_path: str) -> str:
    """
    Reads content from .txt or .eml files.
    """
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == '.eml':
            with open(file_path, 'rb') as f:
                msg = email.message_from_binary_file(f, policy=policy.default)
                content = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            content += part.get_payload(decode=True).decode(errors='ignore')
                else:
                    content = msg.get_content()
                return content or ""
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return ""

def load_raw_datasets(base_path: str = 'datasets') -> pd.DataFrame:
    """
    Loads email data from the datasets directory structure.
    """
    data = []
    categories = ['legitimate', 'suspicious', 'phishing']
    
    if not os.path.exists(base_path):
        logger.warning(f"Dataset path {base_path} not found.")
        return pd.DataFrame(columns=['text', 'label'])

    for category in categories:
        cat_path = os.path.join(base_path, category)
        if not os.path.exists(cat_path):
            continue
            
        for filename in os.listdir(cat_path):
            file_path = os.path.join(cat_path, filename)
            if os.path.isfile(file_path):
                text = load_text_from_file(file_path)
                if text.strip():
                    data.append({'text': text, 'label': category})
    
    df = pd.DataFrame(data)
    if df.empty:
        logger.warning("No data loaded for training.")
    return df

def get_email_pipeline():
    """
    Returns an optimized scikit-learn pipeline for email classification.
    """
    return Pipeline([
        ('tfidf', TfidfVectorizer(
            stop_words='english',
            max_features=10000,
            ngram_range=(1, 2),
            sublinear_tf=True
        )),
        ('clf', LogisticRegression(max_iter=1000))
    ])

def get_file_pipeline():
    """
    Returns a scikit-learn pipeline for file extension classification.
    """
    return Pipeline([
        ('tfidf', TfidfVectorizer(
            analyzer='char',
            ngram_range=(2, 4),
            max_features=2000
        )),
        ('clf', LogisticRegression(max_iter=1000, class_weight='balanced'))
    ])
