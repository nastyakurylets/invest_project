"""
app.py — Stock Scorer Streamlit UI.
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from data import CATALOG, FACTORS, STRATEGIES, FACTOR_HELP, SECTOR_TICKERS
from config import GEMINI_MODEL
from logic import (
    fetch_factors,
    pick_candidates,
    normalize,
    capm_return,
    sharpe_ratio,
    ddm_price,
    ddm_signal,
    future_value,
    calc_cagr,
    calc_monthly_pmt,
    goal_status,
    portfolio_beta,
    get_gemini_client,
)

_OPTS: list[str] = [f"{t} — {n}" for t, n in sorted(CATALOG.items())]


def _parse(opts: list[str]) -> list[str]:
    """Strip the company-name suffix from multiselect entries"""
    return sorted({o.split(" — ")[0].strip() for o in opts if o.strip()})


# ---SIDEBAR---

def _sidebar_language() -> bool:
    """Language radio"""
    lang = st.radio(
        "Language",
        ["English", "Українська"],
        horizontal=True,
        key="lang",
    )
    return lang == "Українська"


def _sidebar_stocks(ua: bool) -> tuple[list[str], list[str]]:
    """Portfolio + watchlist multiselects"""
    st.header("1. Your stocks" if not ua else "1. Ваші акції")

    portfolio_sel = st.multiselect(
        "Portfolio — stocks you own" if not ua else "Портфель — акції які маєш",
        options=_OPTS,
        default=[],
        placeholder="Type ticker or company name…",
        help=("Used for the goal calculator."
              if not ua else "Використовується для калькулятора цілі."),
        key="portfolio_sel",
    )
    owned_none = st.checkbox(
        "I have no stocks / skip" if not ua else "Немає акцій / пропустити",
        key="owned_none",
    )

    watchlist_sel = st.multiselect(
        "Watchlist — stocks you're considering"
        if not ua else "Watchlist — розглядаю до купівлі",
        options=_OPTS,
        default=[],
        placeholder="Type ticker or company name…",
        help=("Guaranteed to appear in the top-N."
              if not ua else "Гарантовано у топі."),
        key="watchlist_sel",
    )
    watch_none = st.checkbox(
        "No watchlist / skip" if not ua else "Немає watchlist / пропустити",
        key="watch_none",
    )

    portfolio = [] if owned_none else _parse(portfolio_sel)
    watchlist = [] if watch_none else _parse(watchlist_sel)
    return portfolio, watchlist


def _sidebar_strategy(ua: bool) -> tuple[str, dict[str, float]]:
    """Strategy selectbox + manual-weights expander"""
    st.header("2. Strategy" if not ua else "2. Стратегія")

    strategy_name = st.selectbox(
        "Preset" if not ua else "Стратегія",
        list(STRATEGIES.keys()),
        key="strategy_name",
    )
    strat = STRATEGIES[strategy_name]
    st.caption(strat["desc_ua"] if ua else strat["desc_en"])

    is_manual = strat["weights"] is None
    preset_w = strat["weights"] or {}

    if st.session_state.get("_prev_strategy") != strategy_name:
        for k in FACTORS:
            st.session_state.pop(f"w_{k}", None)
        st.session_state["_prev_strategy"] = strategy_name

    if not is_manual:
        st.caption(
            "Sliders show this preset's weights — disabled. "
            "Choose '(none — manual)' to edit."
            if not ua else
            "Слайдери показують ваги цієї стратегії — заблоковано. "
            "Оберіть «(none — manual)» щоб редагувати."
        )

    with st.expander(
        "Factor weights" if not ua else "Ваги факторів",
        expanded=is_manual,
    ):
        weights: dict[str, float] = {}
        for key, meta in FACTORS.items():
            initial = float(preset_w.get(key, meta["default_weight"]))
            weights[key] = st.slider(
                meta["label"],
                min_value=0.0,
                max_value=5.0,
                value=initial,
                step=0.1,
                help=FACTOR_HELP[key][1] if ua else FACTOR_HELP[key][0],
                disabled=not is_manual,
                key=f"w_{key}",
            )

    return strategy_name, weights


def _sidebar_goal(ua: bool) -> tuple[bool, int, int, int]:
    """Financial goal inputs"""
    st.header("3. Goal (optional)" if not ua else "3. Ціль (необов'язково)")
    use_goal = st.checkbox(
        "Set a financial goal" if not ua else "Встановити фінансову ціль",
        value=False,
        key="use_goal",
    )
    if use_goal:
        target_sum = st.number_input(
            "Target amount ($)" if not ua else "Бажана сума ($)",
            min_value=500, value=20_000, step=1_000,
            key="target_sum",
        )
        invest_years = st.slider(
            "Horizon (years)" if not ua else "Горизонт (роки)",
            1, 30, 7,
            key="invest_years",
        )
        budget = st.number_input(
            "New investment budget ($)" if not ua else "Бюджет ($)",
            min_value=100, value=5_000, step=500,
            key="budget",
        )
    else:
        target_sum, invest_years, budget = 20_000, 7, 5_000

    return use_goal, target_sum, invest_years, budget



# ---PIPELINE---

def _run_analysis(portfolio: list[str], watchlist: list[str], strategy_name: str, weights: dict[str, float], top_n: int) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Pick candidates → fetch factors → normalize → score → filter"""
    strat = STRATEGIES[strategy_name]

    # 1. Choose tickers
    candidates = pick_candidates(watchlist, portfolio, strategy_name, top_n)
    rows = [fetch_factors(t) for t in candidates]
    df = pd.DataFrame(rows).set_index("ticker")
    df = df[df["price"] > 0]
    if df.empty:
        return df, pd.DataFrame(), []

    # 2. Per-factor normalised scores → score_df
    score_df = pd.DataFrame(index=df.index)
    for key, meta in FACTORS.items():
        if key in df.columns:
            score_df[key] = normalize(df[key], meta["higher_better"])

    # 3. Composite weighted score + rank
    total_weight = sum(weights.values())
    composite = sum(
        score_df[k] * (weights[k] / total_weight)
        for k in FACTORS if k in score_df.columns
    )
    df["score"] = composite
    df["rank"] = df["score"].rank(ascending=False, method="min").astype(int)

    # 4. Owned / Watchlist — column for display
    def _status(t: str) -> str:
        if t in portfolio: return "Owned"
        if t in watchlist: return "Watchlist"
        return "—"
    df["status"] = df.index.map(_status)

    # 5. Strategy filters: sector first, then beta cap
    pool = df.copy()
    if strat["sectors"]:
        sector_flat: list[str] = []
        for s in strat["sectors"]:
            sector_flat.extend(SECTOR_TICKERS.get(s, []))
        sf = pool[pool.index.isin(sector_flat)]
        if not sf.empty:
            pool = sf
    bf = pool[pool["beta"].fillna(99) <= strat["beta_max"]]
    if not bf.empty:
        pool = bf
    pool = pool.sort_values("score", ascending=False)

    # 6. Top list — watchlist tickers guaranteed first
    top_tickers: list[str] = [t for t in watchlist if t in df.index]
    for t in pool.index:
        if len(top_tickers) >= top_n:
            break
        if t not in top_tickers:
            top_tickers.append(t)

    return df, score_df, top_tickers


