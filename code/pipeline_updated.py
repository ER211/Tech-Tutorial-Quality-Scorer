import json, re, warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")

OUT = Path(r"C:\Users\ERRoR404\Downloads\output")
OUT.mkdir(parents=True, exist_ok=True)

PALETTE   = ["#4C72B0","#DD8452","#55A868","#C44E52","#8172B2","#937860","#DA8BC3","#8C8C8C"]
sns.set_theme(style="whitegrid", palette=PALETTE)
plt.rcParams.update({"font.family": "DejaVu Sans", "figure.dpi": 150})

with open(r"C:\Users\ERRoR404\Downloads\output\scraped_tutorials.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

df_raw = pd.DataFrame(raw)
print(f"[LOAD] {len(df_raw)} rows × {len(df_raw.columns)} columns")
print("\n" + "█"*60)
print("  *** BEFORE PREPROCESSING — RAW DATA SNAPSHOT ***")
print("█"*60)

print(f"\n  Shape          : {df_raw.shape[0]} rows × {df_raw.shape[1]} columns")
print(f"  Total Nulls    : {df_raw.isnull().sum().sum()}")
_df_raw_hashable = df_raw.apply(
    lambda col: col.map(lambda v: str(v) if isinstance(v, list) else v)
)
print(f"  Duplicate Rows : {_df_raw_hashable.duplicated().sum()}")
print(f"  Dup Titles     : {df_raw['Title'].duplicated().sum()}")

print("\n  [BEFORE] Missing Values per Column:")
nulls_raw = df_raw.isnull().sum()
nulls_raw_nonzero = nulls_raw[nulls_raw > 0]
if nulls_raw_nonzero.empty:
    print("    (none)")
else:
    for col, cnt in nulls_raw_nonzero.items():
        print(f"    {col:35s}: {cnt}")

print("\n  [BEFORE] Column dtypes:")
print(df_raw.dtypes.to_string())

print("\n  [BEFORE] Sample (first 3 rows, key columns):")
key_cols_before = [c for c in ["Title","Category","Level","Rating","Reviews Count",
                                "Duration","Is Free","Certificate"] if c in df_raw.columns]
print(df_raw[key_cols_before].head(3).to_string(index=False))

print("\n  [BEFORE] Numeric Summary:")
num_cols_raw = df_raw.select_dtypes(include=[np.number]).columns.tolist()
if num_cols_raw:
    print(df_raw[num_cols_raw].describe().round(2).to_string())

print("\n  [BEFORE] Level Distribution:")
print(df_raw["Level"].value_counts(dropna=False).to_string())

print("\n  [BEFORE] Is Free Distribution:")
print(df_raw["Is Free"].value_counts(dropna=False).to_string())

print("\n" + "="*60)
print("  1. DATA QUALITY MANAGEMENT")
print("="*60)

df = df_raw.copy()

print("\n[1a] Missing Values (before imputation):")
null_before = df.isnull().sum()
print(null_before[null_before > 0].to_string())

df["Certificate"] = df["Certificate"].fillna(False).astype(bool)

df["Learning Outcomes"] = df["Learning Outcomes"].apply(
    lambda x: x if isinstance(x, list) else []
)

def parse_duration_hours(d):
    if not d or not isinstance(d, str): return np.nan
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hour|week|month)", d, re.I)
    if not m: return np.nan
    v, unit = float(m.group(1)), m.group(2).lower()
    if "week"  in unit: return v * 40
    if "month" in unit: return v * 160
    return v

df["Duration_Hours"] = df["Duration"].apply(parse_duration_hours)
median_dur = df["Duration_Hours"].median()
df["Duration_Hours"] = df["Duration_Hours"].fillna(median_dur)
df["Duration"] = df["Duration"].fillna(f"{int(median_dur)} hours (imputed)")

df.drop(columns=["Published Date"], inplace=True)

df.drop(columns=["Enrolments"], inplace=True)

null_after = df.isnull().sum()
remaining = null_after[null_after > 0]
if remaining.empty:
    print("[1a] ✓ No remaining nulls after imputation.")
else:
    print("[1a] Remaining nulls after imputation:")
    print(remaining.to_string())

print("\n[1b] Duplicate detection:")
dup_title_mask = df["Title"].duplicated(keep=False)
dup_titles = df[dup_title_mask]["Title"].unique()
print(f"  Duplicate Titles: {len(dup_titles)} → {list(dup_titles)}")

before_dup = len(df)
df.drop_duplicates(subset=["Title"], keep="first", inplace=True)
df.reset_index(drop=True, inplace=True)
print(f"  Rows before: {before_dup}  →  after dedup: {len(df)} (removed {before_dup - len(df)})")

