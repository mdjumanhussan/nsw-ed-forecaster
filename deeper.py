# deeper.py
# Step 2 of the NSW ED Pressure Forecaster: dig deeper.
#   1. Is there a seasonal pattern (winter peak)?
#   2. Does demand really go with performance? We measure it with a number.
#   3. Which hospitals improved, and which got worse, since before COVID?
# Run it with:  python deeper.py

import os
import pandas as pd
import matplotlib.pyplot as plt

BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
ON_TIME = "Percentage of patients starting treatment on time"
PRES = "Emergency presentations"

# ---------- Load (fast after the first run) ----------
# Reading Excel is slow. So the first time, we save a clean CSV copy.
# Every run after that loads the CSV in a second or two. Real analysts do this all the time.
if os.path.exists("ed_clean.csv"):
    df = pd.read_csv("ed_clean.csv", parse_dates=["quarter"])
else:
    print("First run: reading the Excel file and saving a fast CSV copy (about 30 seconds)...")
    df = pd.read_excel("bhi_ed_data.xlsx", sheet_name="Overall results")
    MONTH = {"Jan": 1, "Apr": 4, "Jul": 7, "Oct": 10}
    df["quarter"] = pd.to_datetime(
        df["reporting_period"].str[-4:] + "-" + df["reporting_period"].str[:3].map(MONTH).astype(str) + "-01")
    df.to_csv("ed_clean.csv", index=False)
    print("Saved ed_clean.csv")

nsw = df[df["reporting_level"] == "NSW"].pivot(index="quarter", columns="measure_name", values="measure_value")
nsw["season"] = nsw.index.quarter.map({1: "Jan-Mar\n(summer)", 2: "Apr-Jun\n(autumn)", 3: "Jul-Sep\n(winter)", 4: "Oct-Dec\n(spring)"})
covid = (nsw.index >= "2020-01-01") & (nsw.index < "2022-01-01")

def style(ax, title, subtitle):
    ax.set_facecolor(SURFACE)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.set_axisbelow(True)
    ax.text(0, 1.12, title, transform=ax.transAxes, fontsize=15, fontweight="bold", color=INK)
    ax.text(0, 1.05, subtitle, transform=ax.transAxes, fontsize=10, color=MUTED)

# =====================================================================
# 1. SEASONS: is winter the hardest time of year?
# =====================================================================
# We leave out 2020-2021, because COVID would distort the normal pattern.
normal = nsw[~covid]
order = ["Jan-Mar\n(summer)", "Apr-Jun\n(autumn)", "Jul-Sep\n(winter)", "Oct-Dec\n(spring)"]
season_ontime = normal.groupby("season")[ON_TIME].median().reindex(order)
season_pres = normal.groupby("season")[PRES].median().reindex(order)

print("\n1. SEASONS (typical quarter, 2010-2026 without the COVID years)")
for s in order:
    print(f"   {s.replace(chr(10), ' '):22}  treated on time {season_ontime[s]:.1f}%   presentations {season_pres[s]:,.0f}")
worst = season_ontime.idxmin().replace("\n", " ")
print(f"   -> The hardest season is {worst}.")

fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=SURFACE)
bars = ax.bar(order, season_ontime.values, color=[RED if s == season_ontime.idxmin() else BLUE for s in order], width=0.55)
for b, v in zip(bars, season_ontime.values):
    ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}%", ha="center", fontsize=11, color=INK)
ax.set_ylim(0, 100)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.grid(axis="y", color=GRID, linewidth=0.8)
ax.tick_params(axis="x", colors=INK)
style(ax, "Patients treated on time, by season", "Typical (median) quarter in NSW, 2010-2026, leaving out the COVID years 2020-2021")
fig.tight_layout(); fig.savefig("chart_4_seasons.png", dpi=150)
print("   Saved chart_4_seasons.png")

# =====================================================================
# 2. DEMAND vs PERFORMANCE: measure the link with one number
# =====================================================================
# The correlation (r) runs from -1 to +1.
#   Close to -1: when demand goes up, performance goes down.
#   Close to 0:  no clear link.
r_all = nsw[PRES].corr(nsw[ON_TIME])
print("\n2. DEMAND vs PERFORMANCE")
print(f"   Correlation between presentations and % treated on time: r = {r_all:+.2f}")
eras = {"2010-2019": (nsw.index < "2020-01-01"), "2020-2021 (COVID)": covid, "2022-2026": (nsw.index >= "2022-01-01")}
for name, mask in eras.items():
    if mask.sum() > 3:
        print(f"   {name:18}  r = {nsw.loc[mask, PRES].corr(nsw.loc[mask, ON_TIME]):+.2f}   ({mask.sum()} quarters)")
