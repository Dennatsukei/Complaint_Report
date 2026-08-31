import ast
import pandas as pd

import plotly.express as px
from plotly.io import to_html
from config import RuntimePaths
from fields import CATEGORY_MAP, SUBCATEGORY_MAP


# ==================================================
# 1. Configuration
# ==================================================
PATHS = RuntimePaths.from_environment()
INPUT_FILE = PATHS.stage_file("07_structured_complaints.csv")
OUTPUT_FILE = PATHS.dashboard_file


CATEGORY_COLOR_MAP = {
    "客房卫生与房态": "#1f77b4",
    "客房设施与工程": "#ff7f0e",
    "服务与响应": "#2ca02c",
    "噪音与公共环境": "#d62728",
    "预订、房型与费用": "#9467bd",
    "物品、安全与其他": "#8c564b",
}


# ==================================================
# 2. Load data
# ==================================================

df = pd.read_csv(INPUT_FILE)


def parse_issues(value):
    """Convert serialized issues into Python objects."""

    if pd.isna(value):
        return []

    return ast.literal_eval(value)


df["issues"] = df["issues"].apply(parse_issues)


# ==================================================
# 3. Normalize issues
# ==================================================

issue_df = (
    df[
        [
            "complaint_id",
            "record_id",
            "issues"
        ]
    ]
    .explode("issues")
    .dropna(subset=["issues"])
    .reset_index(drop=True)
)


issue_details = (
    pd.json_normalize(issue_df["issues"])
    .reset_index(drop=True)
)


issue_df = pd.concat(
    [
        issue_df.drop(columns="issues"),
        issue_details
    ],
    axis=1
)


# ==================================================
# 4. Standardize category names
# ==================================================

issue_df["category"] = (
    issue_df["category"]
    .map(CATEGORY_MAP)
)


issue_df["subcategory"] = (
    issue_df["subcategory"]
    .map(SUBCATEGORY_MAP)
)


# ==================================================
# 5. Calculate complaint weights
# ==================================================

issue_count_by_complaint = (
    issue_df
    .groupby("complaint_id")
    .size()
)


issue_df["issue_count"] = (
    issue_df["complaint_id"]
    .map(issue_count_by_complaint)
)


issue_df["weight"] = (
    1 / issue_df["issue_count"]
)


# ==================================================
# 6. Aggregate analysis data
# ==================================================

# --------------------------------------------------
# 6.1 Category counts
# --------------------------------------------------

category_counts = (
    issue_df["category"]
    .value_counts()
    .rename_axis("category")
    .reset_index(name="count")
)


# --------------------------------------------------
# 6.2 Complaint-weighted category counts
# --------------------------------------------------

weighted_category_counts = (
    issue_df
    .groupby("category")["weight"]
    .sum()
    .reset_index(name="weighted_count")
    .sort_values(
        "weighted_count",
        ascending=False
    )
)


# --------------------------------------------------
# 6.3 Category → Subcategory
# --------------------------------------------------

subcategory_counts = (
    issue_df
    .groupby(
        [
            "category",
            "subcategory"
        ]
    )
    .size()
    .reset_index(name="count")
)


# --------------------------------------------------
# 6.4 Subcategory ranking
# --------------------------------------------------

subcategory_ranking = (
    subcategory_counts
    .sort_values(
        "count",
        ascending=False
    )
)


# --------------------------------------------------
# 6.5 Category × Responsible Department
# --------------------------------------------------

category_department_counts = (
    issue_df
    .groupby(
        [
            "category",
            "responsible_department"
        ]
    )
    .size()
    .reset_index(name="count")
)


# ==================================================
# 7. Create figures
# ==================================================

# --------------------------------------------------
# 7.1 Issue-wise Pie Chart
# --------------------------------------------------

fig_raw = px.pie(
    category_counts,
    names="category",
    values="count",
    color="category",
    title="Complaint by Category（Issue-wise）",
    color_discrete_map=CATEGORY_COLOR_MAP
)


fig_raw.update_traces(
    textinfo="label+percent"
)


fig_raw.update_layout(
    height=500
)


# --------------------------------------------------
# 7.2 Complaint-weighted Pie Chart
# --------------------------------------------------

fig_weighted = px.pie(
    weighted_category_counts,
    names="category",
    values="weighted_count",
    color="category",
    title="Complaint by Category（Complaint-weighted）",
    color_discrete_map=CATEGORY_COLOR_MAP
)


