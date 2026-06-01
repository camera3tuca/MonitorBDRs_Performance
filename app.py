"""
Carteira BDR — Análise de Notas de Corretagem Santander
- Auto-carrega PDFs da pasta notas_pdf/
- Layout mobile-first, coluna única
- Zero duplicatas (dedup global por nota)
"""

import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import plotly.express as px
import pdfplumber
import re, os
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
DB_PATH  = "carteira.db"
DATA_DIR = "notas_pdf"

NOME_TICKER = {
    "AMAZON":          "AMZO34",
    "APPLE":           "AAPL34",
    "ALPHABET":        "GOGL34",
    "MICROSOFT":       "MSFT34",
    "TESLA INC":       "TSLA34",
    "NVIDIA CORP":     "NVDC34",
    "NETFLIX":         "NFLX34",
    "MERCADOLIBRE":    "MELI34",
    "JPMORGAN":        "JPMC34",
    "BERKSHIRE":       "BERK34",
    "ORACLE":          "ORCL34",
    "MASTERCARD":      "MSCD34",
    "MCDONALDS":       "MCDC34",
    "COCA COLA":       "COCA34",
    "INTEL":           "ITLC34",
    "ALIBABAGR":       "BABA34",
    "AIRBNB":          "AIRB34",
    "WALMART":         "WALM34",
    "EMBRAER":         "EMBJ3",
    "TREND OURO":      "GOLD11",
    "SYN PROP TEC":    "SYNE3",
    "SYN PROP TEC ON": "SYNE3",
    "WALT DISNEY":     "DISB34",
}

LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font_color="#ccc",
    margin=dict(l=4, r=4, t=30, b=4),
)

