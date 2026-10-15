# explore.py
# Step 1 of the NSW ED Pressure Forecaster: load 16 years of real data and look at it.
# Run it with:  python explore.py
# Data: Bureau of Health Information (BHI), Healthcare Quarterly - Emergency Department,
#       Jan-Mar 2010 to Jan-Mar 2026.

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Chart colours (checked for colour-blind safety)
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"

# ---------- 1. Load ----------
print("Loading the data. This takes about 30 seconds...")
df = pd.read_excel("bhi_ed_data.xlsx", sheet_name="Overall results")

# Turn "Jan-Mar 2010" into a real date (the first day of the quarter),
# so Python can sort and plot it as time.
MONTH = {"Jan": 1, "Apr": 4, "Jul": 7, "Oct": 10}
df["quarter"] = pd.to_datetime(
    df["reporting_period"].str[-4:] + "-" + df["reporting_period"].str[:3].map(MONTH).astype(str) + "-01"
)

# ---------- 2. Get to know the data ----------
hospitals = df[df["reporting_level"] == "Hospital"]
print()
print(f"Rows:      {len(df):,}")
print(f"Quarters:  {df['quarter'].nunique()}  ({df['reporting_period'].iloc[0]} to {df.sort_values('quarter')['reporting_period'].iloc[-1]})")
print(f"Hospitals: {hospitals['entity_id'].nunique()}")
print(f"Missing hospital values: {hospitals['measure_value'].isna().mean():.1%}")
print()
print("Measures in this sheet:")
for m in df["measure_name"].unique():
    print("  -", m)

# ---------- 3. NSW trend: two percentage measures, one chart ----------
nsw = df[df["reporting_level"] == "NSW"]
ON_TIME = "Percentage of patients starting treatment on time"
FOUR_HR = "Percentage of patients leaving ED within four hours"
trend = nsw[nsw["measure_name"].isin([ON_TIME, FOUR_HR])].pivot(
    index="quarter", columns="measure_name", values="measure_value"
)

def style(ax, title, subtitle):
    ax.set_facecolor(SURFACE)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.set_axisbelow(True)
    ax.text(0, 1.12, title, transform=ax.transAxes, fontsize=15, fontweight="bold", color=INK)
    ax.text(0, 1.05, subtitle, transform=ax.transAxes, fontsize=10, color=MUTED)

fig, ax = plt.subplots(figsize=(11, 6), facecolor=SURFACE)
for col, colour, label in [(ON_TIME, BLUE, "Started treatment on time"), (FOUR_HR, ORANGE, "Left ED within 4 hours")]:
    ax.plot(trend.index, trend[col], color=colour, linewidth=2, label=label)
    last = trend[col].dropna()
    ax.text(last.index[-1], last.iloc[-1], f"  {last.iloc[-1]:.0f}%", color=INK, va="center", fontsize=10)
ax.axvline(pd.Timestamp("2020-01-01"), color=MUTED, linewidth=1, linestyle="--")
ax.text(pd.Timestamp("2020-02-15"), 88, "COVID-19", color=MUTED, fontsize=9)
ax.set_ylim(40, 90)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.legend(frameon=False, loc="lower left", fontsize=10, labelcolor=INK)
style(ax, "NSW emergency departments, 2010 to 2026",
      "Share of patients, per quarter. Source: Bureau of Health Information")
fig.tight_layout()
fig.savefig("chart_1_nsw_trend.png", dpi=150)
print("\nSaved chart_1_nsw_trend.png")

# ---------- 4. Demand: how many patients come to ED each quarter ----------
pres = nsw[nsw["measure_name"] == "Emergency presentations"].set_index("quarter")["measure_value"]
fig, ax = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
ax.plot(pres.index, pres / 1000, color=BLUE, linewidth=2)
ax.set_ylim(0, None)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}k")
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
style(ax, "Emergency presentations in NSW, per quarter",
      "Thousands of patients. Source: Bureau of Health Information")
fig.tight_layout()
fig.savefig("chart_2_nsw_demand.png", dpi=150)
print("Saved chart_2_nsw_demand.png")

# ---------- 5. Which hospitals are struggling most right now? ----------
latest_q = df["quarter"].max()
latest_name = df.loc[df["quarter"] == latest_q, "reporting_period"].iloc[0]
latest = hospitals[(hospitals["quarter"] == latest_q) & (hospitals["measure_name"] == ON_TIME)].dropna(subset=["measure_value"])
bottom = latest.nsmallest(10, "measure_value").sort_values("measure_value", ascending=False)
nsw_now = trend[ON_TIME].iloc[-1]

fig, ax = plt.subplots(figsize=(11, 6), facecolor=SURFACE)
ax.barh(bottom["entity_shortname"], bottom["measure_value"], color=BLUE, height=0.6)
for y, v in enumerate(bottom["measure_value"]):
    ax.text(v + 0.8, y, f"{v:.1f}%", va="center", fontsize=10, color=INK)
ax.axvline(nsw_now, color=MUTED, linewidth=1, linestyle="--")
ax.text(nsw_now + 0.8, len(bottom) - 0.4, f"NSW average {nsw_now:.0f}%", color=MUTED, fontsize=9)
ax.set_xlim(0, 100)
ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.grid(axis="x", color=GRID, linewidth=0.8)
style(ax, f"10 hospitals with the fewest patients treated on time, {latest_name}",
      "Share of patients starting treatment within the benchmark time for their triage category")
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", colors=INK)
fig.tight_layout()
fig.savefig("chart_3_bottom_hospitals.png", dpi=150)
print("Saved chart_3_bottom_hospitals.png")

# ---------- 6. A few headline numbers ----------
first = trend.iloc[0]
lastrow = trend.iloc[-1]
print()
print("HEADLINES")
print(f"  Treated on time:   {first[ON_TIME]:.1f}% in {df.sort_values('quarter')['reporting_period'].iloc[0]}  ->  {lastrow[ON_TIME]:.1f}% in {latest_name}")
four = trend[FOUR_HR].dropna()
print(f"  Left within 4 hrs: {first[FOUR_HR]:.1f}%  ->  {four.iloc[-1]:.1f}% in {four.index[-1]:%b %Y}"
      "  (BHI stopped this measure after 2024; new time targets started in 2025)")
print(f"  Presentations:     {pres.iloc[0]:,.0f}  ->  {pres.iloc[-1]:,.0f} per quarter ({pres.iloc[-1] / pres.iloc[0] - 1:+.0%})")
print(f"  Best quarter for 'on time':  {trend[ON_TIME].idxmax():%b %Y} ({trend[ON_TIME].max():.1f}%)")
print(f"  Worst quarter for 'on time': {trend[ON_TIME].idxmin():%b %Y} ({trend[ON_TIME].min():.1f}%)")