def _enrich_top_df(top_df: pd.DataFrame, budget: int, invest_years: int) -> pd.DataFrame:
    """Add CAPM, Sharpe, DDM (price + signal), shares, invested, projected FV, gain % columns"""
    if top_df.empty:
        return top_df

    df = top_df.copy()
    df["exp_return"] = df["beta"].apply(capm_return)
    df["sharpe"]     = df.apply(
        lambda r: sharpe_ratio(r["exp_return"], r["beta"]), axis=1
    )
    df["ddm_price"]  = df.apply(
        lambda r: ddm_price(r["forward_div"], r["roe"], r["exp_return"]), axis=1
    )
    df["ddm_signal"] = df.apply(
        lambda r: ddm_signal(r["ddm_price"], r["price"]), axis=1
    )

    df["shares"] = (budget / df["price"]).apply(math.floor)
    df = df[df["shares"] > 0]
    if df.empty:
        return df

    df["invested"]   = df["shares"] * df["price"]

    df["proj_value"] = df["invested"] * (1 + df["exp_return"]) ** invest_years
    df["gain_pct"]   = (df["proj_value"] / df["invested"] - 1) * 100
    return df



# ---DISPLAY BLOCKS---

def _show_intro(ua: bool) -> None:
    """Welcome panel"""
    if ua:
        st.info(
            "Налаштуйте параметри у бічній панелі та натисніть "
            "**Запустити аналіз**."
        )
        st.markdown(
            """
**Як це працює:**

**1 · Ваші акції** — додайте акції які вже маєте (портфель) та/або
які розглядаєте (watchlist). Обидва поля необов'язкові. Watchlist
акції гарантовано у топі.

**2 · Стратегія** — оберіть одну з 5 стратегій або налаштуйте ваги
вручну. Кожна стратегія фільтрує по секторах і обмежує бету.

**3 · Ціль** — необов'язково. Введіть бажану суму і горизонт —
порахується CAGR і щомісячний внесок.

**4 · Запустити аналіз** — завантажуються дані до 10 акцій,
розраховується Score, CAPM, Sharpe, DDM і бета портфелю.
            """
        )
    else:
        st.info(
            "Configure your preferences in the sidebar, then click "
            "**Run analysis**."
        )
        st.markdown(
            """
**How it works:**

**1 · Your stocks** — add stocks you own (portfolio) and/or are
considering (watchlist). Both are optional. Watchlist stocks are
guaranteed to appear in the top-N.

**2 · Strategy** — pick one of 5 presets or set weights manually.
Each strategy filters by sector and caps beta.

**3 · Goal** — optional. Enter a target amount and horizon —
the app calculates required CAGR and monthly contribution.

**4 · Run analysis** — fetches up to 10 stocks, computes Score,
CAPM return, Sharpe ratio, DDM fair price, and portfolio beta.
            """
        )


