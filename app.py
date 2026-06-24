import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(layout="wide")


# ======================================================
# EA SPILL EVENT DETECTION (12-HOUR RULE)
# ======================================================
def detect_spill_events(df, time_col, value_col, threshold, merge_hours=12):

    df = df.sort_values(time_col).copy()
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    df["in_spill"] = df[value_col] >= threshold

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
            if current_event:
                events.append(current_event)
                current_event = None

    if current_event:
        events.append(current_event)

    # Merge events within 12 hours
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

    # Add duration
    for e in merged:
        e["duration_hours"] = (
            e["end"] - e["start"]
        ).total_seconds() / 3600

    return pd.DataFrame(merged)


# ======================================================
# SMART COLUMN DETECTION
# ======================================================
def detect_time_column(df):
    dt_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
    if dt_cols:
        return dt_cols[0]

    for col in df.columns:
        if "time" in col.lower() or "date" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col])
                return col
            except:
                pass
    return None


def detect_level_column(df):
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    keywords = ["level", "tank", "%", "percent", "depth"]

    for col in numeric_cols:
        if any(k in col.lower() for k in keywords):
            return col

    return numeric_cols[0] if numeric_cols else None


# ======================================================
# LOAD DATA
# ======================================================
st.sidebar.title("Data Upload")

telemetry_file = st.sidebar.file_uploader("Upload Telemetry CSV", type=["csv"])
model_file = st.sidebar.file_uploader("Upload Model CSV", type=["csv"])

if telemetry_file is None or model_file is None:
    st.title("📊 STW Comparison Dashboard")
    st.info("Upload BOTH telemetry and model CSV files")
    st.stop()

telemetry = pd.read_csv(telemetry_file)
model = pd.read_csv(model_file)


# ======================================================
# PARSE DATES
# ======================================================
def parse_dates(df):
    for col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col])
        except:
            pass
    return df

telemetry = parse_dates(telemetry)
model = parse_dates(model)


# ======================================================
# AUTO SELECT COLUMNS
# ======================================================
time_col = detect_time_column(telemetry)
telemetry_col = detect_level_column(telemetry)
model_col = detect_level_column(model)

if time_col is None or telemetry_col is None or model_col is None:
    st.error("❌ Could not auto-detect required columns")
    st.stop()


# ======================================================
# NAVIGATION
# ======================================================
st.sidebar.title("Navigation")

if "page" not in st.session_state:
    st.session_state.page = "Overview"

for p in ["Overview", "Comparison", "Spill Events", "Data"]:
    if st.sidebar.button(p):
        st.session_state.page = p


# ======================================================
# USER CONTROL (WITH DEFAULTS)
# ======================================================
st.title("📊 Storm Tank Dashboard")

col1, col2 = st.columns(2)

time_col = col1.selectbox(
    "Time column", telemetry.columns,
    index=telemetry.columns.get_loc(time_col)
)

telemetry_col = col2.selectbox(
    "Telemetry Level",
    telemetry.select_dtypes(include="number").columns,
    index=telemetry.select_dtypes(include="number").columns.get_loc(telemetry_col)
)

model_col = st.sidebar.selectbox(
    "Model Level",
    model.select_dtypes(include="number").columns,
    index=model.select_dtypes(include="number").columns.get_loc(model_col)
)

threshold = st.sidebar.number_input("Spill Threshold (%)", value=100.0)

# Ensure types
telemetry[time_col] = pd.to_datetime(telemetry[time_col], errors="coerce")
telemetry[telemetry_col] = pd.to_numeric(telemetry[telemetry_col], errors="coerce")
model[model_col] = pd.to_numeric(model[model_col], errors="coerce")


# ======================================================
# MAIN CHART
# ======================================================
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=telemetry[time_col],
    y=telemetry[telemetry_col],
    name="Telemetry"
))

fig.add_trace(go.Scatter(
    x=telemetry[time_col],
    y=model[model_col],
    name="Model"
))

fig.add_hline(y=threshold, line_dash="dash", line_color="red")

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ======================================================
# SPILL EVENTS PAGE (UPDATED)
# ======================================================
if st.session_state.page == "Spill Events":

    st.subheader("🚨 Spill Event Comparison (EA 12-hour rule)")

    events_t = detect_spill_events(telemetry, time_col, telemetry_col, threshold)
    events_m = detect_spill_events(
        model.rename(columns={model_col: telemetry_col}),
        time_col,
        telemetry_col,
        threshold
    )

    # Add year
    if not events_t.empty:
        events_t["year"] = events_t["start"].dt.year

    if not events_m.empty:
        events_m["year"] = events_m["start"].dt.year

    # Annual aggregation
    annual_t = events_t.groupby("year").agg(
        events=("start", "count"),
        duration_hours=("duration_hours", "sum")
    ).reset_index()

    annual_m = events_m.groupby("year").agg(
        events=("start", "count"),
        duration_hours=("duration_hours", "sum")
    ).reset_index()

    # Merge for comparison
    annual = pd.merge(
        annual_t, annual_m,
        on="year",
        how="outer",
        suffixes=("_telemetry", "_model")
    ).fillna(0)

    # =====================
    # DISPLAY
    # =====================
    st.markdown("### Annual Comparison")

    st.dataframe(annual)

    # Plot comparison
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=annual["year"],
        y=annual["events_telemetry"],
        name="Telemetry Events"
    ))

    fig.add_trace(go.Bar(
        x=annual["year"],
        y=annual["events_model"],
        name="Model Events"
    ))

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Duration Comparison (Hours)")

    fig2 = go.Figure()

    fig2.add_trace(go.Bar(
        x=annual["year"],
        y=annual["duration_hours_telemetry"],
        name="Telemetry Duration"
    ))

    fig2.add_trace(go.Bar(
        x=annual["year"],
        y=annual["duration_hours_model"],
        name="Model Duration"
    ))

    st.plotly_chart(fig2, use_container_width=True)