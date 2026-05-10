"""
logic.py — business logic, formulas, and data fetching for Stock Scorer.
"""

from __future__ import annotations

import math
import os
import warnings
from typing import Optional

import pandas as pd
import streamlit as st
import yfinance as yf
from google import genai as google_genai

from config import (
    GEMINI_API_KEY,
    RF,
    RM_RF,
    SIGMA_M,
    CACHE_TTL,
)
from data import (
    CATALOG,
    SECTOR_TICKERS,
    FACTORS,
    STRATEGIES,
    FACTOR_HELP,
)


def safe_float(value, default: float = 0.0) -> float:
    """`value` to float; return `default` for None / NaN / Inf / non-numeric."""
    if value is None: return default
    try:
        f = float(value)
    except (TypeError, ValueError): return default
    if math.isnan(f) or math.isinf(f): return default
    return f



# ---Gemini---

def get_gemini_client():
    """Build a Gemini client"""
    key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        return google_genai.Client(api_key=key)
    except Exception as e:
        warnings.warn(f"get_gemini_client failed: {type(e).__name__}: {e}")
        return None


# ---Fetch data (Yahoo Finance)---

def _empty_factors(ticker: str) -> dict:
    return {
        "ticker":         ticker,
        "name":           ticker,
        "price":          0.0,
        "sector":         "N/A",
        "beta":           None,
        "revenue_growth": None,
        "pe_ratio":       None,
        "roe":            None,
        "div_yield":      0.0,
        "eps":            0.0,
        "forward_div":    0.0,
    }


@st.cache_data(show_spinner=False, ttl=CACHE_TTL)
def fetch_factors(ticker: str) -> dict:
    """Fetch fundamentals for one ticker"""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as e:
        warnings.warn(f"fetch_factors({ticker}) failed: {type(e).__name__}: {e}")
        return _empty_factors(ticker)

    price = safe_float(info.get("currentPrice"), default=0.0)
    if price == 0:
        price = safe_float(info.get("regularMarketPrice"), default=0.0)

    pe = info.get("trailingPE")
    if pe is not None and pe <= 0:
        pe = None

    forward_div = safe_float(info.get("dividendRate"), default=0.0)
    div_yield = (forward_div / price * 100) if price > 0 else 0.0

    return {
        "ticker":         ticker,
        "name":           info.get("shortName") or info.get("longName") or ticker,
        "price":          price,
        "sector":         info.get("sector", "N/A"),
        "beta":           info.get("beta"),
        "revenue_growth": info.get("revenueGrowth"),
        "pe_ratio":       pe,
        "roe":            info.get("returnOnEquity"),
        "div_yield":      div_yield,
        "eps":            safe_float(info.get("trailingEps"), default=0.0),
        "forward_div":    forward_div,
    }


# ---Scoring---

def normalize(series: pd.Series, higher_better: bool) -> pd.Series:
    """Min-max normalise to [0, 1]"""
    s = series.astype(float)
    valid = s.dropna()
    if valid.empty:
        return pd.Series(0.0, index=s.index)
    lo, hi = valid.min(), valid.max()
    if math.isclose(lo, hi):
        return pd.Series(0.5, index=s.index).where(s.notna(), 0.0)
    norm = (s - lo) / (hi - lo)
    if not higher_better:
        norm = 1.0 - norm
    return norm.fillna(0.0)


def pick_candidates(watchlist: list[str], portfolio: list[str], strategy_name: str, top_n: int = 10) -> list[str]:
    """Choose tickers to fetch given the user's selections and strategy."""
    strat = STRATEGIES[strategy_name]
    must = list(dict.fromkeys(watchlist + portfolio))

    if strat["sectors"]:
        pool: list[str] = []
        for s in strat["sectors"]:
            pool.extend(SECTOR_TICKERS.get(s, []))
        pool = list(dict.fromkeys(pool))
        if not pool:
            pool = list(CATALOG.keys())
    else:
        pool = list(CATALOG.keys())

    portfolio_only = len(set(portfolio) - set(watchlist))
    target = top_n + portfolio_only

    candidates = list(must)
    for t in pool:
        if len(candidates) >= target:
            break
        if t not in candidates:
            candidates.append(t)
    return candidates



# ---Finance formulas---

def capm_return(beta) -> float:
    """CAPM expected return: r = RF + β × (RM − RF)"""
    b = safe_float(beta, default=1.0)
    return RF + b * RM_RF


