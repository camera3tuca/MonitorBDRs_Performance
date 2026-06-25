import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import datetime
import sqlite3
import os
import glob
import logging
import altair as alt
import numpy as np
from collections import deque

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="MonitorBDRs · Performance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CSS PERSONALIZADO — design escuro/financeiro
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ── Fundo ── */
    .stApp { background-color: #0f1117; color: #e2e8f0; }

    /* ── Conteúdo principal ── */
    .main .block-container {
        padding: 1.5rem 1.25rem 3rem 1.25rem !important;
        max-width: 100% !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #161b27 !important;
        border-right: 1px solid #1e2535;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span { color: #94a3b8 !important; }

    /* ── KPI cards ── */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a2035 0%, #1e2535 100%);
        border: 1px solid #2a3548;
        border-radius: 14px;
        padding: 18px 16px 14px 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.35);
        min-height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    [data-testid="metric-container"] label {
        color: #64748b !important;
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.09em !important;
        text-transform: uppercase !important;
        white-space: normal !important;
        line-height: 1.3 !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        white-space: normal !important;
        word-break: break-all !important;
        overflow-wrap: anywhere !important;
        line-height: 1.4 !important;
        overflow: visible !important;
    }
    [data-testid="metric-container"] > div { overflow: visible !important; width: 100% !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] > div {
        overflow: visible !important;
        text-overflow: unset !important;
        white-space: normal !important;
    }
    [data-testid="stMetricDelta"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.8rem !important;
    }

    /* ── Títulos ── */
    h1 { color: #f1f5f9 !important; font-weight: 700 !important; font-size: 1.7rem !important;
         letter-spacing: -0.02em; margin-bottom: 0.25rem !important; }
    h2 { color: #cbd5e1 !important; font-weight: 600 !important; font-size: 1.15rem !important; }
    h3 { color: #94a3b8 !important; font-weight: 500 !important; }

    /* ── Dataframes ── */
    [data-testid="stDataFrame"] { border: 1px solid #1e2535 !important; border-radius: 10px !important; overflow: hidden; }
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { font-size: 0.82rem !important; }

    /* ── Divisores ── */
    hr { border-color: #1e2535 !important; margin: 1rem 0 !important; }

    /* ── Botões ── */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: white !important; border: none !important;
        border-radius: 10px !important; font-weight: 600 !important;
        font-size: 0.9rem !important; padding: 0.6rem 1.5rem !important; width: 100% !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        box-shadow: 0 4px 15px rgba(37,99,235,0.4) !important;
    }

    /* ── Alertas ── */
    .stAlert { border-radius: 10px !important; border-left-width: 4px !important; }

    /* ── Selectbox ── */
    .stSelectbox > div > div {
        background-color: #1a2035 !important; border-color: #2a3548 !important;
        color: #e2e8f0 !important; font-size: 0.9rem !important;
    }

    /* ── Upload ── */
    [data-testid="stFileUploadDropzone"] {
        background-color: #1a2035 !important;
        border: 2px dashed #2a3548 !important; border-radius: 10px !important;
    }

    /* ── Badges ── */
    .badge-pos { color: #10b981; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .badge-neg { color: #ef4444; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .badge-neu { color: #94a3b8; font-weight: 600; font-family: 'JetBrains Mono', monospace; }

    /* ── Caption ── */
    [data-testid="stCaptionContainer"] p { font-size: 0.78rem !important; color: #64748b !important; }

    /* ── Info box personalizado ── */
    .info-box {
        background: linear-gradient(135deg, #1a2035 0%, #1e2535 100%);
        border: 1px solid #2a3548; border-left: 4px solid #3b82f6;
        border-radius: 10px; padding: 14px 16px; margin: 8px 0;
        font-size: 0.88rem; color: #cbd5e1;
    }
    .warn-box {
        background: linear-gradient(135deg, #1a2035 0%, #1e2535 100%);
        border: 1px solid #2a3548; border-left: 4px solid #f59e0b;
        border-radius: 10px; padding: 14px 16px; margin: 8px 0;
        font-size: 0.88rem; color: #cbd5e1;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────
MAX_ATIVOS_PIZZA = 12
CDI_ANUAL_ESTIMADO = 0.1065   # CDI aprox. para benchmark (ajuste conforme necessário)

# ─────────────────────────────────────────────────────────────────────
# MAPA: nome completo nas notas Santander → ticker B3
# ─────────────────────────────────────────────────────────────────────
NOME_PARA_TICKER: dict[str, str] = {
    # ── Tecnologia EUA ──────────────────────────────────────────────────
    "ADOBE INC DRN":        "A1DB34",
    "ADVANCED MICR DRN":    "A1MD34",   # AMD
    "ADVANCED MICR DRN ED": "A1MD34",
    "AIRBNB INC DRN":       "A2BN34",
    "ALPHABET CL A DRN":    "GOGL35",
    "ALPHABET CL C DRN":    "GOGL34",
    "AMAZON DRN":           "AMZO34",
    "AMAZON DRN ED":        "AMZO34",
    "APPLE DRN":            "AAPL34",
    "APPLE DRN ED":         "AAPL34",
    "ARISTA NETW DRN":      "A1NW34",
    "ARROWHEAD PH DRN":     "A2RR34",
    "AUTODESK DRN":         "A1UT34",
    "BAIDU INC DRN":        "BIDU34",
    "BLOCK INC DRN":        "S2Q34",    # ex-Square
    "CLOUDFLARE DRN":       "N2ET34",
    "COINBASE DRN":         "C2OI34",
    "CROWDSTRIKE DRN":      "C2RW34",
    "DATADOG DRN":          "D2DO34",
    "DOCUSIGN DRN":         "D2CU34",
    "FORTINET DRN":         "F1TI34",
    "GDS HOLDINGS DRN":     "G1DS34",
    "INTEL DRN":            "ITLC34",
    "INTEL DRN ED":         "ITLC34",
    "LAM RESEARCH DRN":     "L1RC34",
    "META PLATFRM DRN":     "FBOK34",
    "META PLATFRM DRN ED":  "FBOK34",
    "MICRON TECHN DRN":     "MUTC34",
    "MICRON TECHN DRN ED":  "MUTC34",
    "MICROSOFT DRN":        "MSFT34",
    "MICROSOFT DRN ED":     "MSFT34",
    "NETFLIX INC DRN":      "NFLX34",
    "NETFLIX INC DRN ED":   "NFLX34",
    "NVIDIA CORP DRN":      "NVDC34",
    "NVIDIA CORP DRN ED":   "NVDC34",
    "ORACLE CORP DRN":      "ORCL34",
    "PALO ALTO DRN":        "P1AN34",
    "PAYPAL HLDG DRN":      "PYPL34",
    "PAYPAL HLDG DRN ED":   "PYPL34",
    "QUALCOMM DRN":         "Q1CO34",
    "QUALCOMM DRN ED":      "Q1CO34",
    "SALESFORCE DRN":       "C2RM34",
    "SERVICENOW DRN":       "N2OW34",
    "SHOPIFY INC DRN":      "S2HO34",
    "SHOPIFY INC DRN ED":   "S2HO34",
    "SNOWFLAKE DRN":        "S2NW34",
    "SPOTIFY TECH DRN":     "S2PO34",
    "TAIWANSMFAC DRN":      "TSMC34",
    "TAIWAN SMFAC DRN":     "TSMC34",
    "TAIWAN SMFAC DRN ED":  "TSMC34",
    "TESLA INC DRN":        "TSLA34",
    "TESLA INC DRN ED":     "TSLA34",
    "UNITY SOFTWR DRN":     "U2ST34",
    "UBER TECH DRN":        "U1BE34",
    "UBER TECH DRN ED":     "U1BE34",
    "WORKDAY DRN":          "W1DA34",
    "ZOOM VIDEO DRN":       "Z2OM34",
    # ── Financeiro EUA ──────────────────────────────────────────────────
    "AMERICAN EXP DRN":     "AXPB34",
    "AMERICAN EXP DRN ED":  "AXPB34",
    "BANK AMERICA DRN":     "BOAC34",
    "BANK AMERICA DRN ED":  "BOAC34",
    "BERKSHIRE A DRN":      "B1RK34",
    "BERKSHIRE B DRN":      "B2RK34",
    "BLACKROCK DRN":        "B1LK34",
    "CITIGROUP DRN":        "CTGP34",
    "CITIGROUP DRN ED":     "CTGP34",
    "GOLDMANSACHS DRN":     "GSGI34",
    "GOLDMANSACHS DRN ED":  "GSGI34",
    "HSBC HOLDING DRN":     "H1SB34",
    "HSBC HOLDING DRN ED":  "H1SB34",
    "ING GROEP DRN":        "INGG34",
    "ING GROEP DRN ED":     "INGG34",
    "JPMORGAN DRN":         "JPMC34",
    "JPMORGAN DRN ED":      "JPMC34",
    "MASTERCARD DRN":       "MSCD34",
    "MASTERCARD DRN ED":    "MSCD34",
    "MITSUBISHI U DRN":     "M1UF34",
    "MORGAN STAN DRN":      "MSBR34",
    "MORGAN STAN DRN ED":   "MSBR34",
    "NATWEST GROU DRN":     "N1WG34",
    "PAGSEGURO DRN":        "PAGS34",
    "SANTANDER DRN":        "BCSA34",
    "VISA INC DRN":         "VISA34",
    "VISA INC DRN ED":      "VISA34",
    "WELLS FARGO DRN":      "WFCO34",
    "WELLS FARGO DRN ED":   "WFCO34",
    # ── Consumo / Varejo ────────────────────────────────────────────────
    "BOOKING HLDG DRN":     "B1KN34",
    "COCA COLA DRN":        "COCA34",
    "COCA COLA DRN ED":     "COCA34",
    "COSTCO WHOLE DRN":     "C1ST34",
    "ESTEE LAUDER DRN":     "E1LC34",
    "LVMH MOET DRN":        "M1VL34",
    "MCDONALD'S DRN":       "MCDC34",
    "MCDONALDS DRN":        "MCDC34",
    "MCDONALDS DRN ED":     "MCDC34",
    "NIKE INC DRN":         "NIKE34",
    "NIKE INC DRN ED":      "NIKE34",
    "PROCTER GA DRN":       "PRCT34",
    "PROCTER GA DRN ED":    "PRCT34",
    "STARBUCKS DRN":        "SBUB34",
    "STARBUCKS DRN ED":     "SBUB34",
    "WAL MART DRN":         "WALM34",
    "WAL MART DRN ED":      "WALM34",
    # ── Saúde / Farmacêutica ────────────────────────────────────────────
    "ABBVIE INC DRN":       "A1BB34",
    "AMGEN INC DRN":        "A1MG34",
    "BIOGEN INC DRN":       "B1IO34",
    "BRISTOL-MYE DRN":      "B1MY34",
    "DEXCOM INC DRN":       "D2XC34",
    "EDWARDS LIFE DRN":     "E1DW34",
    "ELI LILLY DRN":        "L1LY34",
    "ILLUMINA DRN":         "I1LM34",
    "JOHNSON DRN":          "JNJB34",
    "JOHNSON DRN ED":       "JNJB34",
    "MEDTRONIC DRN":        "M1DT34",
    "MERCK & CO DRN":       "M1RK34",
    "MODERNA INC DRN":      "M2RN34",
    "PFIZER INC DRN":       "PFIZ34",
    "PFIZER INC DRN ED":    "PFIZ34",
    "REGENERON DRN":        "R1GN34",
    "UNITEDHEALTH DRN":     "U1HG34",
    "VERTEX PHARM DRN":     "V1RT34",
    # ── Indústria / Energia ─────────────────────────────────────────────
    "3M CO DRN":            "M1MM34",
    "BOEING DRN":           "BOEI34",
    "BOEING DRN ED":        "BOEI34",
    "CATERPILLAR DRN":      "CATP34",
    "CATERPILLAR DRN ED":   "CATP34",
    "CHEVRON DRN":          "CHVX34",
    "CHEVRON DRN ED":       "CHVX34",
    "DEERE & CO DRN":       "D1EE34",
    "EXXON MOBIL DRN":      "EXXO34",
    "EXXON MOBIL DRN ED":   "EXXO34",
    "GENERAL ELEC DRN":     "G1EC34",
    "GENERAL MOT DRN":      "GMCO34",
    "GENERAL MOT DRN ED":   "GMCO34",
    "HONEYWELL DRN":        "H1WL34",
    "LOCKHEED DRN":         "L1MT34",
    "RAYTHEON TE DRN":      "R1TN34",
    "SCHLUMBERG DRN":       "S1LB34",
    "TERNIUMSA DRN":        "TXSA34",
    "UPS DRN":              "U1PS34",
    # ── Mineração / Metais ──────────────────────────────────────────────
    "ALBEMARLE CO DRN":     "A1LB34",
    "ALBEMARLE CO DRN ED":  "A1LB34",
    "BARRICK GOLD DRN":     "B1RG34",
    "FREEPORT MC DRN":      "F1CX34",
    "GOLD FIELDS DRN":      "G1FI34",
    "GOLD FIELDS DRN ED":   "G1FI34",
    "NEWMONT CORP DRN":     "N2EM34",
    "RIO TINTO DRN":        "R1IO34",
    "SIBANYE STIL DRN":     "S1BS34",
    "SIBANYE STIL DRN ED":  "S1BS34",
    "SIGMA LITHM DRN":      "S2GM34",
    "VALE ORD DRN":         "VALE3",     # Vale listada como DRN em algumas notas
    # ── Imóveis / REITs ─────────────────────────────────────────────────
    "SIMON PROP DRN":       "SIMN34",
    "SIMON PROP DRN ED":    "SIMN34",
    # ── Brasil (ações nacionais que podem aparecer) ──────────────────────
    "SYN PROP TEC ON NM":   "SYNE3",
    "SYN PROP TEC":         "SYNE3",
    "AURA 360 DR3":         "AURA33",
    # ── ETFs / Fundos ────────────────────────────────────────────────────
    "HASHDEX NCI CI":       "HASH11",    # ETF Cripto Hashdex
    "HASHDEX NCI":          "HASH11",
    "HASHDEX CRYP":         "HASH11",
    "NASDAQ INC DRN":       "N1DA34",
    "TREND OURO CI":        "GOLD11",    # Trend ETF Ouro
    "SP500 VALUE DRE":      "SPXI11",    # ETF S&P500 Value
    # ── China / Ásia ──────────────────────────────────────────────────────
    "ALIBABAGR DRN":        "BABA34",    # Alibaba Group
    "ALIBABAGR DRN ED":     "BABA34",
    "BAIDU INC DRN ED":     "BIDU34",
    "KINGSOFT CHL DRN":     "K2SC34",    # Kingsoft Cloud Holdings
    "KINGSOFT CHL DRN ED":  "K2SC34",
    "WEIBO CORP DRN":       "W2BO34",    # Weibo Corp
    "WEIBO CORP DRN ED":    "W2BO34",
    # ── Variantes de nome truncado Santander ─────────────────────────────
    # (o PDF trunca nomes longos — cada truncagem vira uma entrada)
    "ALPHABET DRN":         "GOGL35",    # Alphabet genérico → Cl A
    "ALPHABET DRN ED":      "GOGL35",
    "NETFLIX DRN":          "NFLX34",
    "NETFLIX DRN ED":       "NFLX34",
    "BERKSHIRE DRN":        "B2RK34",    # Berkshire genérico → Cl B
    "BERKSHIRE DRN ED":     "B2RK34",
    "WALT DISNEY DRN":      "DISB34",
    "WALT DISNEY DRN ED":   "DISB34",
    "AIRBNB DRN":           "A2BN34",
    "AIRBNB DRN ED":        "A2BN34",
    "META PLAT DRN":        "FBOK34",    # Meta Platforms (truncado)
    "META PLAT DRN ED":     "FBOK34",
    "ADVANCED MIC DRN":     "A1MD34",    # AMD (truncado diferente)
    "ADVANCED MIC DRN ED":  "A1MD34",
    "ORACLE DRN":           "ORCL34",
    "ORACLE DRN ED":        "ORCL34",
    "LILLY DRN":            "L1LY34",    # Eli Lilly (truncado)
    "LILLY DRN ED":         "L1LY34",
    "SALESFOR INC DRN":     "C2RM34",   # Salesforce (truncado)
    "SALESFOR INC DRN ED":  "C2RM34",
    "APPLIED MATE DRN":     "A1PM34",   # Applied Materials (truncado)
    "APPLIED MATE DRN ED":  "A1PM34",
    "UBER TECH IN DRN":     "U1BE34",   # Uber (truncado)
    "UBER TECH IN DRN ED":  "U1BE34",
    "BOOKING DRN":          "B1KN34",   # Booking Holdings (truncado)
    "BOOKING DRN ED":       "B1KN34",
    "FREEPORT DRN":         "F1CX34",   # Freeport-McMoRan (truncado)
    "FREEPORT DRN ED":      "F1CX34",
    "NIKE DRN":             "NIKE34",   # Nike (truncado sem INC)
    "NIKE DRN ED":          "NIKE34",
    "TAIWANSMFAC DRN ED":   "TSMC34",   # TSMC sem espaço
    # ── Telecom adicional ────────────────────────────────────────────────
    "ATT INC DRN":          "ATTB34",   # AT&T Inc
    "ATT INC DRN ED":       "ATTB34",
    "VERIZON DRN":          "VERZ34",   # Verizon Communications
    "VERIZON DRN ED":       "VERZ34",
    "LUMEN TECH DRN":       "L2TH34",   # Lumen Technologies
    "LUMEN TECH DRN ED":    "L2TH34",
    # ── Financeiro adicional ──────────────────────────────────────────────
    "UBS GROUP DRN":        "U1BS34",   # UBS Group AG
    "UBS GROUP DRN ED":     "U1BS34",
    "US BANCORP DRN":       "U2SB34",   # U.S. Bancorp
    "US BANCORP DRN ED":    "U2SB34",
    "WR BERKLEY C DRN":     "W2RB34",   # W. R. Berkley Corp
    "WR BERKLEY C DRN ED":  "W2RB34",
    "WESTERNUNION DRN":     "W2UN34",   # Western Union
    "WESTERNUNION DRN ED":  "W2UN34",
    # ── Tecnologia adicional ──────────────────────────────────────────────
    "MARVELL TEC DRN":      "MRVL34",   # Marvell Technology Group
    "MARVELL TEC DRN ED":   "MRVL34",
    "FISERV INC DRN":       "F1SV34",   # Fiserv Inc
    "FISERV INC DRN ED":    "F1SV34",
    "PAYPAL HOLD DRN":      "PYPL34",   # PayPal (truncado diferente)
    "PAYPAL HOLD DRN ED":   "PYPL34",
    "OKTA INC DRN":         "O2KT34",   # Okta Inc
    "OKTA INC DRN ED":      "O2KT34",
    "PALANTIRTECH DRN":     "P1LT34",   # Palantir Technologies
    "PALANTIRTECH DRN ED":  "P1LT34",
    "ASML HOLD DRN":        "A2SL34",   # ASML Holding (chip litografia)
    "ASML HOLD DRN ED":     "A2SL34",
    "BROADCOM INC DRN":     "A1VG34",   # Broadcom (truncado sem sufixo)
    "BROADCOM INC DRN ED":  "A1VG34",
    # ── Energia / Materiais ───────────────────────────────────────────────
    "ENPHASE ENER DRN":     "E1NP34",   # Enphase Energy
    "ENPHASE ENER DRN ED":  "E1NP34",
    "MP MATERIALS DRN":     "M2PM34",   # MP Materials
    "MP MATERIALS DRN ED":  "M2PM34",
    "TRANSOCEAN DRN":       "R1GI34",   # Transocean (perfuração offshore)
    "TRANSOCEAN DRN ED":    "R1GI34",
    "EXELON CORP DRN":      "E1XC34",   # Exelon Corp (energia elétrica)
    "EXELON CORP DRN ED":   "E1XC34",
    "DOW INC DRN":          "D2OW34",   # Dow Inc (química)
    "DOW INC DRN ED":       "D2OW34",
    "VISTRA CORP DRN ED":   "V2ST34",   # Vistra Corp (energia)
    "VISTRA CORP DRN":      "V2ST34",
    "VERTIV HOLDS DRN":     "V2RT34",   # Vertiv Holdings
    "VERTIV HOLDS DRN ED":  "V2RT34",
    # ── Saúde adicional ───────────────────────────────────────────────────
    "INCYTE CORP DRN":      "I2NC34",   # Incyte Corp
    "INCYTE CORP DRN ED":   "I2NC34",
    "SAREPTA THER DRN":     "S2RT34",   # Sarepta Therapeutics
    "SAREPTA THER DRN ED":  "S2RT34",
    "NOVOCURE DRN":         "N2VC34",   # NovoCure Ltd
    "NOVOCURE DRN ED":      "N2VC34",
    "MEDICAL P TR DRN ED":  "M2PT34",   # Medical Properties Trust (REIT saúde)
    "MEDICAL P TR DRN":     "M2PT34",
    # ── Consumo / E-commerce ──────────────────────────────────────────────
    "EBAY DRN":             "E1BA34",   # eBay Inc
    "EBAY DRN ED":          "E1BA34",
    "WAYFAIR INC DRN":      "W2YF34",   # Wayfair Inc
    "WAYFAIR INC DRN ED":   "W2YF34",
    "MACY S DRN":           "M2CY34",   # Macy's Inc
    "MACY S DRN ED":        "M2CY34",
    "STONE CO DRN":         "STOC31",   # StoneCo Ltd
    "STONE CO DRN ED":      "STOC31",
    "SEA LTD DRN":          "S2EA34",   # Sea Limited
    "SEA LTD DRN ED":       "S2EA34",
    "FIVERR INTL DRN":      "F2VR34",   # Fiverr International
    "FIVERR INTL DRN ED":   "F2VR34",
    "WARNER MUSIC DRN":     "W2MG34",   # Warner Music Group
    "WARNER MUSIC DRN ED":  "W2MG34",
    # ── Inovação / Deep Tech ──────────────────────────────────────────────
    "QUANTUMSCAPE DRN":     "Q2SC34",   # QuantumScape (baterias estado sólido)
    "QUANTUMSCAPE DRN ED":  "Q2SC34",
    "RIGETTI COMP DRN":     "R2GT34",   # Rigetti Computing (computação quântica)
    "RIGETTI COMP DRN ED":  "R2GT34",
    "BEYOND MEAT DRN":      "B2YN34",   # Beyond Meat
    "BEYOND MEAT DRN ED":   "B2YN34",
    "PDD HOLDING DRN":      "P2DD34",   # PDD Holdings (Temu/Pinduoduo)
    "PDD HOLDING DRN ED":   "P2DD34",
    "COSTAR GROUP DRN":     "C2SG34",   # CoStar Group
    "COSTAR GROUP DRN ED":  "C2SG34",
    "UNITED RENTA DRN":     "U1RI34",   # United Rentals
    "UNITED RENTA DRN ED":  "U1RI34",
    "NEWMONT GOLD DRN":     "N2EM34",   # Newmont (truncado diferente de NEWMONT CORP)
    "NEWMONT GOLD DRN ED":  "N2EM34",
    # ── Brasil / Fundos ───────────────────────────────────────────────────
    "NU HOLDINGS DRN":      "NUBR33",   # Nu Holdings (Nubank)
    "NU HOLDINGS DRN ED":   "NUBR33",
    "FIAGRO KINEA CI":      "KNCA11",   # Fiagro Kinea
    "FIAGRO KINEA CI ER":   "KNCA11",
    "FIAGRO SUNO CI ER":    "SNAG11",   # Fiagro Suno Agro
    "FIAGRO SUNO CI":       "SNAG11",
    # ── ETF / Certificados especiais ──────────────────────────────────────
    "GX AI TECH DRE EB":    "XAIG11",   # Global X AI Tech ETF
    "SOLAR TECH DRN":       "S2OL34",   # Solar Tech (verificar ticker exato)
    # ── Tecnologia adicional ──────────────────────────────────────────────
    "CISCO DRN":            "C1SC34",
    "CISCO DRN ED":         "C1SC34",
    "STRATEGY INC DRN":     "M2ST34",   # MicroStrategy (rebrand → Strategy)
    "STRATEGY INC DRN ED":  "M2ST34",
    "ROBLOX CORP DRN":      "R2OB34",
    "ROBLOX CORP DRN ED":   "R2OB34",
    "AXON ENTERPR DRN":     "A2XN34",   # Axon Enterprise
    "AXON ENTERPR DRN ED":  "A2XN34",
    "GOPRO DRN":            "G2PR34",
    "GOPRO DRN ED":         "G2PR34",
    "STRIDE INC DRN":       "S2TR34",   # Stride Inc (educação)
    "STRIDE INC DRN ED":    "S2TR34",
    "GRUPOCIBEST DRN":      "G2CB34",   # Grupo CI Best
    "GRUPOCIBEST DRN ED":   "G2CB34",
    # ── Financeiro adicional ──────────────────────────────────────────────
    "SCHWAB DRN":           "S1WB34",   # Charles Schwab
    "SCHWAB DRN ED":        "S1WB34",
    "VERISK ANALY DRN":     "V1RS34",   # Verisk Analytics
    "VERISK ANALY DRN ED":  "V1RS34",
    "MERCADOLIBRE DRN":     "MELI34",   # MercadoLibre
    "MERCADOLIBRE DRN ED":  "MELI34",
    "XP INC DR1":           "XPBR31",   # XP Inc
    "INTER CO DR2":         "INBR32",   # Inter & Co
    "JBS N.V. DR2":         "JBSS3",    # JBS N.V.
    # ── Consumo / Outros EUA ──────────────────────────────────────────────
    "MONSTER BEVE DRN":     "M2ST34",   # Monster Beverage
    "MONSTER BEVE DRN ED":  "M2ST34",
    "COTY INC DRN":         "C2OT34",
    "COTY INC DRN ED":      "C2OT34",
    "KRAFT HEINZ DRN":      "K1HZ34",
    "KRAFT HEINZ DRN ED":   "K1HZ34",
    "PEPSICO INC DRN":      "P1EP34",
    "PEPSICO INC DRN ED":   "P1EP34",
    "KOHLS CORP DRN":       "K2SS34",   # Kohl's
    "KOHLS CORP DRN ED":    "K2SS34",
    # ── Saúde adicional ───────────────────────────────────────────────────
    "RELX PLC DRN":         "R1LX34",   # RELX (info & analytics)
    "RELX PLC DRN ED":      "R1LX34",
    # ── Telecom ───────────────────────────────────────────────────────────
    "TELEFONIC DRN":        "TLEF34",   # Telefonica
    "TELEFONIC DRN ED":     "TLEF34",
    # ── Automotivo ────────────────────────────────────────────────────────
    "HONDA MO DRN":         "H1MC34",   # Honda Motor
    "HONDA MO DRN ED":      "H1MC34",
    # ── Mineração ─────────────────────────────────────────────────────────
    "FRANCONEVADA DRN":     "F1NV34",   # Franco-Nevada
    "FRANCONEVADA DRN ED":  "F1NV34",
    # ── Brasil adicional ──────────────────────────────────────────────────
    "EMBRAER ON NM":        "EMBR3",
    "MARFRIG ON NM":        "MRFG3",
    "SYN PROP TEC ON ED NM": "SYNE3",   # variante com ED
    "SYN PROP TEC ON ER NM": "SYNE3",   # variante com ER
    # ── Outros já no dict mas com variante diferente ──────────────────────
    "CLOUDFLARE DRN ED":    "N2ET34",
    "PAGSEGURO DRN ED":     "PAGS34",
}

# Variantes com sufixo " ED" automáticas já cobertas acima individualmente.
# Se aparecer nome novo nos logs, adicione aqui no formato:
#   "NOME EXATO DA NOTA": "TICKERB3",

# Conjunto de ativos mapeados para detecção rápida
_TICKERS_CONHECIDOS = set(NOME_PARA_TICKER.values())
# Controla ativos já avisados nesta sessão — evita spam de warnings repetidos
_ATIVOS_JA_AVISADOS: set[str] = set()


def normalizar_ativo(nome: str) -> str:
    """Converte nome completo da nota Santander para ticker B3.
    Loga aviso UMA VEZ por sessão se ativo não encontrado no mapa."""
    nome_clean = nome.strip()
    for suf in (" D@", " @", " D#", " D", " #"):
        if nome_clean.endswith(suf):
            nome_clean = nome_clean[:-len(suf)].strip()
    ticker = NOME_PARA_TICKER.get(nome_clean, nome_clean)
    if ticker == nome_clean and nome_clean not in _TICKERS_CONHECIDOS:
        if nome_clean not in _ATIVOS_JA_AVISADOS:
            log.warning("Ativo não mapeado: '%s' — adicione em NOME_PARA_TICKER", nome_clean)
            _ATIVOS_JA_AVISADOS.add(nome_clean)
    return ticker


# ─────────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────────
def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect('carteira.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            cv TEXT NOT NULL,
            ativo TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            preco REAL NOT NULL,
            valor REAL NOT NULL,
            dc TEXT,
            taxa_rateada REAL DEFAULT 0.0,
            preco_liquido REAL DEFAULT 0.0,
            daytrade INTEGER DEFAULT 0,
            nr_nota TEXT DEFAULT ''
        )
    ''')
    # Migração segura: adiciona colunas ausentes
    colunas_migrar = [
        ('taxa_rateada',  'REAL',    '0.0'),
        ('preco_liquido', 'REAL',    '0.0'),
        ('daytrade',      'INTEGER', '0'),
        ('nr_nota',       'TEXT',    "''"),
    ]
    for col, tipo, default in colunas_migrar:
        try:
            # Valores são todos literais hardcoded — sem risco de injeção
            c.execute(f"ALTER TABLE operacoes ADD COLUMN {col} {tipo} DEFAULT {default}")
            log.info("Coluna '%s' adicionada ao schema.", col)
        except sqlite3.OperationalError:
            pass  # Coluna já existe — comportamento esperado
        except Exception as exc:
            log.error("Falha na migração da coluna '%s': %s", col, exc)

    c.execute('''
        CREATE TABLE IF NOT EXISTS arquivos_processados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT UNIQUE,
            data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn


conn = init_db()


# ─────────────────────────────────────────────
# PARSE DE PDF — com taxas do Resumo Financeiro
# ─────────────────────────────────────────────
def _br(s: str) -> float:
    """Converte string numérica BR para float. Retorna 0.0 em caso de falha."""
    try:
        return float(s.strip().replace('.', '').replace(',', '.'))
    except (ValueError, AttributeError):
        return 0.0


def _safe_float(value, default: float = 0.0) -> float:
    """Converte valor para float com fallback seguro."""
    try:
        v = float(value)
        return v if np.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def parse_pdf(file_obj) -> list[dict]:
    """
    Lê nota(s) de corretagem Santander e retorna lista de operações com:
      - preco          : preço bruto
      - taxa_rateada   : fração das taxas rateada pelo valor da operação
      - preco_liquido  : preço ajustado pelas taxas
      - daytrade       : 1 se operação com flag D/D@
      - nr_nota        : número da nota de corretagem
    """
    notas = []
    current_nota = None
    ativos_nao_mapeados: set[str] = set()

    with pdfplumber.open(file_obj) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                log.debug("Página %d sem texto — ignorada.", page_num)
                continue
            lines = text.split('\n')

            for line in lines:
                # ── Cabeçalho da nota: "220402 1 02/01/2026" ──
                hdr = re.match(r'^(\d{5,7})\s+\d+\s+(\d{2}/\d{2}/\d{4})$', line.strip())
                if hdr:
                    if current_nota:
                        notas.append(current_nota)
                    current_nota = {
                        'nr_nota': hdr.group(1),
                        'data': hdr.group(2),
                        'operacoes': [],
                        'liq': 0.0, 'emol': 0.0,
                        'corretagem': 0.0, 'irrf': 0.0,
                        'outras': 0.0, 'iss': 0.0,
                    }
                    log.debug("Nota %s detectada em %s.", hdr.group(1), hdr.group(2))
                    continue

                if current_nota is None:
                    continue

                # ── Operações ──
                # Regex primário: formato histórico Santander (até ~2025)
                # Grupos: 1=CV, 2=mercado, 3=nome_ativo, 4=obs/flag, 5=qtde, 6=preco, 7=valor, 8=D|C
                _OP_RE_V1 = r"LISTADO([CV])\s+(VISTA|FRACION[AÁ]RIO)\s+(.*?)\s+([@D#]{1,2}|\s)\s+([\d\.]+)\s+([\d\,]+)\s+([\d\.,]+)\s+(D|C)$"
                # Regex alternativo: formato 2026 — pode omitir "LISTADO" ou mudar mercado
                _OP_RE_V2 = r"([CV])\s+(VISTA|FRACION[AÁ]RIO|BALC[AÃ]O|ETF|FII|BDR)\s+(.*?)\s+([@D#]{0,2})\s+([\d\.]+)\s+([\d\,]+)\s+([\d\.,]+)\s+(D|C)$"

                op = re.search(_OP_RE_V1, line)
                op_v2 = None
                if not op and 'LISTADO' not in line:
                    # Tenta padrão alternativo apenas em linhas sem LISTADO (evita falsos positivos)
                    op_v2 = re.search(_OP_RE_V2, line)

                # Log diagnóstico: linha com LISTADO mas sem match (formato novo desconhecido)
                if 'LISTADO' in line and not op:
                    log.warning("Linha com LISTADO não reconhecida (formato novo?) — nota %s: %s",
                                current_nota['nr_nota'], line.strip())

                if op or op_v2:
                    m = op or op_v2
                    cv    = m.group(1)
                    nome_bruto = m.group(3).strip()
                    nome  = normalizar_ativo(nome_bruto)
                    obs   = m.group(4).strip()
                    qty_str = m.group(5).replace('.', '')

                    # Valida quantidade
                    if not qty_str.isdigit() or int(qty_str) <= 0:
                        log.warning("Quantidade inválida '%s' na linha: %s", qty_str, line.strip())
                        continue
                    qty = int(qty_str)

                    preco = _br(m.group(6))
                    valor = _br(m.group(7))
                    dc    = m.group(8)
                    is_dt = 'D' in obs

                    if nome not in NOME_PARA_TICKER.values() and nome == nome_bruto:
                        ativos_nao_mapeados.add(nome_bruto)

                    current_nota['operacoes'].append({
                        'data': current_nota['data'],
                        'nr_nota': current_nota['nr_nota'],
                        'cv': cv, 'ativo': nome,
                        'quantidade': qty, 'preco': preco,
                        'valor': valor, 'dc': dc,
                        'daytrade': 1 if is_dt else 0,
                    })

                # ── Taxas do Resumo Financeiro ──
                def _taxa(pat: str) -> float:
                    m = re.search(pat, line)
                    return _br(m.group(1)) if m else 0.0

                current_nota['liq']        += _taxa(r'Taxa de liquidação/CCP\s+([\d\.,]+)')
                current_nota['emol']       += _taxa(r'^Emolumentos\s+([\d\.,]+)')
                current_nota['corretagem'] += _taxa(r'^Clearing\s+([\d\.,]+)\s+D$')
                current_nota['iss']        += _taxa(r'ISS.*?([\d\.,]+)\s+D$')
                current_nota['outras']     += _taxa(r'^Outras Despesas\s+([\d\.,]+)\s+D$')
                current_nota['irrf']       += _taxa(r'I\.R\.R\.F\. s/ operações.*?([\d\.,]+)\s+D$')

    if current_nota:
        notas.append(current_nota)

    if ativos_nao_mapeados:
        log.warning("Ativos sem ticker mapeado: %s", ", ".join(sorted(ativos_nao_mapeados)))

    # ── Rateia taxas por operação, proporcional ao valor ──
    trades: list[dict] = []
    for nota in notas:
        ops = nota['operacoes']
        if not ops:
            total_taxas_nota = (nota['liq'] + nota['emol'] + nota['corretagem'] +
                                nota['iss'] + nota['outras'] + nota['irrf'])
            if total_taxas_nota > 0:
                log.warning("Nota %s sem operações mas com taxas R$%.2f — verifique formato do PDF.",
                            nota['nr_nota'], total_taxas_nota)
            else:
                log.debug("Nota %s sem operações (provável nota de custódia/direitos).", nota["nr_nota"])
            continue

        total_taxas = (nota['liq'] + nota['emol'] + nota['corretagem'] +
                       nota['iss'] + nota['outras'] + nota['irrf'])
        total_valor = sum(o['valor'] for o in ops)

        for o in ops:
            quantidade = o['quantidade']
            if quantidade <= 0:
                log.warning("Operação ignorada: quantidade=%d em %s/%s", quantidade, o['ativo'], o['data'])
                continue

            peso = (o['valor'] / total_valor) if total_valor > 0 else (1.0 / len(ops))
            taxa_op = round(total_taxas * peso, 6)

            if o['cv'] == 'C':
                preco_liq = (o['valor'] + taxa_op) / quantidade
            else:
                preco_liq = (o['valor'] - taxa_op) / quantidade

            trades.append({
                'data':          o['data'],
                'cv':            o['cv'],
                'ativo':         o['ativo'],
                'quantidade':    quantidade,
                'preco':         o['preco'],
                'valor':         o['valor'],
                'dc':            o['dc'],
                'taxa_rateada':  taxa_op,
                'preco_liquido': round(preco_liq, 6),
                'daytrade':      o['daytrade'],
                'nr_nota':       o['nr_nota'],
            })

    log.info("PDF parseado: %d nota(s), %d operação(ões).", len(notas), len(trades))
    return trades


def save_to_db(trades: list[dict], conn: sqlite3.Connection) -> int:
    """Salva operações novas no banco. Usa nr_nota na deduplicação."""
    c = conn.cursor()
    new_trades = 0
    for t in trades:
        # Validações básicas antes de inserir
        if not t.get('ativo') or not t.get('data') or t.get('quantidade', 0) <= 0:
            log.warning("Operação inválida ignorada: %s", t)
            continue

        c.execute(
            '''SELECT COUNT(*) FROM operacoes
               WHERE data=? AND cv=? AND ativo=? AND quantidade=? AND preco=? AND nr_nota=?''',
            (t['data'], t['cv'], t['ativo'], t['quantidade'], t['preco'], t.get('nr_nota', ''))
        )
        if c.fetchone()[0] == 0:
            c.execute(
                '''INSERT INTO operacoes
                    (data, cv, ativo, quantidade, preco, valor, dc,
                     taxa_rateada, preco_liquido, daytrade, nr_nota)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (t['data'], t['cv'], t['ativo'], t['quantidade'],
                 t['preco'], t['valor'], t.get('dc', ''),
                 t.get('taxa_rateada', 0.0), t.get('preco_liquido', t['preco']),
                 t.get('daytrade', 0), t.get('nr_nota', ''))
            )
            new_trades += 1
    conn.commit()
    return new_trades


def processar_notas_iniciais(conn: sqlite3.Connection) -> tuple[int, list[str]]:
    """
    Varre notas_pdf/ e processa PDFs ainda não registrados.
    Idempotente — seguro para chamar múltiplas vezes.
    """
    os.makedirs('notas_pdf', exist_ok=True)
    c = conn.cursor()
    total_novas = 0
    arquivos_novos: list[str] = []

    for caminho in sorted(glob.glob('notas_pdf/*.pdf')):
        nome = os.path.basename(caminho)
        c.execute('SELECT COUNT(*) FROM arquivos_processados WHERE nome_arquivo=?', (nome,))
        if c.fetchone()[0] == 0:
            try:
                trades = parse_pdf(caminho)
                novas  = save_to_db(trades, conn)
                total_novas += novas
                arquivos_novos.append(nome)
                c.execute('INSERT OR IGNORE INTO arquivos_processados (nome_arquivo) VALUES (?)', (nome,))
                conn.commit()
                log.info("Arquivo '%s' processado: %d operação(ões) novas.", nome, novas)
            except Exception as exc:
                log.error("Erro ao processar '%s': %s", nome, exc, exc_info=True)
                st.warning(f"Erro ao processar {nome}: {exc}")

    return total_novas, arquivos_novos


# Processa notas existentes na pasta ao iniciar
_novas_inicio, _arqs_inicio = processar_notas_iniciais(conn)
if _arqs_inicio:
    st.toast(f"📂 {len(_arqs_inicio)} nota(s) nova(s) processada(s) da pasta notas_pdf/", icon="✅")


def load_data(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM operacoes ORDER BY data ASC, id ASC", conn)


# ─────────────────────────────────────────────
# ENGINE DE CÁLCULO DE PERFORMANCE
# ─────────────────────────────────────────────
def calculate_performance(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Calcula carteira atual, histórico de trades fechados e resultado mensal.
    Retorna: (df_carteira, df_historico, df_mensal)
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = df.copy()
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
    invalidas = df['data'].isna().sum()
    if invalidas > 0:
        log.warning("%d data(s) inválida(s) descartada(s).", invalidas)
    df = df.dropna(subset=['data']).sort_values(['data', 'id'])

    carteira: dict[str, dict] = {}
    historico: list[dict] = []

    # ── Pré-processa compras DayTrade: FIFO por (data, ativo, nr_nota) ──
    dt_compras: dict[tuple, deque] = {}
    for _, row in df.iterrows():
        if not bool(row.get('daytrade', 0)) or row['cv'] != 'C':
            continue
        key = (str(row["data"])[:10], row["ativo"])
        if key not in dt_compras:
            dt_compras[key] = deque()
        pliq = _safe_float(row.get('preco_liquido') or row.get('preco'))
        qtde = int(row.get('quantidade', 0))
        for _ in range(qtde):
            dt_compras[key].append(pliq)

    for _, row in df.iterrows():
        ativo      = row['ativo']
        qtde       = int(row.get('quantidade', 0))
        preco_liq  = _safe_float(row.get('preco_liquido') or row.get('preco'))
        preco_bruto = _safe_float(row.get('preco'))
        is_dt      = bool(row.get('daytrade', 0))
        nr_nota    = str(row.get('nr_nota', ''))
        data_str   = str(row['data'])[:10]

        if qtde <= 0:
            continue

        if ativo not in carteira:
            carteira[ativo] = {'qtde': 0, 'preco_medio': 0.0, 'custo_total': 0.0}

        if row['cv'] == 'C':
            if not is_dt:
                pos = carteira[ativo]
                nova_qtde  = pos['qtde'] + qtde
                novo_custo = pos['custo_total'] + (qtde * preco_liq)
                pos['qtde']        = nova_qtde
                pos['custo_total'] = novo_custo
                pos['preco_medio'] = novo_custo / nova_qtde if nova_qtde > 0 else 0.0

        elif row['cv'] == 'V':
            if is_dt:
                key = (data_str, ativo)
                fila = dt_compras.get(key, deque())
                lucro_dt     = 0.0
                qtde_pareada = 0
                # Quantidades sem par DT — serão tratadas como swing via carteira
                qtde_sem_par = 0
                for _ in range(qtde):
                    if fila:
                        pm_dt = fila.popleft()
                        lucro_dt     += preco_liq - pm_dt
                        qtde_pareada += 1
                    else:
                        qtde_sem_par += 1

                if qtde_sem_par > 0:
                    _dt_key = f"dt_sem_compra:{data_str}:{ativo}"
                    if _dt_key not in _ATIVOS_JA_AVISADOS:
                        _ATIVOS_JA_AVISADOS.add(_dt_key)
                        log.info(
                            "DT sem compra pareada: %s %s (%d unid.) — tratando como venda swing.",
                            data_str, ativo, qtde_sem_par,
                        )
                    # Fallback: usa preço médio da carteira swing
                    pos_fb = carteira.get(ativo, {'qtde': 0, 'preco_medio': 0.0, 'custo_total': 0.0})
                    qtde_valida_fb = min(pos_fb['qtde'], qtde_sem_par)
                    if qtde_valida_fb > 0:
                        pm_fb       = pos_fb['preco_medio']
                        lucro_fb    = (preco_liq - pm_fb) * qtde_valida_fb
                        retpct_fb   = ((preco_liq / pm_fb) - 1) * 100 if pm_fb > 0 else 0.0
                        historico.append({
                            'data':              row['data'],
                            'mes_ano':           row['data'].strftime('%Y-%m'),
                            'ano':               row['data'].year,
                            'ativo':             ativo,
                            'qtde_vendida':      qtde_valida_fb,
                            'preco_venda':       preco_liq,
                            'preco_venda_bruto': preco_bruto,
                            'preco_medio_compra': pm_fb,
                            'resultado':         lucro_fb,
                            'retorno_pct':       retpct_fb,
                            'custo_base':        pm_fb * qtde_valida_fb,
                            'daytrade':          False,
                            'nr_nota':           nr_nota,
                        })
                        pos_fb['qtde']       -= qtde_valida_fb
                        pos_fb['custo_total'] = pos_fb['preco_medio'] * pos_fb['qtde']
                        if ativo not in carteira:
                            carteira[ativo] = pos_fb

                if qtde_pareada > 0:
                    custo_dt = sum([preco_liq - lucro_dt / qtde_pareada] * qtde_pareada)
                    retorno_pct_dt = (lucro_dt / custo_dt * 100) if custo_dt > 0 else 0.0
                    historico.append({
                        'data':             row['data'],
                        'mes_ano':          row['data'].strftime('%Y-%m'),
                        'ano':              row['data'].year,
                        'ativo':            ativo,
                        'qtde_vendida':     qtde_pareada,
                        'preco_venda':      preco_liq,
                        'preco_venda_bruto': preco_bruto,
                        'preco_medio_compra': preco_liq - (lucro_dt / qtde_pareada),
                        'resultado':        lucro_dt,
                        'retorno_pct':      retorno_pct_dt,
                        'custo_base':       custo_dt,
                        'daytrade':         True,
                        'nr_nota':          nr_nota,
                    })
            else:
                pos = carteira[ativo]
                if pos['qtde'] > 0:
                    qtde_valida = min(pos['qtde'], qtde)
                    pm          = pos['preco_medio']
                    lucro       = (preco_liq - pm) * qtde_valida
                    retorno_pct = ((preco_liq / pm) - 1) * 100 if pm > 0 else 0.0
                    custo_base  = pm * qtde_valida
                    historico.append({
                        'data':             row['data'],
                        'mes_ano':          row['data'].strftime('%Y-%m'),
                        'ano':              row['data'].year,
                        'ativo':            ativo,
                        'qtde_vendida':     qtde_valida,
                        'preco_venda':      preco_liq,
                        'preco_venda_bruto': preco_bruto,
                        'preco_medio_compra': pm,
                        'resultado':        lucro,
                        'retorno_pct':      retorno_pct,
                        'custo_base':       custo_base,
                        'daytrade':         False,
                        'nr_nota':          nr_nota,
                    })
                    pos['qtde']       -= qtde_valida
                    pos['custo_total'] = pos['preco_medio'] * pos['qtde']
                else:
                    _venda_key = f"venda_sem_pos:{ativo}"
                    if _venda_key not in _ATIVOS_JA_AVISADOS:
                        _ATIVOS_JA_AVISADOS.add(_venda_key)
                        log.warning("Venda de %s sem posição em carteira (primeira ocorrência em %s).", ativo, data_str)

    # Monta carteira atual
    carteira_atual = [
        {
            'Ativo':           ativo,
            'Quantidade':      d['qtde'],
            'Preço Médio':     d['preco_medio'],
            'Valor Investido': d['qtde'] * d['preco_medio'],
        }
        for ativo, d in carteira.items() if d['qtde'] > 0
    ]
    df_carteira  = pd.DataFrame(carteira_atual)
    df_historico = pd.DataFrame(historico)

    df_mensal = pd.DataFrame()
    if not df_historico.empty:
        df_mensal = (
            df_historico.groupby('mes_ano')
            .agg(
                resultado=('resultado', 'sum'),
                trades=('resultado', 'count'),
                win_rate=('resultado', lambda x: (x > 0).mean() * 100),
                trades_dt=('daytrade', 'sum'),
            )
            .reset_index()
        )

    return df_carteira, df_historico, df_mensal


# ─────────────────────────────────────────────
# MÉTRICAS AVANÇADAS
# ─────────────────────────────────────────────
def max_streak(bool_series: pd.Series) -> int:
    """Maior sequência consecutiva de True."""
    max_s = cur = 0
    for v in bool_series:
        if v:
            cur += 1
            max_s = max(max_s, cur)
        else:
            cur = 0
    return max_s


def calc_advanced_metrics(df_historico: pd.DataFrame) -> dict:
    """Calcula métricas quantitativas de performance de trading."""
    if df_historico.empty:
        return {}

    resultados = df_historico['resultado']
    retornos   = df_historico['retorno_pct']

    lucros = resultados[resultados > 0]
    perdas = resultados[resultados < 0]

    # Payoff Ratio
    payoff = (lucros.mean() / abs(perdas.mean())) if (not lucros.empty and not perdas.empty) else None

    # Fator de Lucro
    fator_lucro = (lucros.sum() / abs(perdas.sum())) if not perdas.empty else None

    # Sequências
    max_seq_win  = max_streak(resultados > 0)
    max_seq_loss = max_streak(resultados <= 0)

    # Curva de capital
    curva   = resultados.cumsum()
    peak    = curva.cummax()
    drawdown = curva - peak
    max_dd  = drawdown.min()
    max_dd_pct = (drawdown / peak.replace(0, np.nan)).min() * 100 if peak.max() > 0 else None

    # Sharpe simplificado
    sharpe = (retornos.mean() / retornos.std()) if retornos.std() > 0 else None

    # Sortino (penaliza apenas volatilidade negativa)
    ret_negativos = retornos[retornos < 0]
    downside_std  = ret_negativos.std() if len(ret_negativos) > 1 else None
    sortino = (retornos.mean() / downside_std) if downside_std and downside_std > 0 else None

    # Expectativa matemática
    win_rate  = (resultados > 0).mean()
    loss_rate = 1 - win_rate
    avg_win   = lucros.mean() if not lucros.empty else 0.0
    avg_loss  = perdas.mean() if not perdas.empty else 0.0
    expectativa = (win_rate * avg_win) + (loss_rate * avg_loss)

    # Calmar Ratio
    calmar = (resultados.sum() / abs(max_dd)) if max_dd != 0 else None

    # Recovery Factor = lucro total / |max drawdown|
    recovery_factor = (resultados.sum() / abs(max_dd)) if max_dd != 0 else None

    # Volatilidade anualizada dos retornos %
    vol_diaria = retornos.std()
    vol_anual  = vol_diaria * np.sqrt(252) if vol_diaria > 0 else 0.0

    # Média dias entre trades (se data disponível)
    if 'data' in df_historico.columns and len(df_historico) > 1:
        datas = pd.to_datetime(df_historico['data'])
        media_dias_entre_trades = datas.diff().dt.days.mean()
    else:
        media_dias_entre_trades = None

    # Análise DayTrade vs Swing
    if 'daytrade' in df_historico.columns:
        df_dt   = df_historico[df_historico['daytrade'] == True]
        df_sw   = df_historico[df_historico['daytrade'] == False]
        resultado_dt = df_dt['resultado'].sum() if not df_dt.empty else 0.0
        resultado_sw = df_sw['resultado'].sum() if not df_sw.empty else 0.0
        wr_dt        = (df_dt['resultado'] > 0).mean() * 100 if not df_dt.empty else None
        wr_sw        = (df_sw['resultado'] > 0).mean() * 100 if not df_sw.empty else None
    else:
        resultado_dt = resultado_sw = 0.0
        wr_dt = wr_sw = None

    return {
        'win_rate':            win_rate * 100,
        'payoff_ratio':        payoff,
        'fator_lucro':         fator_lucro,
        'expectativa':         expectativa,
        'sharpe':              sharpe,
        'sortino':             sortino,
        'calmar':              calmar,
        'recovery_factor':     recovery_factor,
        'vol_anual_pct':       vol_anual,
        'max_drawdown':        max_dd,
        'max_drawdown_pct':    max_dd_pct,
        'max_seq_win':         max_seq_win,
        'max_seq_loss':        max_seq_loss,
        'total_trades':        len(resultados),
        'trades_lucro':        len(lucros),
        'trades_perda':        len(perdas),
        'maior_lucro':         lucros.max() if not lucros.empty else 0.0,
        'maior_perda':         perdas.min() if not perdas.empty else 0.0,
        'media_lucro':         avg_win,
        'media_perda':         avg_loss,
        'lucro_bruto_total':   resultados.sum(),
        'retorno_medio_pct':   retornos.mean(),
        'retorno_melhor_pct':  retornos.max(),
        'retorno_pior_pct':    retornos.min(),
        'curva_capital':       curva,
        'drawdown_series':     drawdown,
        'media_dias_entre_trades': media_dias_entre_trades,
        'resultado_daytrade':  resultado_dt,
        'resultado_swing':     resultado_sw,
        'win_rate_daytrade':   wr_dt,
        'win_rate_swing':      wr_sw,
        'n_daytrades':         len(df_dt) if 'daytrade' in df_historico.columns else 0,
        'n_swings':            len(df_sw) if 'daytrade' in df_historico.columns else 0,
    }


def calc_qualidade_dados(df: pd.DataFrame) -> list[dict]:
    """
    Verifica qualidade dos dados carregados.
    Retorna lista de alertas: {'nivel': 'aviso'|'erro', 'mensagem': str}
    """
    alertas = []
    if df.empty:
        return alertas

    # Quantidade zero ou negativa
    qtde_invalida = (df['quantidade'] <= 0).sum()
    if qtde_invalida:
        alertas.append({'nivel': 'erro', 'mensagem': f"{qtde_invalida} operação(ões) com quantidade ≤ 0"})

    # Preços zero
    preco_zero = (df['preco'] <= 0).sum()
    if preco_zero:
        alertas.append({'nivel': 'erro', 'mensagem': f"{preco_zero} operação(ões) com preço ≤ 0"})

    # Datas inválidas
    datas = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
    datas_invalidas = datas.isna().sum()
    if datas_invalidas:
        alertas.append({'nivel': 'erro', 'mensagem': f"{datas_invalidas} data(s) em formato inválido"})

    # Ativos sem ticker reconhecido (não terminam em número — heurística simples)
    ativos_suspeitos = df['ativo'].dropna().unique()
    nao_padrao = [a for a in ativos_suspeitos if not re.search(r'\d{1,2}$', a) and len(a) > 8]
    if nao_padrao:
        alertas.append({
            'nivel': 'aviso',
            'mensagem': f"Ativos com ticker não-padrão B3: {', '.join(nao_padrao[:5])}"
        })

    # Taxa rateada zerada em todas operações (PDF sem resumo financeiro)
    if 'taxa_rateada' in df.columns and df['taxa_rateada'].sum() == 0:
        alertas.append({'nivel': 'aviso', 'mensagem': "Nenhuma taxa rateada detectada — PDFs podem estar sem resumo financeiro"})

    # Operações duplicadas aproximadas (mesma data, ativo, qtde, preço, mas nr_nota diferente)
    cols_dup = ['data', 'cv', 'ativo', 'quantidade', 'preco']
    n_dup = df.duplicated(subset=cols_dup).sum()
    if n_dup:
        alertas.append({'nivel': 'aviso', 'mensagem': f"{n_dup} possível(is) operação(ões) duplicada(s) (mesma data/ativo/qtde/preço)"})

    return alertas


# ─────────────────────────────────────────────
# HELPERS DE FORMATAÇÃO
# ─────────────────────────────────────────────
def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def fmt_kpi(value: float) -> str:
    s = f"{abs(value):.2f}".replace('.', ',')
    prefix = "R$ " if value >= 0 else "- R$ "
    return f"{prefix}{s}"


def fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def fmt_metric(value, fmt: str = ".2f", suffix: str = "", prefix: str = "", na: str = "N/A") -> str:
    """Formata métrica com suporte a None → N/A."""
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return na
    return f"{prefix}{value:{fmt}}{suffix}"


def color_result(val):
    try:
        v = float(str(val).replace('R$', '').replace('.', '').replace(',', '.').strip())
        color = '#10b981' if v > 0 else ('#ef4444' if v < 0 else '#94a3b8')
        return f'color: {color}; font-family: JetBrains Mono, monospace; font-weight: 600'
    except Exception:
        return ''


def brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return str(v)


def brl4(v) -> str:
    try:
        return f"R$ {float(v):,.4f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return str(v)


# ─────────────────────────────────────────────
# TEMA PARA ALTAIR
# ─────────────────────────────────────────────
ALTAIR_THEME = {
    "config": {
        "background": "transparent",
        "view": {"stroke": "transparent"},
        "axis": {
            "domainColor": "#2a3548", "gridColor": "#1e2535",
            "labelColor": "#64748b", "titleColor": "#94a3b8",
            "labelFont": "Inter", "titleFont": "Inter",
        },
        "legend": {"labelColor": "#94a3b8", "titleColor": "#64748b", "labelFont": "Inter"},
        "title": {"color": "#cbd5e1", "font": "Inter"},
    }
}
@alt.theme.register("dark_finance", enable=True)
def _dark_finance_theme():
    return ALTAIR_THEME


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 MonitorBDRs")
    st.markdown("<hr>", unsafe_allow_html=True)

    menu = st.selectbox(
        "Navegação",
        [
            "🏠 Visão Geral",
            "📥 Importar Notas",
            "💼 Carteira Atual",
            "📈 Performance Mensal",
            "🔍 Análise Individual",
            "🧮 Métricas Avançadas",
            "⚡ Day Trade vs Swing",
            "📋 Histórico de Operações",
            "🔬 Qualidade dos Dados",
        ],
        label_visibility="collapsed",
    )

    st.markdown("<hr>", unsafe_allow_html=True)

    df_sidebar = load_data(conn)
    if not df_sidebar.empty:
        df_cart_sb, df_hist_sb, _ = calculate_performance(df_sidebar)
        n_ativos = len(df_cart_sb) if not df_cart_sb.empty else 0
        n_ops    = len(df_sidebar)
        st.markdown(f"**{n_ops}** operações · **{n_ativos}** ativos")

        if not df_hist_sb.empty:
            total_resultado = df_hist_sb['resultado'].sum()
            cor = "badge-pos" if total_resultado >= 0 else "badge-neg"
            st.markdown(
                f'Resultado acumulado<br><span class="{cor}">{fmt_brl(total_resultado)}</span>',
                unsafe_allow_html=True
            )
    else:
        st.caption("Nenhum dado carregado.")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.caption("⚠️ Inclui taxas B3. IRRF e corretagem não deduzidos do resultado.")


# ─────────────────────────────────────────────
# PÁGINA: VISÃO GERAL
# ─────────────────────────────────────────────
if menu == "🏠 Visão Geral":
    st.title("Visão Geral do Portfólio")

    df = load_data(conn)
    if df.empty:
        st.info("O banco de dados está vazio. Vá em **Importar Notas** para começar.")
    else:
        df_carteira, df_historico, df_mensal = calculate_performance(df)
        metrics = calc_advanced_metrics(df_historico)

        total_investido  = df_carteira['Valor Investido'].sum() if not df_carteira.empty else 0.0
        ativos_diferentes = len(df_carteira) if not df_carteira.empty else 0
        lucro_total      = metrics.get('lucro_bruto_total', 0.0)
        win_rate         = metrics.get('win_rate', 0.0)
        payoff           = metrics.get('payoff_ratio')
        expectativa      = metrics.get('expectativa', 0.0)
        sharpe           = metrics.get('sharpe')
        sortino          = metrics.get('sortino')

        # ── KPIs: 2 linhas ──
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Valor em Carteira", fmt_kpi(total_investido))
        c2.metric(
            "📊 Resultado Acumulado",
            fmt_kpi(lucro_total),
            delta=f"{(lucro_total / total_investido * 100):+.1f}%" if total_investido > 0 else None
        )
        c3.metric("🎯 Ativos em Carteira", str(ativos_diferentes))

        c4, c5, c6 = st.columns(3)
        c4.metric("✅ Win Rate", f"{win_rate:.1f}%")
        c5.metric("⚖️ Payoff Ratio", fmt_metric(payoff, ".2f", "×"))
        c6.metric("🎲 Expectativa/Trade", fmt_kpi(expectativa))

        c7, c8, c9 = st.columns(3)
        c7.metric("📐 Sharpe Ratio", fmt_metric(sharpe, ".3f"),
                  help="Retorno médio / desvio padrão dos retornos. >0 é positivo.")
        c8.metric("📐 Sortino Ratio", fmt_metric(sortino, ".3f"),
                  help="Como Sharpe, mas penaliza somente a volatilidade negativa.")
        c9.metric("📉 Max Drawdown", fmt_metric(metrics.get('max_drawdown'), ".2f", "", "R$ "))

        st.divider()

        # ── Gráfico de Rosca ──
        st.subheader("Alocação da Carteira")
        if not df_carteira.empty:
            df_chart = df_carteira.sort_values('Valor Investido', ascending=False).copy()
            if len(df_chart) > MAX_ATIVOS_PIZZA:
                top    = df_chart.head(MAX_ATIVOS_PIZZA)
                outros = pd.DataFrame([{
                    'Ativo': 'OUTROS', 'Quantidade': 0, 'Preço Médio': 0,
                    'Valor Investido': df_chart.iloc[MAX_ATIVOS_PIZZA:]['Valor Investido'].sum()
                }])
                df_chart = pd.concat([top, outros], ignore_index=True)

            pie = alt.Chart(df_chart).mark_arc(innerRadius=70, outerRadius=150).encode(
                theta=alt.Theta('Valor Investido:Q'),
                color=alt.Color('Ativo:N', scale=alt.Scale(scheme='tableau20'),
                                legend=alt.Legend(orient='bottom', labelLimit=160, columns=3)),
                tooltip=[
                    alt.Tooltip('Ativo:N', title='Ativo'),
                    alt.Tooltip('Valor Investido:Q', title='Valor (R$)', format=',.2f'),
                ]
            ).properties(height=380)
            st.altair_chart(pie, width="stretch")
        else:
            st.info("Carteira vazia.")

        # ── Resultado Mensal ──
        st.subheader("Resultado por Mês")
        if not df_mensal.empty:
            df_mc = df_mensal.copy()
            df_mc['cor'] = df_mc['resultado'].apply(lambda x: '#10b981' if x >= 0 else '#ef4444')
            bars = alt.Chart(df_mc).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X('mes_ano:N', title='Mês', axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('resultado:Q', title='Resultado (R$)'),
                color=alt.Color('cor:N', scale=None, legend=None),
                tooltip=[
                    alt.Tooltip('mes_ano:N', title='Mês'),
                    alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                    alt.Tooltip('trades:Q', title='Trades'),
                    alt.Tooltip('win_rate:Q', title='Win Rate (%)', format='.1f'),
                ]
            ).properties(height=300)
            st.altair_chart(bars, width="stretch")
        else:
            st.info("Nenhuma venda registrada.")

        # ── Curva de Capital ──
        if metrics.get('curva_capital') is not None and not metrics['curva_capital'].empty:
            st.divider()
            st.subheader("Curva de Capital Acumulada")
            curva = metrics['curva_capital'].reset_index(drop=True)
            df_curva = pd.DataFrame({'trade_n': range(1, len(curva) + 1), 'capital': curva.values})
            line  = alt.Chart(df_curva).mark_line(color='#3b82f6', strokeWidth=2).encode(
                x=alt.X('trade_n:Q', title='Nº do Trade'),
                y=alt.Y('capital:Q', title='Resultado Acumulado (R$)'),
                tooltip=[
                    alt.Tooltip('trade_n:Q', title='Trade #'),
                    alt.Tooltip('capital:Q', title='Acumulado (R$)', format=',.2f'),
                ]
            )
            area  = alt.Chart(df_curva).mark_area(color='#3b82f6', opacity=0.15).encode(
                x='trade_n:Q', y='capital:Q'
            )
            zero  = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='#2a3548', strokeDash=[4, 4]
            ).encode(y='y:Q')
            st.altair_chart((area + line + zero).properties(height=240), width="stretch")

        # ── Heatmap Mensal ──
        if not df_historico.empty:
            st.divider()
            st.subheader("Heatmap de Performance Mensal")
            df_hm = df_historico.copy()
            df_hm['mes'] = df_hm['data'].dt.month
            df_hm['ano'] = df_hm['data'].dt.year
            df_hm_pivot = df_hm.groupby(['ano', 'mes'])['resultado'].sum().reset_index()
            df_hm_pivot['mes_label'] = df_hm_pivot['mes'].apply(
                lambda m: ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][m-1]
            )
            heatmap = alt.Chart(df_hm_pivot).mark_rect(cornerRadius=4).encode(
                x=alt.X('mes_label:O', sort=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'],
                        title='Mês'),
                y=alt.Y('ano:O', title='Ano'),
                color=alt.Color('resultado:Q', title='R$',
                                scale=alt.Scale(scheme='redyellowgreen', domainMid=0)),
                tooltip=[
                    alt.Tooltip('ano:O', title='Ano'),
                    alt.Tooltip('mes_label:O', title='Mês'),
                    alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                ]
            ).properties(height=max(80, df_hm_pivot['ano'].nunique() * 50))
            st.altair_chart(heatmap, width="stretch")


# ─────────────────────────────────────────────
# PÁGINA: IMPORTAR NOTAS
# ─────────────────────────────────────────────
elif menu == "📥 Importar Notas":
    st.title("Importar Notas de Corretagem")
    st.markdown("Faça upload dos PDFs ou adicione-os diretamente à pasta `notas_pdf/` no repositório Git.")

    col_scan, col_info = st.columns([1, 3])
    with col_scan:
        if st.button("🔄 Verificar Novos PDFs na Pasta", use_container_width=True):
            novas_git, arqs_git = processar_notas_iniciais(conn)
            if arqs_git:
                st.success(f"**{novas_git}** operação(ões) importada(s) de {len(arqs_git)} arquivo(s):")
                for a in arqs_git:
                    st.write(f"  • {a}")
            else:
                st.info("Nenhum PDF novo encontrado na pasta `notas_pdf/`.")
    with col_info:
        st.caption(
            "Use após `git push` com novos PDFs em `notas_pdf/`. "
            "Arquivos já processados são ignorados automaticamente."
        )
    st.divider()

    uploaded_files = st.file_uploader(
        "Selecione os PDFs das notas de corretagem",
        accept_multiple_files=True,
        type=['pdf']
    )

    processar = st.button("⚙️ Processar Notas", use_container_width=True)

    if processar:
        if uploaded_files:
            os.makedirs('notas_pdf', exist_ok=True)
            c = conn.cursor()
            total_novas = 0
            resultados_upload = []
            ativos_nao_mapeados_geral: set[str] = set()

            progress = st.progress(0)
            for i, file in enumerate(uploaded_files):
                # Sanitiza nome de arquivo contra path traversal
                nome_arquivo = os.path.basename(file.name)
                file_path    = os.path.join('notas_pdf', nome_arquivo)

                try:
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())
                except OSError as exc:
                    st.error(f"Erro ao salvar {nome_arquivo}: {exc}")
                    resultados_upload.append((nome_arquivo, 0, "-", "❌ Erro de escrita"))
                    progress.progress((i + 1) / len(uploaded_files))
                    continue

                c.execute('SELECT COUNT(*) FROM arquivos_processados WHERE nome_arquivo=?', (nome_arquivo,))
                ja_processado = c.fetchone()[0] > 0

                if not ja_processado:
                    try:
                        trades   = parse_pdf(file_path)
                        novas    = save_to_db(trades, conn)
                        total_novas += novas
                        total_tx = sum(t.get('taxa_rateada', 0) for t in trades)
                        c.execute('INSERT OR IGNORE INTO arquivos_processados (nome_arquivo) VALUES (?)', (nome_arquivo,))
                        conn.commit()
                        resultados_upload.append((nome_arquivo, novas, f"R$ {total_tx:.2f}", "✅ Importado"))
                    except Exception as exc:
                        log.error("Falha ao processar '%s': %s", nome_arquivo, exc, exc_info=True)
                        resultados_upload.append((nome_arquivo, 0, "-", f"❌ {exc}"))
                else:
                    resultados_upload.append((nome_arquivo, 0, "-", "⏭️ Já processado"))

                progress.progress((i + 1) / len(uploaded_files))

            st.success(f"Concluído! **{total_novas}** novas operações importadas.")
            df_res = pd.DataFrame(resultados_upload, columns=['Arquivo', 'Operações', 'Taxas capturadas', 'Status'])
            st.dataframe(df_res, width="stretch", hide_index=True)
        else:
            st.warning("Selecione pelo menos um arquivo PDF.")

    st.divider()
    st.subheader("Notas já processadas")
    df_arqs = pd.read_sql_query(
        "SELECT nome_arquivo AS 'Arquivo', data_processamento AS 'Processado em' "
        "FROM arquivos_processados ORDER BY data_processamento DESC",
        conn
    )
    if not df_arqs.empty:
        st.dataframe(df_arqs, width="stretch", hide_index=True)
    else:
        st.info("Nenhuma nota processada ainda.")


# ─────────────────────────────────────────────
# PÁGINA: CARTEIRA ATUAL
# ─────────────────────────────────────────────
elif menu == "💼 Carteira Atual":
    st.title("Carteira Atual")

    df = load_data(conn)
    df_carteira, _, _ = calculate_performance(df)

    if not df_carteira.empty:
        total_investido = df_carteira['Valor Investido'].sum()
        maior_pos_ativo = df_carteira.loc[df_carteira['Valor Investido'].idxmax(), 'Ativo']
        maior_pos_pct   = df_carteira['Valor Investido'].max() / total_investido * 100

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Alocado", fmt_kpi(total_investido))
        c2.metric("Ativos Diferentes", str(len(df_carteira)))
        c3.metric("Maior Posição", f"{maior_pos_ativo} ({maior_pos_pct:.1f}%)")

        st.divider()

        df_view = df_carteira.copy().sort_values('Valor Investido', ascending=False)
        df_view['% Carteira'] = (df_view['Valor Investido'] / total_investido * 100).round(2)
        # Concentração HHI (Herfindahl-Hirschman Index) — 0-10000, >2500 = alta concentração
        hhi = ((df_view['% Carteira'] ** 2).sum())
        st.caption(f"Índice de Concentração HHI: **{hhi:.0f}** {'🔴 Alta' if hhi > 2500 else '🟡 Moderada' if hhi > 1000 else '🟢 Diversificada'}")

        st.dataframe(
            df_view.style
                .format({'Preço Médio': brl4, 'Valor Investido': brl, '% Carteira': '{:.2f}%'})
                .map(lambda v: 'color: #f59e0b' if isinstance(v, (int, float)) and v > 20 else '', subset=['% Carteira']),
            width="stretch",
            hide_index=True
        )

        st.subheader("Concentração por Ativo")
        bar_h = alt.Chart(df_view.head(20)).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
            y=alt.Y('Ativo:N', sort='-x', title=None),
            x=alt.X('Valor Investido:Q', title='Valor Investido (R$)'),
            color=alt.Color('% Carteira:Q', scale=alt.Scale(scheme='blues'), legend=None),
            tooltip=[
                alt.Tooltip('Ativo:N'),
                alt.Tooltip('Quantidade:Q'),
                alt.Tooltip('Preço Médio:Q', format='.4f'),
                alt.Tooltip('Valor Investido:Q', format=',.2f'),
                alt.Tooltip('% Carteira:Q', format='.2f'),
            ]
        ).properties(height=max(200, len(df_view.head(20)) * 28))
        st.altair_chart(bar_h, width="stretch")

        # Linha de aviso de concentração
        if maior_pos_pct > 25:
            st.markdown(
                f'<div class="warn-box">⚠️ <b>{maior_pos_ativo}</b> representa <b>{maior_pos_pct:.1f}%</b> da carteira — concentração elevada.</div>',
                unsafe_allow_html=True
            )
    else:
        st.info("Sua carteira está vazia ou nenhum dado foi carregado.")


# ─────────────────────────────────────────────
# PÁGINA: PERFORMANCE MENSAL
# ─────────────────────────────────────────────
elif menu == "📈 Performance Mensal":
    st.title("Performance Mensal")
    st.caption("Resultado inclui taxas B3 rateadas. IRRF e corretagem Santander não deduzidos.")

    df = load_data(conn)
    _, df_historico, df_mensal = calculate_performance(df)

    if not df_mensal.empty:
        meses_positivos = (df_mensal['resultado'] > 0).sum()
        meses_negativos = (df_mensal['resultado'] <= 0).sum()
        melhor_mes      = df_mensal.loc[df_mensal['resultado'].idxmax(), 'mes_ano']
        melhor_valor    = df_mensal['resultado'].max()
        pior_mes        = df_mensal.loc[df_mensal['resultado'].idxmin(), 'mes_ano']
        pior_valor      = df_mensal['resultado'].min()
        consistencia    = meses_positivos / len(df_mensal) * 100

        c1, c2, c3 = st.columns(3)
        c1.metric("Meses Positivos", f"{meses_positivos}")
        c2.metric("Meses Negativos", f"{meses_negativos}")
        c3.metric("Consistência Mensal", f"{consistencia:.1f}%", help="% de meses com resultado positivo")
        c4, c5 = st.columns(2)
        c4.metric("Melhor Mês", melhor_mes, delta=fmt_kpi(melhor_valor))
        c5.metric("Pior Mês", pior_mes, delta=fmt_kpi(pior_valor))

        st.divider()

        df_chart = df_mensal.copy()
        df_chart['cor'] = df_chart['resultado'].apply(lambda x: '#10b981' if x >= 0 else '#ef4444')

        bars = alt.Chart(df_chart).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X('mes_ano:N', title='Mês/Ano', sort=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('resultado:Q', title='Resultado Bruto (R$)'),
            color=alt.Color('cor:N', scale=None, legend=None),
            tooltip=[
                alt.Tooltip('mes_ano:N', title='Período'),
                alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                alt.Tooltip('trades:Q', title='Trades'),
                alt.Tooltip('win_rate:Q', title='Win Rate (%)', format='.1f'),
                alt.Tooltip('trades_dt:Q', title='DayTrades'),
            ]
        ).properties(height=280)
        st.altair_chart(bars, width="stretch")

        # Resultado acumulado ao longo dos meses
        df_chart['acumulado'] = df_chart['resultado'].cumsum()
        line_acc = alt.Chart(df_chart).mark_line(color='#3b82f6', strokeWidth=2, point=True).encode(
            x=alt.X('mes_ano:N', sort=None, title='Mês/Ano', axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('acumulado:Q', title='Acumulado (R$)'),
            tooltip=[
                alt.Tooltip('mes_ano:N', title='Mês'),
                alt.Tooltip('acumulado:Q', title='Acumulado (R$)', format=',.2f'),
            ]
        ).properties(height=200, title='Resultado Acumulado por Mês')
        st.altair_chart(line_acc, width="stretch")

        # Tabela mensal
        df_mensal_display = df_mensal.copy()
        df_mensal_display.columns = ['Mês/Ano', 'Resultado (R$)', 'Trades', 'Win Rate (%)', 'Day Trades']
        st.dataframe(
            df_mensal_display.style
                .map(color_result, subset=['Resultado (R$)'])
                .format({'Resultado (R$)': brl, 'Win Rate (%)': '{:.1f}%'}),
            width="stretch",
            hide_index=True
        )

        st.divider()
        st.subheader("Detalhamento dos Trades")
        lucros = df_historico[df_historico['resultado'] > 0]['resultado']
        perdas = df_historico[df_historico['resultado'] < 0]['resultado']

        c1, c2 = st.columns(2)
        c1.metric("Maior Ganho", fmt_kpi(lucros.max() if not lucros.empty else 0))
        c2.metric("Maior Perda",  fmt_kpi(perdas.min() if not perdas.empty else 0))
        c3, c4 = st.columns(2)
        c3.metric("Média Ganhos", fmt_kpi(lucros.mean() if not lucros.empty else 0))
        c4.metric("Média Perdas", fmt_kpi(perdas.mean() if not perdas.empty else 0))

        total = df_mensal['resultado'].sum()
        if total > 0:
            st.success(f"**Resultado Acumulado Total: {fmt_brl(total)}**")
        else:
            st.error(f"**Resultado Acumulado Total: {fmt_brl(total)}**")

        # Scatter de retorno por trade
        if not df_historico.empty:
            st.subheader("Distribuição de Retorno por Trade (%)")
            df_scatter = df_historico.copy()
            df_scatter['cor']     = df_scatter['resultado'].apply(lambda x: '#10b981' if x >= 0 else '#ef4444')
            df_scatter['trade_n'] = range(1, len(df_scatter) + 1)
            df_scatter['tipo']    = df_scatter['daytrade'].apply(lambda x: 'DayTrade' if x else 'Swing')

            scatter = alt.Chart(df_scatter).mark_circle(size=60, opacity=0.7).encode(
                x=alt.X('trade_n:Q', title='Trade #'),
                y=alt.Y('retorno_pct:Q', title='Retorno (%)'),
                color=alt.Color('cor:N', scale=None, legend=None),
                shape=alt.Shape('tipo:N', legend=alt.Legend(title='Tipo')),
                tooltip=[
                    alt.Tooltip('ativo:N', title='Ativo'),
                    alt.Tooltip('data:T', title='Data', format='%d/%m/%Y'),
                    alt.Tooltip('tipo:N', title='Tipo'),
                    alt.Tooltip('retorno_pct:Q', title='Retorno (%)', format='.2f'),
                    alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                ]
            ).properties(height=260)
            zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='#2a3548', strokeDash=[4, 4]
            ).encode(y='y:Q')
            st.altair_chart((scatter + zero_line), width="stretch")
    else:
        st.info("Nenhuma operação de venda registrada para calcular performance.")


# ─────────────────────────────────────────────
# PÁGINA: ANÁLISE INDIVIDUAL
# ─────────────────────────────────────────────
elif menu == "🔍 Análise Individual":
    st.title("Análise Individual de BDR")

    df = load_data(conn)
    if df.empty:
        st.info("O banco de dados está vazio.")
    else:
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
        ativos_disponiveis = sorted(df['ativo'].dropna().unique().tolist())

        ativo_selecionado = st.selectbox("Ativo / BDR", ativos_disponiveis)
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            data_inicio = st.date_input("De", value=df['data'].min().date())
        with col_d2:
            data_fim = st.date_input("Até", value=df['data'].max().date())

        df_ativo = df[df['ativo'] == ativo_selecionado].copy()
        df_carteira_bdr, df_historico_bdr, df_mensal_bdr = calculate_performance(df_ativo)
        metrics_bdr = calc_advanced_metrics(df_historico_bdr)

        df_hist_filtrado = pd.DataFrame()
        if not df_historico_bdr.empty:
            df_hist_filtrado = df_historico_bdr[
                (df_historico_bdr['data'].dt.date >= data_inicio) &
                (df_historico_bdr['data'].dt.date <= data_fim)
            ]

        # ── KPIs ──
        st.divider()
        lucro_bdr   = df_hist_filtrado['resultado'].sum() if not df_hist_filtrado.empty else 0.0
        win_bdr     = (df_hist_filtrado['resultado'] > 0).mean() * 100 if not df_hist_filtrado.empty else 0.0
        payoff_bdr  = metrics_bdr.get('payoff_ratio')
        sharpe_bdr  = metrics_bdr.get('sharpe')
        sortino_bdr = metrics_bdr.get('sortino')
        max_dd_bdr  = metrics_bdr.get('max_drawdown', 0.0)
        vol_bdr     = metrics_bdr.get('vol_anual_pct', 0.0)

        c1, c2, c3 = st.columns(3)
        c1.metric("Resultado no Período", fmt_kpi(lucro_bdr))
        c2.metric("Trades no Período",    str(len(df_hist_filtrado)))
        c3.metric("Win Rate",             f"{win_bdr:.1f}%")

        c4, c5, c6 = st.columns(3)
        c4.metric("Payoff Ratio",   fmt_metric(payoff_bdr, ".2f", "×"))
        c5.metric("Sharpe Ratio",   fmt_metric(sharpe_bdr, ".3f"))
        c6.metric("Sortino Ratio",  fmt_metric(sortino_bdr, ".3f"))

        c7, c8, c9 = st.columns(3)
        c7.metric("Max Drawdown",   fmt_metric(max_dd_bdr, ".2f", "", "R$ "))
        c8.metric("Volatilidade Anual", f"{vol_bdr:.1f}%" if vol_bdr else "N/A")
        c9.metric("Recovery Factor", fmt_metric(metrics_bdr.get('recovery_factor'), ".2f", "×"))

        st.divider()
        st.subheader("Posição Atual")
        if not df_carteira_bdr.empty:
            df_pos = df_carteira_bdr[df_carteira_bdr['Ativo'] == ativo_selecionado]
            if not df_pos.empty:
                row_p = df_pos.iloc[0]
                cm1, cm2, cm3 = st.columns(3)
                cm1.metric("Qtde em Carteira", int(row_p['Quantidade']))
                cm2.metric("Preço Médio",      fmt_kpi(row_p['Preço Médio']))
                cm3.metric("Custo Total",      fmt_kpi(row_p['Valor Investido']))
            else:
                st.info("Sem posição aberta.")
        else:
            st.info("Sem posição aberta.")

        st.subheader("Trades Fechados no Período")
        if not df_hist_filtrado.empty:
            df_show = df_hist_filtrado[
                ['data', 'qtde_vendida', 'preco_medio_compra', 'preco_venda', 'resultado', 'retorno_pct', 'daytrade']
            ].copy()
            df_show['data']     = df_show['data'].dt.strftime('%d/%m/%Y')
            df_show['daytrade'] = df_show['daytrade'].apply(lambda x: '⚡ DT' if x else 'Swing')
            df_show.columns     = ['Data', 'Qtde', 'PM Compra', 'Preço Venda', 'Resultado (R$)', 'Retorno (%)', 'Tipo']
            st.dataframe(
                df_show.style
                    .map(color_result, subset=['Resultado (R$)'])
                    .format({
                        'PM Compra':    brl4,
                        'Preço Venda':  brl4,
                        'Resultado (R$)': brl,
                        'Retorno (%)':  '{:+.2f}%'
                    }),
                width="stretch",
                hide_index=True
            )
        else:
            st.info("Nenhuma venda no período selecionado.")

        # Resultado mensal do ativo
        if not df_mensal_bdr.empty:
            st.subheader(f"Resultado Mensal — {ativo_selecionado}")
            df_m_chart = df_mensal_bdr.copy()
            df_m_chart['cor'] = df_m_chart['resultado'].apply(lambda x: '#10b981' if x >= 0 else '#ef4444')
            bars_bdr = alt.Chart(df_m_chart).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X('mes_ano:N', sort=None, title='Mês', axis=alt.Axis(labelAngle=-30)),
                y=alt.Y('resultado:Q', title='Resultado (R$)'),
                color=alt.Color('cor:N', scale=None, legend=None),
                tooltip=[
                    alt.Tooltip('mes_ano:N', title='Mês'),
                    alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                ]
            ).properties(height=220)
            st.altair_chart(bars_bdr, width="stretch")

        # Curva de capital do ativo
        if metrics_bdr.get('curva_capital') is not None and not metrics_bdr['curva_capital'].empty:
            st.subheader(f"Curva de Capital — {ativo_selecionado}")
            curva_bdr = metrics_bdr['curva_capital'].reset_index(drop=True)
            df_cb = pd.DataFrame({'trade_n': range(1, len(curva_bdr) + 1), 'capital': curva_bdr.values})
            line_cb = alt.Chart(df_cb).mark_line(color='#a78bfa', strokeWidth=2).encode(
                x=alt.X('trade_n:Q', title='Trade #'),
                y=alt.Y('capital:Q', title='Acumulado (R$)'),
                tooltip=[alt.Tooltip('trade_n:Q', title='Trade #'),
                         alt.Tooltip('capital:Q', title='Acumulado (R$)', format=',.2f')]
            )
            area_cb = alt.Chart(df_cb).mark_area(color='#a78bfa', opacity=0.15).encode(
                x='trade_n:Q', y='capital:Q'
            )
            zero_cb = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='#2a3548', strokeDash=[4, 4]
            ).encode(y='y:Q')
            st.altair_chart((area_cb + line_cb + zero_cb).properties(height=200), width="stretch")

        # Todas as operações do ativo no período
        st.subheader(f"Todas as Operações de {ativo_selecionado}")
        df_ops = df_ativo[
            (df_ativo['data'].dt.date >= data_inicio) &
            (df_ativo['data'].dt.date <= data_fim)
        ].copy()
        if not df_ops.empty:
            df_ops['data']     = df_ops['data'].dt.strftime('%d/%m/%Y')
            df_ops['cv_label'] = df_ops['cv'].map({'C': '🟢 Compra', 'V': '🔴 Venda'})
            df_ops['daytrade'] = df_ops['daytrade'].apply(lambda x: '⚡ DT' if x else '-') if 'daytrade' in df_ops.columns else '-'
            st.dataframe(
                df_ops[['data', 'cv_label', 'quantidade', 'preco', 'preco_liquido', 'taxa_rateada', 'valor', 'daytrade', 'nr_nota']].rename(columns={
                    'data': 'Data', 'cv_label': 'Tipo', 'quantidade': 'Qtde',
                    'preco': 'Preço Bruto', 'preco_liquido': 'Preço Líq.',
                    'taxa_rateada': 'Taxa', 'valor': 'Valor (R$)',
                    'daytrade': 'DT', 'nr_nota': 'Nota'
                }).style.format({'Preço Bruto': brl4, 'Preço Líq.': brl4, 'Taxa': brl, 'Valor (R$)': brl}),
                width="stretch",
                hide_index=True
            )
        else:
            st.info("Nenhuma operação no período selecionado.")


# ─────────────────────────────────────────────
# PÁGINA: MÉTRICAS AVANÇADAS
# ─────────────────────────────────────────────
elif menu == "🧮 Métricas Avançadas":
    st.title("Métricas Avançadas de Performance")
    st.caption("Análise quantitativa do seu estilo e histórico de trading.")

    df = load_data(conn)
    _, df_historico, _ = calculate_performance(df)
    metrics = calc_advanced_metrics(df_historico)

    if not metrics:
        st.info("Nenhuma operação de venda encontrada para calcular métricas.")
    else:
        # ── Bloco 1: Estatísticas Gerais ──
        st.subheader("📌 Estatísticas Gerais")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total de Trades",     str(metrics['total_trades']))
        c2.metric("Win Rate",            f"{metrics['win_rate']:.2f}%")
        c3.metric("Trades Vencedores",   str(metrics['trades_lucro']))
        c4.metric("Trades Perdedores",   str(metrics['trades_perda']))

        if metrics.get('media_dias_entre_trades') is not None:
            st.caption(f"Frequência média: **{metrics['media_dias_entre_trades']:.1f} dias** entre trades")

        st.divider()

        # ── Bloco 2: Risco/Retorno ──
        st.subheader("📐 Risco e Retorno")
        c1, c2, c3 = st.columns(3)
        c1.metric("Fator de Lucro",  fmt_metric(metrics['fator_lucro'], ".2f", "×"),
                  help="Soma dos ganhos / soma das perdas. >1.5 é saudável.")
        c2.metric("Payoff Ratio",    fmt_metric(metrics['payoff_ratio'], ".2f", "×"),
                  help="Média dos ganhos / média das perdas. >1.0 é positivo.")
        c3.metric("Expectativa/Trade", fmt_kpi(metrics['expectativa']),
                  help="Valor esperado por trade com base no histórico.")

        c4, c5, c6 = st.columns(3)
        c4.metric("Sharpe Simplificado", fmt_metric(metrics['sharpe'], ".3f"),
                  help="Média dos retornos % / desvio padrão. >0 é positivo.")
        c5.metric("Sortino Ratio",       fmt_metric(metrics['sortino'], ".3f"),
                  help="Como Sharpe, mas usa apenas a volatilidade dos retornos negativos.")
        c6.metric("Volatilidade Anual",  f"{metrics['vol_anual_pct']:.1f}%" if metrics['vol_anual_pct'] else "N/A",
                  help="Desvio padrão dos retornos anualizado (√252).")

        st.divider()

        # ── Bloco 3: Drawdown ──
        st.subheader("📉 Drawdown e Recuperação")
        c1, c2, c3 = st.columns(3)
        c1.metric("Máximo Drawdown (R$)", fmt_kpi(metrics['max_drawdown']))
        c2.metric("Máximo Drawdown (%)",  fmt_metric(metrics['max_drawdown_pct'], ".2f", "%"))
        c3.metric("Calmar Ratio",         fmt_metric(metrics['calmar'], ".2f", "×"),
                  help="Lucro total / |Max Drawdown|. >1 é bom.")

        c4, c5 = st.columns(2)
        c4.metric("Recovery Factor", fmt_metric(metrics['recovery_factor'], ".2f", "×"),
                  help="Lucro líquido / |Max Drawdown|. Indica eficiência de recuperação.")
        c5.metric("Maior Seq. de Perdas", f"{metrics['max_seq_loss']} trades")

        if metrics.get('drawdown_series') is not None and not metrics['drawdown_series'].empty:
            dd = metrics['drawdown_series'].reset_index(drop=True)
            df_dd = pd.DataFrame({'trade_n': range(1, len(dd) + 1), 'drawdown': dd.values})
            dd_area = alt.Chart(df_dd).mark_area(
                color='#ef4444', opacity=0.3,
                line={'color': '#ef4444', 'strokeWidth': 1.5}
            ).encode(
                x=alt.X('trade_n:Q', title='Trade #'),
                y=alt.Y('drawdown:Q', title='Drawdown (R$)'),
                tooltip=[
                    alt.Tooltip('trade_n:Q', title='Trade #'),
                    alt.Tooltip('drawdown:Q', title='Drawdown (R$)', format=',.2f')
                ]
            ).properties(height=200, title='Série de Drawdown')
            st.altair_chart(dd_area, width="stretch")

        st.divider()

        # ── Bloco 4: Sequências & Extremos ──
        st.subheader("🔢 Sequências & Extremos")
        c1, c2 = st.columns(2)
        c1.metric("Maior Seq. de Ganhos", f"{metrics['max_seq_win']} trades")
        c2.metric("Maior Seq. de Perdas", f"{metrics['max_seq_loss']} trades")
        c3, c4 = st.columns(2)
        c3.metric("Maior Ganho (Trade)", fmt_kpi(metrics['maior_lucro']))
        c4.metric("Maior Perda (Trade)", fmt_kpi(metrics['maior_perda']))

        st.divider()

        # ── Bloco 5: Distribuição ──
        st.subheader("📊 Distribuição dos Retornos (%)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Retorno Médio",  f"{metrics['retorno_medio_pct']:+.2f}%")
        c2.metric("Melhor Trade",   f"{metrics['retorno_melhor_pct']:+.2f}%")
        c3.metric("Pior Trade",     f"{metrics['retorno_pior_pct']:+.2f}%")

        if not df_historico.empty:
            hist = alt.Chart(df_historico).mark_bar(
                cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color='#3b82f6', opacity=0.8
            ).encode(
                x=alt.X('retorno_pct:Q', bin=alt.Bin(maxbins=30), title='Retorno (%)'),
                y=alt.Y('count():Q', title='Frequência'),
                tooltip=[
                    alt.Tooltip('retorno_pct:Q', bin=True, title='Retorno (%)'),
                    alt.Tooltip('count():Q', title='Nº de Trades')
                ]
            ).properties(height=220, title='Histograma de Retornos')
            st.altair_chart(hist, width="stretch")

            # Métricas rolling (janela de 20 trades)
            if len(df_historico) >= 20:
                st.divider()
                st.subheader("📈 Métricas Rolling (Janela de 20 Trades)")
                df_roll = df_historico.copy().reset_index(drop=True)
                df_roll['trade_n']       = range(1, len(df_roll) + 1)
                df_roll['wr_rolling']    = (df_roll['resultado'] > 0).rolling(20).mean() * 100
                df_roll['ret_rolling']   = df_roll['retorno_pct'].rolling(20).mean()
                df_roll['vol_rolling']   = df_roll['retorno_pct'].rolling(20).std()

                line_wr = alt.Chart(df_roll.dropna(subset=['wr_rolling'])).mark_line(
                    color='#10b981', strokeWidth=2
                ).encode(
                    x=alt.X('trade_n:Q', title='Trade #'),
                    y=alt.Y('wr_rolling:Q', title='Win Rate Rolling (%)'),
                    tooltip=[alt.Tooltip('trade_n:Q', title='Trade #'),
                             alt.Tooltip('wr_rolling:Q', title='WR% (20)', format='.1f')]
                )
                rule50 = alt.Chart(pd.DataFrame({'y': [50]})).mark_rule(
                    color='#64748b', strokeDash=[4, 4]
                ).encode(y='y:Q')
                st.altair_chart((line_wr + rule50).properties(height=180, title='Win Rate Rolling (20 trades)'),
                                width="stretch")

                line_vol = alt.Chart(df_roll.dropna(subset=['vol_rolling'])).mark_line(
                    color='#f59e0b', strokeWidth=2
                ).encode(
                    x=alt.X('trade_n:Q', title='Trade #'),
                    y=alt.Y('vol_rolling:Q', title='Volatilidade (%)'),
                    tooltip=[alt.Tooltip('trade_n:Q', title='Trade #'),
                             alt.Tooltip('vol_rolling:Q', title='Vol% (20)', format='.2f')]
                ).properties(height=160, title='Volatilidade Rolling (20 trades)')
                st.altair_chart(line_vol, width="stretch")

        st.divider()

        # ── Bloco 6: Ranking por Ativo ──
        st.subheader("🏆 Ranking de Ativos por Resultado")
        df_rank = (
            df_historico.groupby('ativo')
            .agg(
                resultado_total=('resultado', 'sum'),
                trades=('resultado', 'count'),
                win_rate=('resultado', lambda x: (x > 0).mean() * 100),
                retorno_medio=('retorno_pct', 'mean'),
                maior_ganho=('resultado', 'max'),
                maior_perda=('resultado', 'min'),
            )
            .reset_index()
            .sort_values('resultado_total', ascending=False)
        )
        df_rank.columns = ['Ativo', 'Resultado (R$)', 'Trades', 'Win Rate (%)',
                           'Retorno Médio (%)', 'Maior Ganho (R$)', 'Maior Perda (R$)']
        st.dataframe(
            df_rank.style
                .map(color_result, subset=['Resultado (R$)', 'Maior Ganho (R$)', 'Maior Perda (R$)'])
                .format({
                    'Resultado (R$)':   brl,
                    'Win Rate (%)':     '{:.1f}%',
                    'Retorno Médio (%)': '{:+.2f}%',
                    'Maior Ganho (R$)': brl,
                    'Maior Perda (R$)': brl,
                }),
            width="stretch",
            hide_index=True
        )

        bar_rank = alt.Chart(df_rank.head(15)).mark_bar(
            cornerRadiusTopRight=4, cornerRadiusBottomRight=4
        ).encode(
            y=alt.Y('Ativo:N', sort='-x', title=None),
            x=alt.X('Resultado (R$):Q', title='Resultado Acumulado (R$)'),
            color=alt.condition(
                alt.datum['Resultado (R$)'] > 0,
                alt.value('#10b981'),
                alt.value('#ef4444')
            ),
            tooltip=[
                alt.Tooltip('Ativo:N'),
                alt.Tooltip('Resultado (R$):Q', format=',.2f'),
                alt.Tooltip('Win Rate (%):Q', format='.1f'),
                alt.Tooltip('Retorno Médio (%):Q', format='.2f'),
            ]
        ).properties(height=max(180, len(df_rank.head(15)) * 28))
        st.altair_chart(bar_rank, width="stretch")

        # Correlação entre ativos (se houver pelo menos 2)
        if df_historico['ativo'].nunique() >= 2:
            st.divider()
            st.subheader("🔗 Correlação entre Ativos")
            df_corr_pivot = df_historico.pivot_table(
                index='mes_ano', columns='ativo', values='resultado', aggfunc='sum'
            ).fillna(0)
            if df_corr_pivot.shape[0] > 2 and df_corr_pivot.shape[1] >= 2:
                corr_matrix = df_corr_pivot.corr()
                corr_long = corr_matrix.reset_index().melt(id_vars='ativo', var_name='ativo2', value_name='correlacao')
                heat_corr = alt.Chart(corr_long).mark_rect().encode(
                    x=alt.X('ativo:O', title=None),
                    y=alt.Y('ativo2:O', title=None),
                    color=alt.Color('correlacao:Q',
                                    scale=alt.Scale(scheme='redblue', domain=[-1, 0, 1]),
                                    title='Correlação'),
                    tooltip=[
                        alt.Tooltip('ativo:O', title='Ativo A'),
                        alt.Tooltip('ativo2:O', title='Ativo B'),
                        alt.Tooltip('correlacao:Q', title='Correlação', format='.2f'),
                    ]
                ).properties(
                    height=max(200, corr_matrix.shape[0] * 40),
                    title='Correlação de Resultados Mensais entre Ativos'
                )
                st.altair_chart(heat_corr, width="stretch")
                st.caption("Baseado em resultado mensal por ativo. Correlação negativa = diversificação eficiente.")
            else:
                st.caption("Dados insuficientes para matriz de correlação (mínimo 3 meses e 2 ativos).")


# ─────────────────────────────────────────────
# PÁGINA: DAY TRADE vs SWING
# ─────────────────────────────────────────────
elif menu == "⚡ Day Trade vs Swing":
    st.title("Day Trade vs Swing Trade")
    st.caption("Comparação detalhada entre as duas modalidades de operação.")

    df = load_data(conn)
    _, df_historico, _ = calculate_performance(df)

    if df_historico.empty:
        st.info("Nenhuma operação de venda registrada.")
    else:
        df_dt = df_historico[df_historico['daytrade'] == True].copy()
        df_sw = df_historico[df_historico['daytrade'] == False].copy()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("⚡ Day Trade")
            if not df_dt.empty:
                wr_dt  = (df_dt['resultado'] > 0).mean() * 100
                med_dt = df_dt['resultado'].mean()
                m_dt   = calc_advanced_metrics(df_dt)
                st.metric("Total de Trades",     str(len(df_dt)))
                st.metric("Resultado Total",     fmt_kpi(df_dt['resultado'].sum()))
                st.metric("Win Rate",            f"{wr_dt:.1f}%")
                st.metric("Média por Trade",     fmt_kpi(med_dt))
                st.metric("Payoff Ratio",        fmt_metric(m_dt.get('payoff_ratio'), ".2f", "×"))
                st.metric("Fator de Lucro",      fmt_metric(m_dt.get('fator_lucro'), ".2f", "×"))
                st.metric("Max Drawdown",        fmt_metric(m_dt.get('max_drawdown'), ".2f", "", "R$ "))
                st.metric("Sharpe",              fmt_metric(m_dt.get('sharpe'), ".3f"))
            else:
                st.info("Nenhum Day Trade registrado.")

        with col2:
            st.subheader("📅 Swing Trade")
            if not df_sw.empty:
                wr_sw  = (df_sw['resultado'] > 0).mean() * 100
                med_sw = df_sw['resultado'].mean()
                m_sw   = calc_advanced_metrics(df_sw)
                st.metric("Total de Trades",     str(len(df_sw)))
                st.metric("Resultado Total",     fmt_kpi(df_sw['resultado'].sum()))
                st.metric("Win Rate",            f"{wr_sw:.1f}%")
                st.metric("Média por Trade",     fmt_kpi(med_sw))
                st.metric("Payoff Ratio",        fmt_metric(m_sw.get('payoff_ratio'), ".2f", "×"))
                st.metric("Fator de Lucro",      fmt_metric(m_sw.get('fator_lucro'), ".2f", "×"))
                st.metric("Max Drawdown",        fmt_metric(m_sw.get('max_drawdown'), ".2f", "", "R$ "))
                st.metric("Sharpe",              fmt_metric(m_sw.get('sharpe'), ".3f"))
            else:
                st.info("Nenhum Swing Trade registrado.")

        st.divider()

        # Comparativo visual
        if not df_dt.empty and not df_sw.empty:
            st.subheader("Comparativo de Resultados por Mês")
            df_dt_m = df_dt.groupby('mes_ano')['resultado'].sum().reset_index()
            df_dt_m['tipo'] = 'Day Trade'
            df_sw_m = df_sw.groupby('mes_ano')['resultado'].sum().reset_index()
            df_sw_m['tipo'] = 'Swing'
            df_comp = pd.concat([df_dt_m, df_sw_m])

            bars_comp = alt.Chart(df_comp).mark_bar().encode(
                x=alt.X('mes_ano:N', title='Mês', sort=None, axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('resultado:Q', title='Resultado (R$)'),
                color=alt.Color('tipo:N', scale=alt.Scale(
                    domain=['Day Trade', 'Swing'],
                    range=['#f59e0b', '#3b82f6']
                )),
                xOffset='tipo:N',
                tooltip=[
                    alt.Tooltip('mes_ano:N', title='Mês'),
                    alt.Tooltip('tipo:N', title='Tipo'),
                    alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                ]
            ).properties(height=280)
            st.altair_chart(bars_comp, width="stretch")

            # Histograma comparativo de retornos
            st.subheader("Distribuição de Retornos — Day Trade vs Swing (%)")
            df_hist_comp = pd.concat([
                df_dt[['retorno_pct']].assign(tipo='Day Trade'),
                df_sw[['retorno_pct']].assign(tipo='Swing')
            ])
            hist_comp = alt.Chart(df_hist_comp).mark_bar(opacity=0.6).encode(
                x=alt.X('retorno_pct:Q', bin=alt.Bin(maxbins=25), title='Retorno (%)'),
                y=alt.Y('count():Q', title='Frequência', stack=None),
                color=alt.Color('tipo:N', scale=alt.Scale(
                    domain=['Day Trade', 'Swing'],
                    range=['#f59e0b', '#3b82f6']
                )),
                tooltip=[
                    alt.Tooltip('tipo:N', title='Tipo'),
                    alt.Tooltip('retorno_pct:Q', bin=True, title='Retorno (%)'),
                    alt.Tooltip('count():Q', title='Frequência'),
                ]
            ).properties(height=220)
            st.altair_chart(hist_comp, width="stretch")

        # Tabela combinada
        st.divider()
        st.subheader("Todos os Trades Fechados")
        df_todos = df_historico.copy()
        df_todos['Tipo']    = df_todos['daytrade'].apply(lambda x: '⚡ DT' if x else 'Swing')
        df_todos['Data']    = df_todos['data'].dt.strftime('%d/%m/%Y')
        df_show = df_todos[['Data', 'ativo', 'Tipo', 'qtde_vendida', 'preco_medio_compra', 'preco_venda', 'resultado', 'retorno_pct']].copy()
        df_show.columns     = ['Data', 'Ativo', 'Tipo', 'Qtde', 'PM Compra', 'Preço Venda', 'Resultado (R$)', 'Retorno (%)']
        st.dataframe(
            df_show.style
                .map(color_result, subset=['Resultado (R$)'])
                .format({'PM Compra': brl4, 'Preço Venda': brl4, 'Resultado (R$)': brl, 'Retorno (%)': '{:+.2f}%'}),
            width="stretch",
            hide_index=True
        )


# ─────────────────────────────────────────────
# PÁGINA: HISTÓRICO DE OPERAÇÕES
# ─────────────────────────────────────────────
elif menu == "📋 Histórico de Operações":
    st.title("Histórico Completo de Operações")

    df = load_data(conn)
    if df.empty:
        st.info("Nenhuma operação encontrada.")
    else:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            ativos_filtro = ['Todos'] + sorted(df['ativo'].unique().tolist())
            ativo_filtro  = st.selectbox("Filtrar por Ativo", ativos_filtro)
        with col_f2:
            tipo_filtro = st.selectbox("Tipo", ['Todos', 'Compra (C)', 'Venda (V)'])
        with col_f3:
            dt_filtro = st.selectbox("DayTrade", ['Todos', 'Somente DT', 'Somente Swing'])

        df_view = df.copy()
        if ativo_filtro != 'Todos':
            df_view = df_view[df_view['ativo'] == ativo_filtro]
        if tipo_filtro == 'Compra (C)':
            df_view = df_view[df_view['cv'] == 'C']
        elif tipo_filtro == 'Venda (V)':
            df_view = df_view[df_view['cv'] == 'V']
        if dt_filtro == 'Somente DT' and 'daytrade' in df_view.columns:
            df_view = df_view[df_view['daytrade'] == 1]
        elif dt_filtro == 'Somente Swing' and 'daytrade' in df_view.columns:
            df_view = df_view[df_view['daytrade'] == 0]

        df_view['cv']       = df_view['cv'].map({'C': '🟢 Compra', 'V': '🔴 Venda'})
        df_view['daytrade'] = df_view['daytrade'].map({1: '⚡ Sim', 0: 'Não'}) if 'daytrade' in df_view.columns else 'Não'

        cols_show = ['data', 'cv', 'ativo', 'quantidade', 'preco', 'preco_liquido', 'taxa_rateada', 'valor', 'daytrade', 'nr_nota']
        cols_show = [c for c in cols_show if c in df_view.columns]
        df_view   = df_view[cols_show].rename(columns={
            'data': 'Data', 'cv': 'Tipo', 'ativo': 'Ativo',
            'quantidade': 'Qtde', 'preco': 'Preço Bruto',
            'preco_liquido': 'Preço Líq.', 'taxa_rateada': 'Taxa Rateada',
            'valor': 'Valor (R$)', 'daytrade': 'DayTrade', 'nr_nota': 'Nota'
        })

        st.caption(f"Exibindo **{len(df_view)}** de **{len(df)}** operações")
        fmt_cols = {c: brl4 for c in ['Preço Bruto', 'Preço Líq.'] if c in df_view.columns}
        fmt_cols.update({c: brl for c in ['Taxa Rateada', 'Valor (R$)'] if c in df_view.columns})
        st.dataframe(df_view.style.format(fmt_cols), width="stretch", hide_index=True)

        col_csv, col_xlsx = st.columns(2)
        with col_csv:
            csv_data = df_view.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="⬇️ Exportar CSV",
                data=csv_data,
                file_name=f"historico_{datetime.date.today()}.csv",
                mime='text/csv'
            )
        with col_xlsx:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_view.to_excel(writer, index=False, sheet_name='Operações')
            buf.seek(0)
            st.download_button(
                label="⬇️ Exportar Excel",
                data=buf,
                file_name=f"historico_{datetime.date.today()}.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )


# ─────────────────────────────────────────────
# PÁGINA: QUALIDADE DOS DADOS
# ─────────────────────────────────────────────
elif menu == "🔬 Qualidade dos Dados":
    st.title("Qualidade dos Dados")
    st.caption("Diagnóstico automático de integridade, consistência e completude das operações importadas.")

    df = load_data(conn)
    if df.empty:
        st.info("Nenhum dado carregado.")
    else:
        alertas = calc_qualidade_dados(df)

        if not alertas:
            st.success("✅ Nenhum problema de qualidade detectado nos dados.")
        else:
            erros  = [a for a in alertas if a['nivel'] == 'erro']
            avisos = [a for a in alertas if a['nivel'] == 'aviso']
            if erros:
                st.error(f"**{len(erros)} problema(s) crítico(s) encontrado(s):**")
                for e in erros:
                    st.markdown(f"• 🔴 {e['mensagem']}")
            if avisos:
                st.warning(f"**{len(avisos)} aviso(s):**")
                for a in avisos:
                    st.markdown(f"• 🟡 {a['mensagem']}")

        st.divider()
        st.subheader("Resumo Estatístico das Operações")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total de Operações",   str(len(df)))
        c2.metric("Ativos Únicos",        str(df['ativo'].nunique()))
        c3.metric("Notas Processadas",    str(df['nr_nota'].nunique()) if 'nr_nota' in df.columns else "N/A")
        datas_ok = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce').notna()
        c4.metric("Datas Válidas",        f"{datas_ok.sum()}/{len(df)}")

        st.divider()
        st.subheader("Distribuição por Ativo")
        df_dist = df.groupby('ativo').agg(
            operacoes=('id', 'count'),
            compras=('cv', lambda x: (x == 'C').sum()),
            vendas=('cv', lambda x: (x == 'V').sum()),
            valor_total=('valor', 'sum'),
        ).reset_index().sort_values('operacoes', ascending=False)
        df_dist.columns = ['Ativo', 'Operações', 'Compras', 'Vendas', 'Valor Total (R$)']
        st.dataframe(
            df_dist.style.format({'Valor Total (R$)': brl}),
            width="stretch", hide_index=True
        )

        st.divider()
        st.subheader("Distribuição de Operações por Período")
        df_periodo = df.copy()
        df_periodo['data_dt'] = pd.to_datetime(df_periodo['data'], format='%d/%m/%Y', errors='coerce')
        df_periodo = df_periodo.dropna(subset=['data_dt'])
        df_periodo['mes_ano'] = df_periodo['data_dt'].dt.strftime('%Y-%m')
        df_por_mes = df_periodo.groupby('mes_ano').agg(
            operacoes=('id', 'count'),
            ativos=('ativo', 'nunique'),
            valor_total=('valor', 'sum'),
        ).reset_index()
        df_por_mes.columns = ['Mês/Ano', 'Operações', 'Ativos', 'Volume (R$)']

        bar_ops = alt.Chart(df_por_mes).mark_bar(color='#3b82f6', cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X('Mês/Ano:N', sort=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('Operações:Q', title='Nº de Operações'),
            tooltip=[
                alt.Tooltip('Mês/Ano:N', title='Mês'),
                alt.Tooltip('Operações:Q'),
                alt.Tooltip('Ativos:Q', title='Ativos diferentes'),
                alt.Tooltip('Volume (R$):Q', format=',.2f'),
            ]
        ).properties(height=220, title='Volume de Operações por Mês')
        st.altair_chart(bar_ops, width="stretch")

        st.divider()
        st.subheader("Ativos Não Mapeados para Ticker B3")
        ativos_db = set(df['ativo'].unique())
        nao_mapeados = [a for a in ativos_db if a not in _TICKERS_CONHECIDOS and not re.search(r'\d{1,2}$', str(a))]
        if nao_mapeados:
            st.warning(
                "Os seguintes ativos não foram reconhecidos como tickers B3 padrão. "
                "Verifique se precisam ser adicionados ao dicionário `NOME_PARA_TICKER`:"
            )
            for nm in sorted(nao_mapeados):
                st.markdown(f"• `{nm}`")
        else:
            st.success("Todos os ativos estão mapeados para tickers B3.")
