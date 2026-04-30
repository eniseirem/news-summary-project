import json
import pandas as pd
from pathlib import Path

BASE_PATH = Path("data/output/run_full")
OUT_FILE = BASE_PATH / "m2_predictions_full.csv"

all_records = []

for i in range(1, 51):
    file_path = BASE_PATH / f"test_kaggle_results_{i}.json"
    with open(file_path, "r", encoding="utf-8") as f:
        all_records.extend(json.load(f))

df = pd.DataFrame(all_records)

df.to_csv(OUT_FILE, index=False)

print(f"Saved merged file with {len(df)} articles to {OUT_FILE}")
