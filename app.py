import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import datetime
import sqlite3
import os
import glob
import altair as alt
import numpy as np

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="MonitorBDRs · Performance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CSS PERSONALIZADO — design escuro/financeiro
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ── Fundo ── */
    .stApp { background-color: #0f1117; color: #e2e8f0; }

    /* ── Conteúdo principal: padding generoso para tablet ── */
    .main .block-container {
        padding: 1.5rem 1.25rem 3rem 1.25rem !important;
        max-width: 100% !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #161b27 !important;
        border-right: 1px solid #1e2535;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span { color: #94a3b8 !important; }

    /* ── KPI cards: altura fixa, valor nunca truncado ── */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a2035 0%, #1e2535 100%);
        border: 1px solid #2a3548;
        border-radius: 14px;
        padding: 18px 16px 14px 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.35);
        min-height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    [data-testid="metric-container"] label {
        color: #64748b !important;
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.09em !important;
        text-transform: uppercase !important;
        white-space: normal !important;
        line-height: 1.3 !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        white-space: normal !important;
        word-break: break-word !important;
        line-height: 1.35 !important;
    }
    [data-testid="stMetricDelta"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.8rem !important;
    }

    /* ── Títulos ── */
    h1 {
        color: #f1f5f9 !important;
        font-weight: 700 !important;
        font-size: 1.7rem !important;
        letter-spacing: -0.02em;
        margin-bottom: 0.25rem !important;
    }
    h2 {
        color: #cbd5e1 !important;
        font-weight: 600 !important;
        font-size: 1.15rem !important;
    }
    h3 { color: #94a3b8 !important; font-weight: 500 !important; }

    /* ── Dataframes ── */
    [data-testid="stDataFrame"] {
        border: 1px solid #1e2535 !important;
        border-radius: 10px !important;
        overflow: hidden;
    }
    /* Fonte maior nas células da tabela */
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
        font-size: 0.82rem !important;
    }

    /* ── Divisores ── */
    hr { border-color: #1e2535 !important; margin: 1rem 0 !important; }

    /* ── Botões ── */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 1.5rem !important;
        width: 100% !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        box-shadow: 0 4px 15px rgba(37,99,235,0.4) !important;
    }

    /* ── Alertas ── */
    .stAlert { border-radius: 10px !important; border-left-width: 4px !important; }

    /* ── Selectbox ── */
    .stSelectbox > div > div {
        background-color: #1a2035 !important;
        border-color: #2a3548 !important;
        color: #e2e8f0 !important;
        font-size: 0.9rem !important;
    }

    /* ── Upload ── */
    [data-testid="stFileUploadDropzone"] {
        background-color: #1a2035 !important;
        border: 2px dashed #2a3548 !important;
        border-radius: 10px !important;
    }

    /* ── Badges ── */
    .badge-pos { color: #10b981; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .badge-neg { color: #ef4444; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .badge-neu { color: #94a3b8; font-weight: 600; font-family: 'JetBrains Mono', monospace; }

    /* ── Caption / helper text ── */
    [data-testid="stCaptionContainer"] p {
        font-size: 0.78rem !important;
        color: #64748b !important;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect('carteira.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            cv TEXT,
            ativo TEXT,
            quantidade INTEGER,
            preco REAL,
            valor REAL,
            dc TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS arquivos_processados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT UNIQUE,
            data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn


conn = init_db()


# ─────────────────────────────────────────────
# PARSE DE PDF
# ─────────────────────────────────────────────
def parse_pdf(file_obj):
    trades = []
    current_date = None

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')
            for line in lines:
                date_match = re.match(r"\d+\s+\d+\s+(\d{2}/\d{2}/\d{4})", line)
                if date_match:
                    current_date = date_match.group(1)

                match = re.search(
                    r"LISTADO[CV]\s+(?:VISTA|FRACIONARIO)\s+(.*?)\s+(?:@|D|#|\s)*\s+([\d\.]+)\s+([\d\,]+)\s+([\d\.,]+)\s+(D|C)$",
                    line
                )
                if match:
                    cv_match = re.search(r"LISTADO(C|V)", line)
                    cv = cv_match.group(1) if cv_match else ""
                    name = match.group(1).strip()
                    qty = match.group(2).replace('.', '')
                    price = match.group(3).replace('.', '').replace(',', '.')
                    value = match.group(4).replace('.', '').replace(',', '.')
                    dc = match.group(5)

                    trades.append({
                        "data": current_date,
                        "cv": cv,
                        "ativo": name,
                        "quantidade": int(qty),
                        "preco": float(price),
                        "valor": float(value),
                        "dc": dc
                    })
    return trades


def save_to_db(trades, conn):
    c = conn.cursor()
    new_trades = 0
    for trade in trades:
        c.execute(
            'SELECT COUNT(*) FROM operacoes WHERE data=? AND cv=? AND ativo=? AND quantidade=? AND preco=?',
            (trade['data'], trade['cv'], trade['ativo'], trade['quantidade'], trade['preco'])
        )
        if c.fetchone()[0] == 0:
            c.execute(
                'INSERT INTO operacoes (data, cv, ativo, quantidade, preco, valor, dc) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (trade['data'], trade['cv'], trade['ativo'], trade['quantidade'], trade['preco'], trade['valor'], trade['dc'])
            )
            new_trades += 1
    conn.commit()
    return new_trades


def processar_notas_iniciais(conn):
    os.makedirs('notas_pdf', exist_ok=True)
    c = conn.cursor()
    total_novas = 0
    for caminho_arquivo in glob.glob('notas_pdf/*.pdf'):
        nome_arquivo = os.path.basename(caminho_arquivo)
        c.execute('SELECT COUNT(*) FROM arquivos_processados WHERE nome_arquivo=?', (nome_arquivo,))
        if c.fetchone()[0] == 0:
            trades = parse_pdf(caminho_arquivo)
            total_novas += save_to_db(trades, conn)
            c.execute('INSERT OR IGNORE INTO arquivos_processados (nome_arquivo) VALUES (?)', (nome_arquivo,))
            conn.commit()
    return total_novas


processar_notas_iniciais(conn)


def load_data(conn):
    return pd.read_sql_query("SELECT * FROM operacoes ORDER BY data ASC", conn)


# ─────────────────────────────────────────────
# ENGINE DE CÁLCULO DE PERFORMANCE
# ─────────────────────────────────────────────
def calculate_performance(df):
    """
    Calcula carteira atual, histórico de trades fechados e resultado mensal.
    Retorna: df_carteira, df_historico, df_mensal
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = df.copy()
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
    df = df.dropna(subset=['data']).sort_values('data')

    carteira = {}   # {ativo: {qtde, preco_medio, custo_total}}
    historico = []

    for _, row in df.iterrows():
        ativo = row['ativo']
        qtde = row['quantidade']
        preco = row['preco']

        if ativo not in carteira:
            carteira[ativo] = {'qtde': 0, 'preco_medio': 0.0, 'custo_total': 0.0}

        if row['cv'] == 'C':
            pos = carteira[ativo]
            nova_qtde = pos['qtde'] + qtde
            novo_custo = pos['custo_total'] + (qtde * preco)
            pos['qtde'] = nova_qtde
            pos['custo_total'] = novo_custo
            pos['preco_medio'] = novo_custo / nova_qtde if nova_qtde > 0 else 0.0

        elif row['cv'] == 'V':
            pos = carteira[ativo]
            if pos['qtde'] > 0:
                qtde_valida = min(pos['qtde'], qtde)
                pm = pos['preco_medio']
                lucro = (preco - pm) * qtde_valida
                retorno_pct = ((preco / pm) - 1) * 100 if pm > 0 else 0.0

                historico.append({
                    'data': row['data'],
                    'mes_ano': row['data'].strftime('%Y-%m'),
                    'ano': row['data'].year,
                    'ativo': ativo,
                    'qtde_vendida': qtde_valida,
                    'preco_venda': preco,
                    'preco_medio_compra': pm,
                    'resultado': lucro,
                    'retorno_pct': retorno_pct,
                    'custo_base': pm * qtde_valida,
                })
                # Deduz posição
                pos['qtde'] -= qtde_valida
                pos['custo_total'] = pos['preco_medio'] * pos['qtde']

    # Monta carteira atual
    carteira_atual = [
        {
            'Ativo': ativo,
            'Quantidade': d['qtde'],
            'Preço Médio': d['preco_medio'],
            'Valor Investido': d['qtde'] * d['preco_medio'],
        }
        for ativo, d in carteira.items() if d['qtde'] > 0
    ]
    df_carteira = pd.DataFrame(carteira_atual)
    df_historico = pd.DataFrame(historico)

    df_mensal = pd.DataFrame()
    if not df_historico.empty:
        df_mensal = (
            df_historico.groupby('mes_ano')
            .agg(
                resultado=('resultado', 'sum'),
                trades=('resultado', 'count'),
                win_rate=('resultado', lambda x: (x > 0).mean() * 100)
            )
            .reset_index()
        )

    return df_carteira, df_historico, df_mensal


# ─────────────────────────────────────────────
# MÉTRICAS AVANÇADAS
# ─────────────────────────────────────────────
def calc_advanced_metrics(df_historico: pd.DataFrame) -> dict:
    """Calcula métricas quantitativas de performance de trading."""
    if df_historico.empty:
        return {}

    resultados = df_historico['resultado']
    retornos = df_historico['retorno_pct']

    lucros = resultados[resultados > 0]
    perdas = resultados[resultados < 0]

    # Payoff Ratio (média de ganhos / média de perdas absolutas)
    payoff = (lucros.mean() / abs(perdas.mean())) if (not lucros.empty and not perdas.empty) else 0.0

    # Fator de Lucro: soma ganhos / soma perdas absolutas
    fator_lucro = (lucros.sum() / abs(perdas.sum())) if not perdas.empty else float('inf')

    # Sequências
    max_seq_win = max_streak(resultados > 0)
    max_seq_loss = max_streak(resultados <= 0)

    # Curva de capital acumulada (para drawdown)
    curva = resultados.cumsum()
    peak = curva.cummax()
    drawdown = curva - peak
    max_dd = drawdown.min()
    max_dd_pct = (drawdown / peak.replace(0, np.nan)).min() * 100 if peak.max() > 0 else 0.0

    # Sharpe simplificado (retorno médio / desvio padrão dos retornos)
    sharpe = (retornos.mean() / retornos.std()) if retornos.std() > 0 else 0.0

    # Expectativa matemática (em R$)
    win_rate = (resultados > 0).mean()
    loss_rate = 1 - win_rate
    avg_win = lucros.mean() if not lucros.empty else 0.0
    avg_loss = perdas.mean() if not perdas.empty else 0.0
    expectativa = (win_rate * avg_win) + (loss_rate * avg_loss)

    # Calmar Ratio = retorno anualizado / max drawdown absoluto
    calmar = (resultados.sum() / abs(max_dd)) if max_dd != 0 else 0.0

    return {
        'win_rate': win_rate * 100,
        'payoff_ratio': payoff,
        'fator_lucro': fator_lucro,
        'expectativa': expectativa,
        'sharpe': sharpe,
        'calmar': calmar,
        'max_drawdown': max_dd,
        'max_drawdown_pct': max_dd_pct,
        'max_seq_win': max_seq_win,
        'max_seq_loss': max_seq_loss,
        'total_trades': len(resultados),
        'trades_lucro': len(lucros),
        'trades_perda': len(perdas),
        'maior_lucro': lucros.max() if not lucros.empty else 0.0,
        'maior_perda': perdas.min() if not perdas.empty else 0.0,
        'media_lucro': avg_win,
        'media_perda': avg_loss,
        'lucro_bruto_total': resultados.sum(),
        'retorno_medio_pct': retornos.mean(),
        'retorno_melhor_pct': retornos.max(),
        'retorno_pior_pct': retornos.min(),
        'curva_capital': curva,
        'drawdown_series': drawdown,
    }


def max_streak(bool_series: pd.Series) -> int:
    """Maior sequência consecutiva de True."""
    max_s = cur = 0
    for v in bool_series:
        if v:
            cur += 1
            max_s = max(max_s, cur)
        else:
            cur = 0
    return max_s


# ─────────────────────────────────────────────
# HELPERS DE FORMATAÇÃO
# ─────────────────────────────────────────────
def fmt_brl(value: float) -> str:
    """Formata número como Real Brasileiro."""
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def color_result(val):
    """Aplica cor em células de resultado."""
    try:
        v = float(val)
        color = '#10b981' if v > 0 else ('#ef4444' if v < 0 else '#94a3b8')
        return f'color: {color}; font-family: JetBrains Mono, monospace; font-weight: 600'
    except Exception:
        return ''


# ─────────────────────────────────────────────
# TEMA PARA ALTAIR
# ─────────────────────────────────────────────
ALTAIR_THEME = {
    "config": {
        "background": "transparent",
        "view": {"stroke": "transparent"},
        "axis": {
            "domainColor": "#2a3548",
            "gridColor": "#1e2535",
            "labelColor": "#64748b",
            "titleColor": "#94a3b8",
            "labelFont": "Inter",
            "titleFont": "Inter",
        },
        "legend": {
            "labelColor": "#94a3b8",
            "titleColor": "#64748b",
            "labelFont": "Inter",
        },
        "title": {"color": "#cbd5e1", "font": "Inter"},
    }
}

alt.themes.register("dark_finance", lambda: ALTAIR_THEME)
alt.themes.enable("dark_finance")


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 MonitorBDRs")
    st.markdown("<hr>", unsafe_allow_html=True)

    menu = st.selectbox(
        "Navegação",
        [
            "🏠 Visão Geral",
            "📥 Importar Notas",
            "💼 Carteira Atual",
            "📈 Performance Mensal",
            "🔍 Análise Individual",
            "🧮 Métricas Avançadas",
            "📋 Histórico de Operações",
        ],
        label_visibility="collapsed",
    )

    st.markdown("<hr>", unsafe_allow_html=True)

    # Resumo rápido na sidebar
    df_sidebar = load_data(conn)
    if not df_sidebar.empty:
        df_cart_sb, df_hist_sb, _ = calculate_performance(df_sidebar)
        n_ativos = len(df_cart_sb) if not df_cart_sb.empty else 0
        n_ops = len(df_sidebar)
        st.markdown(f"**{n_ops}** operações · **{n_ativos}** ativos")

        if not df_hist_sb.empty:
            total_resultado = df_hist_sb['resultado'].sum()
            cor = "badge-pos" if total_resultado >= 0 else "badge-neg"
            st.markdown(
                f'Resultado acumulado<br><span class="{cor}">{fmt_brl(total_resultado)}</span>',
                unsafe_allow_html=True
            )
    else:
        st.caption("Nenhum dado carregado.")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.caption("⚠️ Valores brutos, sem taxas/impostos.")


# ─────────────────────────────────────────────
# PÁGINA: VISÃO GERAL
# ─────────────────────────────────────────────
if menu == "🏠 Visão Geral":
    st.title("Visão Geral do Portfólio")

    df = load_data(conn)
    if df.empty:
        st.info("O banco de dados está vazio. Vá em **Importar Notas** para começar.")
    else:
        df_carteira, df_historico, df_mensal = calculate_performance(df)
        metrics = calc_advanced_metrics(df_historico)

        total_investido = df_carteira['Valor Investido'].sum() if not df_carteira.empty else 0.0
        ativos_diferentes = len(df_carteira) if not df_carteira.empty else 0
        lucro_total = metrics.get('lucro_bruto_total', 0.0)
        win_rate = metrics.get('win_rate', 0.0)
        payoff = metrics.get('payoff_ratio', 0.0)
        expectativa = metrics.get('expectativa', 0.0)

        # ── KPIs: 2 linhas de 3 para tablet ──
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Valor em Carteira", fmt_brl(total_investido))
        c2.metric(
            "📊 Resultado Acumulado",
            fmt_brl(lucro_total),
            delta=f"{(lucro_total / total_investido * 100):+.1f}%" if total_investido > 0 else None
        )
        c3.metric("🎯 Ativos em Carteira", str(ativos_diferentes))
        c4, c5, c6 = st.columns(3)
        c4.metric("✅ Win Rate", f"{win_rate:.1f}%")
        c5.metric("⚖️ Payoff Ratio", f"{payoff:.2f}×")
        c6.metric("🎲 Expectativa/Trade", fmt_brl(expectativa))

        st.divider()

        # ── Gráfico de Pizza / Rosca da Carteira ──
        st.subheader("Alocação da Carteira")
        if not df_carteira.empty:
            df_chart = df_carteira.sort_values('Valor Investido', ascending=False).copy()
            if len(df_chart) > 12:
                top = df_chart.head(12)
                outros = pd.DataFrame([{
                    'Ativo': 'OUTROS', 'Quantidade': 0,
                    'Preço Médio': 0,
                    'Valor Investido': df_chart.iloc[12:]['Valor Investido'].sum()
                }])
                df_chart = pd.concat([top, outros], ignore_index=True)

            pie = alt.Chart(df_chart).mark_arc(innerRadius=70, outerRadius=150).encode(
                theta=alt.Theta('Valor Investido:Q'),
                color=alt.Color(
                    'Ativo:N',
                    scale=alt.Scale(scheme='tableau20'),
                    legend=alt.Legend(orient='bottom', labelLimit=160, columns=3)
                ),
                tooltip=[
                    alt.Tooltip('Ativo:N', title='Ativo'),
                    alt.Tooltip('Valor Investido:Q', title='Valor (R$)', format=',.2f'),
                ]
            ).properties(height=380)
            st.altair_chart(pie, use_container_width=True)
        else:
            st.info("Carteira vazia.")

        # ── Gráfico de Resultado Mensal ──
        st.subheader("Resultado por Mês")
        if not df_mensal.empty:
            df_mensal_chart = df_mensal.copy()
            df_mensal_chart['cor'] = df_mensal_chart['resultado'].apply(
                lambda x: '#10b981' if x >= 0 else '#ef4444'
            )
            bars = alt.Chart(df_mensal_chart).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X('mes_ano:N', title='Mês', axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('resultado:Q', title='Resultado (R$)'),
                color=alt.Color('cor:N', scale=None, legend=None),
                tooltip=[
                    alt.Tooltip('mes_ano:N', title='Mês'),
                    alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                    alt.Tooltip('trades:Q', title='Trades'),
                    alt.Tooltip('win_rate:Q', title='Win Rate (%)', format='.1f'),
                ]
            ).properties(height=300)
            st.altair_chart(bars, use_container_width=True)
        else:
            st.info("Nenhuma venda registrada.")

        # ── Curva de Capital ──
        if metrics.get('curva_capital') is not None and not metrics['curva_capital'].empty:
            st.divider()
            st.subheader("Curva de Capital Acumulada")
            curva = metrics['curva_capital'].reset_index(drop=True)
            df_curva = pd.DataFrame({
                'trade_n': range(1, len(curva) + 1),
                'capital': curva.values
            })
            line = alt.Chart(df_curva).mark_line(
                color='#3b82f6', strokeWidth=2
            ).encode(
                x=alt.X('trade_n:Q', title='Nº do Trade'),
                y=alt.Y('capital:Q', title='Resultado Acumulado (R$)'),
                tooltip=[
                    alt.Tooltip('trade_n:Q', title='Trade #'),
                    alt.Tooltip('capital:Q', title='Acumulado (R$)', format=',.2f'),
                ]
            )
            area = alt.Chart(df_curva).mark_area(
                color='#3b82f6', opacity=0.15
            ).encode(
                x='trade_n:Q',
                y='capital:Q'
            )
            zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='#2a3548', strokeDash=[4, 4]
            ).encode(y='y:Q')
            st.altair_chart((area + line + zero).properties(height=240), use_container_width=True)


# ─────────────────────────────────────────────
# PÁGINA: IMPORTAR NOTAS
# ─────────────────────────────────────────────
elif menu == "📥 Importar Notas":
    st.title("Importar Notas de Corretagem")
    st.markdown("Faça upload dos PDFs gerados pela sua corretora. Operações duplicadas são ignoradas automaticamente.")

    uploaded_files = st.file_uploader(
        "Selecione os PDFs das notas de corretagem",
        accept_multiple_files=True,
        type=['pdf']
    )

    processar = st.button("⚙️ Processar Notas", use_container_width=True)

    if processar:
        if uploaded_files:
            os.makedirs('notas_pdf', exist_ok=True)
            c = conn.cursor()
            total_novas = 0
            resultados_upload = []

            progress = st.progress(0)
            for i, file in enumerate(uploaded_files):
                nome_arquivo = file.name
                file_path = os.path.join('notas_pdf', nome_arquivo)

                with open(file_path, "wb") as f:
                    f.write(file.getbuffer())

                c.execute('SELECT COUNT(*) FROM arquivos_processados WHERE nome_arquivo=?', (nome_arquivo,))
                ja_processado = c.fetchone()[0] > 0

                if not ja_processado:
                    trades = parse_pdf(file_path)
                    novas = save_to_db(trades, conn)
                    total_novas += novas
                    c.execute('INSERT OR IGNORE INTO arquivos_processados (nome_arquivo) VALUES (?)', (nome_arquivo,))
                    conn.commit()
                    resultados_upload.append((nome_arquivo, novas, "✅ Importado"))
                else:
                    resultados_upload.append((nome_arquivo, 0, "⏭️ Já processado"))

                progress.progress((i + 1) / len(uploaded_files))

            st.success(f"Concluído! **{total_novas}** novas operações importadas.")

            df_res = pd.DataFrame(resultados_upload, columns=['Arquivo', 'Operações importadas', 'Status'])
            st.dataframe(df_res, use_container_width=True, hide_index=True)
        else:
            st.warning("Selecione pelo menos um arquivo PDF.")

    # Arquivos já processados
    st.divider()
    st.subheader("Notas já processadas")
    df_arqs = pd.read_sql_query(
        "SELECT nome_arquivo as 'Arquivo', data_processamento as 'Processado em' FROM arquivos_processados ORDER BY data_processamento DESC",
        conn
    )
    if not df_arqs.empty:
        st.dataframe(df_arqs, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma nota processada ainda.")


# ─────────────────────────────────────────────
# PÁGINA: CARTEIRA ATUAL
# ─────────────────────────────────────────────
elif menu == "💼 Carteira Atual":
    st.title("Carteira Atual")

    df = load_data(conn)
    df_carteira, _, _ = calculate_performance(df)

    if not df_carteira.empty:
        total_investido = df_carteira['Valor Investido'].sum()

        c1, c2 = st.columns(2)
        c1.metric("Total Alocado", fmt_brl(total_investido))
        c2.metric("Ativos Diferentes", str(len(df_carteira)))
        st.metric("Maior Posição", df_carteira.loc[df_carteira['Valor Investido'].idxmax(), 'Ativo'])

        st.divider()

        # Adiciona % do portfólio
        df_view = df_carteira.copy().sort_values('Valor Investido', ascending=False)
        df_view['% Carteira'] = (df_view['Valor Investido'] / total_investido * 100).round(2)

        st.dataframe(
            df_view.style
                .format({
                    'Preço Médio': 'R$ {:.4f}',
                    'Valor Investido': 'R$ {:,.2f}',
                    '% Carteira': '{:.2f}%'
                })
                ,
            use_container_width=True,
            hide_index=True
        )

        # Gráfico de barras horizontais
        st.subheader("Concentração por Ativo")
        bar_h = alt.Chart(df_view.head(20)).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
            y=alt.Y('Ativo:N', sort='-x', title=None),
            x=alt.X('Valor Investido:Q', title='Valor Investido (R$)'),
            color=alt.Color('% Carteira:Q', scale=alt.Scale(scheme='blues'), legend=None),
            tooltip=[
                alt.Tooltip('Ativo:N'),
                alt.Tooltip('Quantidade:Q'),
                alt.Tooltip('Preço Médio:Q', format='.4f'),
                alt.Tooltip('Valor Investido:Q', format=',.2f'),
                alt.Tooltip('% Carteira:Q', format='.2f'),
            ]
        ).properties(height=max(200, len(df_view.head(20)) * 28))
        st.altair_chart(bar_h, use_container_width=True)
    else:
        st.info("Sua carteira está vazia ou nenhum dado foi carregado.")


# ─────────────────────────────────────────────
# PÁGINA: PERFORMANCE MENSAL
# ─────────────────────────────────────────────
elif menu == "📈 Performance Mensal":
    st.title("Performance Mensal")
    st.caption("Valores brutos — taxas de corretagem, emolumentos B3 e IRRF não estão deduzidos.")

    df = load_data(conn)
    _, df_historico, df_mensal = calculate_performance(df)

    if not df_mensal.empty:
        # ── KPIs mensais ──
        meses_positivos = (df_mensal['resultado'] > 0).sum()
        meses_negativos = (df_mensal['resultado'] <= 0).sum()
        melhor_mes = df_mensal.loc[df_mensal['resultado'].idxmax(), 'mes_ano']
        melhor_valor = df_mensal['resultado'].max()
        pior_mes = df_mensal.loc[df_mensal['resultado'].idxmin(), 'mes_ano']
        pior_valor = df_mensal['resultado'].min()

        c1, c2 = st.columns(2)
        c1.metric("Meses Positivos", f"{meses_positivos}")
        c2.metric("Meses Negativos", f"{meses_negativos}")
        c3, c4 = st.columns(2)
        c3.metric("Melhor Mês", melhor_mes, delta=fmt_brl(melhor_valor))
        c4.metric("Pior Mês", pior_mes, delta=fmt_brl(pior_valor))

        st.divider()

        # ── Gráfico de barras mensais ──
        df_chart = df_mensal.copy()
        df_chart['cor'] = df_chart['resultado'].apply(lambda x: '#10b981' if x >= 0 else '#ef4444')

        bars = alt.Chart(df_chart).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X('mes_ano:N', title='Mês/Ano', sort=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('resultado:Q', title='Resultado Bruto (R$)'),
            color=alt.Color('cor:N', scale=None, legend=None),
            tooltip=[
                alt.Tooltip('mes_ano:N', title='Período'),
                alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                alt.Tooltip('trades:Q', title='Trades'),
                alt.Tooltip('win_rate:Q', title='Win Rate (%)', format='.1f'),
            ]
        ).properties(height=280)
        st.altair_chart(bars, use_container_width=True)

        # ── Tabela mensal ──
        df_mensal_display = df_mensal.copy()
        df_mensal_display.columns = ['Mês/Ano', 'Resultado (R$)', 'Trades', 'Win Rate (%)']
        st.dataframe(
            df_mensal_display.style
                .map(color_result, subset=['Resultado (R$)'])
                .format({'Resultado (R$)': 'R$ {:,.2f}', 'Win Rate (%)': '{:.1f}%'}),
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # ── Análise de trades ──
        st.subheader("Detalhamento dos Trades")
        lucros = df_historico[df_historico['resultado'] > 0]['resultado']
        perdas = df_historico[df_historico['resultado'] < 0]['resultado']

        c1, c2 = st.columns(2)
        c1.metric("Maior Ganho", fmt_brl(lucros.max() if not lucros.empty else 0))
        c2.metric("Maior Perda", fmt_brl(perdas.min() if not perdas.empty else 0))
        c3, c4 = st.columns(2)
        c3.metric("Média Ganhos", fmt_brl(lucros.mean() if not lucros.empty else 0))
        c4.metric("Média Perdas", fmt_brl(perdas.mean() if not perdas.empty else 0))

        total = df_mensal['resultado'].sum()
        if total > 0:
            st.success(f"**Resultado Acumulado Total: {fmt_brl(total)}**")
        else:
            st.error(f"**Resultado Acumulado Total: {fmt_brl(total)}**")

        # Scatter: retorno % por trade
        if not df_historico.empty:
            st.subheader("Distribuição de Retorno por Trade (%)")
            df_scatter = df_historico.copy()
            df_scatter['cor'] = df_scatter['resultado'].apply(lambda x: '#10b981' if x >= 0 else '#ef4444')
            df_scatter['trade_n'] = range(1, len(df_scatter) + 1)

            scatter = alt.Chart(df_scatter).mark_circle(size=60, opacity=0.7).encode(
                x=alt.X('trade_n:Q', title='Trade #'),
                y=alt.Y('retorno_pct:Q', title='Retorno (%)'),
                color=alt.Color('cor:N', scale=None, legend=None),
                tooltip=[
                    alt.Tooltip('ativo:N', title='Ativo'),
                    alt.Tooltip('data:T', title='Data', format='%d/%m/%Y'),
                    alt.Tooltip('retorno_pct:Q', title='Retorno (%)', format='.2f'),
                    alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                ]
            ).properties(height=240)
            zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='#2a3548', strokeDash=[4, 4]
            ).encode(y='y:Q')
            st.altair_chart((scatter + zero_line), use_container_width=True)
    else:
        st.info("Nenhuma operação de venda registrada para calcular performance.")


# ─────────────────────────────────────────────
# PÁGINA: ANÁLISE INDIVIDUAL
# ─────────────────────────────────────────────
elif menu == "🔍 Análise Individual":
    st.title("Análise Individual de BDR")

    df = load_data(conn)
    if df.empty:
        st.info("O banco de dados está vazio.")
    else:
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
        ativos_disponiveis = sorted(df['ativo'].dropna().unique().tolist())

        ativo_selecionado = st.selectbox("Ativo / BDR", ativos_disponiveis)
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            data_inicio = st.date_input("De", value=df['data'].min().date())
        with col_d2:
            data_fim = st.date_input("Até", value=df['data'].max().date())

        df_ativo = df[df['ativo'] == ativo_selecionado].copy()
        df_carteira_bdr, df_historico_bdr, df_mensal_bdr = calculate_performance(df_ativo)
        metrics_bdr = calc_advanced_metrics(df_historico_bdr)

        # Filtra exibição pelo período
        df_hist_filtrado = pd.DataFrame()
        if not df_historico_bdr.empty:
            df_hist_filtrado = df_historico_bdr[
                (df_historico_bdr['data'].dt.date >= data_inicio) &
                (df_historico_bdr['data'].dt.date <= data_fim)
            ]

        # ── KPIs do ativo ──
        st.divider()
        total_trades_bdr = metrics_bdr.get('total_trades', 0)
        lucro_bdr = df_hist_filtrado['resultado'].sum() if not df_hist_filtrado.empty else 0.0
        win_bdr = (df_hist_filtrado['resultado'] > 0).mean() * 100 if not df_hist_filtrado.empty else 0.0
        payoff_bdr = metrics_bdr.get('payoff_ratio', 0.0)

        c1, c2 = st.columns(2)
        c1.metric("Resultado no Período", fmt_brl(lucro_bdr))
        c2.metric("Trades no Período", str(len(df_hist_filtrado)))
        c3, c4 = st.columns(2)
        c3.metric("Win Rate", f"{win_bdr:.1f}%")
        c4.metric("Payoff Ratio", f"{payoff_bdr:.2f}×")

        st.divider()
        st.subheader("Posição Atual")
        if not df_carteira_bdr.empty:
            df_pos = df_carteira_bdr[df_carteira_bdr['Ativo'] == ativo_selecionado]
            if not df_pos.empty:
                row_p = df_pos.iloc[0]
                cm1, cm2, cm3 = st.columns(3)
                cm1.metric("Qtde em Carteira", int(row_p['Quantidade']))
                cm2.metric("Preço Médio", fmt_brl(row_p['Preço Médio']))
                cm3.metric("Custo Total", fmt_brl(row_p['Valor Investido']))
            else:
                st.info("Sem posição aberta.")
        else:
            st.info("Sem posição aberta.")

        st.subheader("Trades Fechados no Período")
        if not df_hist_filtrado.empty:
            df_show = df_hist_filtrado[['data', 'qtde_vendida', 'preco_medio_compra', 'preco_venda', 'resultado', 'retorno_pct']].copy()
            df_show['data'] = df_show['data'].dt.strftime('%d/%m/%Y')
            df_show.columns = ['Data', 'Qtde', 'PM Compra', 'Preço Venda', 'Resultado (R$)', 'Retorno (%)']
            st.dataframe(
                df_show.style
                    .map(color_result, subset=['Resultado (R$)'])
                    .format({
                        'PM Compra': 'R$ {:.4f}',
                        'Preço Venda': 'R$ {:.4f}',
                        'Resultado (R$)': 'R$ {:,.2f}',
                        'Retorno (%)': '{:+.2f}%'
                    }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhuma venda no período selecionado.")

        # ── Resultado mensal do ativo ──
        if not df_mensal_bdr.empty:
            st.subheader(f"Resultado Mensal — {ativo_selecionado}")
            df_m_chart = df_mensal_bdr.copy()
            df_m_chart['cor'] = df_m_chart['resultado'].apply(lambda x: '#10b981' if x >= 0 else '#ef4444')
            bars_bdr = alt.Chart(df_m_chart).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X('mes_ano:N', sort=None, title='Mês', axis=alt.Axis(labelAngle=-30)),
                y=alt.Y('resultado:Q', title='Resultado (R$)'),
                color=alt.Color('cor:N', scale=None, legend=None),
                tooltip=[
                    alt.Tooltip('mes_ano:N', title='Mês'),
                    alt.Tooltip('resultado:Q', title='Resultado (R$)', format=',.2f'),
                ]
            ).properties(height=220)
            st.altair_chart(bars_bdr, use_container_width=True)

        # ── Todas operações do ativo no período ──
        st.subheader(f"Todas as Operações de {ativo_selecionado}")
        df_ops = df_ativo[
            (df_ativo['data'].dt.date >= data_inicio) &
            (df_ativo['data'].dt.date <= data_fim)
        ].copy()
        if not df_ops.empty:
            df_ops['data'] = df_ops['data'].dt.strftime('%d/%m/%Y')
            df_ops['cv_label'] = df_ops['cv'].map({'C': '🟢 Compra', 'V': '🔴 Venda'})
            st.dataframe(
                df_ops[['data', 'cv_label', 'quantidade', 'preco', 'valor']].rename(columns={
                    'data': 'Data', 'cv_label': 'Tipo', 'quantidade': 'Qtde',
                    'preco': 'Preço (R$)', 'valor': 'Valor (R$)'
                }).style.format({'Preço (R$)': 'R$ {:.4f}', 'Valor (R$)': 'R$ {:,.2f}'}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhuma operação no período selecionado.")


# ─────────────────────────────────────────────
# PÁGINA: MÉTRICAS AVANÇADAS
# ─────────────────────────────────────────────
elif menu == "🧮 Métricas Avançadas":
    st.title("Métricas Avançadas de Performance")
    st.caption("Análise quantitativa do seu estilo e histórico de trading. Valores brutos sem taxas.")

    df = load_data(conn)
    _, df_historico, _ = calculate_performance(df)
    metrics = calc_advanced_metrics(df_historico)

    if not metrics:
        st.info("Nenhuma operação de venda encontrada para calcular métricas.")
    else:
        # ── Bloco 1: Estatísticas Gerais ──
        st.subheader("📌 Estatísticas Gerais")
        c1, c2 = st.columns(2)
        c1.metric("Total de Trades", str(metrics['total_trades']))
        c2.metric("Win Rate", f"{metrics['win_rate']:.2f}%")
        c3, c4 = st.columns(2)
        c3.metric("Trades Vencedores", str(metrics['trades_lucro']))
        c4.metric("Trades Perdedores", str(metrics['trades_perda']))

        st.divider()

        # ── Bloco 2: Métricas de Risco/Retorno ──
        st.subheader("📐 Risco e Retorno")
        c1, c2 = st.columns(2)
        c1.metric("Fator de Lucro", f"{metrics['fator_lucro']:.2f}×",
                  help="Soma dos ganhos / soma das perdas. >1.5 é saudável.")
        c2.metric("Payoff Ratio", f"{metrics['payoff_ratio']:.2f}×",
                  help="Média dos ganhos / média das perdas. >1.0 é positivo.")
        c3, c4 = st.columns(2)
        c3.metric("Expectativa/Trade", fmt_brl(metrics['expectativa']),
                  help="Valor esperado por trade com base no histórico.")
        c4.metric("Sharpe Simplificado", f"{metrics['sharpe']:.3f}",
                  help="Média dos retornos % / desvio padrão. >0 é positivo.")

        st.divider()

        # ── Bloco 3: Drawdown ──
        st.subheader("📉 Drawdown")
        c1, c2, c3 = st.columns(3)
        c1.metric("Máximo Drawdown (R$)", fmt_brl(metrics['max_drawdown']))
        c2.metric("Máximo Drawdown (%)", f"{metrics['max_drawdown_pct']:.2f}%")
        c3.metric("Calmar Ratio", f"{metrics['calmar']:.2f}×",
                  help="Lucro total / |Max Drawdown|. >1 é bom.")

        # Gráfico de Drawdown
        if metrics.get('drawdown_series') is not None and not metrics['drawdown_series'].empty:
            dd = metrics['drawdown_series'].reset_index(drop=True)
            df_dd = pd.DataFrame({'trade_n': range(1, len(dd) + 1), 'drawdown': dd.values})
            dd_area = alt.Chart(df_dd).mark_area(
                color='#ef4444', opacity=0.3, line={'color': '#ef4444', 'strokeWidth': 1.5}
            ).encode(
                x=alt.X('trade_n:Q', title='Trade #'),
                y=alt.Y('drawdown:Q', title='Drawdown (R$)'),
                tooltip=[
                    alt.Tooltip('trade_n:Q', title='Trade #'),
                    alt.Tooltip('drawdown:Q', title='Drawdown (R$)', format=',.2f')
                ]
            ).properties(height=200, title='Série de Drawdown')
            st.altair_chart(dd_area, use_container_width=True)

        st.divider()

        # ── Bloco 4: Sequências & Extremos ──
        st.subheader("🔢 Sequências & Extremos")
        c1, c2 = st.columns(2)
        c1.metric("Maior Seq. de Ganhos", f"{metrics['max_seq_win']} trades")
        c2.metric("Maior Seq. de Perdas", f"{metrics['max_seq_loss']} trades")
        c3, c4 = st.columns(2)
        c3.metric("Maior Ganho (Trade)", fmt_brl(metrics['maior_lucro']))
        c4.metric("Maior Perda (Trade)", fmt_brl(metrics['maior_perda']))

        st.divider()

        # ── Bloco 5: Distribuição dos retornos ──
        st.subheader("📊 Distribuição dos Retornos (%)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Retorno Médio", f"{metrics['retorno_medio_pct']:+.2f}%")
        c2.metric("Melhor Trade", f"{metrics['retorno_melhor_pct']:+.2f}%")
        c3.metric("Pior Trade", f"{metrics['retorno_pior_pct']:+.2f}%")

        if not df_historico.empty:
            hist = alt.Chart(df_historico).mark_bar(
                cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color='#3b82f6', opacity=0.8
            ).encode(
                x=alt.X('retorno_pct:Q', bin=alt.Bin(maxbins=30), title='Retorno (%)'),
                y=alt.Y('count():Q', title='Frequência'),
                tooltip=[
                    alt.Tooltip('retorno_pct:Q', bin=True, title='Retorno (%)'),
                    alt.Tooltip('count():Q', title='Nº de Trades')
                ]
            ).properties(height=220, title='Histograma de Retornos')
            st.altair_chart(hist, use_container_width=True)

        st.divider()

        # ── Bloco 6: Breakdown por Ativo ──
        st.subheader("🏆 Ranking de Ativos por Resultado")
        df_rank = (
            df_historico.groupby('ativo')
            .agg(
                resultado_total=('resultado', 'sum'),
                trades=('resultado', 'count'),
                win_rate=('resultado', lambda x: (x > 0).mean() * 100),
                retorno_medio=('retorno_pct', 'mean')
            )
            .reset_index()
            .sort_values('resultado_total', ascending=False)
        )
        df_rank.columns = ['Ativo', 'Resultado (R$)', 'Trades', 'Win Rate (%)', 'Retorno Médio (%)']
        st.dataframe(
            df_rank.style
                .map(color_result, subset=['Resultado (R$)'])
                .format({
                    'Resultado (R$)': 'R$ {:,.2f}',
                    'Win Rate (%)': '{:.1f}%',
                    'Retorno Médio (%)': '{:+.2f}%'
                }),
            use_container_width=True,
            hide_index=True
        )

        bar_rank = alt.Chart(df_rank.head(15)).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
            y=alt.Y('Ativo:N', sort='-x', title=None),
            x=alt.X('Resultado (R$):Q', title='Resultado Acumulado (R$)'),
            color=alt.condition(
                alt.datum['Resultado (R$)'] > 0,
                alt.value('#10b981'),
                alt.value('#ef4444')
            ),
            tooltip=[
                alt.Tooltip('Ativo:N'),
                alt.Tooltip('Resultado (R$):Q', format=',.2f'),
                alt.Tooltip('Win Rate (%):Q', format='.1f'),
            ]
        ).properties(height=max(180, len(df_rank.head(15)) * 28))
        st.altair_chart(bar_rank, use_container_width=True)


# ─────────────────────────────────────────────
# PÁGINA: HISTÓRICO DE OPERAÇÕES
# ─────────────────────────────────────────────
elif menu == "📋 Histórico de Operações":
    st.title("Histórico Completo de Operações")

    df = load_data(conn)
    if df.empty:
        st.info("Nenhuma operação encontrada.")
    else:
        # Filtros
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            ativos_filtro = ['Todos'] + sorted(df['ativo'].unique().tolist())
            ativo_filtro = st.selectbox("Filtrar por Ativo", ativos_filtro)
        with col_f2:
            tipo_filtro = st.selectbox("Tipo", ['Todos', 'Compra (C)', 'Venda (V)'])

        df_view = df.copy()
        if ativo_filtro != 'Todos':
            df_view = df_view[df_view['ativo'] == ativo_filtro]
        if tipo_filtro == 'Compra (C)':
            df_view = df_view[df_view['cv'] == 'C']
        elif tipo_filtro == 'Venda (V)':
            df_view = df_view[df_view['cv'] == 'V']

        df_view['cv'] = df_view['cv'].map({'C': '🟢 Compra', 'V': '🔴 Venda'})
        df_view = df_view.rename(columns={
            'id': 'ID', 'data': 'Data', 'cv': 'Tipo',
            'ativo': 'Ativo', 'quantidade': 'Qtde',
            'preco': 'Preço (R$)', 'valor': 'Valor (R$)', 'dc': 'D/C'
        })

        st.caption(f"Exibindo **{len(df_view)}** de **{len(df)}** operações")
        st.dataframe(
            df_view.style.format({'Preço (R$)': 'R$ {:.4f}', 'Valor (R$)': 'R$ {:,.2f}'}),
            use_container_width=True,
            hide_index=True
        )

        # Botão de exportação CSV
        csv_data = df_view.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇️ Exportar CSV",
            data=csv_data,
            file_name=f"historico_operacoes_{datetime.date.today()}.csv",
            mime='text/csv'
        )