def _show_ranking(top_df: pd.DataFrame, score_df: pd.DataFrame, ua: bool, top_n: int, strategy_name: str) -> None:
    """Top-N table with score progress bars + per-factor scores expander"""
    st.subheader("Ranking" if not ua else "Рейтинг акцій")
    st.caption(
        f"Top-{top_n} · Strategy: **{strategy_name}** · "
        + (
            "Score = weighted blend of factors · CAPM for expected return · "
            "Lower beta and P/E is better · Higher ROE and growth is better"
            if not ua else
            "Score = зважена суміш факторів · CAPM для дохідності · "
            "Нижча бета і P/E — краще · Вищий ROE і зростання — краще"
        )
    )

    cols_wanted = [
        "rank", "name", "score", "status", "beta",
        "revenue_growth", "pe_ratio", "roe", "div_yield", "sector",
    ]
    cols = [c for c in cols_wanted if c in top_df.columns]
    display = top_df.sort_values("score", ascending=False)[cols].copy()

    # Decimals → percentage for display only.
    if "revenue_growth" in display.columns:
        display["revenue_growth"] = display["revenue_growth"] * 100
    if "roe" in display.columns:
        display["roe"] = display["roe"] * 100

    st.dataframe(
        display,
        use_container_width=True,
        column_config={
            "rank":           st.column_config.NumberColumn("Rank", format="%d"),
            "name":           st.column_config.TextColumn("Name"),
            "score":          st.column_config.ProgressColumn(
                                  "Score", min_value=0.0, max_value=1.0, format="%.3f"),
            "status":         st.column_config.TextColumn("Status"),
            "beta":           st.column_config.NumberColumn("Beta", format="%.2f"),
            "revenue_growth": st.column_config.NumberColumn("Rev growth %", format="%.2f"),
            "pe_ratio":       st.column_config.NumberColumn("P/E", format="%.2f"),
            "roe":            st.column_config.NumberColumn("ROE %", format="%.2f"),
            "div_yield":      st.column_config.NumberColumn("Div yield %", format="%.2f"),
            "sector":         st.column_config.TextColumn("Sector"),
        },
    )

    with st.expander(
        "Per-factor normalized scores (0–1)"
        if not ua else "Скори по факторах (0–1)"
    ):
        idx = [t for t in top_df.index if t in score_df.index]
        st.dataframe(score_df.loc[idx].round(3), use_container_width=True)