def fmt(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ─── Banco ───────────────────────────────────
def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nr_nota TEXT, data TEXT, nome TEXT, ticker TEXT, tipo TEXT,
            cv TEXT, day_trade INTEGER, quantidade REAL,
            preco REAL, valor REAL, fonte TEXT
        );
        CREATE TABLE IF NOT EXISTS notas_importadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE, importado TEXT
        );
    """)
    conn.commit(); conn.close()

def ja_importada(f):
    conn = get_conn()
    r = conn.execute("SELECT 1 FROM notas_importadas WHERE filename=?", (f,)).fetchone()
    conn.close(); return r is not None

def registrar(f):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO notas_importadas(filename,importado) VALUES(?,?)",
                 (f, datetime.now().isoformat()))
    conn.commit(); conn.close()

def salvar(ops):
    conn = get_conn()
    conn.executemany("""INSERT INTO operacoes
        (nr_nota,data,nome,ticker,tipo,cv,day_trade,quantidade,preco,valor,fonte)
        VALUES (:nr_nota,:data,:nome,:ticker,:tipo,:cv,:day_trade,:quantidade,:preco,:valor,:fonte)""", ops)
    conn.commit(); conn.close()

def carregar():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM operacoes ORDER BY data, nr_nota", conn)
    conn.close()
    if df.empty: return df
    df["data_dt"]   = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["mes"]       = df["data_dt"].dt.strftime("%Y-%m")
    df["mes_label"] = df["data_dt"].dt.strftime("%b/%Y")
    df["day_trade"] = df["day_trade"].astype(bool)
    return df

# ─── Parser PDF ───────────────────────────────
LINE_RE = re.compile(
    r'B3\s+RV\s+LISTADO([CV])\s+'
    r'(?:FRACION[AÁ]RIO|VISTA|FUTURO)\s+'
    r'(.+?)\s+(DRN|CI|NM|ON|PN)\s*(?:ED|NM)?\s*(D)?\s*'
    r'(\d+)\s+([\d]+,[\d]+)\s+([\d]+,[\d]+)\s+([CD])'
)
NOTA_RE = re.compile(r'^\s*(\d{4,6})\s+(\d+)\s+(\d{2}/\d{2}/\d{4})')

def parse_pdf(path, fonte):
    ops, global_seen = [], {}
    with pdfplumber.open(path) as pdf:
        cur = {}
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            for line in lines:
                mn = NOTA_RE.match(line)
                if mn:
                    cur = {"nr": mn.group(1), "data": mn.group(3)}
                    break
            for line in lines:
                m = LINE_RE.search(line)
                if not m or not cur: continue
                nome  = re.sub(r'\s+(ED|NM|ON|PN)\s*$', '', m.group(2).strip())
                nr    = cur["nr"]
                chave = (m.group(1), nome, m.group(5), m.group(6), m.group(7))
                if nr not in global_seen: global_seen[nr] = set()
                if chave in global_seen[nr]: continue
                global_seen[nr].add(chave)
                ticker = NOME_TICKER.get(nome, nome[:8].upper().replace(" ", ""))
                ops.append({
                    "nr_nota": nr, "data": cur["data"],
                    "nome": nome, "ticker": ticker, "tipo": m.group(3),
                    "cv": "Compra" if m.group(1) == "C" else "Venda",
                    "day_trade": 1 if m.group(4) == "D" else 0,
                    "quantidade": int(m.group(5)),
                    "preco": float(m.group(6).replace(",", ".")),
                    "valor": float(m.group(7).replace(",", ".")),
                    "fonte": fonte,
                })
    return ops

def auto_load():
    os.makedirs(DATA_DIR, exist_ok=True)
    total = 0
    for f in sorted(Path(DATA_DIR).glob("*.pdf")):
        if not ja_importada(f.name):
            try:
                ops = parse_pdf(str(f), f.name)
                if ops:
                    salvar(ops); registrar(f.name)
                    total += len(ops)
            except Exception as e:
                st.warning(f"Erro em {f.name}: {e}")
    return total

# ─── Cálculos ────────────────────────────────
def posicao(df):
    rows = []
    for nome, g in df.groupby("nome"):
        g = g.sort_values("data_dt")
        qtd = custo = pl = 0.0
        for _, r in g.iterrows():
            if r["cv"] == "Compra":
                custo += r["valor"]; qtd += r["quantidade"]
            else:
                if qtd > 0:
                    cm = custo / qtd
                    pl += (r["preco"] - cm) * r["quantidade"]
                    custo -= cm * r["quantidade"]
                    qtd -= r["quantidade"]
        rows.append({
            "nome": nome, "ticker": g["ticker"].iloc[0],
            "qtd_atual": qtd,
            "custo_medio": custo / qtd if qtd > 0 else 0,
            "custo_total": custo, "pl_realizado": pl,
        })
    return pd.DataFrame(rows)

def pl_mes(df):
    rows = []
    for mes, g in df.groupby("mes"):
        c = g[g["cv"] == "Compra"]["valor"].sum()
        v = g[g["cv"] == "Venda"]["valor"].sum()
        rows.append({
            "mes": mes, "label": g["mes_label"].iloc[0],
            "vol_compra": c, "vol_venda": v, "saldo": v - c,
            "n_ops": len(g), "n_dt": int(g["day_trade"].sum()),
        })
    return pd.DataFrame(rows).sort_values("mes")

# ─── App ─────────────────────────────────────
st.set_page_config(
    page_title="Carteira BDR", page_icon="📊",
    layout="wide", initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
[data-testid="stSidebar"]{background:#0f0f1a}
.block-container{padding-top:.8rem;padding-bottom:.8rem;max-width:860px}
</style>""", unsafe_allow_html=True)

init_db()
if "loaded" not in st.session_state:
    n = auto_load()
    st.session_state.loaded = True
    if n: st.session_state.msg = f"✅ {n} operações carregadas de `{DATA_DIR}/`"

if "msg" in st.session_state:
    st.toast(st.session_state.pop("msg"), icon="📂")

