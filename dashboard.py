"""
Self-Healing Web Scraper - Analytics Dashboard
Professional, emoji-free Streamlit dashboard.
Reads from the SQLite database written by the scraper.
Run with:  streamlit run dashboard.py
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DB_PATH, SELECTOR_HISTORY_PATH

# ------------------------------------------------------------------
# Page setup (no emoji icon, wide layout)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Self-Healing Scraper Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Clean, professional styling
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e1e4e8;
        border-radius: 8px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] .css-1l5t867,
    div[data-testid="stMetric"] .css-1l5t867 p,
    div[data-testid="stMetric"] .css-1l5t867 strong,
    div[data-testid="stMetric"] [data-testid="stMetricValue"],
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: #212529 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

METHOD_LABELS = {
    "json_ld": "JSON-LD",
    "css_selector": "CSS Selector",
    "regex": "Regex Fallback",
    "self_healing": "Fuzzy Self-Heal",
    "llm": "LLM (Gemini)",
}

METHOD_COLORS = {
    "JSON-LD": "#2e7d32",
    "CSS Selector": "#1565c0",
    "Regex Fallback": "#ef6c00",
    "Fuzzy Self-Heal": "#8e24aa",
    "LLM (Gemini)": "#c62828",
    "Unknown": "#757575",
}


# ------------------------------------------------------------------
# Data loading (cached, auto-expires every 30 seconds)
# ------------------------------------------------------------------
@st.cache_data(ttl=30)
def load_products() -> pd.DataFrame:
    if not Path(DB_PATH).exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    if df.empty:
        return df
    df["scrape_timestamp"] = pd.to_datetime(df["scrape_timestamp"], errors="coerce")
    df["method_label"] = df["scrape_method"].map(METHOD_LABELS).fillna("Unknown")
    df["price_value"] = pd.to_numeric(df["price_float"], errors="coerce")
    df["scrape_date"] = df["scrape_timestamp"].dt.date

    # Normalize image URLs — convert "N/A" to None (handle missing column gracefully)
    if "image_url" in df.columns:
        df["image_url"] = df["image_url"].where(df["image_url"].str.lower() != "n/a", None)
    else:
        df["image_url"] = None

    # Classify products into categories based on product name keywords
    def classify_product(name):
        if name is None:
            return "Other"
        name_lower = str(name).lower()
        # Laptop keywords
        laptop_keywords = ["laptop", "notebook", "vivobook", "rog", "asus", "acer", "hp pavilion",
                           "hp 15", "inspiron", "galaxy book", "asus tuf", "hp victus"]
        # Arduino keywords
        arduino_keywords = ["arduino", "uno r3", "controller board", "micro controller", "sensor module",
                            "mega 2560", "raspberry pi", "iot", "electronic hobby", "electronic components"]
        for kw in arduino_keywords:
            if kw in name_lower:
                return "Arduino Uno"
        for kw in laptop_keywords:
            if kw in name_lower:
                return "Laptop"
        return "Other"

    df["category"] = df["product_name"].apply(classify_product)
    return df


@st.cache_data(ttl=30)
def load_history() -> dict:
    path = Path(SELECTOR_HISTORY_PATH)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def inr(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"Rs {value:,.0f}"


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------
st.title("Self-Healing Web Scraper - Analytics")
st.caption("Extraction performance, price intelligence and self-healing telemetry")

df = load_products()

if df.empty:
    st.info("No data found yet. Run the scraper first: python main.py")
    st.stop()

# ------------------------------------------------------------------
# Sidebar filters
# ------------------------------------------------------------------
st.sidebar.header("Filters")

search = st.sidebar.text_input("Search product name", "")

all_sites = sorted(df["site_name"].dropna().unique().tolist())
sel_sites = st.sidebar.multiselect("Websites", all_sites, default=all_sites)

all_methods = sorted(df["method_label"].unique().tolist())
sel_methods = st.sidebar.multiselect("Extraction methods", all_methods, default=all_methods)

dates = df["scrape_date"].dropna()
date_range = None
if len(dates):
    d_min, d_max = dates.min(), dates.max()
    date_range = st.sidebar.date_input(
        "Date range", value=(d_min, d_max), min_value=d_min, max_value=d_max
    )

only_healed = st.sidebar.checkbox("Show only self-healed extractions", False)

if st.sidebar.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("About the strategy cascade"):
    st.write(
        """
        The engine tries strategies in order and stops at the first success:
        1. JSON-LD structured data
        2. CSS selectors (prioritized by learned history)
        3. Regex fallback
        4. Fuzzy self-healing
        5. LLM (Gemini) as last resort

        "Self-healed" rows are extractions that required a fallback
        strategy instead of the primary selector path.
        """
    )

# ------------------------------------------------------------------
# Apply filters
# ------------------------------------------------------------------
filtered = df.copy()
if search:
    filtered = filtered[filtered["product_name"].str.contains(search, case=False, na=False)]
filtered = filtered[filtered["site_name"].isin(sel_sites)]
filtered = filtered[filtered["method_label"].isin(sel_methods)]
if only_healed:
    filtered = filtered[filtered["self_healed"] == 1]
if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    filtered = filtered[
        (filtered["scrape_date"] >= date_range[0]) & (filtered["scrape_date"] <= date_range[1])
    ]

if filtered.empty:
    st.warning("No rows match the current filters.")
    st.stop()

# ------------------------------------------------------------------
# Product Category Selector with Graphs
# ------------------------------------------------------------------
st.subheader("Product Category Comparison")

available_categories = filtered["category"].unique()
available_categories = [c for c in available_categories if c != "Other"]

selected_categories = st.multiselect(
    "Select product categories to compare",
    options=available_categories,
    default=available_categories if len(available_categories) <= 2 else [],
)
if len(selected_categories) >= 1:
    cat_data = filtered[filtered["category"].isin(selected_categories)].copy()

    if not cat_data.empty and len(selected_categories) > 1:
        tab_labels = [f"{cat} ({len(cat_data[cat_data['category'] == cat])} items)" for cat in selected_categories]
        tabs = st.tabs(tab_labels)
        for (cat, tab) in zip(selected_categories, tabs):
            cat_df = cat_data[cat_data["category"] == cat]
            with tab:
                st.markdown(f"### {cat}")
                cat_prices = cat_df["price_value"].dropna()
                if len(cat_prices):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("Total Items", f"{len(cat_df):,}")
                    c2.metric("Lowest Price", inr(cat_prices.min()))
                    c3.metric("Highest Price", inr(cat_prices.max()))
                    c4.metric("Avg Price", inr(cat_prices.mean()))
                    c5.metric("Median Price", inr(cat_prices.median()))
                if len(cat_prices) > 1:
                    st.plotly_chart(
                        px.histogram(cat_prices, nbins=min(20, len(cat_prices) // 3),
                                     title="Price Distribution",
                                     labels={"value": "Price (INR)", "count": "Number of Products"},
                                     color_discrete_sequence=["#1f77b4"] if cat == "Laptop" else ["#d62728"]),
                        use_container_width=True, key=f"hist_{cat}")
                top_products = (cat_df[["product_name", "price_value"]].dropna()
                                .sort_values("price_value", ascending=True).tail(15))
                if len(top_products):
                    fig = px.bar(top_products, x="price_value", y="product_name", orientation="h",
                                 title="Product Prices", labels={"price_value": "Price (INR)", "product_name": "Product"},
                                 color="price_value", color_continuous_scale="Viridis")
                    fig.update_layout(height=max(400, len(top_products) * 25), yaxis={"categoryorder": "total ascending"})
                    st.plotly_chart(fig, use_container_width=True, key=f"bar_{cat}")
        st.markdown("---")
        st.subheader("Category Comparison Overview")
        comparison_data = (cat_data.groupby("category")
                           .agg(product_count=("product_name", "count"),
                                avg_price=("price_value", "mean"),
                                median_price=("price_value", "median"),
                                min_price=("price_value", "min"),
                                max_price=("price_value", "max"))
                           .reset_index())
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Product Count by Category")
            st.plotly_chart(px.pie(comparison_data, values="product_count", names="category",
                                   title="Number of Products per Category",
                                   color_discrete_sequence=["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e"]),
                            use_container_width=True, key="pie_count")
        with col2:
            st.markdown("#### Average Price by Category")
            fig_avg = px.bar(comparison_data, x="category", y="avg_price",
                             title="Average Price per Category",
                             labels={"category": "Category", "avg_price": "Average Price (INR)"},
                             color="category", color_discrete_sequence=["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e"])
            fig_avg.update_layout(showlegend=False)
            st.plotly_chart(fig_avg, use_container_width=True, key="bar_avg")
            st.markdown("#### Price Range Comparison")
            fig_range = px.bar(comparison_data, x="category", y=["min_price", "median_price", "avg_price", "max_price"],
                               title="Price Range per Category (Min - Max)",
                               labels={"value": "Price (INR)", "variable": "Statistic"})
            fig_range.update_layout(barmode="group")
            st.plotly_chart(fig_range, use_container_width=True, key="bar_range")
    elif not cat_data.empty:
        cat = selected_categories[0]
        cat_df = cat_data[cat_data["category"] == cat]
        st.markdown(f"### {cat} ({len(cat_df)} products)")
        cat_prices = cat_df["price_value"].dropna()
        if len(cat_prices):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total Items", f"{len(cat_df):,}")
            c2.metric("Lowest Price", inr(cat_prices.min()))
            c3.metric("Highest Price", inr(cat_prices.max()))
            c4.metric("Avg Price", inr(cat_prices.mean()))
            c5.metric("Median Price", inr(cat_prices.median()))
        if len(cat_prices) > 1:
            st.plotly_chart(px.histogram(cat_prices, nbins=min(20, len(cat_prices) // 3),
                             title="Price Distribution",
                             labels={"value": "Price (INR)", "count": "Number of Products"}),
                            use_container_width=True, key=f"hist_{cat}_single")
        top_products = (cat_df[["product_name", "price_value"]].dropna()
                        .sort_values("price_value", ascending=True).tail(15))
        if len(top_products):
            fig = px.bar(top_products, x="price_value", y="product_name", orientation="h",
                         title="Product Prices (Top 15 by Price)",
                         labels={"price_value": "Price (INR)", "product_name": "Product"},
                         color="price_value", color_continuous_scale="Viridis")
            fig.update_layout(height=max(400, len(top_products) * 25), yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True, key=f"bar_{cat}_single")


healed = int(filtered["self_healed"].sum())
heal_rate = (healed / len(filtered)) * 100 if len(filtered) else 0.0

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total products", f"{len(filtered):,}")
k2.metric("Websites", int(filtered["site_name"].nunique()))
_prices = filtered["price_value"].dropna()
k3.metric("Minimum price", inr(_prices.min()) if len(_prices) else "-")
k4.metric("Maximum price", inr(_prices.max()) if len(_prices) else "-")
k5.metric("Average price", inr(_prices.mean()) if len(_prices) else "-")
k6.metric("Self-heal rate", f"{heal_rate:.1f}%")

st.markdown("---")

# ------------------------------------------------------------------
# SECTION 1: LIVE EXACT PRICES (No Averages)
# ------------------------------------------------------------------
st.subheader("Live Exact Prices (Individual Products)")
st.caption("Every single product extracted with its exact real-time price. No averages.")

# Sort by most recent first to act like a live feed
live_feed = filtered.sort_values("scrape_timestamp", ascending=False).copy()

st.dataframe(
    live_feed[[
        "scrape_timestamp", "site_name", "product_name", "price_inr", "method_label"
    ]].rename(columns={
        "scrape_timestamp": "Checked At",
        "site_name": "Website",
        "product_name": "Product Name",
        "price_inr": "Exact Price",
        "method_label": "Extracted Via",
    }),
    use_container_width=True,
    hide_index=True,
    height=400,
)

# ------------------------------------------------------------------
# SECTION 2: REAL-TIME PRICE HISTORY MONITOR
# ------------------------------------------------------------------
st.markdown("---")
st.subheader("Real-Time Price History Monitor")
st.caption("Track how the exact price of a specific product changes over time across different websites.")

# Get unique products for the dropdown
unique_products = sorted(filtered["product_name"].dropna().unique().tolist())

if unique_products:
    selected_product = st.selectbox("Select a product to monitor:", unique_products)
    
    # Filter data for the selected product
    product_history = filtered[filtered["product_name"] == selected_product].copy()
    product_history = product_history.sort_values("scrape_timestamp")
    
    if not product_history.empty:
        # Create a line chart showing price over time for each website
        fig_hist = px.line(
            product_history, 
            x="scrape_timestamp", 
            y="price_value", 
            color="site_name",
            markers=True,
            labels={
                "scrape_timestamp": "Date & Time",
                "price_value": "Exact Price (INR)",
                "site_name": "Website"
            },
            title=f"Price Trend for: {selected_product}"
        )
        fig_hist.update_layout(height=400)
        st.plotly_chart(fig_hist, use_container_width=True)
        
        # Show a detailed table of the history for this product
        st.dataframe(
            product_history[["scrape_timestamp", "site_name", "price_inr", "method_label"]].rename(columns={
                "scrape_timestamp": "Checked At",
                "site_name": "Website",
                "price_inr": "Exact Price",
                "method_label": "Extracted Via"
            }),
            use_container_width=True,
            hide_index=True,
            height=250
        )
    else:
        st.info("No history data available for this product yet.")
else:
    st.info("No products available to monitor yet. Run the scraper first.")

# ------------------------------------------------------------------
# SECTION 3: RAW DATA EXPORT
# ------------------------------------------------------------------
st.markdown("---")
st.subheader("Export Data")

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download Filtered Data as CSV",
    data=csv_bytes,
    file_name="scraper_exact_prices.csv",
    mime="text/csv",
)
