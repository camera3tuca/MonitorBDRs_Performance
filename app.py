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
    initial_sidebar_state="expanded",
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
    .stApp { background-color: #0f1117; color: #e2e8f0; }
    .main .block-container { padding: 1.5rem 1.25rem 3rem 1.25rem !important; max-width: 100% !important; }
    [data-testid="stSidebar"] { background-color: #161b27 !important; border-right: 1px solid #1e2535; }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #94a3b8 !important; }
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a2035 0%, #1e2535 100%);
        border: 1px solid #2a3548; border-radius: 14px; padding: 18px 16px 14px 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.35); min-height: 100px;
        display: flex; flex-direction: column; justify-content: center;
    }
    [data-testid="metric-container"] label {
        color: #64748b !important; font-size: 0.7rem !important; font-weight: 600 !important;
        letter-spacing: 0.09em !important; text-transform: uppercase !important;
        white-space: normal !important; line-height: 1.3 !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #f1f5f9 !important; font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.05rem !important; font-weight: 700 !important; white-space: normal !important;
        word-break: break-all !important; overflow-wrap: anywhere !important; line-height: 1.4 !important;
    }
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
def brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(v)


def fmt_kpi(value: float) -> str:
    s = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}" if value >= 0 else f"- R$ {s}"


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

VERDE, VERMELHO, AZUL, CINZA = "#10b981", "#ef4444", "#3b82f6", "#64748b"


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
    }


# ─────────────────────────────────────────────
# IMPORTAÇÃO AUTOMÁTICA NA INICIALIZAÇÃO
# ─────────────────────────────────────────────
if "importado" not in st.session_state:
    n, novos = processar_relatorios(conn)
    st.session_state["importado"] = True
    if novos:
        st.session_state["import_msg"] = f"{len(novos)} relatório(s) importado(s) · {n} operações."

df_all = load_ops(conn, _cache_key(conn))


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 MonitorBDRs")
    st.caption("Fonte: relatórios MyCapital")
    st.markdown("<hr>", unsafe_allow_html=True)

    menu = st.selectbox(
        "Navegação",
        ["🏠 Visão Geral", "📈 Performance Mensal", "💼 Por Ativo",
         "⚡ Day Trade vs Swing", "🧮 Métricas", "📋 Operações", "📥 Importar"],
        label_visibility="collapsed",
    )
    st.markdown("<hr>", unsafe_allow_html=True)

    if not df_all.empty:
        rm = resumo_mensal(df_all)
        liq = rm["total"].sum()
        cor = "badge-pos" if liq >= 0 else "badge-neg"
        st.markdown(f"**{len(df_all)}** operações · **{df_all['periodo'].nunique()}** meses")
        st.markdown(f"Resultado acumulado<br><span class='{cor}'>{brl(liq)}</span>",
                    unsafe_allow_html=True)
    else:
        st.caption("Nenhum dado carregado.")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.caption("Resultados conforme apuração MyCapital (líquidos de taxas).")


def kpi_delta(valor):
    """Texto de delta colorido para st.metric."""
    return ("normal" if valor >= 0 else "inverse")


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
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Win Rate", fmt_pct(m["win_rate"], sign=False))
        c2.metric("Trades Fechados", str(m["trades"]))
        c3.metric("Payoff", f"{m['payoff']:.2f}" if m["payoff"] else "N/A")
        c4.metric("Fator de Lucro", f"{m['fator_lucro']:.2f}" if m["fator_lucro"] else "N/A")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Operações Ganhas", str(m["ganhos"]))
        c6.metric("Operações Perdidas", str(m["perdas"]))
        c7.metric("Média de Ganho", fmt_kpi(m["media_ganho"]))
        c8.metric("Média de Perda", fmt_kpi(m["media_perda"]))

        c9, c10 = st.columns(2)
        c9.metric("Maior Ganho", fmt_kpi(m["maior_ganho"]))
        c10.metric("Maior Perda", fmt_kpi(m["maior_perda"]))

        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Distribuição dos Resultados (trades fechados)")
        fch = trades_fechados(df_all)
        hist = alt.Chart(fch).mark_bar(color=AZUL).encode(
            x=alt.X("resultado:Q", bin=alt.Bin(maxbins=40), title="Resultado por trade (R$)"),
            y=alt.Y("count():Q", title="Frequência"),
            tooltip=[alt.Tooltip("count():Q", title="Trades")])
        st.altair_chart(hist, width="stretch")


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

        st.caption(f"{len(d)} operação(ões)")
        disp = d[["data", "mercado", "ticker", "tipo", "quantidade", "preco",
                  "valor", "resultado"]].copy()
        disp.columns = ["Data", "Mercado", "Ativo", "Tipo", "Qtd", "Preço", "Valor", "Resultado"]
        st.dataframe(
            disp.style
                .format({"Preço": brl, "Valor": brl, "Resultado": brl, "Qtd": "{:.0f}"})
                .map(color_result, subset=["Resultado"]),
            width="stretch", hide_index=True, height=560,
        )


# ─────────────────────────────────────────────
# PÁGINA: IMPORTAR
# ─────────────────────────────────────────────
elif menu == "📥 Importar":
    st.title("Importar Relatórios MyCapital")
    st.markdown(
        "Envie os relatórios **\"Operações no mês\"** (PDF) exportados do MyCapital. "
        "Os resultados já vêm apurados e batem com sua contabilidade oficial."
    )
    if msg := st.session_state.pop("import_msg", None):
        st.success(msg)

    up = st.file_uploader("Relatórios MyCapital (PDF)", type=["pdf"], accept_multiple_files=True)
    if up:
        total = 0
        for f in up:
            destino = os.path.join(RELATORIOS_DIR, f.name)
            with open(destino, "wb") as out:
                out.write(f.getbuffer())
            # Evita duplicar: remove registro anterior do mesmo arquivo
            conn.execute("DELETE FROM operacoes WHERE arquivo=?", (f.name,))
            conn.execute("DELETE FROM relatorios WHERE nome_arquivo=?", (f.name,))
            conn.commit()
        n, novos = processar_relatorios(conn)
        load_ops.clear()
        st.success(f"{len(novos)} relatório(s) processado(s) · {n} operações importadas.")
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