def _show_goal_calc(current_value: float, target_sum: int, invest_years: int, required_rate: float | None, monthly_pmt: float | None, ua: bool) -> None:
    """Five metric cards + status box"""
    st.subheader("Goal calculator" if not ua else "Калькулятор цілі")
    st.caption(
        "Required annual return and monthly contribution to reach your target."
        if not ua else
        "Необхідна річна дохідність та щомісячний внесок для досягнення цілі."
    )

    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric(
        "Current portfolio" if not ua else "Поточний портфель",
        f"${current_value:,.0f}" if current_value else "—",
    )
    g2.metric("Target" if not ua else "Ціль", f"${target_sum:,.0f}")
    g3.metric(
        "Horizon" if not ua else "Горизонт",
        f"{invest_years} yr" if not ua else f"{invest_years} р.",
    )
    g4.metric(
        "Required CAGR" if not ua else "Потрібний CAGR",
        f"{required_rate:.1%}" if required_rate is not None else "—",
        help=("Annual return needed to reach your target."
              if not ua else "Річна дохідність для досягнення цілі."),
    )
    g5.metric(
        "Monthly contribution" if not ua else "Внесок/місяць",
        f"${monthly_pmt:,.0f}" if monthly_pmt else "—",
        help=("Extra monthly investment needed."
              if not ua else "Додатковий щомісячний внесок."),
    )

    status_type, msg_en, msg_ua = goal_status(
        current_value, float(target_sum), int(invest_years), required_rate
    )
    msg = msg_ua if ua else msg_en
    if status_type == "success": st.success(msg)
    elif status_type == "warning": st.warning(msg)
    elif status_type == "error":   st.error(msg)
    elif status_type == "info":    st.info(msg)


def _show_top_picks(top_df: pd.DataFrame, portfolio: list[str], watchlist: list[str], use_goal: bool, invest_years: int, ua: bool, strategy_name: str) -> None:
    """Top-N stock cards"""
    st.subheader(
        f"Top-{len(top_df)} picks" if not ua else f"Топ-{len(top_df)} акцій"
    )
    if watchlist:
        st.caption(
            f"Watchlist ({', '.join(watchlist)}) guaranteed in top · "
            f"Strategy: **{strategy_name}**"
            if not ua else
            f"Watchlist ({', '.join(watchlist)}) гарантовано у топі · "
            f"Стратегія: **{strategy_name}**"
        )
    else:
        st.caption(
            f"Top by score · Strategy: **{strategy_name}**"
            if not ua else
            f"Топ за скором · Стратегія: **{strategy_name}**"
        )

    sorted_df = top_df.sort_values("score", ascending=False)
    cols_per_row = 3

    for chunk_start in range(0, len(sorted_df), cols_per_row):
        cols = st.columns(cols_per_row)
        chunk = sorted_df.iloc[chunk_start:chunk_start + cols_per_row]
        for col, (ticker, row) in zip(cols, chunk.iterrows()):
            with col, st.container(border=True):
                score = float(row["score"])
                ddm_s = row["ddm_signal"]

                # Buy / Hold / Avoid verdict
                if score > 0.55 or ddm_s == "↑ undervalued":
                    verdict = ":green-background[**BUY**]" if not ua else ":green-background[**КУПИТИ**]"
                elif score < 0.30:
                    verdict = ":red-background[**AVOID**]" if not ua else ":red-background[**УНИКАТИ**]"
                else:
                    verdict = ":orange-background[**HOLD**]" if not ua else ":orange-background[**ТРИМАТИ**]"

                # Owned / Watchlist tag
                if ticker in portfolio:
                    tag = " · :blue-background[OWNED]" if not ua else " · :blue-background[ПОРТФЕЛЬ]"
                elif ticker in watchlist:
                    tag = " · :gray-background[WATCH]" if not ua else " · :gray-background[ВОТЧЛІСТ]"
                else:
                    tag = ""

                # Ticker stays prominent (h3); verdict + tag drop to body size.
                st.markdown(f"### `{ticker}`")
                st.markdown(f"{verdict}{tag}")
                st.caption(f"{row['name']} · {row['sector']}")

                bv = float(row["beta"]) if pd.notna(row["beta"]) else 0.0
                st.markdown(
                    f"**CAPM** {row['exp_return']:.1%} &nbsp;·&nbsp; "
                    f"**Sharpe** {row['sharpe']:.2f} &nbsp;·&nbsp; "
                    f"**β** {bv:.2f}"
                )

                ddm_p = row["ddm_price"]
                ddm_lbl = "DDM" if not ua else "DDM ціна"
                if ddm_p and pd.notna(ddm_p):
                    st.caption(f"{ddm_lbl}: ${ddm_p:,.0f} · {ddm_s}")
                else:
                    st.caption(f"{ddm_lbl}: {ddm_s}")

                if use_goal:
                    fv_lbl = (f"in {invest_years} yr" if not ua
                              else f"за {invest_years} р.")
                    st.markdown(
                        f"**${row['proj_value']:,.0f}** "
                        f":gray[(+{row['gain_pct']:.0f}% · {fv_lbl})]"
                    )

                # Score progress bar
                st.progress(
                    min(max(score, 0.0), 1.0),
                    text=f"Score {score:.3f}",
                )


