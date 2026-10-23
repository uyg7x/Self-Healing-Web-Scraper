"""
SELF-HEALING SCRAPER - ENTERPRISE DASHBOARD
Run with: streamlit run dashboard.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DB_PATH

# Page Config
st.set_page_config(
    page_title="Scraper Intelligence", layout="wide", initial_sidebar_state="expanded"
)

# Custom CSS for clean look
st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    div[data-testid="stMetric"] {
        background-color: #f8f9fa; border: 1px solid #e1e4e8; border-radius: 8px; padding: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=10)
def load_data():
    if not Path(DB_PATH).exists():
        return pd.DataFrame()

    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()

    if df.empty:
        return df

    # Clean and prep data
    df["scrape_timestamp"] = pd.to_datetime(df["scrape_timestamp"], errors="coerce")

    # Safely convert price_inr string (e.g., "₹45,000") to float
    if "price_inr" in df.columns:
        df["price_numeric"] = (
            df["price_inr"]
            .astype(str)
            .str.replace("₹", "")
            .str.replace(",", "")
            .str.replace("N/A", "")
        )
        df["price_numeric"] = pd.to_numeric(df["price_numeric"], errors="coerce")
    else:
        df["price_numeric"] = None

    df["self_healed"] = (
        pd.to_numeric(df["self_healed"], errors="coerce").fillna(0).astype(int)
    )
    return df


# Header
st.title("🕷️ Self-Healing Scraper - Intelligence Dashboard")
st.caption("Real-time analytics from your hybrid fetching engine.")

df = load_data()

if df.empty:
    st.info("No data found. Run `python main.py` to scrape some products first!")
    st.stop()

# Sidebar Filters
st.sidebar.header("Filters")
all_sites = df["site_name"].dropna().unique().tolist()
selected_sites = st.sidebar.multiselect("Select Websites", all_sites, default=all_sites)

all_methods = df["scrape_method"].dropna().unique().tolist()
selected_methods = st.sidebar.multiselect(
    "Extraction Methods", all_methods, default=all_methods
)

# Apply Filters
filtered_df = df[
    (df["site_name"].isin(selected_sites))
    & (df["scrape_method"].isin(selected_methods))
]

if filtered_df.empty:
    st.warning("No data matches your filters.")
    st.stop()

# --- KPI METRICS ---
total_products = len(filtered_df)
healed_count = filtered_df["self_healed"].sum()
heal_rate = (healed_count / total_products) * 100 if total_products else 0
avg_price = filtered_df["price_numeric"].mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Products", f"{total_products:,}")
col2.metric("Active Websites", len(selected_sites))
col3.metric("Avg Price (INR)", f"₹{avg_price:,.0f}" if pd.notna(avg_price) else "N/A")
col4.metric("Self-Healing Rate", f"{heal_rate:.1f}%")

st.markdown("---")

# --- CHARTS ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Products by Website")
    site_counts = filtered_df["site_name"].value_counts().reset_index()
    site_counts.columns = ["Website", "Count"]
    fig_pie = px.pie(
        site_counts,
        names="Website",
        values="Count",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    st.subheader("Price Distribution")
    fig_box = px.box(
        filtered_df,
        x="site_name",
        y="price_numeric",
        color="site_name",
        labels={"site_name": "Website", "price_numeric": "Price (INR)"},
    )
    fig_box.update_layout(showlegend=False)
    st.plotly_chart(fig_box, use_container_width=True)

# --- DATA TABLE ---
st.subheader("Live Data Feed")
display_df = filtered_df[
    ["scrape_timestamp", "site_name", "product_name", "price_inr", "scrape_method"]
].copy()
display_df.columns = [
    "Timestamp",
    "Website",
    "Product Name",
    "Price (INR)",
    "Extraction Method",
]
st.dataframe(
    display_df.sort_values("Timestamp", ascending=False),
    use_container_width=True,
    hide_index=True,
)

# --- EXPORT ---
st.markdown("---")
csv = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download Filtered Data as CSV",
    data=csv,
    file_name="scraper_export.csv",
    mime="text/csv",
)
