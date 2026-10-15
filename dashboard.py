# dashboard.py
# Step 4 of the NSW ED Pressure Forecaster: an interactive dashboard.
# Pick any hospital, health district or all of NSW, and see its trend and a 4-quarter forecast.
# Run it with:  python -m streamlit run dashboard.py

import warnings
import altair as alt
import pandas as pd
import streamlit as st
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")
st.set_page_config(page_title="NSW ED Pressure Forecaster", page_icon="🏥", layout="wide")

BLUE, ORANGE = "#2a78d6", "#eb6834"

# The measures people can pick. "better" tells us if higher numbers are good or bad.
MEASURES = {
    "Patients treated on time (%)": ("Percentage of patients starting treatment on time", "%", "higher"),
    "Emergency presentations": ("Emergency presentations", "patients", "neutral"),
    "Ambulance handover within 30 min (%)": ("Percentage of patients transferred from paramedics to ED staff within 30 minutes", "%", "higher"),
    "Median ambulance handover time (minutes)": ("Median time to transfer care from paramedics to ED staff", "min", "lower"),
    "Median time in ED (minutes) - ended 2024": ("Median time from arrival at ED to leaving", "min", "lower"),
    "Left ED within 4 hours (%) - ended 2024": ("Percentage of patients leaving ED within four hours", "%", "higher"),
}


# ---------- Data (loaded once, then remembered) ----------
@st.cache_data
def load():
    cols = ["reporting_level", "entity_shortname", "lhd_shortname", "peer_group_shortname",
            "measure_name", "measure_value", "quarter", "reporting_period"]
    return pd.read_csv("ed_clean.csv", usecols=cols, parse_dates=["quarter"])

df = load()
LATEST = df["quarter"].max()
LATEST_NAME = df.loc[df["quarter"] == LATEST, "reporting_period"].iloc[0]


@st.cache_data
def forecast(values: tuple, start: str):
    """Holt-Winters forecast for the next 4 quarters, plus a simple likely range."""
    s = pd.Series(values, index=pd.date_range(start, periods=len(values), freq="QS"))
    fit = ExponentialSmoothing(s, trend="add", damped_trend=True, seasonal="add", seasonal_periods=4).fit()
    future = fit.forecast(4)
    spread = (fit.fittedvalues - s).abs().quantile(0.8)
    return future, spread


# ---------- Sidebar: what to look at ----------
with st.sidebar:
    st.header("Choose")
    level = st.radio("Level", ["All of NSW", "Local health district", "Hospital"], index=2)
    if level == "All of NSW":
        entity = "NSW"; lvl = "NSW"
    elif level == "Local health district":
        lvl = "LHD"
        entity = st.selectbox("Health district", sorted(df.loc[df["reporting_level"] == "LHD", "entity_shortname"].unique()))
    else:
        lvl = "Hospital"
        names = sorted(df.loc[df["reporting_level"] == "Hospital", "entity_shortname"].unique())
        entity = st.selectbox("Hospital", names, index=names.index("Westmead") if "Westmead" in names else 0)
    measure_label = st.selectbox("Measure", list(MEASURES))
    from_year = st.slider("Show chart from year", 2010, 2024, 2018)
    st.divider()
    st.caption("Data: Bureau of Health Information, Healthcare Quarterly, Jan-Mar 2010 to Jan-Mar 2026. "
               "Built by Md Juman Hussan · Python, pandas, statsmodels, Streamlit")

measure, unit, better = MEASURES[measure_label]
series = (df[(df["reporting_level"] == lvl) & (df["entity_shortname"] == entity) & (df["measure_name"] == measure)]
          .set_index("quarter")["measure_value"].sort_index().asfreq("QS"))

# ---------- Header ----------
st.title("🏥 NSW ED Pressure Forecaster")
st.caption("16 years of real NSW emergency department data, with a 4-quarter forecast for any hospital.")

if series.dropna().empty:
    st.warning("No data for this choice. Try another measure or hospital.")
    st.stop()

def fmt(v):
    if pd.isna(v):
        return "n/a"
    return f"{v:,.0f}" if unit == "patients" else (f"{v:.0f} min" if unit == "min" else f"{v:.1f}%")

# ---------- Headline numbers ----------
last_q = series.dropna().index[-1]
now = series[last_q]
year_ago = series.get(last_q - pd.DateOffset(years=1))
c1, c2, c3 = st.columns(3)
delta_colour = {"higher": "normal", "lower": "inverse", "neutral": "off"}[better]
c1.metric(f"{entity}, {last_q:%b %Y} quarter", fmt(now),
          delta=None if pd.isna(year_ago) else f"{now - year_ago:+,.1f} vs a year earlier",
          delta_color=delta_colour)

nsw = df[(df["reporting_level"] == "NSW") & (df["measure_name"] == measure) & (df["quarter"] == last_q)]["measure_value"]
c2.metric(f"NSW, same quarter", fmt(nsw.iloc[0]) if len(nsw) else "n/a")