print("\n[1c] Noise Reduction:")

blank_levels = (df["Level"] == "").sum()
df["Level"] = df["Level"].replace("", "Unknown")
print(f"  Blank Level values replaced with 'Unknown': {blank_levels}")

str_cols = df.select_dtypes(include="object").columns
for c in str_cols:
    df[c] = df[c].apply(lambda x: x.strip() if isinstance(x, str) else x)

def dedupe_comments(comments):
    if not isinstance(comments, list): return []
    seen = set(); clean = []
    for c in comments:
        key = c.strip().lower()
        if key not in seen:
            seen.add(key); clean.append(c.strip())
    return clean

before_comments = df["Comments"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()
df["Comments"] = df["Comments"].apply(dedupe_comments)
after_comments  = df["Comments"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()
print(f"  Duplicate comments removed: {before_comments - after_comments}")

zero_rating_noreviews = ((df["Rating"] == 0) & (df["Reviews Count"] == 0)).sum()
print(f"  Courses with Rating=0 and Reviews=0 (no-engagement noise): {zero_rating_noreviews}")
df["Has_Engagement"] = (df["Rating"] > 0) | (df["Reviews Count"] > 0)

print(f"  Duration parsed to numeric (hours) for {df['Duration_Hours'].notna().sum()} records")

df["Instructor_Count"] = df["Instructor"].apply(
    lambda x: len(x) if isinstance(x, list) else 1
)
df["Tag_Count"] = df["Tags"].apply(lambda x: len(x) if isinstance(x, list) else 0)
df["LO_Count"]  = df["Learning Outcomes"].apply(lambda x: len(x) if isinstance(x, list) else 0)
df["Module_Density"] = (df["Lessons Count"] / df["Modules Count"].replace(0, np.nan)).round(2)

print("\n" + "="*60)
print("  2. DATA PREPROCESSING PIPELINE")
print("="*60)

steps = [
    ("Certificate null→False",     27),
    ("Learning Outcomes null→[]",  19),
    ("Duration null→median impute", 2),
    ("Dropped: Published Date",    168),
    ("Dropped: Enrolments",        168),
    ("Removed duplicate titles",     1),
    ("Blank Level→'Unknown'",       21),
    ("Deduplicated comments",  before_comments - after_comments),
    ("Stripped whitespace", df[str_cols].shape[0]),
    ("Engineered: Duration_Hours",   "✓"),
    ("Engineered: Instructor_Count", "✓"),
    ("Engineered: Tag_Count",        "✓"),
    ("Engineered: LO_Count",         "✓"),
    ("Engineered: Module_Density",   "✓"),
    ("Flagged: Has_Engagement",      "✓"),
]

print("\nCleaning steps applied:")
for step, val in steps:
    print(f"  {step:45s}  {val}")


print("Before vs After:")
print(f"  Rows:    {len(df_raw)} → {len(df)}")
print(f"  Columns: {len(df_raw.columns)} → {len(df.columns)}")
print(f"  Nulls:   {df_raw.isnull().sum().sum()} → {df.isnull().sum().sum()}")


print("\n" + "="*60)
print("  3. EXPLORATORY DATA ANALYSIS (EDA)")
print("="*60)

print("\n[3a] Key Patterns:")

cat_counts = df["Category"].value_counts()
print(f"\n  Top Category: {cat_counts.index[0]} ({cat_counts.iloc[0]} courses)")

lv_counts = df["Level"].value_counts()
print(f"  Level distribution:\n{lv_counts.to_string()}")

free_pct = df["Is Free"].mean() * 100
print(f"\n  Free courses: {free_pct:.1f}%  |  Paid: {100-free_pct:.1f}%")

eng_pct = df["Has_Engagement"].mean() * 100
print(f"  Courses with engagement (rating or reviews): {eng_pct:.1f}%")

print(f"\n  Duration_Hours — median: {df['Duration_Hours'].median():.0f}h | "
      f"mean: {df['Duration_Hours'].mean():.0f}h | "
      f"max: {df['Duration_Hours'].max():.0f}h")

print("\n[3b] Statistical Insights:")
num_cols = ["Rating", "Reviews Count", "Modules Count", "Lessons Count",
            "Duration_Hours", "Tag_Count", "LO_Count"]
stats = df[num_cols].describe().round(2)
print(stats.to_string())

print("\n  Correlation with Rating:")
corr = df[num_cols].corr()["Rating"].drop("Rating").sort_values(ascending=False)
print(corr.round(3).to_string())
print("\n" + "="*60)
print("  4. DATA VISUALIZATION & INSIGHTS")
print("="*60)

fig_paths = []

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("Fig 1 — Missing Values: Before vs After Preprocessing", fontsize=13, fontweight="bold")

nulls_before = df_raw.isnull().sum().sort_values(ascending=False)
nulls_before = nulls_before[nulls_before > 0]
axes[0].barh(nulls_before.index, nulls_before.values, color="#C44E52")
axes[0].set_title("Before Preprocessing")
axes[0].set_xlabel("Null Count")
for i, v in enumerate(nulls_before.values):
    axes[0].text(v + 1, i, str(v), va="center", fontsize=8)

nulls_after = df.isnull().sum().sort_values(ascending=False)
nulls_after = nulls_after[nulls_after > 0]
if nulls_after.empty:
    axes[1].text(0.5, 0.5, "✓ Zero Null Values\nAfter Preprocessing",
                 ha="center", va="center", fontsize=14, color="#55A868",
                 fontweight="bold", transform=axes[1].transAxes)
    axes[1].set_title("After Preprocessing")
    axes[1].axis("off")
else:
    axes[1].barh(nulls_after.index, nulls_after.values, color="#55A868")
    axes[1].set_title("After Preprocessing")

plt.tight_layout()
p = OUT / "fig1_missing_values.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 1 saved: {p.name}")


fig, ax = plt.subplots(figsize=(9, 7))
fig.suptitle("Fig 2 — Course Distribution by Category", fontsize=13, fontweight="bold")

cat_short = cat_counts.copy()
cat_short.index = cat_short.index.str.replace("School of ", "", regex=False)
wedges, texts, autotexts = ax.pie(
    cat_short.values,
    labels=cat_short.index,
    autopct="%1.1f%%",
    startangle=140,
    colors=PALETTE[:len(cat_short)],
    pctdistance=0.82,
    wedgeprops=dict(width=0.55)
)
for at in autotexts: at.set_fontsize(8)
ax.set_title("Total: 167 courses", fontsize=10, pad=12)
plt.tight_layout()
p = OUT / "fig2_category_donut.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 2 saved: {p.name}")


fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("Fig 3 — Course Ratings", fontsize=13, fontweight="bold")

engaged = df[df["Has_Engagement"]]
axes[0].hist(engaged["Rating"], bins=20, color=PALETTE[0], edgecolor="white", alpha=0.85)
axes[0].axvline(engaged["Rating"].mean(), color=PALETTE[1], lw=2, linestyle="--",
                label=f'Mean={engaged["Rating"].mean():.2f}')
axes[0].axvline(engaged["Rating"].median(), color=PALETTE[2], lw=2, linestyle="-.",
                label=f'Median={engaged["Rating"].median():.2f}')
axes[0].set_title("Rating Distribution (engaged courses)")
axes[0].set_xlabel("Rating"); axes[0].set_ylabel("Count")
axes[0].legend()

level_order = ["Beginner","Intermediate","Advanced","Fluency","Discovery","Unknown"]
level_order = [l for l in level_order if l in df["Level"].unique()]
bp_data = [df[df["Level"] == l]["Rating"].dropna().values for l in level_order]
bp = axes[1].boxplot(bp_data, labels=level_order, patch_artist=True, notch=False)
for patch, color in zip(bp["boxes"], PALETTE):
    patch.set_facecolor(color)
axes[1].set_title("Rating by Course Level")
axes[1].set_xlabel("Level"); axes[1].set_ylabel("Rating")
plt.tight_layout()
p = OUT / "fig3_ratings.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 3 saved: {p.name}")


all_tags = [t for tags in df["Tags"] for t in (tags if isinstance(tags, list) else [])]
tag_counts = Counter(all_tags)
top_tags = pd.Series(dict(tag_counts.most_common(15))).sort_values()

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.barh(top_tags.index, top_tags.values, color=sns.color_palette("Blues_d", len(top_tags)))
ax.set_title("Fig 4 — Top 15 Course Tags", fontsize=13, fontweight="bold")
ax.set_xlabel("Number of Courses")
for bar in bars:
    ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
            str(int(bar.get_width())), va="center", fontsize=8)
plt.tight_layout()
p = OUT / "fig4_top_tags.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 4 saved: {p.name}")


fig, ax = plt.subplots(figsize=(10, 6))
colors_map = {True: PALETTE[2], False: PALETTE[0]}
for is_free, group in df.groupby("Is Free"):
    ax.scatter(group["Duration_Hours"], group["Rating"],
               alpha=0.6, s=50, c=colors_map[is_free],
               label="Free" if is_free else "Paid", edgecolors="white", lw=0.4)
