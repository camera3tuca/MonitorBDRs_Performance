"""
Analysis UI for the MonitorBDRs_Performance application.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.config import NOME_TICKER, LAYOUT
from src.utils import fmt

def render_analysis(df: pd.DataFrame, pos: pd.DataFrame):
    """Render the detailed analysis tab."""
    st.markdown("## 🔍 Análise Detalhada por Ativo")

    if df.empty or pos.empty:
        st.info("Nenhum dado para mostrar.")
        return

    nomes_sorted = sorted(df.nome.unique())
    sel = st.selectbox(
        "Selecione o ativo:",
        nomes_sorted,
        format_func=lambda n: f"{n}  ({NOME_TICKER.get(n, '?')})"
    )

    dfa = df[df.nome == sel].sort_values("data_dt")
    row = pos[pos.nome == sel]
    pa  = row.iloc[0] if not row.empty else None

    # ── Métricas do ativo
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

    cmp = dfa[dfa.cv == "Compra"]
    vnd = dfa[dfa.cv == "Venda"]

    # ── Histórico de preços com linha de custo médio
    st.markdown(f"#### 📉 Histórico de preços — {sel}")
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
        figh.add_hline(
            y=pa.custo_medio, line_dash="dash", line_color="#fbbf24",
            annotation_text=f"Custo médio {fmt(pa.custo_medio)}",
            annotation_position="top right"
        )
    figh.update_layout(**LAYOUT, xaxis_title="Data", yaxis_title="R$",
                       legend=dict(orientation="h", y=1.12))
    st.plotly_chart(figh, use_container_width=True)

    # ── Volume por mês
    st.markdown(f"#### 📅 Volume negociado por mês — {sel}")
    vm = dfa.groupby(["mes","mes_label","cv"])["valor"].sum().reset_index()
    if not vm.empty:
        figv = go.Figure()
        for cv_val, cor in [("Compra","#60a5fa"),("Venda","#34d399")]:
            sub = vm[vm.cv == cv_val]
            if not sub.empty:
                figv.add_bar(name=cv_val, x=sub.mes_label, y=sub.valor, marker_color=cor)
        figv.update_layout(**LAYOUT, barmode="group",
                           xaxis=dict(type="category", title=""),
                           yaxis_title="R$", legend=dict(orientation="h", y=1.12))
        st.plotly_chart(figv, use_container_width=True)

    # ── Evolução do preço médio de compra ao longo do tempo
    if len(cmp) > 1:
        st.markdown(f"#### 📊 Evolução do preço médio acumulado — {sel}")
        cmp_sorted = cmp.sort_values("data_dt").copy()
        qtd_acc = custo_acc = 0.0
        pms = []
        for _, r in cmp_sorted.iterrows():
            qtd_acc   += r.quantidade
            custo_acc += r.valor
            pms.append({"data": r.data_dt, "pm": custo_acc / qtd_acc})
        df_pm = pd.DataFrame(pms)
        figpm = go.Figure(go.Scatter(
            x=df_pm.data, y=df_pm.pm, mode="lines+markers",
            line=dict(color="#fbbf24", width=2),
            marker=dict(size=6),
            name="Preço médio acumulado",
            hovertemplate="%{x|%d/%m/%Y}<br>PM: R$ %{y:.2f}<extra></extra>"
        ))
        figpm.update_layout(**LAYOUT, xaxis_title="Data", yaxis_title="R$")
        st.plotly_chart(figpm, use_container_width=True)

    # ── Estatísticas completas
    st.markdown("---")
    st.markdown(f"#### 📊 Estatísticas — {sel}")

    pm_c = cmp.preco.mean() if not cmp.empty else 0
    pm_v = vnd.preco.mean() if not vnd.empty else 0
    pct_dt_a = 100 * dfa.day_trade.sum() / len(dfa) if len(dfa) else 0

    a, b = st.columns(2)
    a.metric("Total de Negócios",  len(dfa))
    b.metric("Day Trades",         f"{int(dfa.day_trade.sum())} ({pct_dt_a:.0f}%)")
    c, d = st.columns(2)
    c.metric("Qtd Total Comprada", f"{cmp.quantidade.sum():.0f}" if not cmp.empty else "0")
    d.metric("Qtd Total Vendida",  f"{vnd.quantidade.sum():.0f}" if not vnd.empty else "0")
    e, f_ = st.columns(2)
    e.metric("Preço Mínimo Compra", fmt(cmp.preco.min()) if not cmp.empty else "—")
    f_.metric("Preço Máximo Compra", fmt(cmp.preco.max()) if not cmp.empty else "—")
    g_, h = st.columns(2)
    g_.metric("Preço Médio Compra", fmt(pm_c) if pm_c else "—")
    h.metric("Preço Médio Venda",   fmt(pm_v) if pm_v else "—")
    i_, j = st.columns(2)
    i_.metric("Volume Comprado", fmt(cmp.valor.sum()) if not cmp.empty else fmt(0))
    j.metric("Volume Vendido",   fmt(vnd.valor.sum()) if not vnd.empty else fmt(0))

    # ── Insights automáticos do ativo
    st.markdown("---")
    st.markdown(f"#### 💡 Insights — {sel}")

    st.info(
        f"**{len(cmp)} compras** e **{len(vnd)} vendas** registradas · "
        f"**{pct_dt_a:.0f}%** das operações foram Day Trade"
    )

    if pm_c > 0 and pm_v > 0:
        diff = pm_v - pm_c
        emoji = "📈" if diff >= 0 else "📉"
        st.info(
            f"{emoji} Preço médio de compra: **{fmt(pm_c)}** · "
            f"Preço médio de venda: **{fmt(pm_v)}** · "
            f"Diferença por cota: **{fmt(diff)}**"
        )

    if pa is not None:
        if pa.qtd_atual > 0:
            st.success(
                f"📦 **Posição aberta:** {pa.qtd_atual:.0f} cotas · "
                f"Custo médio: **{fmt(pa.custo_medio)}** · "
                f"Custo total em carteira: **{fmt(pa.custo_total)}**"
            )
        else:
            st.info("Posição **zerada** — todas as cotas foram vendidas.")

        pl = pa.pl_realizado
        if   pl > 0: st.success(f"✅ P&L realizado positivo: **{fmt(pl)}**")
        elif pl < 0: st.error(f"⚠️ P&L realizado negativo: **{fmt(pl)}**")
        else:        st.info("P&L realizado: zero (sem vendas ou break-even).")

    # ── Tabela de operações do ativo
    st.markdown("---")
    st.markdown(f"#### 📄 Todas as operações — {sel}")

    ops_show = dfa[["data","nr_nota","cv","day_trade","quantidade","preco","valor"]].copy()
    ops_show.columns = ["Data","Nota","C/V","DT","Qtd","Preço","Valor R$"]
    ops_show["Preço"]    = ops_show["Preço"].map(fmt)
    ops_show["Valor R$"] = ops_show["Valor R$"].map(fmt)
    ops_show["DT"]       = ops_show["DT"].map({True:"✅",False:"—",1:"✅",0:"—"})
    ops_show["Qtd"]      = ops_show["Qtd"].map(lambda x: f"{x:.0f}")

    st.dataframe(
        ops_show.sort_values("Data", ascending=False),
        use_container_width=True, hide_index=True
    )

    csv_ativo = dfa.to_csv(index=False).encode("utf-8")
    st.download_button(
        f"⬇️ Exportar operações de {sel}",
        csv_ativo, f"operacoes_{sel.replace(' ','_')}.csv", "text/csv"
    )