def _show_portfolio_summary(user_prices: pd.Series, user_betas: pd.Series, top_df: pd.DataFrame, ua: bool) -> None:
    """4 metric cards: Portfolio β, Avg CAPM, Avg Sharpe, DDM count"""
    st.subheader("Portfolio summary" if not ua else "Зведення портфелю")
    st.caption(
        "Portfolio β reflects YOUR holdings · CAPM/Sharpe/DDM are averages "
        "across the top picks."
        if not ua else
        "Бета портфелю — за вашими активами · CAPM/Sharpe/DDM — середні "
        "по топу."
    )

    port_beta = portfolio_beta(user_prices, user_betas)
    has_portfolio = not user_prices.empty

    if top_df.empty:
        avg_capm = avg_sharpe = 0.0
        ddm_under = 0
    else:
        avg_capm   = float(top_df["exp_return"].mean())
        avg_sharpe = float(top_df["sharpe"].mean())
        ddm_under  = int((top_df["ddm_signal"] == "↑ undervalued").sum())

    if not has_portfolio:
        beta_d = ("no holdings" if not ua else "без активів")
    elif port_beta < 0.8:
        beta_d = ("↓ defensive" if not ua else "↓ захисний")
    elif port_beta > 1.2:
        beta_d = ("↑ aggressive" if not ua else "↑ агресивний")
    else:
        beta_d = ("≈ market" if not ua else "≈ ринок")

    capm_d   = (("↑ high" if not ua else "↑ висока") if avg_capm > 0.15
                else ("moderate" if not ua else "помірна"))
    if avg_sharpe > 0.6:
        sharpe_d = ("↑ efficient" if not ua else "↑ ефективний")
    elif avg_sharpe < 0.3:
        sharpe_d = ("low" if not ua else "низький")
    else:
        sharpe_d = ("ok" if not ua else "норм")
    ddm_d = ((f"{ddm_under} picks" if not ua else f"{ddm_under} кандидатів")
             if ddm_under > 0 else None)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric(
        "Your portfolio β" if not ua else "Бета портфелю",
        f"{port_beta:.2f}" if has_portfolio else "—",
        delta=beta_d,
        help=("β<1 = less volatile · β>1 = more volatile · β=1 = tracks market"
              if not ua else
              "β<1 = менш волатильний · β>1 = більш волатильний · β=1 = слідує ринку"),
    )
    s2.metric(
        "Avg CAPM return" if not ua else "Серед. CAPM",
        f"{avg_capm:.1%}",
        delta=capm_d,
        help=("r = rf + β×(rm−rf) · across top picks"
              if not ua else
              "r = rf + β×(rm−rf) · по топ-вибірці"),
    )
    s3.metric(
        "Avg Sharpe" if not ua else "Серед. Sharpe",
        f"{avg_sharpe:.2f}",
        delta=sharpe_d,
        help=("(r−rf)/σ · >0.5 good · >1.0 excellent · <0.3 poor"
              if not ua else
              "(r−rf)/σ · >0.5 добре · >1.0 відмінно · <0.3 погано"),
    )
    s4.metric(
        "DDM undervalued" if not ua else "DDM недооцінених",
        f"{ddm_under}/{len(top_df)}",
        delta=ddm_d,
        help=("P=DIV/(r−g) · fair value > market price by 15%+"
              if not ua else
              "P=DIV/(r−g) · справедлива ціна > ринкова на 15%+"),
    )