print("   Careful: correlation is not proof of cause. Both numbers also change over time for other reasons,")
print("   like staff numbers, new hospitals and policy changes.")

fig, ax = plt.subplots(figsize=(10, 6.5), facecolor=SURFACE)
for (name, mask), colour in zip(eras.items(), [BLUE, ORANGE, AQUA]):
    ax.scatter(nsw.loc[mask, PRES] / 1000, nsw.loc[mask, ON_TIME], s=70, color=colour,
               edgecolor=SURFACE, linewidth=2, label=name, zorder=3)
ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="lower left")
ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}k")
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.grid(color=GRID, linewidth=0.8)
ax.set_xlabel("Emergency presentations per quarter", color=MUTED)
ax.set_ylabel("Treated on time", color=MUTED)
style(ax, "Demand and performance: the link changed after COVID",
      f"Each dot is one quarter in NSW. Overall r = {r_all:+.2f}, but it differs by era (see the terminal)")
fig.tight_layout(); fig.savefig("chart_5_demand_vs_performance.png", dpi=150)
print("   Saved chart_5_demand_vs_performance.png")

# =====================================================================
# 3. HOSPITALS: who improved and who got worse since before COVID?
# =====================================================================
# We compare 2019 (the last normal year) with the latest 4 quarters.
# Note: an average of 4 quarterly percentages is a fair summary, but it is NOT
# the official yearly figure. BHI asks users not to treat it as one.
hosp = df[(df["reporting_level"] == "Hospital") & (df["measure_name"] == ON_TIME)].dropna(subset=["measure_value"])
latest4 = sorted(hosp["quarter"].unique())[-4:]
before = hosp[hosp["quarter"].dt.year == 2019].groupby("entity_shortname")["measure_value"].agg(["mean", "count"])
after = hosp[hosp["quarter"].isin(latest4)].groupby("entity_shortname")["measure_value"].agg(["mean", "count"])
change = pd.DataFrame({"before": before["mean"], "after": after["mean"],
                       "n": before["count"] + after["count"]}).dropna()
change = change[change["n"] == 8]                     # only hospitals with all 8 quarters
change["change"] = change["after"] - change["before"]
change = change.sort_values("change")

print("\n3. HOSPITALS: change in % treated on time, 2019 vs the latest 4 quarters")
print(f"   Hospitals compared: {len(change)}")
print(f"   Got worse: {(change['change'] < 0).sum()}   Improved: {(change['change'] > 0).sum()}")
print("   Biggest falls:")
for name, row in change.head(5).iterrows():
    print(f"     {name:28} {row['before']:5.1f}% -> {row['after']:5.1f}%  ({row['change']:+.1f} points)")
print("   Biggest improvements:")
for name, row in change.tail(5)[::-1].iterrows():
    print(f"     {name:28} {row['before']:5.1f}% -> {row['after']:5.1f}%  ({row['change']:+.1f} points)")

show = pd.concat([change.head(8), change.tail(8)]).sort_values("change")
fig, ax = plt.subplots(figsize=(11, 7.5), facecolor=SURFACE)
ax.barh(show.index, show["change"], color=[RED if v < 0 else BLUE for v in show["change"]], height=0.6)
for y, v in enumerate(show["change"]):
    ax.text(v + (0.4 if v >= 0 else -0.4), y, f"{v:+.1f}", va="center", ha="left" if v >= 0 else "right", fontsize=10, color=INK)
ax.axvline(0, color="#c3c2b7", linewidth=1)
ax.grid(axis="x", color=GRID, linewidth=0.8)
ax.tick_params(axis="y", colors=INK)
lim = show["change"].abs().max() + 5
ax.set_xlim(-lim, lim)
ax.set_xlabel("Change in percentage points (red = worse, blue = better)", color=MUTED)
style(ax, "Biggest falls and gains in patients treated on time",
      "Average of 2019 quarters vs average of the latest 4 quarters. 8 biggest falls and 8 biggest gains")
fig.tight_layout(); fig.savefig("chart_6_hospital_change.png", dpi=150)
print("   Saved chart_6_hospital_change.png")
