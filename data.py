"""
data.py — Static data for Stock Scorer.
"""

from __future__ import annotations

# ---Tickers---
# Ticker → company name
CATALOG: dict[str, str] = {
    # Technology
    "AAPL":  "Apple",            "MSFT":  "Microsoft",        "NVDA":  "NVIDIA",
    "AMD":   "AMD",              "INTC":  "Intel",            "QCOM":  "Qualcomm",
    "ORCL":  "Oracle",           "CRM":   "Salesforce",       "ADBE":  "Adobe",
    "SNOW":  "Snowflake",
    # Communication Services
    "GOOGL": "Alphabet",         "META":  "Meta",             "NFLX":  "Netflix",
    "DIS":   "Disney",           "T":     "AT&T",             "VZ":    "Verizon",
    "SPOT":  "Spotify",
    # Consumer Cyclical
    "TSLA":  "Tesla",            "AMZN":  "Amazon",           "SHOP":  "Shopify",
    "UBER":  "Uber",             "ABNB":  "Airbnb",           "DASH":  "DoorDash",
    "MCD":   "McDonald's",       "HD":    "Home Depot",
    # Consumer Defensive
    "KO":    "Coca-Cola",        "PEP":   "PepsiCo",          "PG":    "Procter & Gamble",
    "WMT":   "Walmart",          "COST":  "Costco",
    # Financial Services
    "JPM":   "JPMorgan",         "BAC":   "Bank of America",  "V":     "Visa",
    "MA":    "Mastercard",       "GS":    "Goldman Sachs",    "BRK-B": "Berkshire",
    "PYPL":  "PayPal",           "AXP":   "American Express",
    # Healthcare
    "UNH":   "UnitedHealth",     "LLY":   "Eli Lilly",        "PFE":   "Pfizer",
    "ABBV":  "AbbVie",           "JNJ":   "Johnson & Johnson",
    # Energy
    "XOM":   "ExxonMobil",       "CVX":   "Chevron",
}

# ---Ticker sectors---
# Sector name → list of tickers in that sector
SECTOR_TICKERS: dict[str, list[str]] = {
    "Technology":             ["AAPL", "MSFT", "NVDA", "AMD", "INTC", "QCOM", "ORCL", "CRM", "ADBE", "SNOW"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "T", "VZ", "SPOT"],
    "Consumer Cyclical":      ["TSLA", "AMZN", "SHOP", "UBER", "ABNB", "DASH", "MCD", "HD"],
    "Consumer Defensive":     ["KO", "PEP", "PG", "WMT", "COST"],
    "Financial Services":     ["JPM", "BAC", "V", "MA", "GS", "BRK-B", "PYPL", "AXP"],
    "Healthcare":             ["UNH", "LLY", "PFE", "ABBV", "JNJ"],
    "Energy":                 ["XOM", "CVX"],
    "Utilities":              [],
    "Real Estate":            [],
}


# SCORING MODEL

# ---Factors---
# Factor → {'label', 'higher_better', 'default_weight'}
FACTORS: dict[str, dict] = {
    "beta":           {"label": "Beta",           "higher_better": False, "default_weight": 1.0},
    "revenue_growth": {"label": "Revenue growth", "higher_better": True,  "default_weight": 3.0},
    "pe_ratio":       {"label": "P/E ratio",      "higher_better": False, "default_weight": 2.0},
    "roe":            {"label": "ROE",            "higher_better": True,  "default_weight": 2.0},
    "div_yield":      {"label": "Div yield",      "higher_better": True,  "default_weight": 0.0},
}