# ─── Sidebar ─────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Carteira BDR")
    st.markdown("---")
    st.markdown("### 📥 Importar nota")
    up = st.file_uploader("PDF da nota mensal Santander", type=["pdf"])
    if up:
        tmp = f"/tmp/{up.name}"
        open(tmp, "wb").write(up.read())
        if ja_importada(up.name):
            st.warning("Nota já importada.")
        else:
            with st.spinner("Processando…"):
                ops = parse_pdf(tmp, up.name)
            if ops:
                salvar(ops); registrar(up.name)
                st.success(f"✅ {len(ops)} operações importadas!"); st.rerun()
            else:
                st.error("Nenhuma operação encontrada.")
    st.markdown("---")
    conn = get_conn()
    notas = pd.read_sql_query(
        "SELECT filename FROM notas_importadas ORDER BY importado DESC", conn)
    conn.close()
    if not notas.empty:
        st.markdown(f"**Notas importadas:** {len(notas)}")
        with st.expander("Ver lista"):
            for _, r in notas.iterrows():
                st.markdown(f"• `{r.filename}`")
    st.markdown("---")
    if st.button("🗑️ Limpar todos os dados", type="secondary"):
        conn = get_conn()
        conn.executescript("DELETE FROM operacoes; DELETE FROM notas_importadas;")
        conn.commit(); conn.close()
        st.session_state.pop("loaded", None); st.rerun()

# ─── Dados ───────────────────────────────────
df = carregar()
if df.empty:
    st.title("📊 Carteira BDR")
    st.info(f"Importe uma nota PDF pelo menu lateral ← ou coloque PDFs em `{DATA_DIR}/`.")
    st.stop()

pos = posicao(df)
plm = pl_mes(df)

# ─── Tabs ────────────────────────────────────
t1, t2, t3, t4 = st.tabs([
    "📈 Dashboard", "📋 Todos os Ativos",
    "🔍 Análise por Ativo", "📄 Operações"
])

# ══════════════════════════════════════
#  TAB 1 — Dashboard
# ══════════════════════════════════════
with t1:
    st.markdown("## Dashboard Geral")

    tot_c  = df[df.cv == "Compra"]["valor"].sum()
    tot_v  = df[df.cv == "Venda"]["valor"].sum()
    n_ops  = len(df)
    n_dt   = int(df.day_trade.sum())
    pl_tot = pos.pl_realizado.sum()
    n_at   = int((pos.qtd_atual > 0).sum())

    a, b = st.columns(2)
    a.metric("💰 Volume Comprado",    fmt(tot_c))
    b.metric("💵 Volume Vendido",     fmt(tot_v))
    c, d = st.columns(2)
    c.metric("📦 Ativos em Carteira", n_at)
    d.metric("🔢 Total de Operações", n_ops)
    e, f_ = st.columns(2)
    e.metric("⚡ Day Trades",          f"{n_dt}  ({100*n_dt/n_ops:.0f}%)")
    f_.metric("📈 P&L Realizado",      fmt(pl_tot),
              delta=f"{pl_tot:+.2f}",
              delta_color="normal" if pl_tot >= 0 else "inverse")

    st.markdown("---")

    # Volume mensal
    st.markdown("#### 📅 Volume mensal")
    fig = go.Figure()
    fig.add_bar(name="Compras", x=plm.label, y=plm.vol_compra, marker_color="#60a5fa")
    fig.add_bar(name="Vendas",  x=plm.label, y=plm.vol_venda,  marker_color="#34d399")
    fig.update_layout(**LAYOUT, barmode="group",
                      xaxis=dict(type="category", title=""),
                      yaxis_title="R$",
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)

    # Saldo líquido mensal
    st.markdown("#### 💹 Saldo líquido por mês")
    cols_bar = ["#34d399" if v >= 0 else "#f87171" for v in plm.saldo]
    fig2 = go.Figure(go.Bar(
        x=plm.label, y=plm.saldo, marker_color=cols_bar,
        text=[fmt(v) for v in plm.saldo], textposition="outside",
    ))
    fig2.update_layout(**LAYOUT, xaxis=dict(type="category", title=""), yaxis_title="R$")
    st.plotly_chart(fig2, use_container_width=True)

    # Top ativos por volume
    st.markdown("#### 🏆 Top 15 ativos por volume")
    vol = df.groupby("nome")["valor"].sum().sort_values(ascending=True).tail(15).reset_index()
    fig3 = px.bar(vol, x="valor", y="nome", orientation="h",
                  color="valor", color_continuous_scale="Blues",
                  labels={"valor": "Volume R$", "nome": ""})
    fig3.update_layout(**LAYOUT, coloraxis_showscale=False)
    st.plotly_chart(fig3, use_container_width=True)

    # Operações por dia da semana
    st.markdown("#### 📅 Operações por dia da semana")
    ordem  = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    ptmap  = {"Monday":"Seg","Tuesday":"Ter","Wednesday":"Qua","Thursday":"Qui","Friday":"Sex"}
    dow    = df.data_dt.dt.day_name().value_counts().reindex(ordem, fill_value=0).reset_index()
    dow.columns = ["dia", "ops"]
    dow["dia_pt"] = dow.dia.map(ptmap)
    fig4 = px.bar(dow, x="dia_pt", y="ops",
                  color="ops", color_continuous_scale="Purples",
                  labels={"dia_pt": "", "ops": "Operações"})
    fig4.update_layout(**LAYOUT, coloraxis_showscale=False)
    st.plotly_chart(fig4, use_container_width=True)

    # Insights
    st.markdown("---")
    st.markdown("### 💡 Insights")
    mais_vol   = df.groupby("nome")["valor"].sum()
    at_vol     = mais_vol.idxmax()
    v_vol      = mais_vol.max()
    pct_dt     = 100 * n_dt / n_ops
    mes_at     = plm.loc[plm.n_ops.idxmax(), "label"] if not plm.empty else "—"
    n_ops_mes  = plm.n_ops.max()         if not plm.empty else 0
    melhor_at  = pos.loc[pos.pl_realizado.idxmax(), "nome"]
    melhor_val = pos.pl_realizado.max()
    pior_at    = pos.loc[pos.pl_realizado.idxmin(), "nome"]
    pior_val   = pos.pl_realizado.min()

    st.info(f"📊 **Ativo mais negociado:** {at_vol} — {fmt(v_vol)} em volume total")
    st.info(f"⚡ **Day trade:** {pct_dt:.1f}% das operações — {n_dt} de {n_ops} negócios")
    st.info(f"📆 **Mês mais ativo:** {mes_at} — {n_ops_mes} operações")
    st.success(f"✅ **Melhor resultado realizado:** {melhor_at} — {fmt(melhor_val)}")
    st.error(f"⚠️ **Pior resultado realizado:** {pior_at} — {fmt(pior_val)}")

