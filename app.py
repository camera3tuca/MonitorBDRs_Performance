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

def processar_notas_iniciais(conn):
    """Lê todas as notas já existentes na pasta e tenta salvar no banco se ainda não foram processadas."""
    os.makedirs('notas_pdf', exist_ok=True)
    c = conn.cursor()

    arquivos_pdf = glob.glob('notas_pdf/*.pdf')
    total_novas = 0
    for caminho_arquivo in arquivos_pdf:
        nome_arquivo = os.path.basename(caminho_arquivo)

        # Verifica se o arquivo já foi processado
        c.execute('SELECT COUNT(*) FROM arquivos_processados WHERE nome_arquivo=?', (nome_arquivo,))
        if c.fetchone()[0] == 0:
            trades = parse_pdf(caminho_arquivo)
            novas = save_to_db(trades, conn)
            total_novas += novas

            # Marca o arquivo como processado
            c.execute('INSERT INTO arquivos_processados (nome_arquivo) VALUES (?)', (nome_arquivo,))
            conn.commit()

    return total_novas

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

# Tenta ler as notas iniciais e avisa apenas no backend/logs (não precisa mostrar toast se não for novo pra não ser chato)
# Vamos processar as notas e deixar pronto.
processar_notas_iniciais(conn)

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
                # O usuário pode ter vendido ativos que foram comprados antes do período analisado pelos PDFs.
                # Para não estragar a carteira com quantidades negativas e distorcer o resultado:
                qtde_valida_para_lucro = min(qtde_atual, qtde)
                lucro_prejuizo = (preco - pm_atual) * qtde_valida_para_lucro

                historico.append({
                    'data': row['data'],
                    'mes_ano': row['data'].strftime('%Y-%m'),
                    'ativo': ativo,
                    'qtde_vendida': qtde_valida_para_lucro,
                    'preco_venda': preco,
                    'preco_medio_compra': pm_atual,
                    'resultado': lucro_prejuizo
                })
                carteira[ativo]['qtde'] -= qtde_valida_para_lucro

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

menu = st.sidebar.selectbox("Menu", ["Visão Geral", "Importar Notas", "Carteira Atual", "Performance Mensal", "Análise Individual de BDR", "Histórico de Operações"])

