"""
Configuration constants for Stock Scorer.
"""

# ---Gemini AI---
# Paste your key here
# Get a free key at https://aistudio.google.com/api-keys
GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-2.5-flash"

# ---Market constants (used by CAPM, Sharpe, DDM)---
RF = 0.037        # risk-free rate
RM_RF = 0.078     # equity risk premium
SIGMA_M = 0.195   # market standard deviation

# ---Cache---
CACHE_TTL = 60 * 30   # 30 min cache for Yahoo Finance