fig_weighted.update_traces(
    textinfo="label+percent"
)


fig_weighted.update_layout(
    height=500
)


# --------------------------------------------------
# 7.3 Category → Subcategory Sunburst
# --------------------------------------------------

fig_sunburst = px.sunburst(
    subcategory_counts,
    path=[
        "category",
        "subcategory"
    ],
    values="count",
    color="category",
    title="Breakdown of Complaint Issues",
    color_discrete_map=CATEGORY_COLOR_MAP
)


fig_sunburst.update_layout(
    height=700
)


# --------------------------------------------------
# 7.4 Subcategory Bar Chart
# --------------------------------------------------

fig_bar = px.bar(
    subcategory_ranking,
    x="count",
    y="subcategory",
    color="category",
    orientation="h",
    title="Count of Complaint Issues",
    text="count",
    color_discrete_map=CATEGORY_COLOR_MAP
)


fig_bar.update_layout(
    height=600,
    yaxis={
        "categoryorder": "total ascending"
    }
)


# --------------------------------------------------
# 7.5 Category × Responsible Department
# --------------------------------------------------

fig_category_department = px.bar(
    category_department_counts,
    x="count",
    y="category",
    color="responsible_department",
    orientation="h",
    title="Complaint Issues by Category and Responsible Department",
    text="count",
    barmode="stack"
)


fig_category_department.update_layout(
    height=600,
    yaxis={
        "categoryorder": "total ascending"
    }
)


# ==================================================
# 8. Debug output
# ==================================================

print("=" * 50)

print("Original df:", len(df))
print("Issue df:", len(issue_df))

print("\nCategory counts:")
print(category_counts)

print("\nWeighted category counts:")
print(weighted_category_counts)

print("\nSubcategory counts:")
print(subcategory_counts)

print("\nPie chart values:")
print(fig_raw.data[0].values)

print("=" * 50)


# ==================================================
# 9. Convert figures to HTML
# ==================================================

def figure_to_html(fig, include_js=False):
    """
    Convert a Plotly figure to an HTML fragment.

    Only the first figure embeds Plotly.js.
    """

    return to_html(
        fig,
        full_html=False,
        include_plotlyjs=include_js,
        config={
            "responsive": True
        }
    )


# The first chart includes Plotly.js
html_raw = figure_to_html(
    fig_raw,
    include_js=True
)


# Other charts reuse the embedded Plotly.js
html_weighted = figure_to_html(
    fig_weighted
)


html_sunburst = figure_to_html(
    fig_sunburst
)


html_bar = figure_to_html(
    fig_bar
)


html_category_department = figure_to_html(
    fig_category_department
)


# ==================================================
# 10. Build dashboard
# ==================================================

dashboard_html = f"""
<!DOCTYPE html>

<html lang="zh-CN">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
Prince Hotel of Secret Garden Dashboard
</title>


<style>

body {{
    font-family: Arial, sans-serif;
    margin: 40px;
    background-color: #f5f5f5;
}}


h1 {{
    text-align: center;
    margin-bottom: 40px;
}}


.dashboard {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 20px;
}}


.chart {{
    background: white;
    padding: 20px;
    border-radius: 10px;
}}


.full-width {{
    grid-column: 1 / -1;
}}


/* Mobile layout */

@media (max-width: 900px) {{

    body {{
        margin: 15px;
    }}


    .dashboard {{
        grid-template-columns: 1fr;
    }}


    .full-width {{
        grid-column: auto;
    }}

}}

</style>

</head>


<body>


<h1>
Prince Hotel of Secret Garden
Complaint Analysis Dashboard
</h1>


<div class="dashboard">


    <!-- Issue-wise Pie -->

    <div class="chart">
        {html_raw}
    </div>


    <!-- Complaint-weighted Pie -->

    <div class="chart">
        {html_weighted}
    </div>


    <!-- Sunburst -->

    <div class="chart full-width">
        {html_sunburst}
    </div>


    <!-- Subcategory Bar -->

    <div class="chart">
        {html_bar}
    </div>


    <!-- Category × Department -->

    <div class="chart">
        {html_category_department}
    </div>


</div>


</body>

</html>
"""


# ==================================================
# 11. Export dashboard
# ==================================================

PATHS.ensure_report_dir()

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    f.write(dashboard_html)


print(
    f"\nDashboard saved to: {OUTPUT_FILE}"
)