if menu == "Visão Geral":
    st.header("Visão Geral do Portfólio")
    df = load_data(conn)

    if df.empty:
        st.info("O banco de dados está vazio. Vá em 'Importar Notas' para começar.")
    else:
        df_carteira, df_historico, _ = calculate_performance(df)

        # KPIs principais
        col1, col2, col3, col4 = st.columns(4)

        total_investido = df_carteira['Valor Investido'].sum() if not df_carteira.empty else 0.0
        ativos_diferentes = len(df_carteira) if not df_carteira.empty else 0

        lucro_bruto_total = df_historico['resultado'].sum() if not df_historico.empty else 0.0

        if not df_historico.empty:
            operacoes_vencedoras = len(df_historico[df_historico['resultado'] > 0])
            total_vendas = len(df_historico)
            win_rate = (operacoes_vencedoras / total_vendas) * 100 if total_vendas > 0 else 0
        else:
            win_rate = 0.0

        col1.metric("Total Investido", f"R$ {total_investido:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        col2.metric("Lucro Bruto Acumulado", f"R$ {lucro_bruto_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        col3.metric("Ativos em Carteira", f"{ativos_diferentes}")
        col4.metric("Win Rate (Vendas com Lucro)", f"{win_rate:.1f}%")

        st.divider()

        # Gráficos
        if not df_carteira.empty:
            st.subheader("Distribuição da Carteira")

            # Pega o top 10 ativos e agrupa o resto em "Outros" para o gráfico não ficar ilegível
            df_chart = df_carteira.sort_values(by='Valor Investido', ascending=False)
            if len(df_chart) > 10:
                top10 = df_chart.head(10).copy()
                outros_valor = df_chart.iloc[10:]['Valor Investido'].sum()
                outros_df = pd.DataFrame([{'Ativo': 'OUTROS', 'Quantidade': 0, 'Preço Médio': 0, 'Valor Investido': outros_valor}])
                df_chart = pd.concat([top10, outros_df], ignore_index=True)

            # Usa Altair para criar gráfico de rosca (donut chart)
            chart = alt.Chart(df_chart).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="Valor Investido", type="quantitative"),
                color=alt.Color(field="Ativo", type="nominal", legend=alt.Legend(title="Ativos")),
                tooltip=[alt.Tooltip("Ativo", type="nominal"), alt.Tooltip("Valor Investido", type="quantitative", format=".2f")]
            ).properties(
                width=600,
                height=400
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.write("Carteira atual está vazia.")

elif menu == "Importar Notas":
    st.header("Importar Notas de Corretagem (PDF)")
    uploaded_files = st.file_uploader("Selecione as notas de corretagem (PDF)", accept_multiple_files=True, type=['pdf'])

    if st.button("Processar Notas"):
        if uploaded_files:
            total_novas = 0
            os.makedirs('notas_pdf', exist_ok=True)
            c = conn.cursor()
            for file in uploaded_files:
                nome_arquivo = file.name
                file_path = os.path.join('notas_pdf', nome_arquivo)

                # Salvar o arquivo fisicamente na pasta notas_pdf
                with open(file_path, "wb") as f:
                    f.write(file.getbuffer())

                # Verifica se já foi processado
                c.execute('SELECT COUNT(*) FROM arquivos_processados WHERE nome_arquivo=?', (nome_arquivo,))
                if c.fetchone()[0] == 0:
                    # Processa o arquivo recém-salvo
                    trades = parse_pdf(file_path)
                    novas = save_to_db(trades, conn)
                    total_novas += novas

                    # Marca o arquivo como processado
                    c.execute('INSERT INTO arquivos_processados (nome_arquivo) VALUES (?)', (nome_arquivo,))
                    conn.commit()

            st.success(f"Processamento concluído! {total_novas} novas operações importadas e arquivos salvos em notas_pdf/.")
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
    st.info("Atenção: Os valores calculados referem-se ao **Lucro Bruto** das operações. O sistema atualmente não desconta as taxas de corretagem, emolumentos (B3), taxa de liquidação e impostos retidos na fonte (IRRF). Isso pode gerar pequenas discrepâncias em relação às suas planilhas de controle líquido.")

    df = load_data(conn)
    _, df_historico, df_mensal = calculate_performance(df)

    if not df_mensal.empty:
        st.bar_chart(data=df_mensal.set_index('mes_ano'))
        st.dataframe(df_mensal.style.format({"resultado": "R$ {:.2f}"}), use_container_width=True)

        total_resultado = df_mensal['resultado'].sum()

        # Novas métricas de Análise
        st.subheader("Análise de Trades")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        lucros = df_historico[df_historico['resultado'] > 0]['resultado']
        prejuizos = df_historico[df_historico['resultado'] < 0]['resultado']

        maior_lucro = lucros.max() if not lucros.empty else 0.0
        maior_prejuizo = prejuizos.min() if not prejuizos.empty else 0.0
        media_lucros = lucros.mean() if not lucros.empty else 0.0
        media_prejuizos = prejuizos.mean() if not prejuizos.empty else 0.0

        col_m1.metric("Maior Lucro (Trade)", f"R$ {maior_lucro:.2f}")
        col_m2.metric("Maior Prejuízo (Trade)", f"R$ {maior_prejuizo:.2f}")
        col_m3.metric("Média (Trades Vencedores)", f"R$ {media_lucros:.2f}")
        col_m4.metric("Média (Trades Perdedores)", f"R$ {media_prejuizos:.2f}")

        st.divider()
        if total_resultado > 0:
            st.success(f"Resultado Acumulado Total: R$ {total_resultado:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        else:
            st.error(f"Resultado Acumulado Total: R$ {total_resultado:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    else:
        st.info("Nenhuma operação de venda registrada para calcular performance.")

elif menu == "Análise Individual de BDR":
    st.header("Análise Individual de BDR")
    df = load_data(conn)

    if not df.empty:
        ativos_disponiveis = df['ativo'].unique().tolist()
        ativos_disponiveis.sort()
        ativo_selecionado = st.selectbox("Selecione a BDR (Ativo):", ativos_disponiveis)

        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        min_date = df['data'].min().date()
        max_date = df['data'].max().date()

        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data de Início", value=min_date, min_value=min_date, max_value=max_date)
        with col2:
            data_fim = st.date_input("Data de Fim", value=max_date, min_value=min_date, max_value=max_date)

        # Seleciona TODAS as operações do ativo para calcular o PM e o lucro corretamente ao longo do tempo
        df_ativo_completo = df[df['ativo'] == ativo_selecionado].copy()

        if not df_ativo_completo.empty:
            # Calcula performance no ativo inteiro
            df_carteira_bdr, df_historico_bdr_completo, df_mensal_bdr = calculate_performance(df_ativo_completo)

            # Filtra apenas a exibição das tabelas para o período solicitado
            df_filtrado_exibicao = df_ativo_completo[(df_ativo_completo['data'].dt.date >= data_inicio) & (df_ativo_completo['data'].dt.date <= data_fim)].copy()
            df_filtrado_exibicao['data'] = df_filtrado_exibicao['data'].dt.strftime('%d/%m/%Y')

            st.subheader(f"Operações de {ativo_selecionado} no período selecionado")
            if not df_filtrado_exibicao.empty:
                st.dataframe(df_filtrado_exibicao, use_container_width=True)
            else:
                st.write("Nenhuma operação de compra/venda neste período específico.")

            # Filtra o histórico de lucros
            if not df_historico_bdr_completo.empty:
                df_historico_bdr = df_historico_bdr_completo[(df_historico_bdr_completo['data'].dt.date >= data_inicio) & (df_historico_bdr_completo['data'].dt.date <= data_fim)]
            else:
                df_historico_bdr = pd.DataFrame()

            st.subheader("Resumo no Período Selecionado")
            st.info("Nota: Os lucros/prejuízos representam o valor bruto das operações. Taxas e emolumentos não estão sendo deduzidos.")

            col_a, col_b = st.columns(2)

            with col_a:
                st.write("**Carteira Resultante (no final do período):**")
                if not df_carteira_bdr.empty:
                    st.dataframe(df_carteira_bdr.style.format({"Preço Médio": "R$ {:.2f}", "Valor Investido": "R$ {:.2f}"}))
                else:
                    st.write("Sem posição em aberto no período analisado.")

            with col_b:
                st.write("**Resultado (Lucro/Prejuízo) das Vendas:**")
                if not df_historico_bdr.empty:
                    total_resultado = df_historico_bdr['resultado'].sum()
                    st.metric("Resultado Consolidado", f"R$ {total_resultado:.2f}")
                    st.dataframe(df_historico_bdr[['data', 'qtde_vendida', 'preco_venda', 'resultado']].style.format({"resultado": "R$ {:.2f}"}))
                else:
                    st.write("Nenhuma venda que pudesse calcular lucro encontrada no período.")

        else:
            st.warning("Nenhuma operação encontrada para este ativo no período selecionado.")
    else:
        st.info("O banco de dados está vazio.")

elif menu == "Histórico de Operações":
    st.header("Todas as Operações")
    df = load_data(conn)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhuma operação encontrada.")
