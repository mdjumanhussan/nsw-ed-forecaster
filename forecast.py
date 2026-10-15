# forecast.py
# Step 3 of the NSW ED Pressure Forecaster: predict the future, and PROVE how good the prediction is.
#
# The fair test:
#   1. Hide the last 4 quarters (we pretend we don't know them yet).
#   2. Let 4 methods predict those 4 quarters.
#   3. Compare each prediction with what really happened.
#   4. Use the winner to forecast the next 4 quarters.
#
# Run it with:  python forecast.py

import warnings
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")   # statsmodels prints a lot of technical notes; we hide them

# What do we forecast? Try changing this to "Emergency presentations" later.
TARGET = "Percentage of patients starting treatment on time"
LABEL = "Treated on time (%)"

BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"

# ---------- Load the fast CSV from step 2 ----------
df = pd.read_csv("ed_clean.csv", parse_dates=["quarter"])
s = (df[(df["reporting_level"] == "NSW") & (df["measure_name"] == TARGET)]
     .set_index("quarter")["measure_value"].sort_index().asfreq("QS"))
print(f"Forecasting: {TARGET}")
print(f"History: {len(s)} quarters, {s.index[0]:%b %Y} to {s.index[-1]:%b %Y}")

# ---------- 1. Hide the last 4 quarters ----------
train, test = s.iloc[:-4], s.iloc[-4:]
print(f"Training on data up to {train.index[-1]:%b %Y}. Testing on the 4 quarters after it.\n")

def holt_winters(series, steps):
    """A classic forecasting model: it learns the level, the trend and the seasonal pattern."""
    model = ExponentialSmoothing(series, trend="add", damped_trend=True,
                                 seasonal="add", seasonal_periods=4).fit()
    return model.forecast(steps)

# ---------- 2. Four methods ----------
predictions = {
    # A. Naive: "the next 4 quarters will be the same as the last one we saw"
    "A. Naive (repeat last quarter)": pd.Series(train.iloc[-1], index=test.index),
    # B. Seasonal naive: "each quarter will be the same as that quarter one year ago"
    "B. Seasonal naive (same quarter last year)": pd.Series(train.iloc[-4:].values, index=test.index),
    # C. Holt-Winters trained on ALL years since 2010
    "C. Model trained on all years (2010+)": holt_winters(train, 4),
    # D. Holt-Winters trained only AFTER the structural break we found in step 2
    "D. Model trained on recent years (2022+)": holt_winters(train["2022":], 4),
}

# ---------- 3. Score each method ----------
# MAE = Mean Absolute Error: on average, how many percentage points was the guess off?
# Smaller is better.
scores = {name: (pred - test).abs().mean() for name, pred in predictions.items()}
print("HOW ACCURATE WAS EACH METHOD? (average error, in percentage points)")
for name, mae in sorted(scores.items(), key=lambda x: x[1]):
    print(f"  {mae:5.2f}   {name}")
best = min(scores, key=scores.get)
print(f"\nWinner: {best}")
print("Careful: this test uses only 4 quarters, so luck plays a part. A bigger test would be more convincing.\n")

print("Quarter by quarter:")
table = pd.DataFrame({"Actual": test, **{k[:2].strip(): v for k, v in predictions.items()}}).round(1)
table.index = table.index.strftime("%b %Y")
print(table.to_string())

# ---------- Chart: the test ----------
def style(ax, title, subtitle):
    ax.set_facecolor(SURFACE)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.text(0, 1.12, title, transform=ax.transAxes, fontsize=15, fontweight="bold", color=INK)
    ax.text(0, 1.05, subtitle, transform=ax.transAxes, fontsize=10, color=MUTED)

fig, ax = plt.subplots(figsize=(11, 6.8), facecolor=SURFACE)
recent = s["2022":]
ax.plot(recent.index, recent, color=INK, linewidth=2, label="Actual")
for (name, pred), colour in zip(predictions.items(), [MUTED, BLUE, ORANGE, AQUA]):
    ax.plot(pred.index, pred, color=colour, linewidth=2, marker="o", markersize=6,
            label=f"{name}  (error {scores[name]:.1f})")
ax.axvspan(test.index[0] - pd.Timedelta(days=45), test.index[-1] + pd.Timedelta(days=45), color=GRID, alpha=0.5, zorder=0)
ax.text(test.index[0] - pd.Timedelta(days=40), ax.get_ylim()[1] - 0.6, "hidden test period", color=MUTED, fontsize=9)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2)
style(ax, "Which method predicted the hidden quarters best?", f"NSW, {LABEL}. Average error in percentage points, smaller is better")
fig.tight_layout(); fig.savefig("chart_7_forecast_test.png", dpi=150)
print("\nSaved chart_7_forecast_test.png")

# ---------- 4. The real forecast: next 4 quarters ----------
# Now we use ALL the data we have (including the 4 test quarters) and look ahead.
if "recent" in best:
    hist = s["2022":]
elif "all years" in best:
    hist = s
else:
    hist = None

future_index = pd.date_range(s.index[-1] + pd.offsets.QuarterBegin(1), periods=4, freq="QS")
if hist is not None:
    fit = ExponentialSmoothing(hist, trend="add", damped_trend=True, seasonal="add", seasonal_periods=4).fit()
    future = fit.forecast(4)
    # A simple range: +/- the typical size of the model's past errors (about 80% of quarters fall inside)
    spread = (fit.fittedvalues - hist).abs().quantile(0.8)
elif "Seasonal" in best:
    future = pd.Series(s.iloc[-4:].values, index=future_index)
    spread = (s - s.shift(4)).abs().quantile(0.8)
else:
    future = pd.Series(s.iloc[-1], index=future_index)
    spread = (s - s.shift(1)).abs().quantile(0.8)
future.index = future_index

print("\nFORECAST FOR THE NEXT 4 QUARTERS (using the winning method)")
for q, v in future.items():
    print(f"  {q:%b %Y}:  {v:5.1f}%   (likely range {v - spread:.1f}% to {v + spread:.1f}%)")

fig, ax = plt.subplots(figsize=(11, 6.8), facecolor=SURFACE)
ax.plot(recent.index, recent, color=INK, linewidth=2, label="Actual")
ax.plot([s.index[-1], *future.index], [s.iloc[-1], *future.values], color=BLUE, linewidth=2,
        linestyle="--", marker="o", markersize=6, label="Forecast")
ax.fill_between(future.index, future - spread, future + spread, color=BLUE, alpha=0.15, linewidth=0, label="Likely range")
for q, v in future.items():
    ax.text(q, v + spread + 0.4, f"{v:.1f}%", ha="center", fontsize=9, color=INK)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.legend(frameon=False, fontsize=10, labelcolor=INK, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3)
style(ax, f"Forecast: {LABEL.lower()}, next 4 quarters", f"NSW. Method: {best[3:]}")
fig.tight_layout(); fig.savefig("chart_8_forecast.png", dpi=150)
print("Saved chart_8_forecast.png")
