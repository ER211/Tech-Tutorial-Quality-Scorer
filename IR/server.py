from flask import Flask, request, jsonify

import json
import pickle
import pandas as pd

from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# Load dataset
with open("tutorials_clean.json","r",
          encoding="utf-8") as f:

    data = json.load(f)

df = pd.DataFrame(data)

# Load AI model
vectorizer = pickle.load(open("tfidf_vectorizer.pkl","rb"))

tfidf_matrix = pickle.load(open("courses_model.pkl","rb"))

@app.route("/recommend", methods=["POST"])

def recommend():

    query = request.json["query"]

    query_vector = vectorizer.transform([query])

    similarity = cosine_similarity(query_vector,
                          tfidf_matrix)

    scores = similarity.flatten()

    top_indices = scores.argsort()[-5:][::-1]

    results = []

    for idx in top_indices:

        course = df.iloc[idx]

        results.append({

            "Title": course["Title"],
            "Category": course["Category"],
            "Level": course["Level"],
            "Rating": float(course["Rating"]),
            "Description": course["Description"],
            "Duration": course["Duration"],
            "Score": float(scores[idx])

        })

    return jsonify(results)

if __name__ == "__main__":

    app.run(debug=True)