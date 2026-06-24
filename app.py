import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# -----------------------------
# Upload CSV
# -----------------------------
uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])

if uploaded_file is None:
    st.title("📊 Dashboard")
    st.info("Upload a CSV to begin")
    st.stop()

df = pd.read_csv(uploaded_file)

# Try auto datetime
for col in df.columns:
    try:
        df[col] = pd.to_datetime(df[col])
    except:
        pass

columns = df.columns.tolist()

# -----------------------------
# Sidebar navigation (like buttons)
# -----------------------------
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "",
    ["Overview", "Thresholds", "Data", "Summary"]
)

# -----------------------------
# TOP HALF (Header + Main Chart)
# -----------------------------
top_col1, top_col2 = st.columns([2, 1])

with top_col1:
    st.title("📊 CSV Dashboard (HTML-style)")

with top_col2:
    st.markdown(f"""
    **Rows:** {len(df)}  
    **Columns:** {len(df.columns)}
    """)

# Main chart selection
st.markdown("### Main Chart")

col1, col2 = st.columns(2)

x_axis = col1.selectbox("X-axis", columns, key="main_x")
y_axis = col2.selectbox("Y-axis", columns, key="main_y")

fig_main = go.Figure()

fig_main.add_trace(go.Scatter(
    x=df[x_axis],
    y=df[y_axis],
    mode='lines',
    name="Main Series"
))

# Optional thresholds
upper = st.sidebar.number_input("Upper Threshold", value=0.0)
lower = st.sidebar.number_input("Lower Threshold", value=0.0)

fig_main.add_hline(y=upper, line_dash="dash", line_color="red")
fig_main.add_hline(y=lower, line_dash="dash", line_color="blue")

st.plotly_chart(fig_main, use_container_width=True)

# -----------------------------
# BOTTOM HALF (Sidebar + Content)
# -----------------------------
st.markdown("---")

sidebar_col, content_col = st.columns([1, 5])

# LEFT (Buttons like your HTML)
with sidebar_col:
    st.markdown("### Views")

    if st.button("Overview"):
        st.session_state.page = "Overview"

    if st.button("Thresholds"):
        st.session_state.page = "Thresholds"

    if st.button("Data"):
        st.session_state.page = "Data"

    if st.button("Summary"):
        st.session_state.page = "Summary"

# Set default page
if "page" not in st.session_state:
    st.session_state.page = page

# RIGHT (Content area like your panels)
with content_col:

    # -------------------------
    # OVERVIEW PAGE
    # -------------------------
    if st.session_state.page == "Overview":
        st.subheader("Overview")

        col1, col2, col3 = st.columns(3)

        col1.metric("Rows", len(df))
        col2.metric("Columns", len(df.columns))

        numeric_cols = df.select_dtypes(include="number").columns
        if len(numeric_cols) > 0:
            col3.metric("Avg", round(df[numeric_cols[0]].mean(), 2))

        st.dataframe(df)

    # -------------------------
    # THRESHOLDS PAGE
    # -------------------------
    elif st.session_state.page == "Thresholds":
        st.subheader("Threshold Analysis")

        y_data = pd.to_numeric(df[y_axis], errors="coerce")

        breaches = df[(y_data > upper) | (y_data < lower)]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df[x_axis],
            y=y_data,
            mode='lines',
            name="Value"
        ))

        fig.add_trace(go.Scatter(
            x=breaches[x_axis],
            y=breaches[y_axis],
            mode='markers',
            marker=dict(color="red", size=8),
            name="Breaches"
        ))

        fig.add_hline(y=upper, line_dash="dash", line_color="red")
        fig.add_hline(y=lower, line_dash="dash", line_color="blue")

        st.plotly_chart(fig, use_container_width=True)

        st.metric("Total Breaches", len(breaches))

        st.dataframe(breaches)

    # -------------------------
    # DATA PAGE
    # -------------------------
    elif st.session_state.page == "Data":
        st.subheader("Data Explorer")

        filter_col = st.selectbox("Filter column", columns)

        vals = df[filter_col].dropna().unique()

        selected = st.multiselect("Values", vals, default=vals[:10])

        filtered = df[df[filter_col].isin(selected)]

        st.dataframe(filtered)

    # -------------------------
    # SUMMARY PAGE
    # -------------------------
    elif st.session_state.page == "Summary":
        st.subheader("Summary Tables")

        st.markdown("### Numeric Summary")

        st.dataframe(df.describe())

        st.markdown("### Nulls")

        st.dataframe(df.isnull().sum())