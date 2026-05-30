"""
Carteira BDR — Análise de Notas de Corretagem Santander
Lê PDFs de notas mensais, salva em SQLite e gera dashboard com insights.
"""

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import pdfplumber
import re
import os
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
#  Constantes
# ─────────────────────────────────────────────
DB_PATH   = "carteira.db"
DATA_DIR  = "notas_pdf"

# Mapa de nomes do PDF → ticker BDR (expansível)
NOME_TICKER = {
    "AMAZON":        "AMZO34",
    "APPLE":         "AAPL34",
    "ALPHABET":      "GOGL34",
    "MICROSOFT":     "MSFT34",
    "TESLA INC":     "TSLA34",
    "NVIDIA CORP":   "NVDC34",
    "NETFLIX":       "NFLX34",
    "MERCADOLIBRE":  "MELI34",
    "JPMORGAN":      "JPMC34",
    "BERKSHIRE":     "BERK34",
    "ORACLE":        "ORCL34",
    "MASTERCARD":    "MSCD34",
    "MCDONALDS":     "MCDC34",
    "COCA COLA":     "COCA34",
    "INTEL":         "ITLC34",
    "ALIBABAGR":     "BABA34",
    "AIRBNB":        "AIRB34",
    "WALMART":       "WALM34",
    "EMBRAER":       "EMBJ3",
    "TREND OURO":    "GOLD11",
    "SYN PROP TEC":  "SYNE3",
    "SYN PROP TEC ON": "SYNE3",
}

