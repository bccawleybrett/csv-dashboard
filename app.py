import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="CSV Dashboard", layout="wide")

# --- Title ---
st.title("📊 Dynamic CSV Dashboard")

# --- Upload ---
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.success("✅ File loaded successfully!")

    # --- Data Preview ---
    st.subheader("Data Preview")
    st.dataframe(df)

    # --- Column Selection ---
    columns = df.columns.tolist()

    st.sidebar.header("⚙️ Controls")

    x_axis = st.sidebar.selectbox("Select X-axis", columns)
    y_axis = st.sidebar.selectbox("Select Y-axis", columns)

    chart_type = st.sidebar.selectbox(
        "Select Chart Type",
        ["Line", "Bar", "Scatter", "Histogram", "Box"]
    )

    # --- Chart Generation ---
    st.subheader("📈 Chart")

    if chart_type == "Line":
        fig = px.line(df, x=x_axis, y=y_axis)

    elif chart_type == "Bar":
        fig = px.bar(df, x=x_axis, y=y_axis)

    elif chart_type == "Scatter":
        fig = px.scatter(df, x=x_axis, y=y_axis)

    elif chart_type == "Histogram":
        fig = px.histogram(df, x=x_axis)

    elif chart_type == "Box":
        fig = px.box(df, x=x_axis, y=y_axis)

    st.plotly_chart(fig, use_container_width=True)

    # --- Filtering ---
    st.subheader("🔍 Filter Data")

    if st.checkbox("Enable filtering"):
        filter_col = st.selectbox("Column to filter", columns)
        unique_vals = df[filter_col].unique()
        selected_vals = st.multiselect("Select values", unique_vals, default=unique_vals)

        filtered_df = df[df[filter_col].isin(selected_vals)]
        st.dataframe(filtered_df)

else:
    st.info("👆 Upload a CSV file to get started")