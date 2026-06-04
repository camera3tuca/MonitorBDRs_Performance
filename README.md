# MonitorBDRs_Performance

Análise de operações realizadas em Swing trade e acompanhamento de carteira de BDRs.

Este projeto consolida notas mensais do Santander e oferece uma análise detalhada da performance das suas operações de BDRs.

## Estrutura do Projeto

O código foi modularizado para melhorar a organização, escalabilidade e manutenção:

*   **`app.py`**: Ponto de entrada da aplicação Streamlit. Carrega os dados, gerencia a interface principal e renderiza as abas.
*   **`src/`**: Diretório principal com o código-fonte da aplicação.
    *   **`config.py`**: Constantes, configurações de caminho e dicionários de mapeamento.
    *   **`database.py`**: Funções para conexão com o SQLite e manipulação de operações salvas.
    *   **`parser.py`**: Lógica de extração de dados das notas de corretagem (PDF) usando regex e `pdfplumber`.
    *   **`financials.py`**: Cálculos de posição, preço médio e P&L (Lucros e Perdas).
    *   **`utils.py`**: Funções utilitárias e de formatação.
    *   **`ui/`**: Componentes da interface Streamlit separados por funcionalidade.
        *   **`sidebar.py`**: Painel lateral (upload de PDFs, controle de dados).
        *   **`dashboard.py`**: Visão geral de métricas, gráficos de P&L, volume mensal e insights.
        *   **`assets.py`**: Resumo da carteira por ativo (custo médio, quantidade, P&L atual).
        *   **`analysis.py`**: Análise profunda por ativo, com gráficos detalhados.
        *   **`operations.py`**: Tabela com o histórico completo de operações e filtros.

## Como Executar

### Pré-requisitos
*   Python 3.8+
*   Bibliotecas listadas em `requirements.txt`

### Instalação
1. Clone o repositório.
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Inicie a aplicação com Streamlit:
   ```bash
   streamlit run app.py
   ```

## Dados Suportados
As notas de corretagem importadas devem estar no formato PDF fornecido pelo Santander. Notas CSV localizadas no diretório `notas_pdf/` (como `operacoes-*.csv`) também são carregadas automaticamente se existirem.