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
# ROBUST AUTO DETECTION (FIXED)
# ======================================================
def detect_time_column(df):
    for col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], errors="raise")
            if parsed.notna().mean() > 0.8:
                df[col] = parsed
                return col
        except:
            continue
    return None


def detect_level_column(df):
    best_col = None
    best_score = -1

    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        score = converted.notna().mean()

        if score > best_score:
            best_score = score
            best_col = col

    if best_score < 0.5:
        return None

    df[best_col] = pd.to_numeric(df[best_col], errors="coerce")
    return best_col


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
# CLEAN & PARSE
# ======================================================
def clean_numeric(df):
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace("%", "", regex=False)
        df[col] = df[col].str.replace(",", "", regex=False)
    return df


telemetry = clean_numeric(telemetry)
model = clean_numeric(model)


# ======================================================
# AUTO DETECT
# ======================================================
time_col = detect_time_column(telemetry)
telemetry_col = detect_level_column(telemetry)
model_col = detect_level_column(model)


# ======================================================
# SAFE FALLBACK (NO CRASH)
# ======================================================
if time_col is None:
    st.warning("⚠️ Could not auto-detect time column")
    time_col = st.selectbox("Select Time Column", telemetry.columns)

if telemetry_col is None:
    st.warning("⚠️ Could not detect telemetry column")
    telemetry_col = st.selectbox("Select Telemetry Column", telemetry.columns)

if model_col is None:
    st.warning("⚠️ Could not detect model column")
    model_col = st.selectbox("Select Model Column", model.columns)


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
# MAIN CONTROLS
# ======================================================
st.title("📊 Storm Tank Dashboard")

threshold = st.sidebar.number_input("Spill Threshold (%)", value=100.0)

# Ensure types
telemetry[time_col] = pd.to_datetime(telemetry[time_col], errors="coerce")
telemetry[telemetry_col] = pd.to_numeric(telemetry[telemetry_col], errors="coerce")
model[model_col] = pd.to_numeric(model[model_col], errors="coerce")


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
# SPILL EVENTS + ANNUAL REPORT
# -----------------------------
elif page == "Spill Events":

    st.subheader("🚨 Spill Event Analysis")

    events_t = detect_spill_events(
        telemetry, time_col, telemetry_col, threshold
    )

    model_temp = model.rename(columns={model_col: telemetry_col})

    events_m = detect_spill_events(
        model_temp, time_col, telemetry_col, threshold
    )

    # ✅ Annual aggregation
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
        annual_t,
        annual_m,
        on="year",
        how="outer",
        suffixes=("_telemetry", "_model")
    ).fillna(0)

    st.markdown("### Annual Summary")
    st.dataframe(annual)

    # Event count chart
    fig = go.Figure()
    fig.add_trace(go.Bar(x=annual["year"], y=annual["events_telemetry"], name="Telemetry"))
    fig.add_trace(go.Bar(x=annual["year"], y=annual["events_model"], name="Model"))
    st.plotly_chart(fig, use_container_width=True)

    # Duration chart
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
