"""
South Africa: clothing & footwear price pressure vs. household consumption (2008-2024).

Usage:  python analysis.py
Inputs (data/raw/, FRED downloads):
  ZAFCP030000IXOBQ.csv                       clothing & footwear CPI index, quarterly      (required)
  Real_Final_Consumption_Expenditure.csv     real final consumption (NCRNSAXDCZAQ)         (required)
  Nominal_Final_Consumption_Expenditure.csv  nominal final consumption (NCNSAXDCZAQ)       (optional;
                                             enables the deflation / broad-vs-clothing-inflation sections)
Outputs: data/processed/panel.csv, outputs/figures/*.png, outputs/tables/*.csv,
         outputs/findings.md (and the Results block of README.md is refreshed automatically).
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

BASE = Path(__file__).resolve().parent          # folder containing analysis.py
RAW, PROC, OUT = BASE / "data" / "raw", BASE / "data" / "processed", BASE / "outputs"
FILES = {"cpi": "ZAFCP030000IXOBQ.csv",
         "rfce": "Real_Final_Consumption_Expenditure.csv",
         "nfce": "Nominal_Final_Consumption_Expenditure.csv"}
START = "2008-01-01"
COVID = ("2020-01-01", "2021-12-31")   # lockdown shock and rebound distort YoY growth (base effect start?)
MAXLAG = 4                             # quarters


#  1. EXTRACT + VALIDATE
def load_d(fname, col):
    path = RAW / fname
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Files in {RAW}: {[f.name for f in RAW.glob('*')]}")
    df = pd.read_csv(RAW / fname, sep=None, engine="python")  # delimiter auto-detects for (); or ,)
    df.columns = ["date", col]
    df["date"] = pd.to_datetime(df["date"])
    df[col] = pd.to_numeric(df[col], errors="coerce")         
    df = df.sort_values("date").set_index("date")
    assert df.index.is_unique, f"{col}: duplicate dates"
    assert df[col].notna().all(), f"{col}: missing values"
    assert df.index.to_series().diff().dropna().dt.days.between(89, 92).all(), f"{col}: gap in quarterly series"
    print(f"[ok] {col:5s} {len(df):3d} obs  {df.index.min():%Y-%m} to {df.index.max():%Y-%m}")
    return df


#  2. TRANSFORM
def build_panel():
    parts = [load_d(FILES[k], k) for k in ("cpi", "rfce")]
    if (RAW / FILES["nfce"]).exists():
        parts.append(load_d(FILES["nfce"], "nfce"))
    p = pd.concat(parts, axis=1, join="inner").loc[START:].asfreq("QS")
    # Series are NOT seasonally adjusted -> use year-on-year growth, which removes the seasonal cycle.
    p["cpi_yoy"] = p.cpi.pct_change(4) * 100
    p["rfce_yoy"] = p.rfce.pct_change(4) * 100
    p["covid"] = (p.index >= COVID[0]) & (p.index <= COVID[1])
    if "nfce" in p:
        p["nfce_yoy"] = p.nfce.pct_change(4) * 100
        p["deflator"] = p.nfce / p.rfce * 100                 # implicit consumption deflator (2008-2024 base-year units)
        p["defl_yoy"] = p.deflator.pct_change(4) * 100        # a broad-based inflation
        p["gap_pp"] = p.cpi_yoy - p.defl_yoy                  # clothing inflation - broad inflation
        p["rel_price"] = (p.cpi / p.cpi.iloc[0]) / (p.deflator / p.deflator.iloc[0]) * 100  # clothing price relative to all prices where 2008Q1=100
    p.index.name = "date"
    p.to_csv(PROC / "panel.csv")
    return p


#  3. ANALYSE
def lag_table(p):
    rows = []
    for k in range(MAXLAG + 1):
        d = pd.DataFrame({"x": p.cpi_yoy.shift(k), "y": p.rfce_yoy, "covid": p.covid}).dropna()
        for label, s in (("full", d), ("ex_covid", d[~d.covid])):
            r, pv = stats.pearsonr(s.x, s.y)
            rows.append(dict(lag=k, sample=label, n=len(s), r=r, p=pv))
    return pd.DataFrame(rows)


def hac_table(p):
    """OLS: real consumption growth_t = a + b * clothing inflation_(t-k); COVID window excluded; Newey-West (HAC) errors.
    All lags use the SAME sample (first MAXLAG obs dropped) so AIC is comparable across lags."""
    X = pd.concat({f"x{k}": p.cpi_yoy.shift(k) for k in range(MAXLAG + 1)}, axis=1)
    d = pd.concat([p.rfce_yoy.rename("y"), X, p.covid], axis=1).dropna()
    d = d[~d.covid]
    rows = []
    for k in range(MAXLAG + 1):
        m = sm.OLS(d.y, sm.add_constant(d[[f"x{k}"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
        rows.append(dict(lag=k, n=int(m.nobs), beta=m.params[f"x{k}"], p=m.pvalues[f"x{k}"], r2=m.rsquared, aic=m.aic))
    return pd.DataFrame(rows)


def deflation_summary(p):
    """Annual aggregates (full calendar years, avoids NSA seasonal bias) -> CAGR of nominal, real, prices."""
    a = p.resample("YE").agg({"cpi": "mean", "rfce": "sum", "nfce": "sum"})
    a["deflator"] = a.nfce / a.rfce * 100
    n = len(a) - 1
    cagr = lambda s: ((s.iloc[-1] / s.iloc[0]) ** (1 / n) - 1) * 100
    out = {"years": f"{a.index[0].year}-{a.index[-1].year}", "nominal": cagr(a.nfce), "real": cagr(a.rfce),
           "deflator": cagr(a.deflator), "clothing": cagr(a.cpi)}
    out["price_share"] = np.log(a.deflator.iloc[-1] / a.deflator.iloc[0]) / np.log(a.nfce.iloc[-1] / a.nfce.iloc[0]) * 100
    out["rel_price_chg"] = (p.rel_price.iloc[-1] / 100 - 1) * 100
    out["share_below"] = (p.gap_pp.dropna() < 0).mean() * 100
    return out, a


# 4. CHARTS
def shade(ax):
    ax.axvspan(pd.Timestamp(COVID[0]), pd.Timestamp(COVID[1]), color="grey", alpha=0.15, label="COVID-19 period")


def charts(p, lags):
    plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})
    f = OUT / "figures"
    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    ax[0].plot(p.index, p.cpi_yoy, color="tab:red"); ax[0].set_title("Clothing & footwear CPI inflation (YoY %)")
    ax[1].plot(p.index, p.rfce_yoy, color="tab:blue"); ax[1].axhline(0, color="k", lw=.6)
    ax[1].set_title("Real final consumption expenditure growth (YoY %)")
    for a in ax: shade(a)
    fig.tight_layout(); fig.savefig(f / "1_inflation_vs_consumption.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for lab, c in (("full", "lightgrey"), ("ex_covid", "tab:blue")):
        s = lags[lags["sample"] == lab]
        ax.bar(s.lag + (0.2 if lab == "ex_covid" else -0.2), s.r, width=0.4, color=c, label=lab.replace("_", " "))
    ax.axhline(0, color="k", lw=.6); ax.set_xlabel("Lag of clothing inflation (quarters)"); ax.set_ylabel("Pearson r")
    ax.set_title("Clothing inflation (t-k) vs real consumption growth (t)"); ax.legend()
    fig.tight_layout(); fig.savefig(f / "2_lag_correlations.png"); plt.close(fig)

    if "nfce" in p:
        ann = p.resample("YE").agg({"rfce": "sum", "nfce": "sum"})
        ann = ann / ann.iloc[0] * 100
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.plot(ann.index.year, ann.nfce, label="Nominal (with inflation)"); ax.plot(ann.index.year, ann.rfce, label="Real (inflation removed)")
        ax.fill_between(ann.index.year, ann.rfce, ann.nfce, alpha=.15, label="Price effect")
        ax.set_title("Consumption, nominal vs real (annual, first year = 100)"); ax.legend()
        fig.tight_layout(); fig.savefig(f / "3_nominal_vs_real.png"); plt.close(fig)

        fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
        ax[0].plot(p.index, p.cpi_yoy, color="tab:red", label="Clothing & footwear"); ax[0].plot(p.index, p.defl_yoy, color="k", label="Broad (consumption deflator)")
        ax[0].set_title("Clothing vs broad inflation (YoY %)"); ax[0].legend()
        ax[1].plot(p.index, p.rel_price, color="tab:purple"); ax[1].axhline(100, color="k", lw=.6)
        ax[1].set_title("Relative price of clothing & footwear (2008Q1 = 100)")
        for a in ax: shade(a)
        fig.tight_layout(); fig.savefig(f / "4_clothing_vs_broad_inflation.png"); plt.close(fig)


#  5. FINDINGS (auto-written; numbers never hand-typed)
def sig(pv):
    ps = "p < 0.001" if pv < 0.001 else (f"p = {pv:.3f}" if pv < 0.05 else f"p = {pv:.2f}")
    return f"statistically significant ({ps})" if pv < 0.05 else f"not statistically significant ({ps})"


def findings(p, lags, hac, adf):
    q = lambda d: f"{d:%Y}Q{(d.month - 1) // 3 + 1}"
    L = []
    c, r = p.cpi_yoy.dropna(), p.rfce_yoy.dropna()
    L += [f"**Sample.** {len(p)} quarters, {q(p.index[0])} to {q(p.index[-1])} ({len(c)} with year-on-year growth rates).", ""]
    L += [f"**Clothing & footwear inflation** averaged {c.mean():.1f}% a year (median {c.median():.1f}%), ranging from "
          f"{c.min():.1f}% ({q(c.idxmin())}) to {c.max():.1f}% ({q(c.idxmax())}). The last four quarters averaged "
          f"{c.tail(4).mean():.1f}%, versus {c.mean():.1f}% over the full sample.", ""]
    L += [f"**Real consumption growth** averaged {r.mean():.1f}% a year (std. dev. {r.std():.1f} pp). Its weakest quarter was "
          f"{q(r.idxmin())} ({r.min():.1f}%) and its strongest {q(r.idxmax())} ({r.max():.1f}%), both inside the COVID-19 window.", ""]
    st = lambda v: "stationary at 5%" if v < 0.05 else "persistent (cannot reject a unit root at 5%)"
    L += [f"**Stationarity (ADF).** Clothing inflation is {st(adf['cpi_yoy'])} (p = {adf['cpi_yoy']:.2f}); real consumption growth is "
          f"{st(adf['rfce_yoy'])} (p = {adf['rfce_yoy']:.3f}). Persistent series can produce spurious correlations, so the robustness checks below also use first differences.", ""]
    ex = lags[lags["sample"] == "ex_covid"].reset_index(drop=True)
    b = ex.loc[ex.r.abs().idxmax()]
    fl = lags[(lags["sample"] == "full") & (lags.lag == b.lag)].iloc[0]
    L += [f"**Lead-lag relationship.** Excluding COVID-19, the strongest correlation between clothing inflation and real consumption growth is "
          f"r = {b.r:.2f} at a lag of {int(b.lag)} quarter(s) (n = {int(b.n)}), {sig(b.p)}. On the full sample the same lag gives r = {fl.r:.2f} "
          f"({sig(fl.p)}). Contemporaneous correlation ex-COVID: r = {ex.loc[0, 'r']:.2f}.", ""]
    e = p[~p.covid][["cpi_yoy", "rfce_yoy"]].dropna()
    dd = p[["cpi_yoy", "rfce_yoy", "covid"]].assign(dx=lambda t: t.cpi_yoy.diff(), dy=lambda t: t.rfce_yoy.diff())
    dd = dd[~dd.covid].dropna()
    pre = p.loc[:"2019-12-31", ["cpi_yoy", "rfce_yoy"]].dropna()
    r_d, p_d = stats.pearsonr(dd.dx, dd.dy); r_p, p_p = stats.pearsonr(pre.cpi_yoy, pre.rfce_yoy)
    L += [f"**Robustness (contemporaneous, ex-COVID).** In first differences r = {r_d:.2f} ({sig(p_d)}, n = {len(dd)}); "
          f"pre-COVID only ({q(pre.index[0])} to {q(pre.index[-1])}) r = {r_p:.2f} ({sig(p_p)}, n = {len(pre)}).", ""]
    h = hac.loc[hac.aic.idxmin()]
    L += [f"**Regression (HAC errors, COVID window excluded, common sample).** The best-fitting lag by AIC is {int(h.lag)} quarter(s): a 1 pp rise in clothing inflation is associated "
          f"with a {h.beta:+.2f} pp change in real consumption growth, {sig(h.p)}, R² = {h.r2:.2f}. "
          f"Real consumption is total, not clothing-specific, so this measures aggregate resilience, not clothing demand elasticity.", ""]
    if "nfce" in p:
        d, _ = deflation_summary(p)
        L += [f"**Deflating nominal consumption ({d['years']}).** Nominal consumption grew {d['nominal']:.1f}% a year; real consumption grew {d['real']:.1f}%; "
              f"the implicit price deflator rose {d['deflator']:.1f}%. About {d['price_share']:.0f}% of nominal growth was price change rather than extra volume. "
              f"(Nominal growth is approximately real growth plus price growth: {d['nominal']:.1f} ≈ {d['real']:.1f} + {d['deflator']:.1f}.)", ""]
        L += [f"**Clothing vs broad inflation.** Clothing & footwear prices grew {d['clothing']:.1f}% a year against {d['deflator']:.1f}% for consumption as a whole. "
              f"Relative to the general price level, clothing is {d['rel_price_chg']:+.0f}% since {q(p.index[0])}, and clothing inflation ran below broad inflation in "
              f"{d['share_below']:.0f}% of quarters. {'Clothing inflation is therefore a component-specific story (cheaper relative to everything else), not the driver of headline inflation.' if d['rel_price_chg'] < 0 else 'Clothing has become relatively more expensive than the average consumption basket.'}", ""]
    y = c.asfreq("QS")
    fc = ARIMA(y, order=(1, 0, 0)).fit().get_forecast(4).summary_frame(alpha=0.2)
    L += [f"**Outlook (illustrative AR(1), 80% interval).** Clothing inflation is projected at {fc['mean'].iloc[0]:.1f}% next quarter, "
          f"{fc['mean'].iloc[-1]:.1f}% in four quarters (interval {fc['mean_ci_lower'].iloc[-1]:.1f}% to {fc['mean_ci_upper'].iloc[-1]:.1f}%), drifting towards the sample mean of {c.mean():.1f}%."]
    return "\n".join(L)


def main():
    for d in (PROC, OUT / "figures", OUT / "tables"):
        d.mkdir(parents=True, exist_ok=True)
    p = build_panel()
    lags, hac = lag_table(p), hac_table(p)
    adf = {k: adfuller(p[k].dropna(), autolag="AIC", result_object=False)[1] for k in ("cpi_yoy", "rfce_yoy")}
    lags.to_csv(OUT / "tables/lag_correlations.csv", index=False); hac.to_csv(OUT / "tables/hac_regressions.csv", index=False)
    charts(p, lags)
    text = findings(p, lags, hac, adf)
    (OUT / "findings.md").write_text(text, encoding="utf-8")
    readme = BASE / "README.md"
    if readme.exists():
        s = readme.read_text(encoding="utf-8")
        s = re.sub(r"(<!-- RESULTS:START -->).*?(<!-- RESULTS:END -->)", lambda m: f"{m.group(1)}\n{text}\n{m.group(2)}", s, flags=re.S)
        readme.write_text(s, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
