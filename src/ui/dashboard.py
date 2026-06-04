"""
Dashboard UI for the MonitorBDRs_Performance application.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from src.config import LAYOUT
from src.utils import fmt

def render_dashboard(df: pd.DataFrame, pos: pd.DataFrame, plm: pd.DataFrame):
    """Render the main dashboard."""
    st.markdown("## Dashboard Geral")

    tot_c  = df[df.cv=="Compra"]["valor"].sum()
    tot_v  = df[df.cv=="Venda"]["valor"].sum()
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
    e.metric("⚡ Day Trades",          f"{n_dt}  ({100*n_dt/n_ops:.0f}%)" if n_ops else "0 (0%)")
    f_.metric("📈 P&L Realizado",      fmt(pl_tot),
              delta=f"{pl_tot:+.2f}",
              delta_color="normal" if pl_tot >= 0 else "inverse")

    st.markdown("---")

    # Volume mensal
    st.markdown("#### 📅 Volume mensal")
    fig1 = go.Figure()
    if not plm.empty:
        fig1.add_bar(name="Compras", x=plm.label, y=plm.vol_compra, marker_color="#60a5fa")
        fig1.add_bar(name="Vendas",  x=plm.label, y=plm.vol_venda,  marker_color="#34d399")
    fig1.update_layout(**LAYOUT, barmode="group",
                       xaxis=dict(type="category", title=""),
                       yaxis_title="R$", legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig1, use_container_width=True)

    # Saldo líquido mensal
    st.markdown("#### 💹 Saldo líquido por mês")
    fig2 = go.Figure()
    if not plm.empty:
        fig2.add_trace(go.Bar(
            x=plm.label, y=plm.saldo,
            marker_color=["#34d399" if v >= 0 else "#f87171" for v in plm.saldo],
            text=[fmt(v) for v in plm.saldo], textposition="outside",
        ))
    fig2.update_layout(**LAYOUT, xaxis=dict(type="category", title=""), yaxis_title="R$")
    st.plotly_chart(fig2, use_container_width=True)

    # Top 15 ativos por volume
    st.markdown("#### 🏆 Top 15 ativos por volume")
    vol = (df.groupby("nome")["valor"].sum()
           .sort_values(ascending=True).tail(15).reset_index())
    fig3 = px.bar(vol, x="valor", y="nome", orientation="h",
                  color="valor", color_continuous_scale="Blues",
                  labels={"valor":"Volume R$","nome":""})
    fig3.update_layout(**LAYOUT, coloraxis_showscale=False)
    st.plotly_chart(fig3, use_container_width=True)

    # Pizza top 10
    st.markdown("#### 🥧 Distribuição de volume — Top 10")
    top10 = (df.groupby("ticker")["valor"].sum()
             .sort_values(ascending=False).head(10).reset_index())
    if not top10.empty:
        fig4 = px.pie(top10, names="ticker", values="valor", hole=0.4,
                      color_discrete_sequence=px.colors.qualitative.Set3)
        fig4.update_traces(textposition="inside", textinfo="percent+label")
        fig4.update_layout(**LAYOUT, showlegend=True,
                           legend=dict(orientation="v", x=1.02))
        st.plotly_chart(fig4, use_container_width=True)

    # Operações por dia da semana
    st.markdown("#### 📅 Operações por dia da semana")
    if not df.empty:
        ordem = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
        ptmap = {"Monday":"Seg","Tuesday":"Ter","Wednesday":"Qua","Thursday":"Qui","Friday":"Sex"}
        dow = (df.data_dt.dt.day_name().value_counts()
               .reindex(ordem, fill_value=0).reset_index())
        dow.columns = ["dia","ops"]
        dow["dia_pt"] = dow.dia.map(ptmap)
        fig5 = px.bar(dow, x="dia_pt", y="ops",
                      color="ops", color_continuous_scale="Purples",
                      labels={"dia_pt":"","ops":"Operações"})
        fig5.update_layout(**LAYOUT, coloraxis_showscale=False)
        st.plotly_chart(fig5, use_container_width=True)

    # Insights
    st.markdown("---")
    st.markdown("### 💡 Insights")
    if not df.empty and not pos.empty:
        at_vol    = df.groupby("nome")["valor"].sum()
        melhor_at = pos.loc[pos.pl_realizado.idxmax(), "nome"]
        pior_at   = pos.loc[pos.pl_realizado.idxmin(), "nome"]
        mes_at    = plm.loc[plm.n_ops.idxmax(), "label"] if not plm.empty else "—"

        st.info(f"📊 **Ativo mais negociado:** {at_vol.idxmax()} — {fmt(at_vol.max())} em volume total")
        st.info(f"⚡ **Day trade:** {100*n_dt/n_ops:.1f}% das operações — {n_dt} de {n_ops} negócios")
        st.info(f"📆 **Mês mais ativo:** {mes_at} — {plm.n_ops.max()} operações")
        st.success(f"✅ **Melhor resultado realizado:** {melhor_at} — {fmt(pos.pl_realizado.max())}")
        st.error(f"⚠️ **Pior resultado realizado:** {pior_at} — {fmt(pos.pl_realizado.min())}")