# ══════════════════════════════════════
#  TAB 2 — Todos os Ativos
# ══════════════════════════════════════
with t2:
    st.markdown("## Resumo por Ativo")

    exib = pos.copy()
    exib[""] = exib.pl_realizado.apply(lambda v: "🟢" if v > 0 else ("🔴" if v < 0 else "⚪"))
    exib["Qtd"]           = exib.qtd_atual.map(lambda x: f"{x:.0f}")
    exib["Custo Médio"]   = exib.custo_medio.map(fmt)
    exib["Custo Total"]   = exib.custo_total.map(fmt)
    exib["P&L Realizado"] = exib.pl_realizado.map(fmt)

    st.dataframe(
        exib[["","nome","ticker","Qtd","Custo Médio","Custo Total","P&L Realizado"]]
        .rename(columns={"nome":"Ativo","ticker":"Ticker"})
        .sort_values("Ativo"),
        use_container_width=True, hide_index=True
    )

    st.markdown("---")
    st.markdown("#### 📊 P&L Realizado por Ativo")
    ps = pos.sort_values("pl_realizado")
    figpl = go.Figure(go.Bar(
        x=ps.pl_realizado, y=ps.nome, orientation="h",
        marker_color=["#f87171" if v < 0 else "#4ade80" for v in ps.pl_realizado],
        text=[fmt(v) for v in ps.pl_realizado], textposition="outside",
    ))
    figpl.update_layout(**LAYOUT, height=max(420, 30 * len(ps)), xaxis_title="R$")
    st.plotly_chart(figpl, use_container_width=True)

