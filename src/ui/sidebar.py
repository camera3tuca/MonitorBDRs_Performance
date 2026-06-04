"""
Sidebar UI for the MonitorBDRs_Performance application.
"""

import streamlit as st
import pandas as pd
from src.database import get_conn, ja_importada, salvar, registrar
from src.parser import parse_pdf

def render_sidebar():
    """Render the sidebar for the application."""
    with st.sidebar:
        st.markdown("## 📊 Carteira BDR")
        st.markdown("---")
        st.markdown("### 📥 Importar nota Santander")
        up = st.file_uploader("PDF da nota mensal", type=["pdf"])
        if up:
            tmp = f"/tmp/{up.name}"
            with open(tmp, "wb") as f:
                f.write(up.read())
            if ja_importada(up.name):
                st.warning("Nota já importada.")
            else:
                with st.spinner("Processando PDF…"):
                    ops = parse_pdf(tmp, up.name)
                if ops:
                    salvar(ops)
                    registrar(up.name)
                    st.success(f"✅ {len(ops)} operações importadas!")
                    st.rerun()
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
            conn.commit()
            conn.close()
            st.session_state.pop("loaded", None)
            st.rerun()
