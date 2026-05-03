import json
import os
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

INPUT_CSV = Path("data/classified_results.csv")
OUT_DIR = Path("analysis")
FIG_DIR = OUT_DIR / "figures"
TABLE_DIR = OUT_DIR / "tables"
SUMMARY_JSON = OUT_DIR / "analysis_summary.json"

PURPLE = "#520671"
GREY = "#6e6c66"
LIGHT_GREY = "#d8d4da"

LABEL_ORDER = [
    "risk_safety",
    "compatibility_constraint",
    "standards_compliance",
    "performance_efficiency",
    "manufacturer_authority",
    "user_experience_opinion",
    "controversy_debate",
    "uncategorised",
]

SOURCE_ORDER = [
    "manufacturer",
    "cycling_media",
    "forum_social_public",
    "standards_policy",
]

PRETTY_LABELS = {
    "risk_safety": "Risk / safety",
    "compatibility_constraint": "Compatibility / constraint",
    "standards_compliance": "Standards / compliance",
    "performance_efficiency": "Performance / efficiency",
    "manufacturer_authority": "Manufacturer authority",
    "user_experience_opinion": "User experience / opinion",
    "controversy_debate": "Controversy / debate",
    "uncategorised": "Uncategorised",
    "manufacturer": "Manufacturer",
    "cycling_media": "Cycling media",
    "forum_social_public": "Public forum/social",
    "standards_policy": "Standards/policy",
}


def ensure_dirs():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)


def load_data():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"{INPUT_CSV} not found. Run: python3 src/hookless_playwright_scraper.py"
        )
    df = pd.read_csv(INPUT_CSV)
    if df.empty:
        raise ValueError("classified_results.csv is empty. Re-run the scraper or add more seed URLs.")
    return df


def order_existing(values, preferred):
    preferred_existing = [v for v in preferred if v in values]
    remaining = [v for v in values if v not in preferred]
    return preferred_existing + sorted(remaining)


def save_tables(df):
    by_source = df["source_group"].value_counts().rename_axis("source_group").reset_index(name="records")
    by_label = df["primary_label"].value_counts().rename_axis("primary_label").reset_index(name="records")

    cross = pd.crosstab(df["source_group"], df["primary_label"])
    cross = cross.reindex(index=order_existing(cross.index.tolist(), SOURCE_ORDER), fill_value=0)
    cross = cross.reindex(columns=order_existing(cross.columns.tolist(), LABEL_ORDER), fill_value=0)

    cross_pct = cross.div(cross.sum(axis=1), axis=0).fillna(0).round(3)

    by_source.to_csv(TABLE_DIR / "records_by_source.csv", index=False)
    by_label.to_csv(TABLE_DIR / "records_by_primary_label.csv", index=False)
    cross.to_csv(TABLE_DIR / "source_by_primary_label_counts.csv")
    cross_pct.to_csv(TABLE_DIR / "source_by_primary_label_row_percent.csv")

    return by_source, by_label, cross, cross_pct


def style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(LIGHT_GREY)
    ax.spines["bottom"].set_color(LIGHT_GREY)
    ax.tick_params(colors=GREY, labelsize=9)
    ax.title.set_color(PURPLE)
    ax.xaxis.label.set_color(GREY)
    ax.yaxis.label.set_color(GREY)


def pretty(items):
    return [PRETTY_LABELS.get(x, x.replace("_", " ")) for x in items]


def figure_source_counts(by_source):
    order = order_existing(by_source["source_group"].tolist(), SOURCE_ORDER)
    data = by_source.set_index("source_group").reindex(order).dropna()

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.barh(pretty(data.index.tolist()), data["records"], color=PURPLE, alpha=0.85)
    ax.invert_yaxis()
    ax.set_xlabel("Extracted discourse segments")
    ax.set_title("A. Corpus composition by source type", loc="left", fontsize=13, fontweight="bold")
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "figure_a_source_counts.svg")
    fig.savefig(FIG_DIR / "figure_a_source_counts.png", dpi=300)
    plt.close(fig)


def figure_label_counts(by_label):
    order = order_existing(by_label["primary_label"].tolist(), LABEL_ORDER)
    data = by_label.set_index("primary_label").reindex(order).dropna()

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.barh(pretty(data.index.tolist()), data["records"], color=GREY, alpha=0.85)
    ax.invert_yaxis()
    ax.set_xlabel("Extracted discourse segments")
    ax.set_title("B. Primary discourse category frequency", loc="left", fontsize=13, fontweight="bold")
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "figure_b_label_counts.svg")
    fig.savefig(FIG_DIR / "figure_b_label_counts.png", dpi=300)
    plt.close(fig)