# ══════════════════════════════════════
#  TAB 3 — Análise por Ativo
# ══════════════════════════════════════
with t3:
    st.markdown("## Análise Detalhada por Ativo")
    sel = st.selectbox("Selecione o ativo:", sorted(df.nome.unique()))

    dfa = df[df.nome == sel].sort_values("data_dt")
    row = pos[pos.nome == sel]
    pa  = row.iloc[0] if not row.empty else None

    if pa is not None:
        a, b = st.columns(2)
        a.metric("📦 Qtd em Carteira", f"{pa.qtd_atual:.0f}")
        b.metric("💰 Custo Médio",     fmt(pa.custo_medio))
        c, d = st.columns(2)
        c.metric("🧾 Custo Total",     fmt(pa.custo_total))
        d.metric("📈 P&L Realizado",   fmt(pa.pl_realizado),
                 delta=f"{pa.pl_realizado:+.2f}",
                 delta_color="normal" if pa.pl_realizado >= 0 else "inverse")

    st.markdown("---")

    # Histórico de preços
    st.markdown(f"#### 📉 Histórico de preços — {sel}")
    cmp = dfa[dfa.cv == "Compra"]
    vnd = dfa[dfa.cv == "Venda"]
    figh = go.Figure()
    if not cmp.empty:
        figh.add_trace(go.Scatter(
            x=cmp.data_dt, y=cmp.preco, mode="markers", name="Compra",
            marker=dict(color="#60a5fa", size=10, symbol="circle"),
            text=cmp.apply(lambda r: f"{r.data} · Qtd {r.quantidade:.0f} @ {fmt(r.preco)}", axis=1),
            hovertemplate="%{text}<extra></extra>",
        ))
    if not vnd.empty:
        figh.add_trace(go.Scatter(
            x=vnd.data_dt, y=vnd.preco, mode="markers", name="Venda",
            marker=dict(color="#f87171", size=10, symbol="x"),
            text=vnd.apply(lambda r: f"{r.data} · Qtd {r.quantidade:.0f} @ {fmt(r.preco)}", axis=1),
            hovertemplate="%{text}<extra></extra>",
        ))
    if pa is not None and pa.custo_medio > 0:
        figh.add_hline(y=pa.custo_medio, line_dash="dash", line_color="#fbbf24",
                       annotation_text=f"PM {fmt(pa.custo_medio)}",
                       annotation_position="top right")
    figh.update_layout(**LAYOUT, xaxis_title="Data", yaxis_title="R$",
                       legend=dict(orientation="h", y=1.12))
    st.plotly_chart(figh, use_container_width=True)

    # Volume por mês
    st.markdown(f"#### 📅 Volume por mês — {sel}")
    vm = dfa.groupby(["mes","mes_label","cv"])["valor"].sum().reset_index()
    if not vm.empty:
        figv = go.Figure()
        for cv, cor in [("Compra","#60a5fa"),("Venda","#34d399")]:
            sub = vm[vm.cv == cv]
            if not sub.empty:
                figv.add_bar(name=cv, x=sub.mes_label, y=sub.valor, marker_color=cor)
        figv.update_layout(**LAYOUT, barmode="group",
                           xaxis=dict(type="category", title=""),
                           yaxis_title="R$", legend=dict(orientation="h", y=1.12))
        st.plotly_chart(figv, use_container_width=True)

    # Estatísticas
    st.markdown("---")
    st.markdown(f"#### 📊 Estatísticas — {sel}")
    a, b = st.columns(2)
    a.metric("Total de Negócios", len(dfa))
    b.metric("Day Trades",        int(dfa.day_trade.sum()))
    c, d = st.columns(2)
    c.metric("Qtd Comprada", f"{cmp.quantidade.sum():.0f}" if not cmp.empty else "0")
    d.metric("Qtd Vendida",  f"{vnd.quantidade.sum():.0f}" if not vnd.empty else "0")
    e, f_ = st.columns(2)
    pm_c = cmp.preco.mean() if not cmp.empty else 0
    pm_v = vnd.preco.mean() if not vnd.empty else 0
    e.metric("Preço Médio Compra", fmt(pm_c) if pm_c else "—")
    f_.metric("Preço Médio Venda", fmt(pm_v) if pm_v else "—")
    g_, h = st.columns(2)
    g_.metric("Volume Comprado", fmt(cmp.valor.sum()) if not cmp.empty else fmt(0))
    h.metric("Volume Vendido",   fmt(vnd.valor.sum()) if not vnd.empty else fmt(0))

    # Insights do ativo
    st.markdown("---")
    st.markdown(f"#### 💡 Insights — {sel}")
    pct_dt_a = 100 * dfa.day_trade.sum() / len(dfa)
    st.info(f"**{len(cmp)} compras** e **{len(vnd)} vendas** · "
            f"**{pct_dt_a:.0f}%** das operações foram Day Trade")
    if pm_c > 0 and pm_v > 0:
        diff = pm_v - pm_c
        st.info(f"{'📈' if diff>=0 else '📉'} PM compra: **{fmt(pm_c)}** · "
                f"PM venda: **{fmt(pm_v)}** · Diferença/cota: **{fmt(diff)}**")
    if pa is not None:
        if pa.qtd_atual > 0:
            st.success(f"📦 Posição aberta: **{pa.qtd_atual:.0f} cotas** · "
                       f"Custo médio: **{fmt(pa.custo_medio)}** · "
                       f"Custo total: **{fmt(pa.custo_total)}**")
        else:
            st.info("Posição zerada — sem cotas em carteira.")
        pl = pa.pl_realizado
        if   pl > 0: st.success(f"✅ P&L realizado positivo: **{fmt(pl)}**")
        elif pl < 0: st.error(f"⚠️ P&L realizado negativo: **{fmt(pl)}**")
        else:        st.info("P&L realizado: zero (sem vendas ou break-even).")

    # Tabela
    st.markdown("---")
    st.markdown(f"#### 📄 Operações — {sel}")
    ops_show = dfa[["data","nr_nota","cv","day_trade","quantidade","preco","valor"]].copy()
    ops_show.columns = ["Data","Nota","C/V","DT","Qtd","Preço","Valor R$"]
    ops_show["Preço"]    = ops_show["Preço"].map(fmt)
    ops_show["Valor R$"] = ops_show["Valor R$"].map(fmt)
    ops_show["DT"]       = ops_show["DT"].map({True:"✅",False:"—",1:"✅",0:"—"})
    ops_show["Qtd"]      = ops_show["Qtd"].map(lambda x: f"{x:.0f}")
    st.dataframe(ops_show.sort_values("Data", ascending=False),
                 use_container_width=True, hide_index=True)

