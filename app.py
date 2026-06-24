import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(layout="wide")


# ======================================================
# EA 12-HOUR SPILL EVENT DETECTION FUNCTION
# ======================================================
def detect_spill_events(df, time_col, value_col, threshold, merge_hours=12):

    df = df.sort_values(time_col).copy()
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    # Flag threshold exceedance
    df["in_spill"] = df[value_col] > threshold

    events = []
    current_event = None

    for i in range(len(df)):
        row = df.iloc[i]

        if row["in_spill"]:
            if current_event is None:
                current_event = {
                    "start": row[time_col],
                    "end": row[time_col],
                }
            else:
                current_event["end"] = row[time_col]

        else:
            if current_event is not None:
                events.append(current_event)
                current_event = None

    if current_event:
        events.append(current_event)

    # -----------------------------
    # Merge events within 12 hours
    # -----------------------------
    merged = []

    for event in events:
        if not merged:
            merged.append(event)
        else:
            last = merged[-1]

            gap = (event["start"] - last["end"]).total_seconds() / 3600

            if gap <= merge_hours:
                last["end"] = event["end"]
            else:
                merged.append(event)

    # -----------------------------
    # Calculate duration
    # -----------------------------
    for e in merged:
        e["duration_hours"] = (
            e["end"] - e["start"]
        ).total_seconds() / 3600

    return pd.DataFrame(merged)


# ======================================================
# LOAD DATA
# ======================================================
uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])

if uploaded_file is None:
    st.title("📊 STW Dashboard")
    st.info("Upload a CSV to begin")
    st.stop()

df = pd.read_csv(uploaded_file)

# Auto parse datetime
for col in df.columns:
    try:
        df[col] = pd.to_datetime(df[col])
    except:
        pass

columns = df.columns.tolist()

# ======================================================
# NAVIGATION (HTML STYLE)
# ======================================================
st.sidebar.title("Navigation")

if "page" not in st.session_state:
    st.session_state.page = "Overview"

if st.sidebar.button("Overview"):
    st.session_state.page = "Overview"

if st.sidebar.button("Thresholds"):
    st.session_state.page = "Thresholds"

if st.sidebar.button("Data"):
    st.session_state.page = "Data"

if st.sidebar.button("Summary"):
    st.session_state.page = "Summary"


# ======================================================
# TOP HALF (HEADER + MAIN GRAPH)
# ======================================================
top1, top2 = st.columns([2, 1])

with top1:
    st.title("📊 Storm Tank Dashboard")

with top2:
    st.markdown(f"""
    **Rows:** {len(df)}  
    **Columns:** {len(df.columns)}
    """)

# Axis selection
col1, col2 = st.columns(2)
x_axis = col1.selectbox("Time / X-axis", columns)
y_axis = col2.selectbox("Level / Y-axis", columns)

# Threshold input
threshold = st.sidebar.number_input("Spill Threshold", value=0.0)

# Ensure types
df[x_axis] = pd.to_datetime(df[x_axis], errors="coerce")
df[y_axis] = pd.to_numeric(df[y_axis], errors="coerce")

# Main chart
st.markdown("### Main Time Series")

main_fig = go.Figure()

main_fig.add_trace(go.Scatter(
    x=df[x_axis],
    y=df[y_axis],
    mode="lines",
    name="Level"
))

main_fig.add_hline(
    y=threshold,
    line_dash="dash",
    line_color="red"
)

st.plotly_chart(main_fig, use_container_width=True)


# ======================================================
# BOTTOM HALF (LIKE YOUR HTML)
# ======================================================
st.markdown("---")

sidebar_col, content_col = st.columns([1, 5])

# LEFT NAV BUTTONS (visual only)
with sidebar_col:
    st.markdown("### Views")
    st.write("Use the sidebar buttons")


# ======================================================
# RIGHT CONTENT AREA
# ======================================================
with content_col:

    # -----------------------------
    # OVERVIEW
    # -----------------------------
    if st.session_state.page == "Overview":

        st.subheader("Overview")

        col1, col2, col3 = st.columns(3)
        col1.metric("Rows", len(df))
        col2.metric("Columns", len(df.columns))

        numeric_cols = df.select_dtypes(include="number").columns
        if len(numeric_cols) > 0:
            col3.metric("Avg", round(df[numeric_cols[0]].mean(), 2))

        st.dataframe(df)

    # -----------------------------
    # THRESHOLDS (EA LOGIC)
    # -----------------------------
    elif st.session_state.page == "Thresholds":

        st.subheader("🚨 EA Spill Event Detection (12 Hour Rule)")

        events_df = detect_spill_events(
            df,
            x_axis,
            y_axis,
            threshold
        )

        # PLOT WITH EVENTS
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df[x_axis],
            y=df[y_axis],
            mode="lines",
            name="Level"
        ))

        fig.add_hline(y=threshold, line_dash="dash", line_color="red")

        # Highlight events
        for _, e in events_df.iterrows():
            fig.add_vrect(
                x0=e["start"],
                x1=e["end"],
                fillcolor="red",
                opacity=0.2,
                line_width=0
            )

        st.plotly_chart(fig, use_container_width=True)

        # METRICS
        st.subheader("Event Summary")

        col1, col2 = st.columns(2)

        col1.metric("Spill Events", len(events_df))

        total_duration = (
            events_df["duration_hours"].sum()
            if not events_df.empty else 0
        )

        col2.metric("Total Duration (hrs)", round(total_duration, 2))

        # TABLE
        st.subheader("Detected Events")
        st.dataframe(events_df)

    # -----------------------------
    # DATA EXPLORER
    # -----------------------------
    elif st.session_state.page == "Data":

        st.subheader("Data Explorer")

        filter_col = st.selectbox("Filter column", columns)
        values = df[filter_col].dropna().unique()

        selected = st.multiselect("Values", values, default=values[:10])

        filtered = df[df[filter_col].isin(selected)]

        st.dataframe(filtered)

    # -----------------------------
    # SUMMARY TABLES
    # -----------------------------
    elif st.session_state.page == "Summary":

        st.subheader("Summary")

        st.markdown("### Statistics")
        st.dataframe(df.describe())

        st.markdown("### Missing Values")
        st.dataframe(df.isnull().sum())