ax.set_title("Fig 5 — Duration vs Rating (Free vs Paid)", fontsize=13, fontweight="bold")
ax.set_xlabel("Duration (Hours)"); ax.set_ylabel("Rating")
ax.legend()
z = np.polyfit(df["Duration_Hours"], df["Rating"], 1)
p_line = np.poly1d(z)
xline = np.linspace(df["Duration_Hours"].min(), df["Duration_Hours"].max(), 200)
ax.plot(xline, p_line(xline), "--", color="gray", lw=1.5, label="Trend")
ax.legend()
plt.tight_layout()
fp = OUT / "fig5_duration_rating.png"
plt.savefig(fp, bbox_inches="tight"); plt.close()
fig_paths.append(fp)
print(f"  ✓ Fig 5 saved: {fp.name}")


fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Fig 6 — Reviews Count Distribution", fontsize=13, fontweight="bold")

axes[0].hist(df["Reviews Count"], bins=30, color=PALETTE[3], edgecolor="white")
axes[0].set_title("Linear Scale"); axes[0].set_xlabel("Reviews Count")

axes[1].hist(df["Reviews Count"][df["Reviews Count"] > 0] + 1,
             bins=30, color=PALETTE[4], edgecolor="white")
axes[1].set_xscale("log")
axes[1].set_title("Log Scale (>0 reviews)"); axes[1].set_xlabel("Reviews Count (log)")
plt.tight_layout()
p = OUT / "fig6_reviews_dist.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 6 saved: {p.name}")


fig, ax = plt.subplots(figsize=(9, 7))
corr_matrix = df[num_cols].corr().round(2)
mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
sns.heatmap(corr_matrix, mask=mask, annot=True, fmt=".2f",
            cmap="coolwarm", center=0, ax=ax,
            annot_kws={"size": 9}, linewidths=0.5)
ax.set_title("Fig 7 — Correlation Heatmap (Numeric Features)", fontsize=13, fontweight="bold")
plt.tight_layout()
p = OUT / "fig7_correlation_heatmap.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 7 saved: {p.name}")


fig, ax = plt.subplots(figsize=(10, 6))
cat_palette = dict(zip(df["Category"].unique(), PALETTE * 5))
for cat, grp in df.groupby("Category"):
    short = cat.replace("School of ", "")
    ax.scatter(grp["Modules Count"], grp["Lessons Count"],
               alpha=0.65, s=55, label=short,
               color=cat_palette[cat], edgecolors="white", lw=0.3)
ax.set_title("Fig 8 — Modules vs Lessons Count by Category", fontsize=13, fontweight="bold")
ax.set_xlabel("Modules Count"); ax.set_ylabel("Lessons Count")
ax.legend(fontsize=7, ncol=2, loc="upper left")
plt.tight_layout()
p = OUT / "fig8_modules_lessons.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 8 saved: {p.name}")


fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Fig 9 — Free vs Paid Courses Analysis", fontsize=13, fontweight="bold")

free_g   = df[df["Is Free"]  == True]
paid_g   = df[df["Is Free"]  == False]

axes[0].hist(free_g["Rating"], bins=15, alpha=0.7, color=PALETTE[2], label="Free", edgecolor="white")
axes[0].hist(paid_g["Rating"], bins=15, alpha=0.7, color=PALETTE[0], label="Paid", edgecolor="white")
axes[0].set_title("Rating Distribution")
axes[0].set_xlabel("Rating"); axes[0].legend()

summary = pd.DataFrame({
    "Metric": ["Avg Rating", "Avg Reviews", "Avg Duration (h)", "Avg Lessons"],
    "Free": [
        free_g["Rating"].mean(), free_g["Reviews Count"].mean(),
        free_g["Duration_Hours"].mean(), free_g["Lessons Count"].mean()
    ],
    "Paid": [
        paid_g["Rating"].mean(), paid_g["Reviews Count"].mean(),
        paid_g["Duration_Hours"].mean(), paid_g["Lessons Count"].mean()
    ]
})
x = np.arange(len(summary))
w = 0.35
axes[1].bar(x - w/2, summary["Free"],  width=w, label="Free", color=PALETTE[2])
axes[1].bar(x + w/2, summary["Paid"],  width=w, label="Paid", color=PALETTE[0])
axes[1].set_xticks(x); axes[1].set_xticklabels(summary["Metric"], rotation=15, ha="right")
axes[1].set_title("Key Metric Comparison"); axes[1].legend()
plt.tight_layout()
p = OUT / "fig9_free_vs_paid.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 9 saved: {p.name}")