# ─────────────────────────────────────────────
#  Banco de dados
# ─────────────────────────────────────────────
def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS operacoes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nr_nota     TEXT,
            data        TEXT,
            nome        TEXT,
            ticker      TEXT,
            tipo        TEXT,
            cv          TEXT,
            day_trade   INTEGER,
            quantidade  REAL,
            preco       REAL,
            valor       REAL,
            fonte       TEXT
        );
        CREATE TABLE IF NOT EXISTS notas_importadas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT UNIQUE,
            importado   TEXT
        );
    """)
    conn.commit()
    conn.close()

def nota_ja_importada(filename):
    conn = get_conn()
    r = conn.execute(
        "SELECT 1 FROM notas_importadas WHERE filename=?", (filename,)
    ).fetchone()
    conn.close()
    return r is not None

def registrar_nota(filename):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO notas_importadas(filename, importado) VALUES(?,?)",
        (filename, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def salvar_operacoes(ops: list[dict], fonte: str):
    conn = get_conn()
    conn.executemany("""
        INSERT INTO operacoes
            (nr_nota, data, nome, ticker, tipo, cv, day_trade, quantidade, preco, valor, fonte)
        VALUES
            (:nr_nota,:data,:nome,:ticker,:tipo,:cv,:day_trade,:quantidade,:preco,:valor,:fonte)
    """, ops)
    conn.commit()
    conn.close()

def carregar_operacoes() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM operacoes ORDER BY data, nr_nota", conn)
    conn.close()
    if df.empty:
        return df
    df["data_dt"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["mes"]     = df["data_dt"].dt.to_period("M").astype(str)
    df["day_trade"] = df["day_trade"].astype(bool)
    return df

# ─────────────────────────────────────────────
#  Parser PDF Santander
# ─────────────────────────────────────────────
LINE_RE = re.compile(
    r'B3\s+RV\s+LISTADO([CV])\s+'
    r'(?:FRACION[AÁ]RIO|VISTA|FUTURO)\s+'
    r'(.+?)\s+'
    r'(DRN|CI|NM|ON|PN)\s*(?:ED|NM)?\s*'
    r'(D)?\s*'
    r'(\d+)\s+'
    r'([\d]+,[\d]+)\s+'
    r'([\d]+,[\d]+)\s+'
    r'([CD])'
)
NOTA_NUM_RE = re.compile(r'^\s*(\d{4,6})\s+\d+\s+(\d{2}/\d{2}/\d{4})')

def parse_pdf(path: str, fonte: str) -> list[dict]:
    ops = []
    cur_nota = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                mn = NOTA_NUM_RE.match(line)
                if mn:
                    cur_nota = {"nr": mn.group(1), "data": mn.group(2)}
                m = LINE_RE.search(line)
                if m and cur_nota:
                    nome = re.sub(r'\s+(ED|NM|ON|PN)\s*$', '', m.group(2).strip())
                    ticker = NOME_TICKER.get(nome, nome[:8].upper().replace(" ", ""))
                    ops.append({
                        "nr_nota":    cur_nota["nr"],
                        "data":       cur_nota["data"],
                        "nome":       nome,
                        "ticker":     ticker,
                        "tipo":       m.group(3),
                        "cv":         "Compra" if m.group(1) == "C" else "Venda",
                        "day_trade":  1 if m.group(4) == "D" else 0,
                        "quantidade": int(m.group(5)),
                        "preco":      float(m.group(6).replace(",", ".")),
                        "valor":      float(m.group(7).replace(",", ".")),
                        "fonte":      fonte,
                    })
    return ops

# ─────────────────────────────────────────────
#  Auto-load PDFs da pasta notas_pdf/
# ─────────────────────────────────────────────
def auto_load_notas():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        return 0
    total = 0
    for f in sorted(Path(DATA_DIR).glob("*.pdf")):
        if not nota_ja_importada(f.name):
            try:
                ops = parse_pdf(str(f), f.name)
                if ops:
                    salvar_operacoes(ops, f.name)
                    registrar_nota(f.name)
                    total += len(ops)
            except Exception as e:
                st.warning(f"Erro ao importar {f.name}: {e}")
    return total

# ─────────────────────────────────────────────
#  Cálculos financeiros
# ─────────────────────────────────────────────
def calcular_posicao(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula posição atual, custo médio ponderado e P&L realizado por ticker."""
    rows = []
    for ticker, g in df.groupby("ticker"):
        g = g.sort_values("data_dt")
        qtd_carteira = 0.0
        custo_total  = 0.0
        pl_realizado = 0.0

        for _, row in g.iterrows():
            if row["cv"] == "Compra":
                custo_total  += row["valor"]
                qtd_carteira += row["quantidade"]
            else:  # Venda
                if qtd_carteira > 0:
                    cm = custo_total / qtd_carteira
                    pl_realizado += (row["preco"] - cm) * row["quantidade"]
                    custo_total  -= cm * row["quantidade"]
                    qtd_carteira -= row["quantidade"]

        custo_medio = custo_total / qtd_carteira if qtd_carteira > 0 else 0
        nome = g["nome"].iloc[0]
        rows.append({
            "ticker":       ticker,
            "nome":         nome,
            "qtd_atual":    qtd_carteira,
            "custo_medio":  custo_medio,
            "custo_total":  custo_total,
            "pl_realizado": pl_realizado,
        })
    return pd.DataFrame(rows)

def calcular_pl_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """P&L realizado agregado por mês (só vendas vs custo médio calculado)."""
    rows = []
    for mes, gm in df.groupby("mes"):
        compras = gm[gm["cv"] == "Compra"]
        vendas  = gm[gm["cv"] == "Venda"]
        vol_c   = compras["valor"].sum()
        vol_v   = vendas["valor"].sum()
        n_ops   = len(gm)
        n_dt    = gm["day_trade"].sum()
        rows.append({
            "mes":        mes,
            "vol_compra": vol_c,
            "vol_venda":  vol_v,
            "saldo":      vol_v - vol_c,
            "n_ops":      n_ops,
            "n_dt":       int(n_dt),
        })
    return pd.DataFrame(rows).sort_values("mes")

# ─────────────────────────────────────────────
#  Formatação
# ─────────────────────────────────────────────
def fmt_brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def color_val(v):
    c = "green" if v >= 0 else "red"
    return f"<span style='color:{c};font-weight:600'>{fmt_brl(v)}</span>"

