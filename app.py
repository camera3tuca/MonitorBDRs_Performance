import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import datetime
import sqlite3

st.set_page_config(page_title="MonitorBDRs Performance", layout="wide")

# Inicializar Banco de Dados
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
    conn.commit()
    return conn

conn = init_db()

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
                if re.match(r"\d+\s+\d+\s+(\d{2}/\d{2}/\d{4})", line):
                    current_date = re.match(r"\d+\s+\d+\s+(\d{2}/\d{2}/\d{4})", line).group(1)

                match = re.search(r"LISTADO[CV]\s+(?:VISTA|FRACIONARIO)\s+(.*?)\s+(?:@|D|#|\s)*\s+([\d\.]+)\s+([\d\,]+)\s+([\d\.,]+)\s+(D|C)$", line)
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
        # Verifica se já existe para evitar duplicidade
        c.execute('SELECT COUNT(*) FROM operacoes WHERE data=? AND cv=? AND ativo=? AND quantidade=? AND preco=?',
                  (trade['data'], trade['cv'], trade['ativo'], trade['quantidade'], trade['preco']))
        if c.fetchone()[0] == 0:
            c.execute('INSERT INTO operacoes (data, cv, ativo, quantidade, preco, valor, dc) VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (trade['data'], trade['cv'], trade['ativo'], trade['quantidade'], trade['preco'], trade['valor'], trade['dc']))
            new_trades += 1
    conn.commit()
    return new_trades

def load_data(conn):
    return pd.read_sql_query("SELECT * FROM operacoes", conn)

def calculate_performance(df):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df = df.sort_values('data')

    carteira = {}
    historico = []

    for index, row in df.iterrows():
        ativo = row['ativo']
        qtde = row['quantidade']
        preco = row['preco']

        if ativo not in carteira:
            carteira[ativo] = {'qtde': 0, 'preco_medio': 0.0}

        if row['cv'] == 'C':
            qtde_atual = carteira[ativo]['qtde']
            pm_atual = carteira[ativo]['preco_medio']

            nova_qtde = qtde_atual + qtde
            novo_pm = ((qtde_atual * pm_atual) + (qtde * preco)) / nova_qtde if nova_qtde > 0 else 0

            carteira[ativo]['qtde'] = nova_qtde
            carteira[ativo]['preco_medio'] = novo_pm

        elif row['cv'] == 'V':
            qtde_atual = carteira[ativo]['qtde']
            pm_atual = carteira[ativo]['preco_medio']

            if qtde_atual > 0:
                lucro_prejuizo = (preco - pm_atual) * qtde
                historico.append({
                    'data': row['data'],
                    'mes_ano': row['data'].strftime('%Y-%m'),
                    'ativo': ativo,
                    'qtde_vendida': qtde,
                    'preco_venda': preco,
                    'preco_medio_compra': pm_atual,
                    'resultado': lucro_prejuizo
                })
                carteira[ativo]['qtde'] -= qtde

    # Carteira Atual
    carteira_atual = []
    for ativo, dados in carteira.items():
        if dados['qtde'] > 0:
            carteira_atual.append({
                'Ativo': ativo,
                'Quantidade': dados['qtde'],
                'Preço Médio': dados['preco_medio'],
                'Valor Investido': dados['qtde'] * dados['preco_medio']
            })

    df_carteira = pd.DataFrame(carteira_atual)
    df_historico = pd.DataFrame(historico)

    df_mensal = pd.DataFrame()
    if not df_historico.empty:
        df_mensal = df_historico.groupby('mes_ano')['resultado'].sum().reset_index()

    return df_carteira, df_historico, df_mensal

st.title("MonitorBDRs - Análise de Performance")

menu = st.sidebar.selectbox("Menu", ["Importar Notas", "Carteira Atual", "Performance Mensal", "Histórico de Operações"])

if menu == "Importar Notas":
    st.header("Importar Notas de Corretagem (PDF)")
    uploaded_files = st.file_uploader("Selecione as notas de corretagem (PDF)", accept_multiple_files=True, type=['pdf'])

    if st.button("Processar Notas"):
        if uploaded_files:
            total_novas = 0
            for file in uploaded_files:
                trades = parse_pdf(file)
                novas = save_to_db(trades, conn)
                total_novas += novas
            st.success(f"Processamento concluído! {total_novas} novas operações importadas.")
        else:
            st.warning("Por favor, faça o upload de pelo menos um arquivo PDF.")

elif menu == "Carteira Atual":
    st.header("Sua Carteira Atual")
    df = load_data(conn)
    df_carteira, _, _ = calculate_performance(df)

    if not df_carteira.empty:
        st.dataframe(df_carteira.style.format({"Preço Médio": "R$ {:.2f}", "Valor Investido": "R$ {:.2f}"}), use_container_width=True)
        st.metric("Total Investido", f"R$ {df_carteira['Valor Investido'].sum():.2f}")
    else:
        st.info("Sua carteira está vazia ou não há dados carregados.")

elif menu == "Performance Mensal":
    st.header("Lucros e Prejuízos Mensais")
    df = load_data(conn)
    _, _, df_mensal = calculate_performance(df)

    if not df_mensal.empty:
        st.bar_chart(data=df_mensal.set_index('mes_ano'))
        st.dataframe(df_mensal.style.format({"resultado": "R$ {:.2f}"}), use_container_width=True)

        total_resultado = df_mensal['resultado'].sum()
        if total_resultado > 0:
            st.success(f"Resultado Acumulado: R$ {total_resultado:.2f}")
        else:
            st.error(f"Resultado Acumulado: R$ {total_resultado:.2f}")
    else:
        st.info("Nenhuma operação de venda registrada para calcular performance.")

elif menu == "Histórico de Operações":
    st.header("Todas as Operações")
    df = load_data(conn)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhuma operação encontrada.")
