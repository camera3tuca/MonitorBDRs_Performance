"""
Carteira BDR — Monitor de Performance
Consolida notas mensais Santander + análise detalhada por BDR selecionável.
"""

import os
import streamlit as st
import pandas as pd
from pathlib import Path
from src.database import init_db, carregar
from src.parser import auto_load
from src.financials import calc_posicao, calc_pl_mes
from src.config import DATA_DIR
from src.ui.sidebar import render_sidebar
from src.ui.dashboard import render_dashboard
from src.ui.assets import render_assets
from src.ui.analysis import render_analysis
from src.ui.operations import render_operations

# ── Configuração da página ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="Carteira BDR", page_icon="📊",
    layout="wide", initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
[data-testid="stSidebar"]{background:#0f0f1a}
.block-container{padding-top:.8rem;padding-bottom:2rem;max-width:900px}
</style>""", unsafe_allow_html=True)

# ── Init ──────────────────────────────────────────────────────────────────────
init_db()
if "loaded" not in st.session_state:
    n = auto_load()
    st.session_state.loaded = True
    if n: st.session_state.msg = f"✅ {n} operações carregadas de `{DATA_DIR}/`"
if "msg" in st.session_state:
    st.toast(st.session_state.pop("msg"), icon="📂")

# ── Sidebar ───────────────────────────────────────────────────────────────────
render_sidebar()

# ── Carregar dados ────────────────────────────────────────────────────────────
df = carregar()
dfs = [df] if not df.empty else []

# Load additional CSV data files dynamically
csv_files = list(Path(DATA_DIR).glob("*.csv"))
for csv_file in csv_files:
    try:
        df_csv = pd.read_csv(csv_file)
        if "data_dt" not in df_csv.columns and "Data" in df_csv.columns:
            df_csv["data"] = df_csv["Data"]
            df_csv["data_dt"] = pd.to_datetime(df_csv["data"], dayfirst=True, errors="coerce")
            df_csv["mes"] = df_csv["data_dt"].dt.strftime("%Y-%m")
            df_csv["mes_label"] = df_csv["data_dt"].dt.strftime("%b/%Y")

        # Mapping column names from csv to expected format
        col_map = {
            "Nota": "nr_nota", "Ativo": "nome", "Ticker": "ticker",
            "C/V": "cv", "DT": "day_trade", "Qtd": "quantidade",
            "Preço": "preco", "Valor R$": "valor"
        }
        df_csv = df_csv.rename(columns=col_map)

        # Data cleaning for CSVs
        if "preco" in df_csv.columns and df_csv["preco"].dtype == 'O':
            df_csv["preco"] = df_csv["preco"].str.replace("R$ ", "").str.replace(".", "").str.replace(",", ".").astype(float)
        if "valor" in df_csv.columns and df_csv["valor"].dtype == 'O':
            df_csv["valor"] = df_csv["valor"].str.replace("R$ ", "").str.replace(".", "").str.replace(",", ".").astype(float)
        if "day_trade" in df_csv.columns:
            df_csv["day_trade"] = df_csv["day_trade"].map({"✅": True, "—": False, True: True, False: False}).astype(bool)
        if "quantidade" in df_csv.columns:
            df_csv["quantidade"] = df_csv["quantidade"].astype(float)

        dfs.append(df_csv)
    except FileNotFoundError:
        pass

if dfs:
    df = pd.concat(dfs, ignore_index=True)
else:
    df = pd.DataFrame()

if df.empty:
    st.title("📊 Carteira BDR")
    st.info(f"Importe uma nota PDF pelo menu lateral ← ou coloque PDFs ou CSVs em `{DATA_DIR}/`.")
    st.stop()

pos = calc_posicao(df)
plm = calc_pl_mes(df)

# ── Tabs ──────────────────────────────────────────────────────────────────────
t1, t2, t3, t4 = st.tabs([
    "📈 Dashboard", "📋 Todos os Ativos",
    "🔍 Análise por Ativo", "📄 Operações"
])

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Dashboard
# ══════════════════════════════════════════════════════════════════════════════
with t1:
    render_dashboard(df, pos, plm)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Todos os Ativos
# ══════════════════════════════════════════════════════════════════════════════
with t2:
    render_assets(pos)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — Análise por Ativo (COMPLETA)
# ══════════════════════════════════════════════════════════════════════════════
with t3:
    render_analysis(df, pos)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — Operações (histórico completo)
# ══════════════════════════════════════════════════════════════════════════════
with t4:
    render_operations(df)