def _show_ai_analysis(
    top_df: pd.DataFrame,
    portfolio_loaded: list[str],
    watchlist_loaded: list[str],
    current_value: float,
    target_sum: int,
    invest_years: int,
    use_goal: bool,
    required_rate: float | None,
    monthly_pmt: float | None,
    port_beta: float,
    strategy_name: str,
    ua: bool,
) -> None:
    """Gemini analysis"""
    st.subheader("AI analysis — Gemini")
    st.caption(
        "Explains scores, assesses goal feasibility, and gives actionable "
        "recommendations."
        if not ua else
        "Пояснює скори, оцінює реалістичність цілі, надає рекомендації."
    )

    if not st.button(
        "Run AI analysis" if not ua else "Запустити AI аналіз",
        key="run_ai",
    ):
        return

    client = get_gemini_client()
    if client is None:
        st.error(
            "Gemini API not configured. Set GEMINI_API_KEY in config.py "
            "or as the GEMINI_API_KEY environment variable."
            if not ua else
            "Gemini API не налаштовано. Встановіть GEMINI_API_KEY у "
            "config.py або як змінну середовища."
        )
        return

    strat = STRATEGIES[strategy_name]
    top5 = top_df.sort_values("score", ascending=False).head(5)

    top_str = "\n".join(
        f"  - {t} [{r['status']}] Score={r['score']:.2f} "
        f"β={(r['beta'] if pd.notna(r['beta']) else 0):.2f} "
        f"CAPM={r['exp_return']:.1%} Sharpe={r['sharpe']:.2f} "
        f"DDM={('${:,.0f}'.format(r['ddm_price']) if r['ddm_price'] and pd.notna(r['ddm_price']) else 'N/A')} "
        f"({r['ddm_signal']}) "
        f"ROE={(r['roe'] if pd.notna(r['roe']) else 0):.1%} "
        f"P/E={(r['pe_ratio'] if pd.notna(r['pe_ratio']) else 0):.1f} "
        f"Sector={r['sector']}"
        for t, r in top5.iterrows()
    )
    proj_str = (
        "\n".join(
            f"  - {t}: ${r['invested']:,.0f} → FV ${r['proj_value']:,.0f} "
            f"(+{r['gain_pct']:.0f}%, CAPM {r['exp_return']:.1%} p.a.)"
            for t, r in top_df.iterrows()
        )
        if use_goal else "Goal calculator not enabled."
    )

    rate_str  = f"{required_rate:.1%}" if required_rate else "N/A"
    topup_str = f"${monthly_pmt:,.0f}/month" if monthly_pmt else "N/A"
    lang_instr = "Respond in Ukrainian." if ua else "Respond in English."
    goal_str = (
        f"${target_sum:,.0f} in {invest_years} years"
        if use_goal else "not set"
    )

    prompt = f"""You are a sharp, direct investment advisor. No academic tone. {lang_instr}

=== CLIENT ===
Strategy: {strategy_name} — {strat["desc_en"]}
Portfolio: ${current_value:,.0f} | Goal: {goal_str}
Required CAGR: {rate_str} | Monthly contribution: {topup_str}
Portfolio Beta: {port_beta:.2f}
Owned: {portfolio_loaded or "none"} | Watchlist: {watchlist_loaded or "none"}

=== TOP-5 ===
{top_str}

=== PROJECTION ===
{proj_str}

FORMAT:
**Bottom line:** [One punchy sentence — the single most important thing this investor needs to hear.]

---
**Your top picks**
One bullet per stock: TICKER — Buy/Hold/Avoid. [Why, referencing CAPM, Sharpe, DDM, score.]

---
**Watch out for**
3 short bullets: biggest risks — concentration, beta, overvaluation, diversification.

---
**3 actions to take now**
Numbered. Specific. Buy/trim/monitor.

No long paragraphs. No academic language. Be direct.
"""
    with st.spinner(
        "Generating analysis…" if not ua else "Gemini аналізує…"
    ):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt
            )
            st.markdown(resp.text)
        except Exception as e:
            st.error(f"Gemini error: {e}")