# ---Strategies---
# Strategy → {'weights', 'sectors', 'beta_max', 'desc_en', 'desc_ua'}
STRATEGIES: dict[str, dict] = {
    "(none — manual)": {
        "weights":  None,
        "sectors":  [],
        "beta_max": 99,
        "desc_en":  "Set factor weights manually with the sliders. Best if you have a specific investment thesis.",
        "desc_ua":  "Встановіть ваги факторів вручну через слайдери. Підходить якщо маєте власну інвестиційну ідею.",
    },
    "Capital Preservation": {
        "weights":  {"beta": 2.5, "revenue_growth": 0.5, "pe_ratio": 3.0, "roe": 2.0, "div_yield": 2.0},
        "sectors":  ["Consumer Defensive", "Utilities", "Financial Services", "Healthcare"],
        "beta_max": 1.2,
        "desc_en":  "Low volatility, dividend income, stable sectors. Prioritises safety over growth. Beta capped at 1.2.",
        "desc_ua":  "Низька волатильність, дивідендний дохід, стабільні сектори. Пріоритет — безпека. Бета обмежена 1.2.",
    },
    "Aggressive Growth": {
        "weights":  {"beta": 0.5, "revenue_growth": 5.0, "pe_ratio": 0.5, "roe": 3.0, "div_yield": 0.0},
        "sectors":  ["Technology", "Communication Services", "Consumer Cyclical"],
        "beta_max": 99,
        "desc_en":  "Maximum growth potential. High volatility — suited for long horizons and high risk tolerance.",
        "desc_ua":  "Максимальний потенціал зростання. Висока волатильність — для довгого горизонту і готовності до ризику.",
    },
    "Dividend Income": {
        "weights":  {"beta": 2.0, "revenue_growth": 1.0, "pe_ratio": 2.0, "roe": 4.5, "div_yield": 5.0},
        "sectors":  ["Financial Services", "Consumer Defensive", "Energy", "Utilities", "Real Estate"],
        "beta_max": 1.5,
        "desc_en":  "Passive income focus. Strongly weights dividend yield and ROE. Lower risk, steady cash flow.",
        "desc_ua":  "Фокус на пасивному доході. Акцент на дивідендній дохідності та ROE. Нижчий ризик.",
    },
    "Balanced": {
        "weights":  {"beta": 1.5, "revenue_growth": 2.5, "pe_ratio": 2.0, "roe": 2.5, "div_yield": 1.5},
        "sectors":  [],
        "beta_max": 99,
        "desc_en":  "Equal balance between growth and stability. No sector filter — searches the entire catalog.",
        "desc_ua":  "Рівний баланс між зростанням і стабільністю. Без фільтру секторів — шукає по всьому каталогу.",
    },
}


# UI TOOLTIPS

FACTOR_HELP: dict[str, tuple[str, str]] = {
    "beta": (
        "Beta measures how much a stock moves relative to the market. "
        "β=1 moves with market · β>1 more volatile · β<1 more stable. "
        "Higher weight = prefer low-beta (safer) stocks.",
        "Бета показує наскільки акція рухається відносно ринку. "
        "β=1 слідує ринку · β>1 більш волатильна · β<1 стабільніша. "
        "Вища вага = перевага акціям з низькою бетою.",
    ),
    "revenue_growth": (
        "Revenue growth = year-over-year increase in company sales. "
        "Higher growth = company is expanding. Higher weight = prefer fast-growing companies.",
        "Зростання виручки — приріст продажів рік до року. "
        "Вище зростання = компанія розширюється. Вища вага = перевага зростаючим компаніям.",
    ),
    "pe_ratio": (
        "P/E = stock price divided by earnings per share. "
        "Low P/E = stock may be cheap. Higher weight = prefer cheaper (lower P/E) stocks.",
        "P/E = ціна акції / прибуток на акцію. "
        "Низький P/E = акція може бути дешевою. Вища вага = перевага дешевшим акціям.",
    ),
    "roe": (
        "Return on Equity = net income / shareholders equity. "
        "Measures how efficiently management uses capital. Higher weight = prefer profitable companies.",
        "ROE = чистий прибуток / власний капітал. "
        "Показує ефективність використання капіталу. Вища вага = перевага прибутковим компаніям.",
    ),
    "div_yield": (
        "Dividend yield = annual dividend / stock price. "
        "Shows cash income per dollar invested. Higher weight = prefer high-dividend stocks.",
        "Дивідендна дохідність = річний дивіденд / ціна акції. "
        "Показує грошовий дохід на вкладений долар. Вища вага = перевага акціям з вищими дивідендами.",
    ),
}