import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import classification_report

# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_PATH = Path("data/output/run_full")

CM_NORM_PATH = BASE_PATH / "m2_confusion_matrix_normalized.csv"
CM_COUNTS_PATH = BASE_PATH / "m2_confusion_matrix.csv"
PRED_PATH = BASE_PATH / "m2_predictions_full.csv"
PAIRS_PATH = BASE_PATH / "m2_top_confusion_pairs.csv"

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def add_bar_labels(ax, *, fmt="{:.0f}", padding=3, fontsize=9):
    """
    Add value labels to bars of a bar chart.
    Works for both vertical and horizontal bars.
    """
    for container in ax.containers:
        labels = []
        for v in container.datavalues:
            if v is None:
                labels.append("")
                continue
            try:
                labels.append(fmt.format(v))
            except (ValueError, TypeError):
                labels.append(str(v))
        ax.bar_label(container, labels=labels, padding=padding, fontsize=fontsize)

# --------------------------------------------------
# Load data
# --------------------------------------------------

cm_norm = pd.read_csv(CM_NORM_PATH, index_col=0)
cm_counts = pd.read_csv(CM_COUNTS_PATH, index_col=0)
df = pd.read_csv(PRED_PATH)

df["predicted_category"] = df["predicted_category"].fillna("unknown")

CATEGORIES = ["business", "entertainment", "politics", "sport", "tech"]

# ==================================================
# 1) Normalized Confusion Matrix (already requested)
# ==================================================

plt.figure(figsize=(8, 6))
sns.heatmap(
    cm_norm,
    annot=True,
    fmt=".2f",
    cmap="Blues",
    cbar=True
)
plt.xlabel("Predicted category")
plt.ylabel("True category")
plt.title("Normalized Confusion Matrix")
plt.tight_layout()
plt.savefig(BASE_PATH / "m2_confusion_matrix_heatmap.png", dpi=300)
plt.close()

# ==================================================
# 2) Confusion Matrix (Counts)
# ==================================================

plt.figure(figsize=(8, 6))
sns.heatmap(
    cm_counts,
    annot=True,
    fmt="d",
    cbar=True
)
plt.xlabel("Predicted category")
plt.ylabel("True category")
plt.title("Confusion Matrix (Counts)")
plt.tight_layout()
plt.savefig(BASE_PATH / "m2_confusion_matrix_counts_heatmap.png", dpi=300)
plt.close()

# ==================================================
# 3) True vs Predicted Label Distribution
# ==================================================

true_counts = df["true_category"].value_counts()
pred_counts = df["predicted_category"].value_counts()

labels = sorted(set(true_counts.index) | set(pred_counts.index))
true_vals = [true_counts.get(l, 0) for l in labels]
pred_vals = [pred_counts.get(l, 0) for l in labels]

x = range(len(labels))

plt.figure()
ax = plt.gca()

b1 = ax.bar(x, true_vals, label="True")
b2 = ax.bar(x, pred_vals, bottom=true_vals, label="Predicted")

# labels on bars
add_bar_labels(ax, fmt="{:.0f}", padding=2)

ax.set_xticks(list(x))
ax.set_xticklabels(labels, rotation=45)
ax.set_xlabel("Category")
ax.set_ylabel("Count")
ax.set_title("True vs Predicted Label Distribution")
ax.legend()

plt.tight_layout()
plt.savefig(BASE_PATH / "m2_label_distribution.png", dpi=300)
plt.close()

# ==================================================
# 4) Precision, Recall, F1 per Class
# ==================================================

y_true = df["true_category"].tolist()
y_pred = df["predicted_category"].replace("unknown", "").tolist()

report = classification_report(
    y_true,
    y_pred,
    labels=CATEGORIES,
    output_dict=True,
    zero_division=0
)

precision = [report[c]["precision"] for c in CATEGORIES]
recall = [report[c]["recall"] for c in CATEGORIES]
f1 = [report[c]["f1-score"] for c in CATEGORIES]

x = range(len(CATEGORIES))
width = 0.25

plt.figure(figsize=(8, 6))
ax = plt.gca()

ax.bar(
    [i - width for i in x],
    precision,
    width=width,
    label="Precision"
)

ax.bar(
    list(x),
    recall,
    width=width,
    label="Recall"
)

ax.bar(
    [i + width for i in x],
    f1,
    width=width,
    label="F1"
)

# labels on bars (3 decimals is usually readable for metrics)
add_bar_labels(ax, fmt="{:.3f}", padding=2)

ax.set_xticks(list(x))
ax.set_xticklabels(CATEGORIES, rotation=45)
ax.set_ylabel("Score")
ax.set_title("Precision, Recall, and F1 per Class")
ax.legend()

plt.tight_layout()
plt.savefig(BASE_PATH / "m2_metrics_per_class.png", dpi=300)
plt.close()

# ==================================================
# 5) Top Confusion Pairs
# ==================================================

pairs = pd.read_csv(PAIRS_PATH).head(10)

pairs["true_category"] = pairs["true_category"].fillna("unknown")
pairs["predicted_category"] = pairs["predicted_category"].fillna("unknown")

pair_labels = (
    pairs["true_category"].astype(str)
    + " → "
    + pairs["predicted_category"].astype(str)
)

plt.figure()
ax = plt.gca()

ax.barh(pair_labels, pairs["count"].astype(int))

# labels on bars (horizontal)
add_bar_labels(ax, fmt="{:.0f}", padding=3)

ax.set_xlabel("Count")
ax.set_title("Top Confusion Pairs")
ax.invert_yaxis()

plt.tight_layout()
plt.savefig(BASE_PATH / "m2_top_confusion_pairs.png", dpi=300)
plt.close()

# ==================================================
# 6) Unknown Rate per True Class
# ==================================================

unknown_rate = (
    df.assign(is_unknown=df["predicted_category"] == "unknown")
    .groupby("true_category")["is_unknown"]
    .mean()
)

plt.figure()
ax = plt.gca()

ax.bar(unknown_rate.index, unknown_rate.values)

# labels on bars (percent format)
add_bar_labels(ax, fmt="{:.1%}", padding=2)

ax.set_xlabel("True category")
ax.set_ylabel("Share of unknown predictions")
ax.set_title("Unknown Prediction Rate per Class")
plt.xticks(rotation=45)

plt.tight_layout()
plt.savefig(BASE_PATH / "m2_unknown_rate_per_class.png", dpi=300)
plt.close()

print("All evaluation plots generated successfully.")
