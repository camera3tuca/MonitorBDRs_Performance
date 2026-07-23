"""
MonitorBDRs · Performance — dashboard de operações na B3.

Fonte de dados: relatórios MyCapital "Operações no mês" (PDF). Esses
relatórios já trazem os resultados apurados (Normal/Day-trade/Proventos)
por ativo e por operação, usando os códigos B3 reais — então batem 100%
com a contabilidade oficial, sem recálculo de preço médio nem FIFO.
"""

import datetime
import glob
import logging
import os
import sqlite3

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from mycapital import parse_mycapital_ops

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="MonitorBDRs · Performance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

RELATORIOS_DIR = "notas_pdf"          # pasta onde ficam os PDFs MyCapital
RELATORIOS_GLOB = "Opera*.pdf"        # padrão dos relatórios "Operações no mês"
DB_PATH = "carteira.db"

# ─────────────────────────────────────────────
# CSS — design escuro/financeiro
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0b0e16; color: #e2e8f0; }
    .main .block-container { padding: 1.25rem 1.5rem 3rem 1.5rem !important; max-width: 1500px !important; }

    /* ── Esconde a sidebar e seu botão (navegação fica no topo) ── */
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }

    /* ── KPI cards ── */
    [data-testid="stMetric"] {
        background: linear-gradient(150deg, #161d30 0%, #131a2a 100%);
        border: 1px solid #243049; border-radius: 16px; padding: 14px 18px 12px 18px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.30);
        overflow: visible !important; min-height: 104px;
        display: flex !important; flex-direction: column; justify-content: center;
    }
    [data-testid="stMetric"] > div { overflow: visible !important; }
    [data-testid="stMetricLabel"] { overflow: visible !important; }
    [data-testid="stMetricLabel"] p {
        color: #7c8aa5 !important; font-size: 0.68rem !important; font-weight: 600 !important;
        letter-spacing: 0.07em !important; text-transform: uppercase !important;
        white-space: normal !important; overflow: visible !important; line-height: 1.25 !important;
    }
    [data-testid="stMetricValue"] {
        color: #f8fafc !important; font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.35rem !important; font-weight: 700 !important;
        white-space: nowrap !important; overflow: visible !important;
        text-overflow: clip !important; line-height: 1.35 !important;
    }
    [data-testid="stMetricValue"] > div { overflow: visible !important; text-overflow: clip !important; }
    [data-testid="stMetricDelta"] { font-size: 0.78rem !important; }

    /* ── Navegação de topo (st.radio horizontal estilizado como pills) ── */
    div[role="radiogroup"] { gap: 6px !important; flex-wrap: wrap !important; }
    div[role="radiogroup"] label {
        background: #131a2a !important; border: 1px solid #243049 !important;
        border-radius: 10px !important; padding: 7px 14px !important; margin: 0 !important;
        transition: all .15s ease; cursor: pointer;
    }
    div[role="radiogroup"] label:hover { border-color: #3b82f6 !important; background: #18223a !important; }
    div[role="radiogroup"] label[data-baseweb] > div:first-child { display: none !important; }
    div[role="radiogroup"] label p { color: #cbd5e1 !important; font-size: 0.86rem !important; font-weight: 600 !important; }
    div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important; border-color: #2563eb !important;
    }
    div[role="radiogroup"] label:has(input:checked) p { color: #fff !important; }
    h1 { color: #f1f5f9 !important; font-weight: 700 !important; font-size: 1.7rem !important;
         letter-spacing: -0.02em; margin-bottom: 0.25rem !important; }
    h2 { color: #cbd5e1 !important; font-weight: 600 !important; font-size: 1.15rem !important; }
    h3 { color: #94a3b8 !important; font-weight: 500 !important; }
    [data-testid="stDataFrame"] { border: 1px solid #1e2535 !important; border-radius: 10px !important; overflow: hidden; }
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { font-size: 0.82rem !important; }
    hr { border-color: #1e2535 !important; margin: 1rem 0 !important; }
    .stButton > button {
        background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white !important;
        border: none !important; border-radius: 10px !important; font-weight: 600 !important;
        font-size: 0.9rem !important; padding: 0.6rem 1.5rem !important; width: 100% !important;
    }
    .stButton > button:hover { background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        box-shadow: 0 4px 15px rgba(37,99,235,0.4) !important; }
    .stAlert { border-radius: 10px !important; border-left-width: 4px !important; }
    .stSelectbox > div > div { background-color: #1a2035 !important; border-color: #2a3548 !important;
        color: #e2e8f0 !important; font-size: 0.9rem !important; }
    [data-testid="stFileUploadDropzone"] { background-color: #1a2035 !important;
        border: 2px dashed #2a3548 !important; border-radius: 10px !important; }
    .badge-pos { color: #10b981; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .badge-neg { color: #ef4444; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .badge-neu { color: #94a3b8; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
    [data-testid="stCaptionContainer"] p { font-size: 0.78rem !important; color: #64748b !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# FORMATADORES
# ─────────────────────────────────────────────
# Moeda corrente (trocada conforme a corretora selecionada)
CFG = {"moeda": "R$"}


def brl(v) -> str:
    try:
        s = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{CFG['moeda']} {s}"
    except (TypeError, ValueError):
        return str(v)


def fmt_kpi(value: float) -> str:
    s = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    m = CFG["moeda"]
    return f"{m} {s}" if value >= 0 else f"- {m} {s}"


def fmt_pct(value: float, sign: bool = True) -> str:
    return f"{value:+.1f}%" if sign else f"{value:.1f}%"


def color_result(val):
    try:
        v = float(str(val).replace("R$", "").replace(".", "").replace(",", ".").strip())
        c = "#10b981" if v > 0 else ("#ef4444" if v < 0 else "#94a3b8")
        return f"color: {c}; font-family: JetBrains Mono, monospace; font-weight: 600"
    except Exception:
        return ""


# ─────────────────────────────────────────────
# TEMA ALTAIR
# ─────────────────────────────────────────────
@alt.theme.register("dark_finance", enable=True)
def _dark_finance_theme():
    return {"config": {
        "background": "transparent",
        "view": {"stroke": "transparent"},
        "axis": {"domainColor": "#2a3548", "gridColor": "#1e2535",
                 "labelColor": "#64748b", "titleColor": "#94a3b8",
                 "labelFont": "Inter", "titleFont": "Inter"},
        "legend": {"labelColor": "#94a3b8", "titleColor": "#64748b", "labelFont": "Inter"},
        "title": {"color": "#cbd5e1", "font": "Inter"},
    }}

VERDE, VERMELHO, AZUL, CINZA = "#22c55e", "#ef4444", "#3b82f6", "#64748b"


# ─────────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────────
def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo TEXT, mercado TEXT, ticker TEXT, data TEXT, tipo TEXT,
            daytrade INTEGER, quantidade REAL, preco REAL, valor REAL,
            res_daytrade REAL, res_normal REAL, res_outros REAL, arquivo TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT UNIQUE, periodo TEXT,
            data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


conn = init_db()


def _salvar_ops(ops: list[dict], arquivo: str, conn: sqlite3.Connection) -> int:
    c = conn.cursor()
    for o in ops:
        c.execute(
            """INSERT INTO operacoes
               (periodo, mercado, ticker, data, tipo, daytrade, quantidade,
                preco, valor, res_daytrade, res_normal, res_outros, arquivo)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (o["periodo"], o["mercado"], o["ticker"], o["data"], o["tipo"],
             1 if o["daytrade"] else 0, o["quantidade"], o["preco"], o["valor"],
             o["res_daytrade"], o["res_normal"], o["res_outros"], arquivo),
        )
    conn.commit()
    return len(ops)


def processar_relatorios(conn: sqlite3.Connection) -> tuple[int, list[str]]:
    """Varre a pasta de relatórios e importa os ainda não processados."""
    os.makedirs(RELATORIOS_DIR, exist_ok=True)
    c = conn.cursor()
    novos: list[str] = []
    total = 0
    for caminho in sorted(glob.glob(os.path.join(RELATORIOS_DIR, RELATORIOS_GLOB))):
        nome = os.path.basename(caminho)
        c.execute("SELECT COUNT(*) FROM relatorios WHERE nome_arquivo=?", (nome,))
        if c.fetchone()[0]:
            continue
        try:
            ops = parse_mycapital_ops(caminho)
            if not ops:
                log.warning("Relatório %s sem operações reconhecidas.", nome)
                continue
            n = _salvar_ops(ops, nome, conn)
            periodo = ops[0]["periodo"]
            c.execute("INSERT OR IGNORE INTO relatorios (nome_arquivo, periodo) VALUES (?,?)",
                      (nome, periodo))
            conn.commit()
            total += n
            novos.append(nome)
            log.info("Relatório %s importado: %d operações (%s).", nome, n, periodo)
        except Exception as exc:
            log.error("Falha ao processar %s: %s", nome, exc)
    return total, novos


@st.cache_data(show_spinner=False)
def load_ops(_conn: sqlite3.Connection, _cache_key: int) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM operacoes", _conn)
    if df.empty:
        return df
    df["data_dt"] = pd.to_datetime(df["data"], format="%d/%m/%y", errors="coerce")
    df["resultado"] = df["res_normal"] + df["res_daytrade"]
    return df


def _cache_key(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM operacoes").fetchone()[0]


EXTRATOS_DIR = "extratos_ir"


def _ir_cache_key() -> str:
    files = sorted(glob.glob(os.path.join(EXTRATOS_DIR, "*.pdf")))
    return "|".join(f"{f}:{os.path.getmtime(f):.0f}" for f in files)


@st.cache_data(show_spinner=False)
def load_ir_oficial(_key: str) -> dict:
    """Apuração oficial de IR a partir dos Extratos Mensais (extratos_ir/)."""
    from mycapital import parse_extrato_ir
    dados: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(EXTRATOS_DIR, "*.pdf"))):
        try:
            dados.update(parse_extrato_ir(f))
        except Exception as exc:
            log.warning("Falha ao ler extrato %s: %s", f, exc)
    return dados


NOMAD_GLOB = "Nomad-*.pdf"


def _nomad_cache_key() -> str:
    files = sorted(glob.glob(os.path.join(RELATORIOS_DIR, NOMAD_GLOB)))
    return "|".join(f"{f}:{os.path.getmtime(f):.0f}" for f in files)


@st.cache_data(show_spinner=False)
def load_nomad(_key: str) -> pd.DataFrame:
    """
    Carrega os extratos da Nomad (ações EUA) e apura o resultado realizado
    via FIFO combinando TODOS os meses (uma venda pode casar com compras de
    meses anteriores). Devolve no mesmo schema das operações MyCapital.
    """
    from nomad import apurar_fifo, parse_nomad_trades
    trades, dividendos = [], []
    for f in sorted(glob.glob(os.path.join(RELATORIOS_DIR, NOMAD_GLOB))):
        try:
            tr, dv = parse_nomad_trades(f)
            trades += tr
            dividendos += dv
        except Exception as exc:
            log.warning("Falha ao ler extrato Nomad %s: %s", f, exc)
    ops = apurar_fifo(trades, dividendos)
    df = pd.DataFrame(ops)
    if df.empty:
        return df
    df = df[[c for c in df.columns if not c.startswith("_")]].copy()  # tira detalhe interno
    df.insert(0, "id", range(1, len(df) + 1))
    df["daytrade"] = df["daytrade"].astype(int)
    df["data_dt"] = pd.to_datetime(df["data"], format="%d/%m/%y", errors="coerce")
    df["resultado"] = df["res_normal"] + df["res_daytrade"]
    return df


@st.cache_data(show_spinner=False)
def load_nomad_raw(_key: str) -> list[dict]:
    """Operações Nomad com o detalhe interno (lotes casados) para conversão cambial."""
    from nomad import apurar_fifo, parse_nomad_trades
    trades, dividendos = [], []
    for f in sorted(glob.glob(os.path.join(RELATORIOS_DIR, NOMAD_GLOB))):
        try:
            tr, dv = parse_nomad_trades(f)
            trades += tr
            dividendos += dv
        except Exception as exc:
            log.warning("Falha Nomad raw %s: %s", f, exc)
    return apurar_fifo(trades, dividendos)


@st.cache_data(show_spinner=False)
def load_nomad_posicoes(_key: str) -> list[dict]:
    """Posições Nomad em aberto (FIFO) com custo de aquisição — ficha Bens e Direitos."""
    from nomad import parse_nomad_trades, posicoes_abertas
    trades = []
    for f in sorted(glob.glob(os.path.join(RELATORIOS_DIR, NOMAD_GLOB))):
        try:
            tr, _ = parse_nomad_trades(f)
            trades += tr
        except Exception as exc:
            log.warning("Falha Nomad posições %s: %s", f, exc)
    return posicoes_abertas(trades)


# ─────────────────────────────────────────────
# AGREGAÇÕES E MÉTRICAS
# ─────────────────────────────────────────────
def resumo_mensal(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = (df.groupby("periodo")
           .agg(normal=("res_normal", "sum"),
                daytrade=("res_daytrade", "sum"),
                outros=("res_outros", "sum"))
           .reset_index()
           .sort_values("periodo"))
    g["total"] = g["normal"] + g["daytrade"] + g["outros"]
    g["acumulado"] = g["total"].cumsum()
    return g


def resumo_ativo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = (df.groupby(["ticker", "mercado"])
           .agg(normal=("res_normal", "sum"),
                daytrade=("res_daytrade", "sum"),
                outros=("res_outros", "sum"),
                operacoes=("id", "count"))
           .reset_index())
    g["total"] = g["normal"] + g["daytrade"] + g["outros"]
    return g.sort_values("total", ascending=False)


def trades_fechados(df: pd.DataFrame) -> pd.DataFrame:
    """Linhas que realizaram resultado (fecharam posição) — base de win rate."""
    if df.empty:
        return df
    return df[(df["res_normal"] != 0) | (df["res_daytrade"] != 0)].copy()


def _com_lado(df: pd.DataFrame) -> pd.DataFrame:
    """Anota cada operação como Compra/Venda e separa volume por lado."""
    d = df.copy()
    d["lado"] = np.where(d["tipo"].str.startswith("Compra"), "Compra", "Venda")
    d["vol_compra"] = np.where(d["lado"] == "Compra", d["valor"], 0.0)
    d["vol_venda"] = np.where(d["lado"] == "Venda", d["valor"], 0.0)
    return d


def por_mercado(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = (df.groupby("mercado")
           .agg(normal=("res_normal", "sum"), daytrade=("res_daytrade", "sum"),
                outros=("res_outros", "sum"), operacoes=("id", "count"),
                volume=("valor", "sum"))
           .reset_index())
    g["total"] = g["normal"] + g["daytrade"] + g["outros"]
    return g.sort_values("total", ascending=False)


def volume_mensal(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    d = _com_lado(df)
    g = (d.groupby("periodo")
           .agg(volume=("valor", "sum"), compras=("vol_compra", "sum"),
                vendas=("vol_venda", "sum"), operacoes=("id", "count"))
           .reset_index().sort_values("periodo"))
    return g


def por_dia_semana(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    d = df.dropna(subset=["data_dt"]).copy()
    d["dow"] = d["data_dt"].dt.weekday
    g = (d.groupby("dow")
           .agg(resultado=("resultado", "sum"), volume=("valor", "sum"),
                operacoes=("id", "count"))
           .reset_index())
    nomes = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}
    g["dia"] = g["dow"].map(nomes)
    return g.sort_values("dow")


def metricas(df: pd.DataFrame) -> dict:
    fechados = trades_fechados(df)
    if fechados.empty:
        return {}
    res = fechados["resultado"]
    ganhos = res[res > 0]
    perdas = res[res < 0]
    win_rate = len(ganhos) / len(res) * 100 if len(res) else 0.0
    payoff = (ganhos.mean() / abs(perdas.mean())) if len(ganhos) and len(perdas) else None
    fator = (ganhos.sum() / abs(perdas.sum())) if len(perdas) else None
    return {
        "trades": len(res),
        "win_rate": win_rate,
        "ganhos": len(ganhos),
        "perdas": len(perdas),
        "payoff": payoff,
        "fator_lucro": fator,
        "media_ganho": ganhos.mean() if len(ganhos) else 0.0,
        "media_perda": perdas.mean() if len(perdas) else 0.0,
        "maior_ganho": res.max(),
        "maior_perda": res.min(),
        "expectativa": res.mean(),
    }


def max_drawdown(rm: pd.DataFrame) -> float:
    """Maior rebaixamento (R$) da curva de resultado acumulado."""
    if rm.empty:
        return 0.0
    acum = rm["acumulado"].values
    pico = -np.inf
    mdd = 0.0
    for v in acum:
        pico = max(pico, v)
        mdd = min(mdd, v - pico)
    return mdd


def sequencias(df: pd.DataFrame) -> tuple[int, int]:
    """Maior sequência de trades vencedores e perdedores (em ordem cronológica)."""
    fch = trades_fechados(df).sort_values(["data_dt", "id"])
    if fch.empty:
        return 0, 0
    melhor = pior = cur_w = cur_l = 0
    for v in fch["resultado"]:
        if v > 0:
            cur_w += 1; cur_l = 0
        elif v < 0:
            cur_l += 1; cur_w = 0
        else:
            cur_w = cur_l = 0
        melhor = max(melhor, cur_w)
        pior = max(pior, cur_l)
    return melhor, pior


def tempo_medio_swing(df: pd.DataFrame):
    """
    Estima o tempo médio de permanência das operações de swing (em dias),
    pareando vendas com compras anteriores por FIFO em cada ticker.
    Day trades são intradiários (0 dias) e ficam de fora desta média.
    Retorna (media_dias, lista_de_(qtde, dias)).
    """
    from collections import deque, defaultdict
    d = df[(df["daytrade"] == 0)].dropna(subset=["data_dt"]).sort_values(["data_dt", "id"])
    filas: dict[str, deque] = defaultdict(deque)
    total_dias = total_qtd = 0.0
    duracoes: list[tuple[float, int]] = []
    for r in d.itertuples():
        tipo = (r.tipo or "")
        q = abs(r.quantidade or 0)
        if q <= 0:
            continue
        if tipo.startswith("Compra"):
            filas[r.ticker].append([r.data_dt, q])
        elif tipo.startswith("Venda"):
            fila = filas[r.ticker]
            rem = q
            while rem > 0 and fila:
                bdate, bq = fila[0]
                m = min(rem, bq)
                dias = max((r.data_dt - bdate).days, 0)
                total_dias += m * dias
                total_qtd += m
                duracoes.append((m, dias))
                bq -= m
                rem -= m
                if bq <= 0:
                    fila.popleft()
                else:
                    fila[0][1] = bq
    media = total_dias / total_qtd if total_qtd else 0.0
    return media, duracoes


def resumo_anual(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    d = df.copy()
    d["ano"] = d["periodo"].str[:4]
    g = (d.groupby("ano")
           .agg(normal=("res_normal", "sum"),
                daytrade=("res_daytrade", "sum"),
                outros=("res_outros", "sum"),
                operacoes=("id", "count"))
           .reset_index())
    g["total"] = g["normal"] + g["daytrade"] + g["outros"]
    return g


# Alíquotas (estimativa): swing comum 15%, day trade 20%
ALIQ_SWING = 0.15
ALIQ_DT = 0.20
DARF_MINIMO = 10.0


def calcular_ir(df: pd.DataFrame) -> pd.DataFrame:
    """
    Estimativa de IR mês a mês, com compensação de prejuízos acumulados
    em dois buckets separados (swing 15% e day trade 20%), como manda a
    Receita. NÃO considera isenção de R$20k para ações, IRRF retido nem
    regras específicas de FII — é uma aproximação para planejamento.
    """
    rm = resumo_mensal(df)
    if rm.empty:
        return pd.DataFrame()
    prej_sw = prej_dt = 0.0
    linhas = []
    for r in rm.itertuples():
        # ── Swing (15%) ──
        if r.normal < 0:
            prej_sw += -r.normal
            trib_sw, darf_sw = 0.0, 0.0
        else:
            comp = min(prej_sw, r.normal)
            prej_sw -= comp
            trib_sw = r.normal - comp
            darf_sw = trib_sw * ALIQ_SWING
        # ── Day trade (20%) ──
        if r.daytrade < 0:
            prej_dt += -r.daytrade
            trib_dt, darf_dt = 0.0, 0.0
        else:
            comp = min(prej_dt, r.daytrade)
            prej_dt -= comp
            trib_dt = r.daytrade - comp
            darf_dt = trib_dt * ALIQ_DT
        darf = darf_sw + darf_dt
        linhas.append({
            "periodo": r.periodo,
            "normal": r.normal,
            "daytrade": r.daytrade,
            "darf_swing": darf_sw,
            "darf_dt": darf_dt,
            "darf": darf,
            "abaixo_minimo": 0 < darf < DARF_MINIMO,
            "prej_swing_acum": prej_sw,
            "prej_dt_acum": prej_dt,
        })
    return pd.DataFrame(linhas)


# ─────────────────────────────────────────────
# IMPORTAÇÃO AUTOMÁTICA NA INICIALIZAÇÃO
# ─────────────────────────────────────────────
if "importado" not in st.session_state:
    n, novos = processar_relatorios(conn)
    st.session_state["importado"] = True
    if novos:
        st.session_state["import_msg"] = f"{len(novos)} relatório(s) importado(s) · {n} operações."

# ─────────────────────────────────────────────
# CABEÇALHO + SELETOR DE CORRETORA + NAVEGAÇÃO
# ─────────────────────────────────────────────
BROKERS = ["🇧🇷 B3 · MyCapital", "🇺🇸 EUA · Nomad"]

hcol1, hcol2 = st.columns([3, 2])
with hcol1:
    st.markdown("## 📊 MonitorBDRs · Performance")
with hcol2:
    corretora = st.radio("Corretora", BROKERS, horizontal=True,
                         label_visibility="collapsed", key="corretora")

# Fonte de dados e moeda conforme a corretora
if corretora == "🇺🇸 EUA · Nomad":
    df_all = load_nomad(_nomad_cache_key())
    CFG["moeda"] = "US$"
    is_nomad = True
else:
    df_all = load_ops(conn, _cache_key(conn))
    CFG["moeda"] = "R$"
    is_nomad = False

if not df_all.empty:
    liq = resumo_mensal(df_all)["total"].sum()
    cor = "#22c55e" if liq >= 0 else "#ef4444"
    st.markdown(
        f"<div style='color:#7c8aa5;font-size:.82rem;margin-top:-6px'>"
        f"{len(df_all)} operações · {df_all['periodo'].nunique()} meses · acumulado "
        f"<span style='color:{cor};font-weight:700;font-family:JetBrains Mono,monospace'>{brl(liq)}</span>"
        f"</div>", unsafe_allow_html=True)

menu = st.radio(
    "Navegação",
    ["🏠 Visão Geral", "📈 Performance Mensal", "💼 Por Ativo",
     "📊 Análise", "⚡ Day Trade vs Swing", "🧮 Métricas", "📑 IR / Anual",
     "📋 Operações", "📥 Importar"],
    horizontal=True, label_visibility="collapsed",
)

# ── Filtro global de período (afeta todas as páginas analíticas) ──
meses_disp = sorted(df_all["periodo"].unique()) if not df_all.empty else []
if len(meses_disp) > 1 and menu != "📥 Importar":
    fc1, fc2 = st.columns([3, 1])
    with fc1:
        ini, fim = st.select_slider(
            "Período", options=meses_disp,
            value=(meses_disp[0], meses_disp[-1]), label_visibility="collapsed",
        )
    df_all = df_all[(df_all["periodo"] >= ini) & (df_all["periodo"] <= fim)]
    if (ini, fim) != (meses_disp[0], meses_disp[-1]):
        fc2.caption(f"📅 {ini} → {fim}")
st.markdown("<hr style='margin-top:.3rem'>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PÁGINA: VISÃO GERAL
# ─────────────────────────────────────────────
if menu == "🏠 Visão Geral":
    st.title("Visão Geral")
    if df_all.empty:
        st.info("Nenhum relatório importado. Vá em **Importar** para começar.")
    else:
        rm = resumo_mensal(df_all)
        m = metricas(df_all)
        normal = df_all["res_normal"].sum()
        dt = df_all["res_daytrade"].sum()
        prov = df_all["res_outros"].sum()
        liq = normal + dt + prov

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Resultado Líquido", fmt_kpi(liq))
        c2.metric("Swing (Normal)", fmt_kpi(normal))
        c3.metric("Day Trade", fmt_kpi(dt))
        c4.metric("Proventos", fmt_kpi(prov))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Win Rate", fmt_pct(m.get("win_rate", 0), sign=False))
        c6.metric("Trades Fechados", str(m.get("trades", 0)))
        melhor = rm.loc[rm["total"].idxmax()]
        pior = rm.loc[rm["total"].idxmin()]
        c7.metric("Melhor Mês", melhor["periodo"], fmt_kpi(melhor["total"]))
        c8.metric("Pior Mês", pior["periodo"], fmt_kpi(pior["total"]))

        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Curva de Resultado Acumulado")
        base = alt.Chart(rm).encode(x=alt.X("periodo:N", title="Mês", axis=alt.Axis(labelAngle=-45)))
        area = base.mark_area(
            line={"color": AZUL}, opacity=0.25,
            color=alt.Gradient(gradient="linear",
                               stops=[alt.GradientStop(color="#0f1117", offset=0),
                                      alt.GradientStop(color=AZUL, offset=1)],
                               x1=1, x2=1, y1=1, y2=0),
        ).encode(y=alt.Y("acumulado:Q", title="Acumulado (R$)"),
                 tooltip=["periodo", alt.Tooltip("acumulado:Q", format=",.2f")])
        st.altair_chart(area, width="stretch")

        st.subheader("Resultado por Mês")
        rmm = rm.melt(id_vars="periodo", value_vars=["normal", "daytrade", "outros"],
                      var_name="tipo", value_name="valor")
        nome_tipo = {"normal": "Swing", "daytrade": "Day Trade", "outros": "Proventos"}
        rmm["tipo"] = rmm["tipo"].map(nome_tipo)
        bars = alt.Chart(rmm).mark_bar().encode(
            x=alt.X("periodo:N", title="Mês", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("valor:Q", title="Resultado (R$)"),
            color=alt.Color("tipo:N", title="",
                            scale=alt.Scale(domain=["Swing", "Day Trade", "Proventos"],
                                            range=[AZUL, "#f59e0b", VERDE])),
            tooltip=["periodo", "tipo", alt.Tooltip("valor:Q", format=",.2f")],
        )
        st.altair_chart(bars, width="stretch")


# ─────────────────────────────────────────────
# PÁGINA: PERFORMANCE MENSAL
# ─────────────────────────────────────────────
elif menu == "📈 Performance Mensal":
    st.title("Performance Mensal")
    if df_all.empty:
        st.info("Nenhum dado carregado.")
    else:
        rm = resumo_mensal(df_all)
        disp = rm.copy()
        disp.columns = ["Mês", "Swing", "Day Trade", "Proventos", "Total", "Acumulado"]
        st.dataframe(
            disp.style
                .format({c: brl for c in ["Swing", "Day Trade", "Proventos", "Total", "Acumulado"]})
                .map(color_result, subset=["Swing", "Day Trade", "Proventos", "Total"]),
            width="stretch", hide_index=True,
        )
        st.markdown("<hr>", unsafe_allow_html=True)
        rm["cor"] = rm["total"].apply(lambda v: "pos" if v >= 0 else "neg")
        ch = alt.Chart(rm).mark_bar().encode(
            x=alt.X("periodo:N", title="Mês", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("total:Q", title="Resultado Total (R$)"),
            color=alt.Color("cor:N", legend=None,
                            scale=alt.Scale(domain=["pos", "neg"], range=[VERDE, VERMELHO])),
            tooltip=["periodo", alt.Tooltip("total:Q", format=",.2f")],
        )
        st.altair_chart(ch, width="stretch")


# ─────────────────────────────────────────────
# PÁGINA: POR ATIVO
# ─────────────────────────────────────────────
elif menu == "💼 Por Ativo":
    st.title("Resultado por Ativo")
    if df_all.empty:
        st.info("Nenhum dado carregado.")
    else:
        ra = resumo_ativo(df_all)
        c1, c2, c3 = st.columns(3)
        c1.metric("Ativos Operados", str(len(ra)))
        c2.metric("Lucrativos", str((ra["total"] > 0).sum()))
        c3.metric("Com Prejuízo", str((ra["total"] < 0).sum()))

        st.markdown("<hr>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏆 Melhores")
            top = ra.head(10)[["ticker", "total"]]
            ch = alt.Chart(top).mark_bar(color=VERDE).encode(
                x=alt.X("total:Q", title="R$"),
                y=alt.Y("ticker:N", sort="-x", title=""),
                tooltip=["ticker", alt.Tooltip("total:Q", format=",.2f")])
            st.altair_chart(ch, width="stretch")
        with col2:
            st.subheader("📉 Piores")
            bot = ra.tail(10)[["ticker", "total"]].sort_values("total")
            ch = alt.Chart(bot).mark_bar(color=VERMELHO).encode(
                x=alt.X("total:Q", title="R$"),
                y=alt.Y("ticker:N", sort="x", title=""),
                tooltip=["ticker", alt.Tooltip("total:Q", format=",.2f")])
            st.altair_chart(ch, width="stretch")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Detalhamento")
        disp = ra[["ticker", "mercado", "operacoes", "normal", "daytrade", "outros", "total"]].copy()
        disp.columns = ["Ativo", "Mercado", "Operações", "Swing", "Day Trade", "Proventos", "Total"]
        st.dataframe(
            disp.style
                .format({c: brl for c in ["Swing", "Day Trade", "Proventos", "Total"]})
                .map(color_result, subset=["Swing", "Day Trade", "Proventos", "Total"]),
            width="stretch", hide_index=True,
        )
        st.download_button("⬇️ Baixar CSV", disp.to_csv(index=False).encode("utf-8"),
                           "resultado_por_ativo.csv", "text/csv")


# ─────────────────────────────────────────────
# PÁGINA: ANÁLISE DETALHADA
# ─────────────────────────────────────────────
elif menu == "📊 Análise":
    st.title("Análise Detalhada das Operações")
    if df_all.empty:
        st.info("Nenhum dado carregado.")
    else:
        dl = _com_lado(df_all)
        vol_total = df_all["valor"].sum()
        vol_compra = dl["vol_compra"].sum()
        vol_venda = dl["vol_venda"].sum()
        n_ops = len(df_all)
        n_compras = int((dl["lado"] == "Compra").sum())
        n_vendas = int((dl["lado"] == "Venda").sum())
        ticket = vol_total / n_ops if n_ops else 0.0

        # ── Somatórios de volume ──
        st.subheader("Volume Operado")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Volume Total", fmt_kpi(vol_total))
        c2.metric("Compras", fmt_kpi(vol_compra), f"{n_compras} ops")
        c3.metric("Vendas", fmt_kpi(vol_venda), f"{n_vendas} ops")
        c4.metric("Ticket Médio", fmt_kpi(ticket))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Operações", str(n_ops))
        c6.metric("Day Trade", str(int((df_all["daytrade"] == 1).sum())))
        c7.metric("Swing", str(int((df_all["daytrade"] == 0).sum())))
        c8.metric("Ativos Distintos", str(df_all["ticker"].nunique()))

        # ── Resultado por mercado ──
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Resultado por Mercado")
        pm = por_mercado(df_all)
        cma, cmb = st.columns([3, 2])
        with cma:
            ch = alt.Chart(pm).mark_bar().encode(
                x=alt.X("total:Q", title="Resultado (R$)"),
                y=alt.Y("mercado:N", sort="-x", title=""),
                color=alt.Color("total:Q", scale=alt.Scale(scheme="redyellowgreen"), legend=None),
                tooltip=["mercado", alt.Tooltip("total:Q", format=",.2f"),
                         alt.Tooltip("volume:Q", format=",.2f"), "operacoes"])
            st.altair_chart(ch, width="stretch")
        with cmb:
            pmd = pm[["mercado", "operacoes", "total"]].copy()
            pmd.columns = ["Mercado", "Ops", "Resultado"]
            st.dataframe(pmd.style.format({"Resultado": brl})
                         .map(color_result, subset=["Resultado"]),
                         width="stretch", hide_index=True)

        # ── Volume operado por mês ──
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Volume Operado por Mês")
        vm = volume_mensal(df_all)
        vmm = vm.melt(id_vars="periodo", value_vars=["compras", "vendas"],
                      var_name="lado", value_name="valor")
        vmm["lado"] = vmm["lado"].map({"compras": "Compras", "vendas": "Vendas"})
        ch = alt.Chart(vmm).mark_bar().encode(
            x=alt.X("periodo:N", title="Mês", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("valor:Q", title="Volume (R$)"),
            color=alt.Color("lado:N", title="",
                            scale=alt.Scale(domain=["Compras", "Vendas"], range=[AZUL, "#f59e0b"])),
            tooltip=["periodo", "lado", alt.Tooltip("valor:Q", format=",.2f")])
        st.altair_chart(ch, width="stretch")

        # ── Resultado por dia da semana ──
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Resultado por Dia da Semana")
        ds = por_dia_semana(df_all)
        ds["cor"] = ds["resultado"].apply(lambda v: "pos" if v >= 0 else "neg")
        cda, cdb = st.columns(2)
        with cda:
            ch = alt.Chart(ds).mark_bar().encode(
                x=alt.X("dia:N", sort=list(ds["dia"]), title=""),
                y=alt.Y("resultado:Q", title="Resultado (R$)"),
                color=alt.Color("cor:N", legend=None,
                                scale=alt.Scale(domain=["pos", "neg"], range=[VERDE, VERMELHO])),
                tooltip=["dia", alt.Tooltip("resultado:Q", format=",.2f"), "operacoes"])
            st.altair_chart(ch, width="stretch")
        with cdb:
            ch = alt.Chart(ds).mark_bar(color=AZUL).encode(
                x=alt.X("dia:N", sort=list(ds["dia"]), title=""),
                y=alt.Y("operacoes:Q", title="Nº de Operações"),
                tooltip=["dia", "operacoes"])
            st.altair_chart(ch, width="stretch")

        # ── Contribuição acumulada (Pareto) ──
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Concentração do Resultado (Pareto por Ativo)")
        ra = resumo_ativo(df_all).sort_values("total", ascending=False).reset_index(drop=True)
        ra_pos = ra[ra["total"] > 0].copy()
        if not ra_pos.empty:
            ra_pos["acum_pct"] = ra_pos["total"].cumsum() / ra_pos["total"].sum() * 100
            ra_pos["rank"] = range(1, len(ra_pos) + 1)
            base = alt.Chart(ra_pos.head(20))
            barras = base.mark_bar(color=VERDE).encode(
                x=alt.X("ticker:N", sort="-y", title=""),
                y=alt.Y("total:Q", title="Resultado (R$)"),
                tooltip=["ticker", alt.Tooltip("total:Q", format=",.2f"),
                         alt.Tooltip("acum_pct:Q", format=".1f", title="% acum.")])
            st.altair_chart(barras, width="stretch")
            n80 = int((ra_pos["acum_pct"] <= 80).sum()) + 1
            st.caption(f"📌 Os {min(n80, len(ra_pos))} ativos mais lucrativos concentram ~80% "
                       f"de todo o ganho positivo do período.")


# ─────────────────────────────────────────────
# PÁGINA: DAY TRADE vs SWING
# ─────────────────────────────────────────────
elif menu == "⚡ Day Trade vs Swing":
    st.title("Day Trade vs Swing")
    if df_all.empty:
        st.info("Nenhum dado carregado.")
    else:
        dt_total = df_all["res_daytrade"].sum()
        sw_total = df_all["res_normal"].sum()
        fch = trades_fechados(df_all)
        dt_f = fch[fch["res_daytrade"] != 0]
        sw_f = fch[fch["res_normal"] != 0]

        def wr(s, col):
            r = s[col]
            return (r > 0).mean() * 100 if len(r) else 0.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Resultado Day Trade", fmt_kpi(dt_total))
        c2.metric("Win Rate DT", fmt_pct(wr(dt_f, "res_daytrade"), sign=False))
        c3.metric("Resultado Swing", fmt_kpi(sw_total))
        c4.metric("Win Rate Swing", fmt_pct(wr(sw_f, "res_normal"), sign=False))

        st.markdown("<hr>", unsafe_allow_html=True)
        comp = pd.DataFrame({
            "Estratégia": ["Day Trade", "Swing"],
            "Resultado": [dt_total, sw_total],
            "Trades": [len(dt_f), len(sw_f)],
        })
        ch = alt.Chart(comp).mark_bar().encode(
            x=alt.X("Estratégia:N", title=""),
            y=alt.Y("Resultado:Q", title="R$"),
            color=alt.Color("Estratégia:N", legend=None,
                            scale=alt.Scale(domain=["Day Trade", "Swing"], range=["#f59e0b", AZUL])),
            tooltip=["Estratégia", alt.Tooltip("Resultado:Q", format=",.2f"), "Trades"])
        st.altair_chart(ch, width="stretch")

        st.subheader("Day Trade por Mês")
        gdt = (df_all.groupby("periodo").agg(dt=("res_daytrade", "sum")).reset_index())
        gdt["cor"] = gdt["dt"].apply(lambda v: "pos" if v >= 0 else "neg")
        ch2 = alt.Chart(gdt).mark_bar().encode(
            x=alt.X("periodo:N", title="Mês", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("dt:Q", title="Day Trade (R$)"),
            color=alt.Color("cor:N", legend=None,
                            scale=alt.Scale(domain=["pos", "neg"], range=[VERDE, VERMELHO])),
            tooltip=["periodo", alt.Tooltip("dt:Q", format=",.2f")])
        st.altair_chart(ch2, width="stretch")


# ─────────────────────────────────────────────
# PÁGINA: MÉTRICAS
# ─────────────────────────────────────────────
elif menu == "🧮 Métricas":
    st.title("Métricas de Performance")
    if df_all.empty:
        st.info("Nenhum dado carregado.")
    else:
        m = metricas(df_all)
        rm = resumo_mensal(df_all)
        melhor_seq, pior_seq = sequencias(df_all)
        mdd = max_drawdown(rm)
        tmedio, duracoes = tempo_medio_swing(df_all)
        fch = trades_fechados(df_all)
        dt_f = fch[fch["res_daytrade"] != 0]["resultado"]
        sw_f = fch[fch["res_normal"] != 0]["resultado"]

        st.subheader("Estatística Geral")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Win Rate", fmt_pct(m["win_rate"], sign=False))
        c2.metric("Trades Fechados", str(m["trades"]))
        c3.metric("Payoff", f"{m['payoff']:.2f}" if m["payoff"] else "N/A")
        c4.metric("Fator de Lucro", f"{m['fator_lucro']:.2f}" if m["fator_lucro"] else "N/A")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Expectativa / Trade", fmt_kpi(m["expectativa"]))
        c6.metric("Máx. Drawdown", fmt_kpi(mdd))
        c7.metric("Seq. Vitórias", f"{melhor_seq} trades")
        c8.metric("Seq. Derrotas", f"{pior_seq} trades")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Lucros vs Perdas")
        c9, c10, c11, c12 = st.columns(4)
        c9.metric("Operações Ganhas", str(m["ganhos"]))
        c10.metric("Operações Perdidas", str(m["perdas"]))
        c11.metric("Média de Ganho", fmt_kpi(m["media_ganho"]))
        c12.metric("Média de Perda", fmt_kpi(m["media_perda"]))

        c13, c14, c15, c16 = st.columns(4)
        c13.metric("Maior Ganho", fmt_kpi(m["maior_ganho"]))
        c14.metric("Maior Perda", fmt_kpi(m["maior_perda"]))
        c15.metric("Média Ganho Swing", fmt_kpi(sw_f[sw_f > 0].mean() if (sw_f > 0).any() else 0))
        c16.metric("Média Ganho Day Trade", fmt_kpi(dt_f[dt_f > 0].mean() if (dt_f > 0).any() else 0))

        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Tempo Médio de Permanência")
        t1, t2, t3 = st.columns(3)
        t1.metric("Swing (médio)", f"{tmedio:.1f} dias")
        if duracoes:
            qts = np.array([q for q, _ in duracoes])
            dys = np.array([d for _, d in duracoes])
            t2.metric("Mais longa", f"{int(dys.max())} dias")
            curtas = (dys <= 1).sum()
            t3.metric("Fechadas em ≤1 dia", f"{curtas} lotes")
        st.caption("Day trades são intradiários (0 dia). O tempo de swing é estimado "
                   "pareando vendas com compras anteriores por FIFO em cada ativo.")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Distribuição dos Resultados (trades fechados)")
        hist = alt.Chart(fch).mark_bar(color=AZUL).encode(
            x=alt.X("resultado:Q", bin=alt.Bin(maxbins=40), title="Resultado por trade (R$)"),
            y=alt.Y("count():Q", title="Frequência"),
            tooltip=[alt.Tooltip("count():Q", title="Trades")])
        st.altair_chart(hist, width="stretch")


# ─────────────────────────────────────────────
# PÁGINA: IR / ANUAL
# ─────────────────────────────────────────────
elif menu == "📑 IR / Anual":
    st.title("Imposto de Renda · Resumo Anual")
    if df_all.empty:
        st.info("Nenhum dado carregado.")
    else:
        ra = resumo_anual(df_all)
        st.subheader("Resultado por Ano")
        disp = ra[["ano", "operacoes", "normal", "daytrade", "outros", "total"]].copy()
        disp.columns = ["Ano", "Operações", "Swing", "Day Trade", "Proventos", "Total"]
        st.dataframe(
            disp.style
                .format({c: brl for c in ["Swing", "Day Trade", "Proventos", "Total"]})
                .map(color_result, subset=["Swing", "Day Trade", "Proventos", "Total"]),
            width="stretch", hide_index=True,
        )

        st.markdown("<hr>", unsafe_allow_html=True)

        if is_nomad:
            # Usa a base COMPLETA (independe do filtro de período) para o ano fiscal
            dfn = load_nomad(_nomad_cache_key())
            posicoes = load_nomad_posicoes(_nomad_cache_key())
            anos = sorted(dfn["periodo"].str[:4].unique())

            st.subheader("Resultado Realizado por Mês (US$)")
            rm = resumo_mensal(dfn)
            disp = rm[["periodo", "normal", "daytrade", "outros", "total"]].copy()
            disp.columns = ["Mês", "Ganho de Capital", "Day Trade", "Dividendos", "Total"]
            st.dataframe(
                disp.style.format({c: brl for c in disp.columns if c != "Mês"})
                    .map(color_result, subset=["Ganho de Capital", "Day Trade", "Dividendos", "Total"]),
                width="stretch", hide_index=True,
            )

            st.markdown("<hr>", unsafe_allow_html=True)
            st.subheader("📄 Gerar Dados para a Declaração de IR")
            raw = load_nomad_raw(_nomad_cache_key())
            vendas_raw = [o for o in raw if o["tipo"].startswith("Venda")]
            divs_raw = [o for o in raw if o["tipo"] == "Dividendo"]

            modo = st.radio(
                "Conversão para reais (R$)",
                ["Somente US$", "Câmbio manual (cotação única)", "Automático (PTAX/BCB)"],
                horizontal=True,
            )

            ptax_map: dict = {}
            fallback = 0.0
            if modo == "Câmbio manual (cotação única)":
                fallback = st.number_input("Cotação USD→BRL", min_value=0.0, value=0.0,
                                           step=0.01, format="%.4f")
            elif modo == "Automático (PTAX/BCB)":
                from cambio import get_ptax
                datas = set()
                for o in vendas_raw:
                    datas.add(o["_iso"])
                    datas.update(l[0] for l in o["_lotes"])
                datas.update(o["_iso"] for o in divs_raw)
                for p in posicoes:
                    datas.update(l[0] for l in p["lotes"])
                with st.spinner("Buscando cotações PTAX no Banco Central…"):
                    ptax_map = get_ptax(datas)
                faltam = sorted(d for d in datas if d not in ptax_map)
                st.caption(f"PTAX obtida para {len(ptax_map)} de {len(datas)} datas."
                           + (f" {len(faltam)} sem cotação — informe um câmbio de reserva."
                              if faltam else " ✅"))
                if faltam:
                    fallback = st.number_input("Câmbio de reserva (datas sem PTAX)",
                                               min_value=0.0, value=0.0, step=0.01, format="%.4f")

            def taxa(iso: str, lado: str):
                if iso in ptax_map:
                    return ptax_map[iso][lado]
                return fallback if fallback > 0 else None

            def custo_rs(lotes):
                total = 0.0
                for data_iso, _q, custo_usd in lotes:
                    t = taxa(data_iso, "venda")  # aquisição → PTAX venda
                    if t is None:
                        return None
                    total += custo_usd * t
                return total

            usar_rs = modo != "Somente US$"

            # ── 1) Bens e Direitos — colunas iguais às da ficha do programa ──
            ano = int(anos[-1])
            ano_ant = ano - 1
            col_ant = f"Situação em 31/12/{ano_ant} (R$)"
            col_atual = f"Situação em 31/12/{ano} (R$)"
            bd_rows = []
            for p in posicoes:
                c_rs = custo_rs(p["lotes"]) if usar_rs else None
                disc = (f"{p['quantidade']:.5f} ação(ões) de {p['nome']} ({p['symbol']}), "
                        f"negociadas em bolsa dos EUA, sob custódia da Apex Clearing Corp. "
                        f"por meio da corretora Nomad (conta NTKY749). "
                        f"Custo médio de aquisição US$ {p['custo_total']:.2f}")
                if c_rs is not None:
                    disc += f" (R$ {c_rs:.2f} pela PTAX das datas de compra)"
                disc += "."
                row = {
                    "Grupo": "",             # confirmar com contador (aplic. financeira no exterior)
                    "Código": "",            # confirmar com contador
                    "Localização (País)": "249 - Estados Unidos",
                    "Discriminação": disc,
                    col_ant: 0.00,           # começou a operar em 2026 → nada em 31/12 anterior
                    col_atual: (round(c_rs, 2) if c_rs is not None else None),
                    "Ativo": p["symbol"],
                    "Quantidade": round(p["quantidade"], 5),
                    "Custo US$": round(p["custo_total"], 2),
                }
                bd_rows.append(row)
            bd = pd.DataFrame(bd_rows)

            # ── 2) Ganhos de Capital (cada venda realizada) ──
            gc_rows = []
            for o in vendas_raw:
                bruto = o["_venda_bruta"]
                comm = o["_comissao"]
                res = o["res_normal"] + o["res_daytrade"]
                custo_usd = bruto - comm - res
                row = {"Data": o["data"], "Ativo": o["ticker"],
                       "Quantidade": round(o["quantidade"], 5),
                       "Venda US$": round(bruto, 2), "Custo US$": round(custo_usd, 2),
                       "Ganho US$": round(res, 2), "_periodo": o["periodo"]}
                if usar_rs:
                    tc = taxa(o["_iso"], "compra")  # alienação → PTAX compra
                    venda_rs = bruto * tc if tc is not None else None
                    comm_rs = comm * tc if tc is not None else None
                    c_rs = custo_rs(o["_lotes"])
                    ganho_rs = (venda_rs - comm_rs - c_rs
                                if None not in (venda_rs, comm_rs, c_rs) else None)
                    row["Venda R$"] = round(venda_rs, 2) if venda_rs is not None else None
                    row["Custo R$"] = round(c_rs, 2) if c_rs is not None else None
                    row["Ganho R$"] = round(ganho_rs, 2) if ganho_rs is not None else None
                gc_rows.append(row)
            gc = pd.DataFrame(gc_rows)

            # ── 2b) Ganhos de Capital consolidado por mês ──
            cols_soma = ["Venda US$", "Ganho US$"] + (["Venda R$", "Ganho R$"] if usar_rs else [])
            gcm = (gc.groupby("_periodo")[cols_soma].sum(min_count=1).reset_index()
                     .rename(columns={"_periodo": "Mês", "Venda US$": "Alienações US$",
                                      "Venda R$": "Alienações R$"}))
            gcm = gcm.rename(columns={"Ganho US$": "Resultado US$", "Ganho R$": "Resultado R$"})
            gc = gc.drop(columns=["_periodo"])

            # ── 3) Rendimentos de aplicações financeiras no exterior (anual, Lei 14.754) ──
            rend_rows = []
            for a in anos:
                sub = gcm[gcm["Mês"].str.startswith(a)]
                ganho_usd = sub["Resultado US$"].sum()
                linha = {"Ano": a, "Resultado US$": round(ganho_usd, 2)}
                if usar_rs and "Resultado R$" in gcm:
                    ganho_rs = sub["Resultado R$"].sum()
                    linha["Resultado R$"] = round(ganho_rs, 2)
                    linha["Imposto 15% (R$)"] = round(max(ganho_rs, 0) * 0.15, 2)
                rend_rows.append(linha)
            rend = pd.DataFrame(rend_rows)

            # ── 4) Dividendos ──
            dv_rows = []
            for o in divs_raw:
                row = {"Data": o["data"], "Ativo": o["ticker"],
                       "Valor US$": round(o["res_outros"], 2)}
                if usar_rs:
                    t = taxa(o["_iso"], "compra")
                    row["Valor R$"] = round(o["res_outros"] * t, 2) if t is not None else None
                dv_rows.append(row)
            dv = pd.DataFrame(dv_rows)

            # ── Instruções: onde cada aba entra no programa "Meu Imposto de Renda" ──
            instru = pd.DataFrame([
                {"Aba desta planilha": "Bens e Direitos",
                 "Ficha no programa Meu Imposto de Renda": "Bens e Direitos",
                 "Como preencher": "Um item por ativo. Grupo/Código: confirmar (aplicação "
                 "financeira no exterior — Lei 14.754/2023). Localização: 249 - Estados Unidos. "
                 "Cole a Discriminação. Situação em 31/12 do ano anterior = R$0,00; "
                 "atualize a do ano-base com a posição em 31/12."},
                {"Aba desta planilha": "Rendimentos (anual)",
                 "Ficha no programa Meu Imposto de Renda":
                 "Rendimentos Tributáveis - Aplicações Financeiras no Exterior (15%)",
                 "Como preencher": "Informe o resultado (ganho) anual em R$. O programa aplica "
                 "os 15% automaticamente. Valores por mês/venda ficam nas outras abas como memória "
                 "de cálculo."},
                {"Aba desta planilha": "Dividendos",
                 "Ficha no programa Meu Imposto de Renda":
                 "Rendimentos recebidos do exterior (carnê-leão)",
                 "Como preencher": "Dividendos são tributados via carnê-leão no mês do "
                 "recebimento; converta pela PTAX de compra da data (já feito na coluna R$)."},
                {"Aba desta planilha": "Vendas / Ganhos Mensais",
                 "Ficha no programa Meu Imposto de Renda": "— (memória de cálculo)",
                 "Como preencher": "Detalhamento de cada venda e o consolidado por mês, apurados "
                 "por FIFO com PTAX por data. Guarde como comprovação."},
            ])

            st.markdown(f"**1 · Bens e Direitos** — colunas iguais à ficha do programa")
            st.dataframe(bd, width="stretch", hide_index=True)
            st.caption(f"Você começou a operar em {ano}, então a Situação em 31/12/{ano_ant} é "
                       f"R$ 0,00. A coluna de 31/12/{ano} traz a posição do último extrato — "
                       f"atualize com a posição do último dia do ano ao declarar.")
            st.markdown("**2 · Rendimentos — resultado anual (Lei 14.754/2023, 15%)**")
            st.dataframe(rend, width="stretch", hide_index=True)
            st.markdown("**3 · Ganhos por mês** (memória de cálculo)")
            st.dataframe(gcm, width="stretch", hide_index=True)
            with st.expander(f"Ver as {len(gc)} vendas detalhadas e {len(dv)} dividendos"):
                st.markdown("**Vendas (apuração FIFO)**")
                st.dataframe(gc, width="stretch", hide_index=True)
                st.markdown("**Dividendos**")
                st.dataframe(dv, width="stretch", hide_index=True)

            # ── Excel consolidado (abas nomeadas conforme as fichas) ──
            import io
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as xw:
                instru.to_excel(xw, sheet_name="Instruções", index=False)
                bd.to_excel(xw, sheet_name="Bens e Direitos", index=False)
                rend.to_excel(xw, sheet_name="Rendimentos (anual)", index=False)
                gcm.to_excel(xw, sheet_name="Ganhos Mensais", index=False)
                gc.to_excel(xw, sheet_name="Vendas (detalhe)", index=False)
                dv.to_excel(xw, sheet_name="Dividendos", index=False)
            st.download_button(
                "⬇️ Baixar planilha completa para IR (Excel)", buf.getvalue(),
                f"IR_Nomad_{anos[-1]}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown(
                "<div style='background:#161d30;border:1px solid #243049;border-left:4px solid #f59e0b;"
                "border-radius:10px;padding:12px 16px;margin-top:12px;font-size:.83rem;color:#cbd5e1'>"
                "⚠️ <b>Material de apoio — confira com seu contador.</b> Investimentos no exterior "
                "seguem a <b>Lei 14.754/2023</b> (vigente desde 2024): os resultados de aplicações "
                "financeiras no exterior são apurados <b>anualmente</b> e tributados a <b>15%</b>, "
                "declarados na DAA. No modo <b>Automático</b>, a conversão usa a <b>PTAX oficial do "
                "Banco Central</b> da data de cada operação (aquisição → dólar de venda; alienação e "
                "dividendo → dólar de compra); em datas sem pregão usa o último PTAX anterior. "
                "Posições, custos e ganhos são apurados por <b>FIFO</b>."
                "</div>", unsafe_allow_html=True)
            st.stop()

        ir_oficial = load_ir_oficial(_ir_cache_key())
        # Mantém apenas os meses presentes no sistema (exclui meses à frente, ex.: junho)
        periodos_sistema = set(df_all["periodo"].unique())
        meses_ir = sorted(p for p in ir_oficial if p in periodos_sistema)

        if meses_ir:
            st.subheader("Apuração Oficial de IR (MyCapital)")
            linhas = []
            for p in meses_ir:
                d = ir_oficial[p]
                ip = (d.get("imp_pagar_c") or 0) + (d.get("imp_pagar_d") or 0)
                linhas.append({
                    "Mês": p,
                    "Swing (15%)": d.get("res_acoes_c", 0.0),
                    "Day Trade (20%)": d.get("res_acoes_d", 0.0),
                    "Prej. Swing a compensar": d.get("prej_compensar_c", 0.0),
                    "Prej. DT a compensar": d.get("prej_compensar_d", 0.0),
                    "Imposto a pagar": ip,
                })
            irv = pd.DataFrame(linhas)
            ult = irv.iloc[-1]
            imp_total = irv["Imposto a pagar"].sum()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Imposto a pagar (período)", fmt_kpi(imp_total))
            k2.metric("Prej. Swing a compensar", fmt_kpi(ult["Prej. Swing a compensar"]))
            k3.metric("Prej. Day Trade a compensar", fmt_kpi(ult["Prej. DT a compensar"]))
            k4.metric("Posição em", ult["Mês"])

            st.dataframe(
                irv.style
                   .format({c: brl for c in irv.columns if c != "Mês"})
                   .map(color_result, subset=["Swing (15%)", "Day Trade (20%)"]),
                width="stretch", hide_index=True,
            )
            st.download_button("⬇️ Baixar CSV (IR oficial)", irv.to_csv(index=False).encode("utf-8"),
                               "ir_oficial.csv", "text/csv")
            st.markdown(
                "<div style='background:#161d30;border:1px solid #243049;border-left:4px solid #22c55e;"
                "border-radius:10px;padding:12px 16px;margin-top:10px;font-size:.84rem;color:#cbd5e1'>"
                "✅ Valores <b>oficiais</b> do Extrato Mensal de Resultados (MyCapital), com prejuízos "
                "acumulados reais (inclui histórico anterior). O <b>prejuízo a compensar</b> abate "
                "ganhos futuros do mesmo tipo (swing 15% / day trade 20%). Sem imposto a pagar enquanto "
                "os prejuízos acumulados absorverem os ganhos. Meses ainda não importados no sistema "
                "(ex.: posteriores ao último relatório) ficam de fora."
                "</div>", unsafe_allow_html=True)
        else:
            st.subheader("Estimativa de DARF (mensal)")
            st.caption("Sem Extrato Mensal de Resultados importado — exibindo estimativa. "
                       "Envie o Extrato na aba Importar para ver a apuração oficial.")
            ir = calcular_ir(df_all)
            ult = ir.iloc[-1]
            k1, k2, k3 = st.columns(3)
            k1.metric("DARF estimado (período)", fmt_kpi(ir["darf"].sum()))
            k2.metric("Prej. Swing a compensar", fmt_kpi(-ult["prej_swing_acum"]))
            k3.metric("Prej. DT a compensar", fmt_kpi(-ult["prej_dt_acum"]))
            irv = ir[["periodo", "normal", "daytrade", "darf"]].copy()
            irv.columns = ["Mês", "Swing", "Day Trade", "DARF estimado"]
            st.dataframe(
                irv.style.format({c: brl for c in irv.columns if c != "Mês"})
                   .map(color_result, subset=["Swing", "Day Trade"]),
                width="stretch", hide_index=True,
            )
            st.caption("⚠️ Estimativa sobre os 12 meses (subestima prejuízo anterior). "
                       "Não considera isenção de R$20k, IRRF nem regras de FII.")


# ─────────────────────────────────────────────
# PÁGINA: OPERAÇÕES
# ─────────────────────────────────────────────
elif menu == "📋 Operações":
    st.title("Operações")
    if df_all.empty:
        st.info("Nenhum dado carregado.")
    else:
        c1, c2, c3 = st.columns(3)
        meses = ["Todos"] + sorted(df_all["periodo"].unique())
        fmes = c1.selectbox("Mês", meses)
        ativos = ["Todos"] + sorted(df_all["ticker"].dropna().unique())
        fativo = c2.selectbox("Ativo", ativos)
        ftipo = c3.selectbox("Tipo", ["Todos", "Day Trade", "Swing"])

        d = df_all.copy()
        if fmes != "Todos":
            d = d[d["periodo"] == fmes]
        if fativo != "Todos":
            d = d[d["ticker"] == fativo]
        if ftipo == "Day Trade":
            d = d[d["daytrade"] == 1]
        elif ftipo == "Swing":
            d = d[d["daytrade"] == 0]

        # ── Somatórios do filtro atual ──
        dl = _com_lado(d)
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Operações", str(len(d)))
        s2.metric("Volume Comprado", fmt_kpi(dl["vol_compra"].sum()))
        s3.metric("Volume Vendido", fmt_kpi(dl["vol_venda"].sum()))
        s4.metric("Resultado", fmt_kpi(d["resultado"].sum()))

        disp = d[["data", "mercado", "ticker", "tipo", "quantidade", "preco",
                  "valor", "resultado"]].copy()
        disp.columns = ["Data", "Mercado", "Ativo", "Tipo", "Qtd", "Preço", "Valor", "Resultado"]
        st.dataframe(
            disp.style
                .format({"Preço": brl, "Valor": brl, "Resultado": brl, "Qtd": "{:.0f}"})
                .map(color_result, subset=["Resultado"]),
            width="stretch", hide_index=True, height=560,
        )
        st.download_button("⬇️ Baixar CSV", disp.to_csv(index=False).encode("utf-8"),
                           "operacoes.csv", "text/csv")


# ─────────────────────────────────────────────
# PÁGINA: IMPORTAR
# ─────────────────────────────────────────────
elif menu == "📥 Importar":
    st.title("Importar Relatórios")
    st.markdown(
        "Envie: **MyCapital** — \"Operações no mês\" e/ou \"Extrato Mensal de Resultados\"; "
        "ou **Nomad** — \"Account Statement\" (ações EUA). O tipo é detectado automaticamente."
    )
    if msg := st.session_state.pop("import_msg", None):
        st.success(msg)

    up = st.file_uploader("Relatórios (PDF)", type=["pdf"], accept_multiple_files=True)
    if up:
        os.makedirs(EXTRATOS_DIR, exist_ok=True)
        n_extratos = n_nomad = 0
        for f in up:
            conteudo = f.getbuffer()
            try:
                import pdfplumber
                f.seek(0)
                with pdfplumber.open(f) as _pdf:
                    cabecalho = _pdf.pages[0].extract_text() or ""
            except Exception:
                cabecalho = ""
            eh_extrato = "Extrato Mensal de Resultados" in cabecalho
            eh_nomad = "Nomad Investment Services" in cabecalho

            if eh_nomad:
                nome = f.name if f.name.startswith("Nomad") else f"Nomad-{f.name}"
                destino = os.path.join(RELATORIOS_DIR, nome)
                n_nomad += 1
            elif eh_extrato:
                destino = os.path.join(EXTRATOS_DIR, f.name)
                n_extratos += 1
            else:
                destino = os.path.join(RELATORIOS_DIR, f.name)
                conn.execute("DELETE FROM operacoes WHERE arquivo=?", (f.name,))
                conn.execute("DELETE FROM relatorios WHERE nome_arquivo=?", (f.name,))
                conn.commit()
            with open(destino, "wb") as out:
                out.write(conteudo)
        n, novos = processar_relatorios(conn)
        load_ops.clear()
        load_ir_oficial.clear()
        load_nomad.clear()
        partes = []
        if novos:
            partes.append(f"{len(novos)} relatório(s) de operações · {n} operações")
        if n_extratos:
            partes.append(f"{n_extratos} extrato(s) de IR")
        if n_nomad:
            partes.append(f"{n_nomad} extrato(s) Nomad")
        st.success("Importado: " + (" · ".join(partes) if partes else "nada novo") + ".")
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("Relatórios processados")
    dfr = pd.read_sql_query(
        "SELECT periodo AS Período, nome_arquivo AS Arquivo, "
        "data_processamento AS Processado FROM relatorios ORDER BY periodo", conn)
    if dfr.empty:
        st.caption("Nenhum relatório processado ainda.")
    else:
        st.dataframe(dfr, width="stretch", hide_index=True)