fig, ax = plt.subplots(figsize=(12, 5))
cat_stats = df.groupby("Category").agg(
    Avg_Rating=("Rating", "mean"),
    Avg_Duration=("Duration_Hours", "mean"),
    Avg_Reviews=("Reviews Count", "mean"),
    Course_Count=("Title", "count")
).round(2)
cat_stats.index = cat_stats.index.str.replace("School of ", "").str.replace("Career resources", "Career")

heat_data = cat_stats[["Avg_Rating","Avg_Duration","Avg_Reviews","Course_Count"]].T
sns.heatmap(heat_data, annot=True, fmt=".1f", cmap="YlGnBu", ax=ax,
            linewidths=0.5, annot_kws={"size": 8})
ax.set_title("Fig 10 — Category KPI Heatmap", fontsize=13, fontweight="bold")
ax.set_xlabel(""); ax.set_ylabel("")
plt.xticks(rotation=25, ha="right", fontsize=8)
plt.tight_layout()
p = OUT / "fig10_category_kpi_heatmap.png"
plt.savefig(p, bbox_inches="tight"); plt.close()
fig_paths.append(p)
print(f"  ✓ Fig 10 saved: {p.name}")


print("\n" + "█"*60)
print("  *** AFTER PREPROCESSING — CLEAN DATA SNAPSHOT ***")
print("█"*60)

print(f"\n  Shape          : {df.shape[0]} rows × {df.shape[1]} columns")
print(f"  Total Nulls    : {df.isnull().sum().sum()}")
_df_hashable = df.apply(
    lambda col: col.map(lambda v: str(v) if isinstance(v, list) else v)
)
print(f"  Duplicate Rows : {_df_hashable.duplicated().sum()}")

print("\n  [AFTER] Missing Values per Column:")
nulls_clean = df.isnull().sum()
nulls_clean_nonzero = nulls_clean[nulls_clean > 0]
if nulls_clean_nonzero.empty:
    print("    ✓ Zero nulls remaining")
else:
    for col, cnt in nulls_clean_nonzero.items():
        print(f"    {col:35s}: {cnt}")

print("\n  [AFTER] Column dtypes:")
print(df.dtypes.to_string())

print("\n  [AFTER] Sample (first 3 rows, key columns):")
key_cols_after = [c for c in ["Title","Category","Level","Rating","Reviews Count",
                               "Duration_Hours","Is Free","Certificate",
                               "Has_Engagement","Tag_Count","LO_Count","Module_Density"]
                  if c in df.columns]
print(df[key_cols_after].head(3).to_string(index=False))

print("\n  [AFTER] Numeric Summary (clean data):")
num_cols_clean = ["Rating","Reviews Count","Modules Count","Lessons Count",
                  "Duration_Hours","Tag_Count","LO_Count","Module_Density",
                  "Instructor_Count"]
num_cols_clean = [c for c in num_cols_clean if c in df.columns]
print(df[num_cols_clean].describe().round(2).to_string())

print("\n  [AFTER] Level Distribution:")
print(df["Level"].value_counts(dropna=False).to_string())

print("\n  [AFTER] Is Free Distribution:")
print(df["Is Free"].value_counts(dropna=False).to_string())

print("\n  [AFTER] Has_Engagement Distribution:")
print(df["Has_Engagement"].value_counts(dropna=False).to_string())

print("\n  [AFTER] New Engineered Columns Summary:")
eng_cols = ["Duration_Hours","Instructor_Count","Tag_Count","LO_Count","Module_Density"]
for col in eng_cols:
    if col in df.columns:
        s = df[col].describe()
        print(f"    {col:20s}  min={s['min']:.1f}  mean={s['mean']:.1f}  max={s['max']:.1f}")


def make_serialisable(val):
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return None if np.isnan(val) else float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, list):
        return [make_serialisable(v) for v in val]
    return val

df_export = df.copy()

list_cols = ["Instructor","Instructor Bio","Tags","Prerequisites",
             "Learning Outcomes","Content Outline","Comments"]
for col in list_cols:
    if col in df_export.columns:
        df_export[col] = df_export[col].apply(
            lambda x: x if isinstance(x, list) else ([x] if pd.notna(x) else [])
        )

records = []
for _, row in df_export.iterrows():
    record = {}
    for k, v in row.items():
        record[k] = make_serialisable(v)
    records.append(record)

json_path = OUT / "tutorials_clean.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"\n  ✓ Clean JSON saved: {json_path.name}  ({len(records)} records)")

print("\n" + "="*60)
print("  PIPELINE COMPLETE")
print(f"  Output files: {len(fig_paths)+1} files → {OUT}")
print("="*60)