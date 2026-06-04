"""
Assets UI for the MonitorBDRs_Performance application.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.config import LAYOUT
from src.utils import fmt

def render_assets(pos: pd.DataFrame):
    """Render the assets summary tab."""
    st.markdown("## Resumo por Ativo")

    if pos.empty:
        st.info("Nenhum dado para mostrar.")
        return

    exib = pos.copy()
    exib[""] = exib.pl_realizado.apply(lambda v: "🟢" if v>0 else ("🔴" if v<0 else "⚪"))
    exib["Qtd"] = exib.qtd_atual.map(lambda x: f"{x:.0f}")
    exib["Custo Médio"] = exib.custo_medio.map(fmt)
    exib["Custo Total"] = exib.custo_total.map(fmt)
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
    if not ps.empty:
        figpl = go.Figure(go.Bar(
            x=ps.pl_realizado, y=ps.nome, orientation="h",
            marker_color=["#f87171" if v<0 else "#4ade80" for v in ps.pl_realizado],
            text=[fmt(v) for v in ps.pl_realizado], textposition="outside",
        ))
        figpl.update_layout(**LAYOUT, height=max(420, 30*len(ps)), xaxis_title="R$")
        st.plotly_chart(figpl, use_container_width=True)
