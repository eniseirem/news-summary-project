import pandas as pd
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix

# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_PATH = Path("data/output/run_full")
CSV_PATH = BASE_PATH / "m2_predictions_full.csv"

# --------------------------------------------------
# Load data
# --------------------------------------------------

df = pd.read_csv(CSV_PATH)

# Ensure correct is boolean (important for performance)
df["correct"] = df["correct"].astype(bool)

# --------------------------------------------------
# Label setup
# --------------------------------------------------

CATEGORIES = ["business", "entertainment", "politics", "sport", "tech"]
LABELS = CATEGORIES + [""]  # empty string = unknown

y_true = df["true_category"].tolist()
y_pred = df["predicted_category"].fillna("").tolist()

# --------------------------------------------------
# Classification report
# --------------------------------------------------

report_str = str(
    classification_report(
        y_true,
        y_pred,
        labels=LABELS,
        target_names=CATEGORIES + ["unknown"],
        digits=3,
        zero_division=0
    )
)

print("\nClassification Report\n")
print(report_str)

report_path = BASE_PATH / "m2_classification_report.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report_str)

print(f"Saved classification report to {report_path}")

# --------------------------------------------------
# Confusion matrix (counts)
# --------------------------------------------------

cm = confusion_matrix(y_true, y_pred, labels=LABELS)

cm_df = pd.DataFrame(
    cm,
    index=CATEGORIES + ["unknown"],
    columns=CATEGORIES + ["unknown"]
)

cm_counts_path = BASE_PATH / "m2_confusion_matrix.csv"
cm_df.to_csv(cm_counts_path)

print(f"Saved confusion matrix to {cm_counts_path}")

# --------------------------------------------------
# Confusion matrix (normalized, row-wise)
# --------------------------------------------------

cm_norm = cm_df.div(cm_df.sum(axis=1).replace(0, 1), axis=0)

cm_norm_path = BASE_PATH / "m2_confusion_matrix_normalized.csv"
cm_norm.to_csv(cm_norm_path)

print(f"Saved normalized confusion matrix to {cm_norm_path}")

# --------------------------------------------------
# Error analysis
# --------------------------------------------------

df_errors = df[~df["correct"]].copy()

errors_path = BASE_PATH / "m2_errors.csv"
df_errors.to_csv(errors_path, index=False)

print(f"Saved misclassified articles to {errors_path}")
print(f"Number of misclassified articles: {len(df_errors)}")

# --------------------------------------------------
# Top confusion pairs (true -> predicted)
# --------------------------------------------------

confusion_pairs = (
    df_errors
    .groupby(["true_category", "predicted_category"], dropna=False)
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)

pairs_path = BASE_PATH / "m2_top_confusion_pairs.csv"
confusion_pairs.to_csv(pairs_path, index=False)

print(f"Saved top confusion pairs to {pairs_path}")

# --------------------------------------------------
# Sample error examples for top confusion pairs
# --------------------------------------------------

TOP_K = 5
SAMPLES_PER_PAIR = 5

top_pairs = confusion_pairs.head(TOP_K)

sampled_rows = []

for _, row in top_pairs.iterrows():
    true_cat = row["true_category"]
    pred_cat = row["predicted_category"]

    subset = df_errors[
        (df_errors["true_category"] == true_cat) &
        (df_errors["predicted_category"] == pred_cat)
    ]

    if len(subset) == 0:
        continue

    sampled = subset.sample(
        n=min(SAMPLES_PER_PAIR, len(subset)),
        random_state=42
    )

    sampled_rows.append(sampled)

if sampled_rows:
    df_samples = pd.concat(sampled_rows, ignore_index=True)

    samples_path = BASE_PATH / "m2_error_samples_top_pairs.csv"
    df_samples.to_csv(samples_path, index=False)

    print(f"Saved error samples to {samples_path}")
else:
    print("No error samples generated")

# --------------------------------------------------
# Done
# --------------------------------------------------

print("Evaluation completed successfully.")