# ══════════════════════════════════════
#  TAB 4 — Operações
# ══════════════════════════════════════
with t4:
    st.markdown("## Histórico de Operações")

    f_at = st.multiselect("Ativo:", sorted(df.nome.unique()), placeholder="Todos")
    col1, col2 = st.columns(2)
    with col1: f_cv = st.multiselect("Tipo:", ["Compra","Venda"], placeholder="Todos")
    with col2: f_dt = st.selectbox("Day Trade:", ["Todos","Somente Day Trade","Somente Normal"])

    df_f = df.copy()
    if f_at: df_f = df_f[df_f.nome.isin(f_at)]
    if f_cv: df_f = df_f[df_f.cv.isin(f_cv)]
    if f_dt == "Somente Day Trade": df_f = df_f[df_f.day_trade]
    elif f_dt == "Somente Normal":  df_f = df_f[~df_f.day_trade]

    st.markdown(f"**{len(df_f)} operações** · Volume: **{fmt(df_f.valor.sum())}**")

    show = df_f[["data","nr_nota","nome","ticker","cv","day_trade","quantidade","preco","valor"]].copy()
    show.columns = ["Data","Nota","Ativo","Ticker","C/V","DT","Qtd","Preço","Valor R$"]
    show["Preço"]    = show["Preço"].map(fmt)
    show["Valor R$"] = show["Valor R$"].map(fmt)
    show["DT"]       = show["DT"].map({True:"✅",False:"—",1:"✅",0:"—"})
    show["Qtd"]      = show["Qtd"].map(lambda x: f"{x:.0f}")
    st.dataframe(show.sort_values("Data", ascending=False),
                 use_container_width=True, hide_index=True)

    csv = df_f.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar CSV", csv, "operacoes.csv", "text/csv")