def figure_heatmap(cross_pct):
    data = cross_pct.copy()
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    im = ax.imshow(data.values, aspect="auto", cmap="Purples", vmin=0, vmax=max(0.01, data.values.max()))

    ax.set_xticks(range(len(data.columns)))
    ax.set_xticklabels(pretty(data.columns.tolist()), rotation=35, ha="right")
    ax.set_yticks(range(len(data.index)))
    ax.set_yticklabels(pretty(data.index.tolist()))

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data.iloc[i, j]
            ax.text(j, i, f"{val:.0%}" if val > 0 else "", ha="center", va="center", fontsize=8, color=GREY)

    ax.set_title("C. Relative discourse profile by source type", loc="left", fontsize=13, fontweight="bold", color=PURPLE)
    ax.tick_params(colors=GREY, labelsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.ax.tick_params(labelsize=8, colors=GREY)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "figure_c_source_label_heatmap.svg")
    fig.savefig(FIG_DIR / "figure_c_source_label_heatmap.png", dpi=300)
    plt.close(fig)


def figure_multi_panel(by_source, by_label, cross_pct):
    fig = plt.figure(figsize=(11, 7.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.15], hspace=0.45, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])
    order_s = order_existing(by_source["source_group"].tolist(), SOURCE_ORDER)
    ds = by_source.set_index("source_group").reindex(order_s).dropna()
    ax1.barh(pretty(ds.index.tolist()), ds["records"], color=PURPLE, alpha=0.85)
    ax1.invert_yaxis()
    ax1.set_title("A. Source composition", loc="left", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Segments")
    style_axes(ax1)

    ax2 = fig.add_subplot(gs[0, 1])
    order_l = order_existing(by_label["primary_label"].tolist(), LABEL_ORDER)
    dl = by_label.set_index("primary_label").reindex(order_l).dropna()
    ax2.barh(pretty(dl.index.tolist()), dl["records"], color=GREY, alpha=0.85)
    ax2.invert_yaxis()
    ax2.set_title("B. Discourse categories", loc="left", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Segments")
    style_axes(ax2)

    ax3 = fig.add_subplot(gs[1, :])
    data = cross_pct.copy()
    im = ax3.imshow(data.values, aspect="auto", cmap="Purples", vmin=0, vmax=max(0.01, data.values.max()))
    ax3.set_xticks(range(len(data.columns)))
    ax3.set_xticklabels(pretty(data.columns.tolist()), rotation=30, ha="right")
    ax3.set_yticks(range(len(data.index)))
    ax3.set_yticklabels(pretty(data.index.tolist()))
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data.iloc[i, j]
            ax3.text(j, i, f"{val:.0%}" if val > 0 else "", ha="center", va="center", fontsize=8, color=GREY)
    ax3.set_title("C. Relative discourse profile by source type", loc="left", fontsize=12, fontweight="bold", color=PURPLE)
    ax3.tick_params(colors=GREY, labelsize=8)
    for spine in ax3.spines.values():
        spine.set_visible(False)
    fig.colorbar(im, ax=ax3, fraction=0.018, pad=0.02)

    fig.suptitle("Hookless Rim Discourse Corpus: Source Type and Framing", x=0.03, y=0.98, ha="left", fontsize=16, fontweight="bold", color=PURPLE)
    fig.text(0.03, 0.935, "Segments extracted from cycling media, manufacturer sources, public discussion pages, and standards/policy references.", color=GREY, fontsize=10)
    fig.savefig(FIG_DIR / "figure_abc_discourse_overview.svg")
    fig.savefig(FIG_DIR / "figure_abc_discourse_overview.png", dpi=300)
    plt.close(fig)


def write_summary(by_source, by_label, cross, cross_pct):
    summary = {
        "total_records": int(by_source["records"].sum()),
        "records_by_source": dict(zip(by_source["source_group"], by_source["records"].astype(int))),
        "records_by_primary_label": dict(zip(by_label["primary_label"], by_label["records"].astype(int))),
        "dominant_label_by_source": {},
        "generated_outputs": {
            "tables": [
                str(TABLE_DIR / "records_by_source.csv"),
                str(TABLE_DIR / "records_by_primary_label.csv"),
                str(TABLE_DIR / "source_by_primary_label_counts.csv"),
                str(TABLE_DIR / "source_by_primary_label_row_percent.csv"),
            ],
            "figures": [
                str(FIG_DIR / "figure_a_source_counts.svg"),
                str(FIG_DIR / "figure_b_label_counts.svg"),
                str(FIG_DIR / "figure_c_source_label_heatmap.svg"),
                str(FIG_DIR / "figure_abc_discourse_overview.svg"),
            ],
        },
    }
    for source, row in cross_pct.iterrows():
        if row.sum() > 0:
            summary["dominant_label_by_source"][source] = row.idxmax()
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main():
    ensure_dirs()
    df = load_data()
    by_source, by_label, cross, cross_pct = save_tables(df)
    figure_source_counts(by_source)
    figure_label_counts(by_label)
    figure_heatmap(cross_pct)
    figure_multi_panel(by_source, by_label, cross_pct)
    summary = write_summary(by_source, by_label, cross, cross_pct)

    print("Analysis complete")
    print(f"Total records: {summary['total_records']}")
    print(f"Figures written to: {FIG_DIR}")
    print(f"Tables written to: {TABLE_DIR}")


if __name__ == "__main__":
    main()