def sharpe_ratio(exp_r: float, beta) -> float:
    """Sharpe ratio: S = (r − RF) / σᵢ, where σᵢ = |β| × SIGMA_M."""
    b = safe_float(beta, default=1.0)
    sigma_i = abs(b) * SIGMA_M
    return (exp_r - RF) / sigma_i if sigma_i > 0 else 0.0


def ddm_price(forward_div: float, roe, exp_r: float, payout: float = 0.6) -> Optional[float]:
    """DDM (Gordon): P = DIV₁ / (r − g), with g = ROE × (1 − payout)."""
    g = max(0.0, safe_float(roe) * (1.0 - payout))
    if exp_r <= g or forward_div <= 0:
        return None
    return forward_div / (exp_r - g)


def ddm_signal(ddm_p: Optional[float], market_p: float) -> str:
    """Verdict comparing DDM value to market price."""
    if ddm_p is None or market_p <= 0:
        return "N/A"
    ratio = ddm_p / market_p
    if ratio > 1.15: return "↑ undervalued"
    if ratio < 0.85: return "↓ overvalued"
    return "≈ fair value"


def future_value(pv: float, r: float, t: int) -> float:
    """Future value: FV = PV × (1 + r)^t."""
    return pv * (1 + r) ** t


def calc_cagr(current: float, target: float, years: int) -> Optional[float]:
    """Required CAGR to grow `current` to `target` over `years`."""
    if current <= 0 or target <= current or years <= 0:
        return None
    return min((target / current) ** (1.0 / years) - 1.0, 5.0) # Cap at 500%


def calc_monthly_pmt(current: float, target: float, years: int, annual_rate: float,) -> float:
    """Monthly contribution so that current + PMT stream reaches target."""
    if years <= 0:
        return 0.0
    rate = safe_float(annual_rate, default=0.0)
    n = years * 12
    r = (1 + rate) ** (1 / 12) - 1
    remaining = target - current * (1 + r) ** n
    if remaining <= 0:
        return 0.0
    if r == 0:
        return remaining / n
    return remaining * r / ((1 + r) ** n - 1)


def portfolio_beta(prices: pd.Series, betas: pd.Series) -> float:
    """Share-price-weighted average beta: β_p = Σ(wᵢ × βᵢ), wᵢ = priceᵢ / Σprice."""
    if prices.empty: return 0.0
    total = prices.sum()
    if total <= 0: return 0.0
    weights = prices / total
    filled_betas = betas.fillna(1.0).astype(float)
    return float((weights * filled_betas).sum())



# ---Goal eval---

def goal_status(current: float, target: float, years: int, required_rate: Optional[float]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Evaluate whether the user's financial goal is realistic.
    Returns status as one of 'success' | 'warning' | 'error' | 'info' | None.
    """
    if current <= 0 and target > 0:
        return ("info",
                "Add portfolio stocks to calculate the required return.",
                "Додайте акції портфелю для розрахунку необхідної дохідності.")
    if current > 0 and math.isclose(current, target):
        return ("success",
                "Your portfolio equals your target exactly. Consider keeping it under the mattress.",
                "Ваш портфель рівно дорівнює цілі. Може, краще під матрац?")
    if current > 0 and current > target:
        return ("warning",
                f"Your portfolio (${current:,.0f}) already exceeds your target (${target:,.0f}). "
                f"Maybe set a higher goal?",
                f"Ваш портфель (${current:,.0f}) вже перевищує ціль (${target:,.0f}). "
                f"Можливо, варто поставити вищу ціль?")
 
    if required_rate is None:
        return (None, None, None)
    if required_rate > 0.5:
        return ("error",
                f"Required CAGR {required_rate:.0%} — not realistic. Reduce target, extend horizon, or add capital.",
                f"Потрібний CAGR {required_rate:.0%} — нереалістично. Зменшіть ціль або збільшіть горизонт.")
    if years == 1 and required_rate > 0.15:
        return ("warning",
                f"1-year horizon with {required_rate:.0%} required return is high-risk.",
                f"1-річний горизонт з {required_rate:.0%} — високий ризик.")
    if required_rate > 0.25:
        return ("warning",
                f"Required CAGR {required_rate:.0%} — ambitious. S&P 500 averages ~10%/yr historically.",
                f"Потрібний CAGR {required_rate:.0%} — амбітно. S&P 500 в середньому ~10%/рік.")
    return (None, None, None)