# ---MAIN---

def main() -> None:
    st.set_page_config(page_title="Stock Scorer", layout="wide")
    st.title("Stock Scorer")
    st.caption("Investment Analysis Platform")

    with st.sidebar:
        ua = _sidebar_language()
        st.divider()
        portfolio, watchlist = _sidebar_stocks(ua)
        st.divider()
        strategy_name, weights = _sidebar_strategy(ua)
        st.divider()
        use_goal, target_sum, invest_years, budget = _sidebar_goal(ua)

        top_n = st.slider(
            "Top N stocks" if not ua else "Топ N акцій",
            min_value=5, max_value=10, value=10,
            key="top_n",
        )
        st.divider()

        goal_warning: tuple[str, str, str] | None = None
        if use_goal and budget >= target_sum:
            goal_warning = (
                "warning",
                "Your budget equals or exceeds the target — nothing to grow towards.",
                "Бюджет рівний або більший за ціль — нема куди зростати.",
            )
        if goal_warning:
            msg = goal_warning[2] if ua else goal_warning[1]
            (st.error if goal_warning[0] == "error" else st.warning)(msg)

        run = st.button(
            "Run analysis" if not ua else "Запустити аналіз",
            type="primary",
            use_container_width=True,
            disabled=(goal_warning is not None and goal_warning[0] == "error"),
        )

    if run:
        st.session_state["ran"] = True

    if not st.session_state.get("ran"):
        _show_intro(ua)
        return

    # Analysis flow
    if sum(weights.values()) == 0:
        st.warning(
            "All weights are zero — set at least one weight above 0."
            if not ua else
            "Всі ваги нульові — встановіть хоча б одну вагу вище 0."
        )
        return

    with st.spinner(
        "Fetching market data…" if not ua else "Завантаження ринкових даних…"
    ):
        df, score_df, top_tickers = _run_analysis(
            portfolio, watchlist, strategy_name, weights, top_n,
        )

    if df.empty:
        st.error(
            "Could not fetch data. Check your internet connection."
            if not ua else
            "Не вдалося завантажити дані. Перевірте підключення."
        )
        return

    top_df = df.loc[[t for t in top_tickers if t in df.index]].copy()
    top_df = _enrich_top_df(top_df, budget, invest_years)

    if top_df.empty:
        st.warning(
            ("Budget is too low — most stocks cost more than your budget."
             if budget < 50 else
             "No tickers match your strategy and budget.")
            if not ua else
            ("Бюджет занадто малий."
             if budget < 50 else
             "Немає акцій що відповідають стратегії та бюджету.")
        )
        return

    portfolio_loaded = [t for t in portfolio if t in df.index]
    watchlist_loaded = [t for t in watchlist if t in df.index]

    if portfolio_loaded:
        user_prices = df.loc[portfolio_loaded, "price"]
        user_betas  = df.loc[portfolio_loaded, "beta"]
        current_value = float(user_prices.sum())
    else:
        user_prices = pd.Series(dtype=float)
        user_betas  = pd.Series(dtype=float)
        current_value = 0.0

    port_beta = portfolio_beta(user_prices, user_betas)

    if use_goal:
        required_rate = calc_cagr(
            current_value, float(target_sum), int(invest_years)
        )
        monthly_pmt = (
            calc_monthly_pmt(current_value, float(target_sum),
                             int(invest_years), required_rate)
            if required_rate is not None else None
        )
    else:
        required_rate = None
        monthly_pmt   = None

    # Display blocks
    _show_ranking(top_df, score_df, ua, top_n, strategy_name)
    st.divider()

    if use_goal:
        _show_goal_calc(
            current_value, target_sum, invest_years,
            required_rate, monthly_pmt, ua,
        )
        st.divider()

    _show_top_picks(
        top_df, portfolio, watchlist, use_goal, invest_years,
        ua, strategy_name,
    )
    st.divider()

    _show_portfolio_summary(user_prices, user_betas, top_df, ua)
    st.divider()

    _show_ai_analysis(
        top_df, portfolio_loaded, watchlist_loaded,
        current_value, target_sum, invest_years, use_goal,
        required_rate, monthly_pmt, port_beta, strategy_name, ua,
    )


if __name__ == "__main__":
    main()