if lvl == "Hospital" and better != "neutral":
    peers = df[(df["reporting_level"] == "Hospital") & (df["measure_name"] == measure) & (df["quarter"] == last_q)].dropna(subset=["measure_value"])
    ranked = peers.sort_values("measure_value", ascending=(better == "lower")).reset_index(drop=True)
    pos = ranked.index[ranked["entity_shortname"] == entity]
    if len(pos):
        c3.metric("Rank among NSW hospitals", f"{pos[0] + 1} of {len(ranked)}", help="1 = best")
else:
    c3.metric("Quarters of data", f"{series.notna().sum()}")

# ---------- Forecast (only when the recent history is complete) ----------
hist = series.dropna()
recent_ok = (last_q == LATEST) and series.loc[last_q - pd.DateOffset(years=4):].notna().all() and len(hist) >= 12
# Use the longest unbroken run of quarters that ends at the latest quarter
run = series.loc[:last_q]
gaps = run[run.isna()]
if len(gaps):
    run = run.loc[gaps.index[-1] + pd.offsets.QuarterBegin(1):]
fc = None
if recent_ok and len(run) >= 12:
    future, spread = forecast(tuple(run.values), str(run.index[0].date()))
    fc = pd.DataFrame({"quarter": future.index, "value": future.values,
                       "low": future.values - spread, "high": future.values + spread})

# ---------- Chart ----------
st.subheader(f"{measure_label}: {entity}")
actual = series.dropna().loc[f"{from_year}":].reset_index().rename(columns={"measure_value": "value"})
actual["Type"] = "Actual"
y_title = {"%": "Percent", "min": "Minutes", "patients": "Patients per quarter"}[unit]

base = alt.Chart(actual).encode(x=alt.X("quarter:T", title=None))
line = base.mark_line(color=BLUE, strokeWidth=2).encode(y=alt.Y("value:Q", title=y_title, scale=alt.Scale(zero=False)))
points = base.mark_circle(size=60, opacity=0).encode(
    y="value:Q", tooltip=[alt.Tooltip("quarter:T", title="Quarter", format="%b %Y"), alt.Tooltip("value:Q", title=measure_label, format=",.1f")])
layers = [line, points]
if fc is not None:
    joined = pd.concat([actual.iloc[[-1]][["quarter", "value"]], fc[["quarter", "value"]]])
    band = alt.Chart(fc).mark_area(color=ORANGE, opacity=0.15).encode(x="quarter:T", y="low:Q", y2="high:Q")
    fline = alt.Chart(joined).mark_line(color=ORANGE, strokeWidth=2, strokeDash=[6, 4], point=True).encode(
        x="quarter:T", y="value:Q",
        tooltip=[alt.Tooltip("quarter:T", title="Forecast quarter", format="%b %Y"), alt.Tooltip("value:Q", title="Forecast", format=",.1f")])
    layers = [band, line, points, fline]
st.altair_chart(alt.layer(*layers).properties(height=380).interactive(bind_y=False), width="stretch")
st.caption("Blue = actual. Orange dashed = forecast, with the shaded likely range. Hover over the line for exact values.")

if fc is not None:
    st.write("**Forecast for the next 4 quarters**")
    show = fc.copy()
    show["Quarter"] = show["quarter"].dt.strftime("%b %Y")
    show["Forecast"] = show["value"].map(fmt)
    show["Likely range"] = [f"{fmt(l)} to {fmt(h)}" for l, h in zip(show["low"], show["high"])]
    st.dataframe(show[["Quarter", "Forecast", "Likely range"]], hide_index=True, width="content")
    st.caption("Method: Holt-Winters (damped trend + seasonal pattern). In a fair test on NSW data, it beat simple "
               "methods with an average error of 0.5 percentage points. Forecasts are estimates, not promises.")
elif last_q != LATEST:
    st.info(f"No forecast: BHI stopped reporting this measure after {last_q:%b %Y}.")
else:
    st.info("No forecast: this series has gaps in recent quarters, so a forecast would not be reliable.")

# ---------- League table ----------
if better != "neutral":
    with st.expander(f"All NSW hospitals, {LATEST_NAME}"):
        table = df[(df["reporting_level"] == "Hospital") & (df["measure_name"] == measure) & (df["quarter"] == LATEST)]
        table = table.dropna(subset=["measure_value"]).sort_values("measure_value", ascending=(better == "lower"))
        table = table.rename(columns={"entity_shortname": "Hospital", "lhd_shortname": "Health district",
                                      "peer_group_shortname": "Hospital type", "measure_value": measure_label})
        st.dataframe(table[["Hospital", "Health district", "Hospital type", measure_label]], hide_index=True, width="stretch")

st.caption("Note: quarterly percentages and medians can't be averaged into yearly figures (BHI guidance). "
           "Some ambulance handover values are flagged by BHI as 'interpret with caution'.")
