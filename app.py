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
# FILE UPLOAD (TWO SOURCES)
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


# Auto parse datetime
def parse_dates(df):
    for col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col])
        except:
            pass
    return df


telemetry = parse_dates(telemetry)
model = parse_dates(model)

columns_t = telemetry.columns.tolist()
columns_m = model.columns.tolist()


# ======================================================
# NAVIGATION
# ======================================================
st.sidebar.title("Navigation")

if "page" not in st.session_state:
    st.session_state.page = "Overview"

if st.sidebar.button("Overview"):
    st.session_state.page = "Overview"

if st.sidebar.button("Comparison"):
    st.session_state.page = "Comparison"

if st.sidebar.button("Spill Events"):
    st.session_state.page = "Spill Events"

if st.sidebar.button("Data"):
    st.session_state.page = "Data"


# ======================================================
# TOP PANEL (MAIN CHART)
# ======================================================
st.title("📊 Storm Tank Dashboard (Telemetry vs Model)")

col1, col2 = st.columns(2)

time_col = col1.selectbox("Time column (Telemetry)", columns_t)
telemetry_col = col2.selectbox("Telemetry Level", columns_t)

model_col = st.sidebar.selectbox("Model Level Column", columns_m)

threshold = st.sidebar.number_input(
    "Spill Threshold (%)",
    value=100.0
)

# Ensure types
telemetry[time_col] = pd.to_datetime(telemetry[time_col], errors="coerce")
telemetry[telemetry_col] = pd.to_numeric(telemetry[telemetry_col], errors="coerce")

model[telemetry_col] = pd.to_numeric(model[model_col], errors="coerce")

# ======================================================
# MAIN CHART (OVERLAY)
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
# PAGE CONTENT
# ======================================================
if st.session_state.page == "Overview":

    st.subheader("Overview")

    col1, col2 = st.columns(2)

    col1.metric("Telemetry Rows", len(telemetry))
    col2.metric("Model Rows", len(model))


# ======================================================
# COMPARISON PAGE
# ======================================================
elif st.session_state.page == "Comparison":

    st.subheader("Performance Comparison")

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
        name="Error (Telemetry - Model)"
    ))

    st.plotly_chart(fig, use_container_width=True)

    st.metric("Mean Error", round(merged["error"].mean(), 2))


# ======================================================
# SPILL EVENTS PAGE
# ======================================================
elif st.session_state.page == "Spill Events":

    st.subheader("🚨 EA Spill Event Comparison")

    events_telemetry = detect_spill_events(
        telemetry,
        time_col,
        telemetry_col,
        threshold
    )

    events_model = detect_spill_events(
        model.rename(columns={model_col: telemetry_col}),
        time_col,
        telemetry_col,
        threshold
    )

    col1, col2 = st.columns(2)

    col1.metric("Telemetry Events", len(events_telemetry))
    col2.metric("Model Events", len(events_model))

    st.markdown("### Telemetry Events")
    st.dataframe(events_telemetry)

    st.markdown("### Model Events")
    st.dataframe(events_model)


# ======================================================
# DATA PAGE
# ======================================================
elif st.session_state.page == "Data":

    st.subheader("Raw Data")

    st.markdown("### Telemetry")
    st.dataframe(telemetry)

    st.markdown("### Model")
    st.dataframe(model)
