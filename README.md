# Stock Scorer

Веб-застосунок для аналізу та ранжування акцій за фундаментальними показниками з використанням формул інвестиційного менеджменту.

---

## Що це таке

Stock Scorer — це інструмент який допомагає підібрати акції для інвестування. Ви обираєте стратегію, вказуєте бюджет і ціль — застосунок завантажує реальні дані з Yahoo Finance, розраховує скори за формулами курсу і показує топ акцій з проекцією дохідності та AI аналізом.

---

## Файли проекту

```
invest/
├── app.py            — головний файл, запускається через streamlit
├── logic.py          — всі формули, розрахунки, дані з API
├── data.py           — статичний каталог: тікери, сектори, фактори, стратегії
├── config.py         — глобальні константи: API ключ, ставки, кеш
├── requirements.txt  — список бібліотек для встановлення
└── README.md         — цей файл
```

### Що робить кожен файл

**app.py** — основний файл застосунку. Тут описано весь інтерфейс: бічна панель з налаштуваннями, таблиця рейтингу, картки акцій, калькулятор цілі та AI аналіз. Для запуску потрібен саме цей файл.

**logic.py** — вся математика і логіка. Тут реалізовано 6 формул курсу: CAPM, Sharpe ratio, DDM, майбутня вартість (FV), CAGR і бета портфелю. Також тут: завантаження даних з yfinance, відбір кандидатів, нормалізація, обробка граничних випадків.

**data.py** — статичні дані: каталог тікерів, мапа секторів, визначення факторів і стратегій, двомовні підказки. Редагуйте тут якщо хочете додати акцію або змінити стратегію.

**config.py** — налаштування: GEMINI_API_KEY, GEMINI_MODEL, ставки RF/RM_RF/SIGMA_M (для CAPM/Sharpe), CACHE_TTL.

---

## Як запустити

### 1. Встановити залежності

```bash
pip install -r requirements.txt
```

### 2. Вставити API ключ Gemini

Відкрий `config.py` і знайди рядок:

```python
GEMINI_API_KEY = ""
```

Вставте свій ключ між лапками. Альтернативно — встановіть змінну середовища `GEMINI_API_KEY`. Ключ можна отримати безкоштовно на [aistudio.google.com](https://aistudio.google.com/api-keys).

### 3. Запустити

```bash
python3 -m streamlit run app.py
```

Streamlit відкриє браузер автоматично. Якщо ні — перейди на `http://localhost:8501`.

---

## Як користуватися

**Крок 1 — Ваші акції** (необов'язково)
Додайте акції які вже маєте (портфель) або які розглядаєте (watchlist). Можна нічого не обирати — система підбере топ автоматично.

**Крок 2 — Стратегія**
Оберіть одну з 5 стратегій або налаштуйте ваги факторів вручну через слайдери.

**Крок 3 — Ціль** (необов'язково)
Вкажіть бажану суму і горизонт — застосунок порахує необхідну річну дохідність і щомісячний внесок.

**Крок 4 — Запустити аналіз**
Натисніть кнопку. Застосунок завантажить дані, розрахує скори і покаже результати.

---

## Формули курсу які використовуються

| Формула | Запис | Лекція |
|---|---|---|
| CAPM | r = rf + β × (rm − rf) | Лекція 9 |
| Sharpe ratio | S = (r − rf) / σ | Лекція 9 |
| DDM (Gordon) | P = DIV₁ / (r − g) | Лекція 4 |
| Майбутня вартість | FV = PV × (1 + r)^t | Лекція 2 |
| CAGR | CAGR = (FV/PV)^(1/t) − 1 | Лекція 2 |
| Beta портфелю | β_p = Σ(wᵢ × βᵢ) | Лекція 9 |

---
---

# Stock Scorer (English)

A web app for analysing and ranking stocks using fundamental investment metrics and course formulas.

---

## What it does

Stock Scorer helps you pick stocks for investment. Choose a strategy, set a budget and goal — the app pulls real data from Yahoo Finance, calculates scores using course formulas, and shows a ranked top list with return projections and AI analysis.

---

## Project files

```
invest/
├── app.py            — main file, launched via streamlit
├── logic.py          — all formulas, calculations, API data
├── data.py           — static catalog: tickers, sectors, factors, strategies
├── config.py         — global constants: API key, rates, cache
├── requirements.txt  — list of libraries to install
└── README.md         — this file
```

### What each file does

**app.py** — the main app file. Contains the entire interface: sidebar with settings, ranking table, stock cards, goal calculator and AI analysis. This is the file you run.

**logic.py** — all the math and business logic. Implements 6 course formulas: CAPM, Sharpe ratio, DDM, Future Value, CAGR and Portfolio Beta. Also handles: yfinance data fetching, candidate selection, normalisation, edge case handling.

**data.py** — static content: ticker catalog, sector mapping, factor and strategy definitions, bilingual help tooltips. Edit here when you want to add a stock or change a strategy.

**config.py** — settings: GEMINI_API_KEY, GEMINI_MODEL, RF / RM_RF / SIGMA_M rates (for CAPM/Sharpe), CACHE_TTL.

---

## How to run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add your Gemini API key

Open `config.py` and paste your API key:

```python
GEMINI_API_KEY = ""
```

Paste your key between the quotes. Alternatively, set the `GEMINI_API_KEY` environment variable. Get a free key at [aistudio.google.com](https://aistudio.google.com/api-keys).

### 3. Run

```bash
python3 -m streamlit run app.py
```

Streamlit will open a browser automatically. If not — go to `http://localhost:8501`.

---

## How to use

**Step 1 — Your stocks** (optional)
Add stocks you already own (portfolio) or are considering (watchlist). You can skip this — the system will auto-select the top stocks.

**Step 2 — Strategy**
Pick one of 5 strategy presets or adjust factor weights manually with sliders.

**Step 3 — Goal** (optional)
Enter a target amount and time horizon — the app calculates the required annual return and monthly contribution.

**Step 4 — Run analysis**
Click the button. The app fetches data, calculates scores and displays results.

---

## Course formulas used

| Formula | Expression | Lecture |
|---|---|---|
| CAPM | r = rf + β × (rm − rf) | Lecture 9 |
| Sharpe ratio | S = (r − rf) / σ | Lecture 9 |
| DDM (Gordon) | P = DIV₁ / (r − g) | Lecture 4 |
| Future Value | FV = PV × (1 + r)^t | Lecture 2 |
| CAGR | CAGR = (FV/PV)^(1/t) − 1 | Lecture 2 |
| Portfolio Beta | β_p = Σ(wᵢ × βᵢ) | Lecture 9 |
