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
# LOAD DATA
# ======================================================
st.sidebar.title("Upload Data")

telemetry_file = st.sidebar.file_uploader("Telemetry CSV", type=["csv"])
model_file = st.sidebar.file_uploader("Model CSV", type=["csv"])

if telemetry_file is None or model_file is None:
    st.title("📊 Dashboard")
    st.info("Upload BOTH telemetry and model CSV files")
    st.stop()

telemetry = pd.read_csv(telemetry_file)
model = pd.read_csv(model_file)


# ======================================================
# FORCE COLUMN STRUCTURE (A & B)
# ======================================================
try:
    time_col = telemetry.columns[0]
    telemetry_col = telemetry.columns[1]
    model_col = model.columns[1]
except:
    st.error("❌ CSV must have at least 2 columns (A = time, B = value)")
    st.stop()


# ======================================================
# CLEAN DATA
# ======================================================
def clean_data(df, time_col, value_col):
    df[value_col] = (
        df[value_col]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False)
    )

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

    return df


telemetry = clean_data(telemetry, time_col, telemetry_col)
model = clean_data(model, time_col, model_col)


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
# CONTROLS
# ======================================================
threshold = st.sidebar.number_input("Spill Threshold (%)", value=100.0)

st.title("📊 Dashboard")


# ======================================================
# MAIN CHART
# ======================================================
st.markdown("### Telemetry vs Model")

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=telemetry[time_col],
    y=telemetry[telemetry_col],
    name="Telemetry",
    line=dict(color="blue")
))

fig.add_trace(go.Scatter(
    x=telemetry[time_col],
    y=model[model_col],
    name="Model",
    line=dict(color="orange")
))

fig.add_hline(y=threshold, line_dash="dash", line_color="red")

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ======================================================
# PAGES
# ======================================================
page = st.session_state.page


# -----------------------------
# OVERVIEW
# -----------------------------
if page == "Overview":

    st.subheader("Overview")

    col1, col2 = st.columns(2)

    col1.metric("Telemetry Rows", len(telemetry))
    col2.metric("Model Rows", len(model))


# -----------------------------
# COMPARISON
# -----------------------------
elif page == "Comparison":

    st.subheader("Error Analysis")

    merged = pd.merge(
        telemetry[[time_col, telemetry_col]],
        model[[time_col, model_col]],
        on=time_col,
        how="inner"
    )

    merged["error"] = merged[telemetry_col] - merged[model_col]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged[time_col],
        y=merged["error"],
        name="Error"
    ))

    st.plotly_chart(fig, use_container_width=True)

    st.metric("Mean Error", round(merged["error"].mean(), 2))


# -----------------------------
# SPILL EVENTS + ANNUAL
# -----------------------------
elif page == "Spill Events":

    st.subheader("🚨 Spill Event Analysis (EA 12-hour rule)")

    events_t = detect_spill_events(
        telemetry, time_col, telemetry_col, threshold
    )

    model_temp = model.rename(columns={model_col: telemetry_col})

    events_m = detect_spill_events(
        model_temp, time_col, telemetry_col, threshold
    )

    # Add year
    if not events_t.empty:
        events_t["year"] = events_t["start"].dt.year
    if not events_m.empty:
        events_m["year"] = events_m["start"].dt.year

    annual_t = events_t.groupby("year").agg(
        events=("start", "count"),
        duration=("duration_hours", "sum")
    ).reset_index()

    annual_m = events_m.groupby("year").agg(
        events=("start", "count"),
        duration=("duration_hours", "sum")
    ).reset_index()

    annual = pd.merge(
        annual_t, annual_m,
        on="year",
        how="outer",
        suffixes=("_telemetry", "_model")
    ).fillna(0)

    st.markdown("### Annual Summary")
    st.dataframe(annual)

    # Event comparison
    fig = go.Figure()
    fig.add_trace(go.Bar(x=annual["year"], y=annual["events_telemetry"], name="Telemetry"))
    fig.add_trace(go.Bar(x=annual["year"], y=annual["events_model"], name="Model"))
    st.plotly_chart(fig, use_container_width=True)

    # Duration comparison
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=annual["year"], y=annual["duration_telemetry"], name="Telemetry Duration"))
    fig2.add_trace(go.Bar(x=annual["year"], y=annual["duration_model"], name="Model Duration"))
    st.plotly_chart(fig2, use_container_width=True)


# -----------------------------
# DATA
# -----------------------------
elif page == "Data":

    st.subheader("Raw Data")

    st.markdown("### Telemetry")
    st.dataframe(telemetry)

    st.markdown("### Model")
    st.dataframe(model)