# ─────────────────────────────────────────────
#  App
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Carteira BDR",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .metric-card{background:#1e1e2e;border-radius:12px;padding:18px 22px;margin-bottom:8px}
  .metric-label{font-size:13px;color:#888;margin-bottom:4px}
  .metric-value{font-size:24px;font-weight:700}
  .pos-green{color:#4ade80}
  .neg-red{color:#f87171}
  [data-testid="stSidebar"]{background:#0f0f1a}
</style>
""", unsafe_allow_html=True)

# ── Init ──
init_db()
if "auto_loaded" not in st.session_state:
    n = auto_load_notas()
    st.session_state["auto_loaded"] = True
    if n:
        st.session_state["load_msg"] = f"✅ {n} operações carregadas automaticamente da pasta `{DATA_DIR}/`"

if "load_msg" in st.session_state:
    st.toast(st.session_state.pop("load_msg"), icon="📂")

# ── Sidebar ──
with st.sidebar:
    st.markdown("## 📊 Carteira BDR")
    st.markdown("---")

    # Upload de nota
    st.markdown("### 📥 Importar nota Santander")
    uploaded = st.file_uploader(
        "PDF da nota mensal de corretagem",
        type=["pdf"],
        key="uploader"
    )
    if uploaded:
        tmp = f"/tmp/{uploaded.name}"
        with open(tmp, "wb") as f:
            f.write(uploaded.read())
        if nota_ja_importada(uploaded.name):
            st.warning("Esta nota já foi importada.")
        else:
            with st.spinner("Processando PDF…"):
                ops = parse_pdf(tmp, uploaded.name)
            if ops:
                salvar_operacoes(ops, uploaded.name)
                registrar_nota(uploaded.name)
                st.success(f"✅ {len(ops)} operações importadas!")
                st.rerun()
            else:
                st.error("Nenhuma operação encontrada. Verifique o PDF.")

    st.markdown("---")

    # Notas já importadas
    conn = get_conn()
    notas = pd.read_sql_query(
        "SELECT filename, importado FROM notas_importadas ORDER BY importado DESC", conn
    )
    conn.close()
    if not notas.empty:
        st.markdown(f"**Notas importadas:** {len(notas)}")
        with st.expander("Ver lista"):
            for _, r in notas.iterrows():
                st.markdown(f"• `{r['filename']}`")

    st.markdown("---")

    # Limpar dados
    if st.button("🗑️ Limpar todos os dados", type="secondary"):
        conn = get_conn()
        conn.executescript("DELETE FROM operacoes; DELETE FROM notas_importadas;")
        conn.commit()
        conn.close()
        st.session_state.pop("auto_loaded", None)
        st.rerun()

# ── Carregar dados ──
df = carregar_operacoes()

if df.empty:
    st.markdown("## Bem-vindo à Carteira BDR 📊")
    st.info(
        "Nenhuma operação encontrada. Importe uma nota de corretagem mensal do Santander "
        f"pelo painel lateral, ou coloque PDFs na pasta `{DATA_DIR}/` e reinicie o app."
    )
    st.stop()

# ── Tabs ──
tab_dash, tab_ativos, tab_ativo, tab_ops = st.tabs([
    "📈 Dashboard", "📋 Todos os Ativos", "🔍 Análise por Ativo", "📄 Operações"
])

pos = calcular_posicao(df)
pl_mensal = calcular_pl_mensal(df)

# ═══════════════════════════════════════════
#  TAB 1 — Dashboard
# ═══════════════════════════════════════════
with tab_dash:
    st.markdown("## Dashboard Geral")

    compras  = df[df["cv"] == "Compra"]["valor"].sum()
    vendas   = df[df["cv"] == "Venda"]["valor"].sum()
    n_ops    = len(df)
    n_dt     = df["day_trade"].sum()
    pl_real  = pos["pl_realizado"].sum()
    n_ativos = len(pos[pos["qtd_atual"] > 0])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Volume Comprado", fmt_brl(compras))
    c2.metric("Volume Vendido",  fmt_brl(vendas))
    c3.metric("Ativos em Carteira", n_ativos)
    c4.metric("Total de Operações", f"{n_ops} ({int(n_dt)} DT)")
    delta_color = "normal" if pl_real >= 0 else "inverse"
    c5.metric("P&L Realizado", fmt_brl(pl_real), delta=f"{pl_real:+.2f}", delta_color=delta_color)

    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Volume mensal (R$)")
        fig = px.bar(
            pl_mensal, x="mes", y=["vol_compra", "vol_venda"],
            barmode="group",
            labels={"mes": "Mês", "value": "R$", "variable": ""},
            color_discrete_map={"vol_compra": "#60a5fa", "vol_venda": "#34d399"},
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", legend_title_text=""
        )
        fig.for_each_trace(lambda t: t.update(name={"vol_compra": "Compras", "vol_venda": "Vendas"}[t.name]))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("#### Saldo líquido mensal (Vendas − Compras)")
        colors = ["#34d399" if v >= 0 else "#f87171" for v in pl_mensal["saldo"]]
        fig2 = go.Figure(go.Bar(
            x=pl_mensal["mes"], y=pl_mensal["saldo"],
            marker_color=colors, text=pl_mensal["saldo"].map(lambda x: fmt_brl(x)),
            textposition="outside"
        ))
        fig2.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", xaxis_title="Mês", yaxis_title="R$"
        )
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("#### Distribuição por ativo (volume total)")
        vol_ativo = (
            df.groupby("nome")["valor"].sum()
            .sort_values(ascending=False).head(15).reset_index()
        )
        fig3 = px.bar(
            vol_ativo, x="valor", y="nome", orientation="h",
            color="valor", color_continuous_scale="Blues",
            labels={"valor": "Volume R$", "nome": ""}
        )
        fig3.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", showlegend=False, coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"}
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.markdown("#### Operações por dia da semana")
        df["dow"] = df["data_dt"].dt.day_name()
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        pt_names = {"Monday":"Seg","Tuesday":"Ter","Wednesday":"Qua","Thursday":"Qui","Friday":"Sex"}
        dow = df["dow"].value_counts().reindex(order, fill_value=0).reset_index()
        dow.columns = ["dia", "ops"]
        dow["dia_pt"] = dow["dia"].map(pt_names)
        fig4 = px.bar(
            dow, x="dia_pt", y="ops",
            color="ops", color_continuous_scale="Purples",
            labels={"dia_pt": "Dia", "ops": "Operações"}
        )
        fig4.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", showlegend=False, coloraxis_showscale=False
        )
        st.plotly_chart(fig4, use_container_width=True)

    # Insights automáticos
    st.markdown("---")
    st.markdown("### 💡 Insights")

    ativo_mais_trad = df.groupby("nome")["valor"].sum().idxmax()
    vol_mais_trad   = df.groupby("nome")["valor"].sum().max()
    pct_dt          = 100 * n_dt / n_ops if n_ops else 0
    mes_mais_ativo  = pl_mensal.loc[pl_mensal["n_ops"].idxmax(), "mes"]
    ativo_maior_pl  = pos.loc[pos["pl_realizado"].idxmax(), "nome"] if not pos.empty else "—"
    ativo_menor_pl  = pos.loc[pos["pl_realizado"].idxmin(), "nome"] if not pos.empty else "—"

    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1:
        st.info(f"**Ativo mais negociado:** {ativo_mais_trad}\n\n{fmt_brl(vol_mais_trad)} em volume total")
    with col_i2:
        st.info(f"**Day trade:** {pct_dt:.1f}% das operações\n\n{int(n_dt)} de {n_ops} negócios")
    with col_i3:
        st.info(f"**Mês mais ativo:** {mes_mais_ativo}\n\n{pl_mensal.loc[pl_mensal['mes']==mes_mais_ativo, 'n_ops'].values[0]} operações")

    col_i4, col_i5 = st.columns(2)
    with col_i4:
        st.success(f"**Melhor resultado realizado:** {ativo_maior_pl}\n\n{fmt_brl(pos['pl_realizado'].max())}")
    with col_i5:
        st.error(f"**Pior resultado realizado:** {ativo_menor_pl}\n\n{fmt_brl(pos['pl_realizado'].min())}")

# ═══════════════════════════════════════════
#  TAB 2 — Todos os Ativos
# ═══════════════════════════════════════════
with tab_ativos:
    st.markdown("## Resumo por Ativo")

    pos_show = pos.copy()
    pos_show["custo_medio_fmt"]  = pos_show["custo_medio"].map(fmt_brl)
    pos_show["custo_total_fmt"]  = pos_show["custo_total"].map(fmt_brl)
    pos_show["pl_realizado_fmt"] = pos_show["pl_realizado"].map(fmt_brl)

    # Tabela interativa
    pos_show["pl_color"] = pos_show["pl_realizado"].apply(
        lambda v: "🟢" if v > 0 else ("🔴" if v < 0 else "⚪")
    )
    exib = pos_show[[
        "pl_color", "nome", "ticker", "qtd_atual",
        "custo_medio_fmt", "custo_total_fmt", "pl_realizado_fmt"
    ]].rename(columns={
        "pl_color": "",
        "nome": "Ativo",
        "ticker": "Ticker",
        "qtd_atual": "Qtd Atual",
        "custo_medio_fmt": "Custo Médio",
        "custo_total_fmt": "Custo Total",
        "pl_realizado_fmt": "P&L Realizado",
    })
    st.dataframe(exib, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### P&L Realizado por Ativo")
    pos_sorted = pos.sort_values("pl_realizado")
    colors_pl  = ["#f87171" if v < 0 else "#4ade80" for v in pos_sorted["pl_realizado"]]
    fig_pl = go.Figure(go.Bar(
        x=pos_sorted["pl_realizado"],
        y=pos_sorted["nome"],
        orientation="h",
        marker_color=colors_pl,
        text=pos_sorted["pl_realizado"].map(fmt_brl),
        textposition="outside",
    ))
    fig_pl.update_layout(
        height=max(400, 28 * len(pos_sorted)),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc", xaxis_title="R$", yaxis_title=""
    )
    st.plotly_chart(fig_pl, use_container_width=True)

# ═══════════════════════════════════════════
#  TAB 3 — Análise por Ativo
# ═══════════════════════════════════════════
with tab_ativo:
    st.markdown("## Análise Detalhada por Ativo")

    nomes_disponiveis = sorted(df["nome"].unique())
    ativo_sel = st.selectbox("Selecione o ativo:", nomes_disponiveis)

    dfa = df[df["nome"] == ativo_sel].copy().sort_values("data_dt")
    pa  = pos[pos["nome"] == ativo_sel].iloc[0] if not pos[pos["nome"] == ativo_sel].empty else None

    if pa is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Quantidade em Carteira", f"{pa['qtd_atual']:.0f}")
        c2.metric("Custo Médio",            fmt_brl(pa["custo_medio"]))
        c3.metric("Custo Total Posição",    fmt_brl(pa["custo_total"]))
        delta_col = "normal" if pa["pl_realizado"] >= 0 else "inverse"
        c4.metric("P&L Realizado",          fmt_brl(pa["pl_realizado"]),
                  delta=f"{pa['pl_realizado']:+.2f}", delta_color=delta_col)

    st.markdown("---")

    col_e1, col_e2 = st.columns(2)

    with col_e1:
        st.markdown(f"#### Histórico de preços — {ativo_sel}")
        compras_a = dfa[dfa["cv"] == "Compra"]
        vendas_a  = dfa[dfa["cv"] == "Venda"]
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Scatter(
            x=compras_a["data_dt"], y=compras_a["preco"],
            mode="markers", name="Compra",
            marker=dict(color="#60a5fa", size=9, symbol="circle"),
            text=compras_a.apply(lambda r: f"Qtd {r['quantidade']} @ {fmt_brl(r['preco'])}", axis=1),
            hovertemplate="%{text}<extra></extra>"
        ))
        fig_hist.add_trace(go.Scatter(
            x=vendas_a["data_dt"], y=vendas_a["preco"],
            mode="markers", name="Venda",
            marker=dict(color="#f87171", size=9, symbol="x"),
            text=vendas_a.apply(lambda r: f"Qtd {r['quantidade']} @ {fmt_brl(r['preco'])}", axis=1),
            hovertemplate="%{text}<extra></extra>"
        ))
        if pa is not None and pa["custo_medio"] > 0:
            fig_hist.add_hline(
                y=pa["custo_medio"], line_dash="dash", line_color="#fbbf24",
                annotation_text=f"PM {fmt_brl(pa['custo_medio'])}", annotation_position="right"
            )
        fig_hist.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", xaxis_title="Data", yaxis_title="R$"
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_e2:
        st.markdown(f"#### Volume negociado por mês — {ativo_sel}")
        vol_mes_a = (
            dfa.groupby(["mes", "cv"])["valor"].sum()
            .reset_index()
        )
        fig_vol = px.bar(
            vol_mes_a, x="mes", y="valor", color="cv", barmode="group",
            color_discrete_map={"Compra": "#60a5fa", "Venda": "#34d399"},
            labels={"mes": "Mês", "valor": "R$", "cv": ""}
        )
        fig_vol.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc"
        )
        st.plotly_chart(fig_vol, use_container_width=True)

    # Estatísticas do ativo
    st.markdown(f"#### Estatísticas — {ativo_sel}")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("Total de Negócios",  len(dfa))
    col_s2.metric("Day Trades",          int(dfa["day_trade"].sum()))
    col_s3.metric("Preço Mín. Compra",  fmt_brl(dfa[dfa["cv"]=="Compra"]["preco"].min()) if not compras_a.empty else "—")
    col_s4.metric("Preço Máx. Compra",  fmt_brl(dfa[dfa["cv"]=="Compra"]["preco"].max()) if not compras_a.empty else "—")

    col_s5, col_s6, col_s7, col_s8 = st.columns(4)
    col_s5.metric("Qtd Total Comprada", f"{dfa[dfa['cv']=='Compra']['quantidade'].sum():.0f}")
    col_s6.metric("Qtd Total Vendida",  f"{dfa[dfa['cv']=='Venda']['quantidade'].sum():.0f}")
    col_s7.metric("Volume Comprado",    fmt_brl(dfa[dfa["cv"]=="Compra"]["valor"].sum()))
    col_s8.metric("Volume Vendido",     fmt_brl(dfa[dfa["cv"]=="Venda"]["valor"].sum()))

    # Insights automáticos do ativo
    st.markdown("---")
    st.markdown(f"#### 💡 Insights — {ativo_sel}")

    n_compras_a = len(compras_a)
    n_vendas_a  = len(vendas_a)
    pct_dt_a    = 100 * dfa["day_trade"].sum() / len(dfa) if len(dfa) else 0
    pm_compra   = dfa[dfa["cv"]=="Compra"]["preco"].mean() if not compras_a.empty else 0
    pm_venda    = dfa[dfa["cv"]=="Venda"]["preco"].mean()  if not vendas_a.empty  else 0

    insights_col1, insights_col2 = st.columns(2)
    with insights_col1:
        st.info(
            f"**{n_compras_a}** compras e **{n_vendas_a}** vendas\n\n"
            f"**{pct_dt_a:.0f}%** das operações foram Day Trade"
        )
        if pm_compra > 0 and pm_venda > 0:
            diff = pm_venda - pm_compra
            emoji = "📈" if diff > 0 else "📉"
            st.info(
                f"{emoji} Preço médio compra: **{fmt_brl(pm_compra)}**\n\n"
                f"Preço médio venda: **{fmt_brl(pm_venda)}**\n\n"
                f"Diferença: {fmt_brl(diff)} por cota"
            )
    with insights_col2:
        if pa is not None and pa["qtd_atual"] > 0:
            st.success(
                f"📦 **Posição aberta:** {pa['qtd_atual']:.0f} cotas\n\n"
                f"Custo médio atual: **{fmt_brl(pa['custo_medio'])}**\n\n"
                f"Custo total: **{fmt_brl(pa['custo_total'])}**"
            )
        else:
            st.info("Posição zerada — não há cotas em carteira.")

        if pa is not None:
            pl = pa["pl_realizado"]
            if pl > 0:
                st.success(f"✅ P&L realizado positivo: **{fmt_brl(pl)}**")
            elif pl < 0:
                st.error(f"⚠️ P&L realizado negativo: **{fmt_brl(pl)}**")
            else:
                st.info("P&L realizado: zero (sem vendas ou break-even).")

    # Tabela de operações do ativo
    st.markdown("---")
    st.markdown(f"#### Operações — {ativo_sel}")
    show_a = dfa[["data", "nr_nota", "cv", "day_trade", "quantidade", "preco", "valor"]].copy()
    show_a.columns = ["Data", "Nota", "C/V", "Day Trade", "Qtd", "Preço", "Valor R$"]
    show_a["Preço"]    = show_a["Preço"].map(fmt_brl)
    show_a["Valor R$"] = show_a["Valor R$"].map(fmt_brl)
    show_a["Day Trade"] = show_a["Day Trade"].map({True: "✅", False: "—", 1: "✅", 0: "—"})
    st.dataframe(show_a.sort_values("Data", ascending=False), use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════
#  TAB 4 — Operações brutas
# ═══════════════════════════════════════════
with tab_ops:
    st.markdown("## Histórico de Operações")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filtro_ativo = st.multiselect("Ativo:", sorted(df["nome"].unique()), placeholder="Todos")
    with col_f2:
        filtro_cv = st.multiselect("Tipo:", ["Compra", "Venda"], placeholder="Todos")
    with col_f3:
        filtro_dt = st.selectbox("Day Trade:", ["Todos", "Somente Day Trade", "Somente Normal"])

    df_show = df.copy()
    if filtro_ativo:
        df_show = df_show[df_show["nome"].isin(filtro_ativo)]
    if filtro_cv:
        df_show = df_show[df_show["cv"].isin(filtro_cv)]
    if filtro_dt == "Somente Day Trade":
        df_show = df_show[df_show["day_trade"]]
    elif filtro_dt == "Somente Normal":
        df_show = df_show[~df_show["day_trade"]]

    st.markdown(f"**{len(df_show)} operações** | Volume: {fmt_brl(df_show['valor'].sum())}")

    exib_ops = df_show[[
        "data", "nr_nota", "nome", "ticker", "cv", "day_trade", "quantidade", "preco", "valor", "fonte"
    ]].copy().sort_values("data", ascending=False)
    exib_ops.columns = ["Data","Nota","Ativo","Ticker","C/V","DT","Qtd","Preço","Valor R$","Fonte"]
    exib_ops["Preço"]    = exib_ops["Preço"].map(fmt_brl)
    exib_ops["Valor R$"] = exib_ops["Valor R$"].map(fmt_brl)
    exib_ops["DT"]       = exib_ops["DT"].map({True: "✅", False: "—", 1: "✅", 0: "—"})

    st.dataframe(exib_ops, use_container_width=True, hide_index=True)

    # Export
    csv = df_show.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar CSV", csv, "operacoes.csv", "text/csv")
