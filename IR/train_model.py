import json
import pandas as pd
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer

# Load dataset
with open("tutorials_clean.json", "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data)

# Combine features
df["combined"] = (
    df["Title"].fillna('') + " " +
    df["Description"].fillna('') + " " +
    df["Category"].fillna('') + " " +
    df["Level"].fillna('') + " " +
    df["Tags"].astype(str)
)

# TF-IDF
vectorizer = TfidfVectorizer(
    stop_words='english',
    max_features=5000
)

tfidf_matrix = vectorizer.fit_transform(df["combined"])

# Save
pickle.dump(vectorizer,
            open("tfidf_vectorizer.pkl","wb"))

pickle.dump(tfidf_matrix,
            open("courses_model.pkl","wb"))

print("AI Model Trained Successfully")