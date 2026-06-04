"""
Operations UI for the MonitorBDRs_Performance application.
"""

import streamlit as st
import pandas as pd
from src.utils import fmt

def render_operations(df: pd.DataFrame):
    """Render the operations history tab."""
    st.markdown("## Histórico Completo de Operações")

    f_at = st.multiselect("Ativo:", sorted(df.nome.unique()), placeholder="Todos os ativos")
    col1, col2 = st.columns(2)
    with col1: f_cv = st.multiselect("Tipo:", ["Compra","Venda"], placeholder="Compra e Venda")
    with col2: f_dt = st.selectbox("Day Trade:", ["Todos","Somente Day Trade","Somente Normal"])

    df_f = df.copy()
    if f_at: df_f = df_f[df_f.nome.isin(f_at)]
    if f_cv: df_f = df_f[df_f.cv.isin(f_cv)]
    if f_dt == "Somente Day Trade": df_f = df_f[df_f.day_trade]
    elif f_dt == "Somente Normal":  df_f = df_f[~df_f.day_trade]

    st.markdown(f"**{len(df_f)} operações** · Volume total: **{fmt(df_f.valor.sum())}**")

    show = df_f[["data","nr_nota","nome","ticker","cv","day_trade","quantidade","preco","valor"]].copy()
    show.columns = ["Data","Nota","Ativo","Ticker","C/V","DT","Qtd","Preço","Valor R$"]
    show["Preço"]    = show["Preço"].map(fmt)
    show["Valor R$"] = show["Valor R$"].map(fmt)
    show["DT"]       = show["DT"].map({True:"✅",False:"—",1:"✅",0:"—"})
    show["Qtd"]      = show["Qtd"].map(lambda x: f"{x:.0f}")

    st.dataframe(
        show.sort_values("Data", ascending=False),
        use_container_width=True, hide_index=True
    )

    csv = df_f.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar CSV", csv, "operacoes.csv", "text/csv")
