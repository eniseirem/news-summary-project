import json
from pathlib import Path

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


DATA_PATH = Path("data/input/articles.json")
OUTPUT_PATH = Path("data/output/clustering_result.json")


def load_german_articles():
    with open(DATA_PATH, encoding="utf-8") as f:
        articles = json.load(f)

    german = [
        {
            "id": a["id"],
            "title": a["title"],
            "text": f'{a["title"]}. {a["body"]}'
        }
        for a in articles
        if a.get("language") == "de"
    ]

    return german[:10]  # bewusst klein halten


def cluster_articles(articles, n_clusters=3):
    texts = [a["text"] for a in articles]

    vectorizer = TfidfVectorizer(
        max_features=500,
        stop_words="german"
    )
    X = vectorizer.fit_transform(texts)

    model = KMeans(
        n_clusters=n_clusters,
        random_state=42,
        n_init=10
    )
    labels = model.fit_predict(X)

    feature_names = vectorizer.get_feature_names_out()

    clusters = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(label, []).append(articles[idx])

    cluster_keywords = {}
    for label in clusters:
        center = model.cluster_centers_[label]
        top_indices = center.argsort()[-8:][::-1]
        cluster_keywords[label] = [feature_names[i] for i in top_indices]

    return clusters, cluster_keywords


def run():
    articles = load_german_articles()
    clusters, keywords = cluster_articles(articles)

    output = []
    for label, items in clusters.items():
        output.append({
            "cluster_id": int(label),
            "keywords": keywords[label],
            "articles": [
                {
                    "id": a["id"],
                    "title": a["title"]
                }
                for a in items
            ]
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("Clustering finished.")
    print(f"Output written to {OUTPUT_PATH}")


if __name__ == "__main__":
    run()
