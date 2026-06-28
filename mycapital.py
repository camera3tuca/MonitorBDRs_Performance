"""
mycapital — leitor dos relatórios "Operações no mês" do MyCapital.

Diferente das notas de corretagem Santander (que listam negócios brutos e
exigem recálculo de preço médio / FIFO), o relatório MyCapital já traz os
resultados apurados por ativo e por mês: Day-trade, Normal (swing) e
Outros (proventos). Logo, é a fonte ideal — bate 100% com a contabilidade
oficial do investidor e usa os códigos B3 reais.

Layout do texto extraído (pdfplumber), por ativo:

    A1LB34 A1LB
    30/04/26 Saldo Anterior 0 0,00 0,00
    04/05/26 Compra 10 39,48 394,80 ...
    ...
    Total da Ação 1,93 14,55 0,00          <- day-trade, normal, outros

E no fim:

    Total de BDR (29,18) 101,18 5,37
    de 01/05/2026 até 29/05/2026           <- período (no cabeçalho)
"""

from __future__ import annotations

import logging
import re

import pdfplumber

log = logging.getLogger(__name__)

# Nomes de mercado que aparecem sozinhos na linha como cabeçalho de seção
_MERCADOS = {
    "Ações", "Açoes", "ETF", "BDR", "FII", "Opções", "Opçoes",
    "Fundos Imobiliários", "Fundos Imobiliarios", "Fiagro", "Termo",
}

# Cabeçalho de bloco de ativo: "A1LB34 A1LB" (ticker + nome-curto repetido)
_RE_ATIVO = re.compile(r"^([A-Z0-9]{4,6})\s+[A-Z0-9]{2,6}$")
# Linha de total do ativo: "Total da Ação <dt> <normal> <outros>"
_RE_TOTAL_ATIVO = re.compile(
    r"^Total da A[çc][ãa]o\s+([\d.,()]+)\s+([\d.,()]+)\s+([\d.,()]+)$"
)
# Total por mercado: "Total de BDR ...", "Total de Ações ...", "Total de ETF ..."
_RE_TOTAL_DE = re.compile(
    r"^Total de ([A-Za-zçõ]+)\s+([\d.,()]+)\s+([\d.,()]+)\s+([\d.,()]+)$"
)
# Período: "de 01/05/2026 até 29/05/2026"
_RE_PERIODO = re.compile(r"de\s+\d{2}/(\d{2})/(\d{4})\s+at[ée]")


def _num(s: str) -> float:
    """Converte número BR do MyCapital para float. Parênteses = negativo."""
    s = s.strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(".", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


# ─────────────────────────────────────────────
# EXTRAÇÃO OPERAÇÃO-A-OPERAÇÃO (máximo detalhe)
# ─────────────────────────────────────────────
# Faixas de coluna (centro-x da palavra) calibradas pelos cabeçalhos do
# relatório. As 3 últimas colunas são o resultado apurado de cada linha.
_COL_X = [
    ("data",      0,   55),
    ("mov",      55,  170),
    ("op_qtd",  170,  225),
    ("op_preco",225,  276),
    ("op_valor",276,  311),
    ("cu_preco",311,  366),
    ("cu_valor",366,  405),
    ("abertura",405,  465),
    ("baixa",   465,  511),
    ("sa_qtd",  511,  566),
    ("sa_preco",566,  621),
    ("sa_valor",621,  658),
    ("daytrade",658,  716),
    ("normal",  716,  776),
    ("outros",  776,  860),
]
_RE_DATA = re.compile(r"^\d{2}/\d{2}/\d{2}$")


def _col_of(xc: float) -> str | None:
    for nome, a, b in _COL_X:
        if a <= xc < b:
            return nome
    return None


def parse_mycapital_ops(file_obj) -> list[dict]:
    """
    Extrai CADA operação do relatório com seu resultado apurado, usando a
    posição-x das palavras (robusto a colunas vazias).

    Retorna lista de dicts:
        {periodo, mercado, ticker, data, tipo, daytrade(bool),
         quantidade, preco, valor, res_daytrade, res_normal, res_outros}

    O somatório de res_* reproduz exatamente os totais do relatório.
    """
    ops: list[dict] = []
    periodo = None
    mercado_atual = None
    ticker_atual = None

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            # Agrupa palavras em linhas pela coordenada vertical (~3px)
            linhas: dict[int, list] = {}
            for w in words:
                linhas.setdefault(round(w["top"] / 3), []).append(w)

            for chave in sorted(linhas):
                ws = sorted(linhas[chave], key=lambda w: w["x0"])
                texto = " ".join(w["text"] for w in ws)

                if periodo is None:
                    mp = _RE_PERIODO.search(texto)
                    if mp:
                        periodo = f"{mp.group(2)}-{mp.group(1)}"

                if texto.strip() in _MERCADOS:
                    mercado_atual = texto.strip()
                    continue

                mh = _RE_ATIVO.match(texto.strip())
                if mh and not texto.startswith(("Total", "Data", "Mercado")):
                    ticker_atual = mh.group(1)
                    continue

                # Distribui as palavras em colunas por x
                cells: dict[str, list] = {}
                for w in ws:
                    c = _col_of((w["x0"] + w["x1"]) / 2)
                    if c:
                        cells.setdefault(c, []).append(w["text"])

                data = cells.get("data", [])
                if not (data and _RE_DATA.match(data[0])):
                    continue
                if "Saldo Anterior" in texto:
                    continue

                mov = " ".join(cells.get("mov", []))
                ops.append({
                    "periodo": periodo,
                    "mercado": mercado_atual,
                    "ticker": ticker_atual,
                    "data": data[0],
                    "tipo": mov,
                    "daytrade": "DayTrade" in mov,
                    "quantidade": _num(" ".join(cells.get("op_qtd", []))),
                    "preco": _num(" ".join(cells.get("op_preco", []))),
                    "valor": _num(" ".join(cells.get("op_valor", []))),
                    "res_daytrade": _num(" ".join(cells.get("daytrade", []))),
                    "res_normal": _num(" ".join(cells.get("normal", []))),
                    "res_outros": _num(" ".join(cells.get("outros", []))),
                })

    return ops


# ─────────────────────────────────────────────
# EXTRATO MENSAL DE RESULTADOS (apuração oficial de IR)
# ─────────────────────────────────────────────
_MESES_NUM = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Marco": 3, "Abril": 4,
    "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9,
    "Outubro": 10, "Novembro": 11, "Dezembro": 12,
}
# Rótulos das linhas do Extrato → chave interna
_EXTRATO_ROWS = {
    "Alienações": "alienacoes",
    "01-Mercado": "res_acoes",
    "14-RESULTADO": "res_liquido",
    "15-Resultado": "neg_anterior",
    "17-Prejuízo": "prej_compensar",
    "19-IMPOSTO": "imp_devido",
    "25-Imposto": "imp_pagar",
}
_RE_ANO = re.compile(r"Ano:\s*(\d{4})")


def parse_extrato_ir(file_obj) -> dict:
    """
    Lê o "Extrato Mensal de Resultados" (apuração oficial de IR do MyCapital)
    e devolve, por período YYYY-MM, os valores oficiais separados em Comuns
    (swing, 15%) e Day Trade (20%):

        {"2026-05": {
            "res_acoes_c", "res_acoes_d",          # resultado do mês
            "prej_compensar_c", "prej_compensar_d",# prejuízo a compensar (acum.)
            "imp_pagar_c", "imp_pagar_d",          # imposto a pagar
            "alienacoes",                          # vendas à vista no mês
        }, ...}

    A tabela é rotacionada (vários meses lado a lado); o parsing usa as
    posições-x das colunas (Comuns / Day Trade de cada mês) e a posição-y
    de cada linha rotulada.
    """
    numre = re.compile(r"^\(?[\d.]+,\d{2}\)?$")
    ano = None
    dados: dict[str, dict] = {}

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            ws = page.extract_words()
            if ano is None:
                txt = page.extract_text() or ""
                ma = _RE_ANO.search(txt)
                if ma:
                    ano = ma.group(1)

            # Colunas: pares (Comuns / Day Trade) por mês, ordenados por x
            comuns = sorted((w["x0"] + w["x1"]) / 2 for w in ws if w["text"] == "Comuns")
            days = [w for w in ws if w["text"] == "Day" and w["top"] < 90]
            trades = [w for w in ws if w["text"] == "Trade" and w["top"] < 90]
            dts = sorted(
                (d["x0"] + t["x1"]) / 2
                for d in days for t in trades
                if abs(d["top"] - t["top"]) < 2 and 0 < t["x0"] - d["x1"] < 6
            )
            meses = sorted(
                ((w["x0"] + w["x1"]) / 2, w["text"]) for w in ws
                if w["text"] in _MESES_NUM and w["top"] < 80
            )
            nomes = [m[1] for m in meses]
            n = min(len(comuns), len(dts), len(nomes))
            cols = []
            for i in range(n):
                cols.append((nomes[i], "c", comuns[i]))
                cols.append((nomes[i], "d", dts[i]))

            # Linhas rotuladas → top
            rowtops: dict[str, float] = {}
            for w in ws:
                for pref, key in _EXTRATO_ROWS.items():
                    if w["text"].startswith(pref) and key not in rowtops:
                        rowtops[key] = w["top"]

            if not cols or not rowtops:
                continue

            for w in ws:
                if not numre.match(w["text"]):
                    continue
                c = (w["x0"] + w["x1"]) / 2
                rk = min(rowtops.items(), key=lambda kv: abs(kv[1] - w["top"]))
                if abs(rk[1] - w["top"]) > 4:
                    continue
                col = min(cols, key=lambda cc: abs(cc[2] - c))
                if abs(col[2] - c) > 55:
                    continue
                mes, tipo, _ = col
                if not ano:
                    continue
                periodo = f"{ano}-{_MESES_NUM[mes]:02d}"
                d = dados.setdefault(periodo, {})
                key = rk[0]
                if key == "alienacoes":
                    d["alienacoes"] = _num(w["text"])
                else:
                    d[f"{key}_{tipo}"] = _num(w["text"])

    return dados


def parse_mycapital(file_obj) -> dict:
    """
    Lê um relatório MyCapital "Operações no mês" e devolve:

        {
          "periodo": "2026-05",
          "ativos": [ {"ticker","daytrade","normal","outros"}, ... ],
          "totais": {"daytrade","normal","outros"},
        }

    Os valores por ativo são os resultados JÁ APURADOS pelo MyCapital
    (não as operações individuais).
    """
    periodo = None
    mercado_atual = None
    ativo_atual = None
    ativos: list[dict] = []
    # Totais por mercado, lidos das linhas "Total de <Mercado>" (conferência)
    totais_mercado: dict[str, dict] = {}

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw in text.split("\n"):
                line = raw.strip()

                if periodo is None:
                    mp = _RE_PERIODO.search(line)
                    if mp:
                        periodo = f"{mp.group(2)}-{mp.group(1)}"

                # Cabeçalho de mercado (sozinho na linha): Ações, ETF, BDR,
                # Fundos Imobiliários, Fiagro, Opções, Termo…
                if line in _MERCADOS:
                    mercado_atual = line
                    continue

                # Total por mercado: "Total de Ações ..." / "Total de BDR ..."
                mtm = _RE_TOTAL_DE.match(line)
                if mtm:
                    totais_mercado[mtm.group(1)] = {
                        "daytrade": _num(mtm.group(2)),
                        "normal": _num(mtm.group(3)),
                        "outros": _num(mtm.group(4)),
                    }
                    continue

                # Total por ativo
                ma = _RE_TOTAL_ATIVO.match(line)
                if ma and ativo_atual:
                    ativos.append({
                        "ticker": ativo_atual,
                        "mercado": mercado_atual,
                        "daytrade": _num(ma.group(1)),
                        "normal": _num(ma.group(2)),
                        "outros": _num(ma.group(3)),
                    })
                    ativo_atual = None
                    continue

                # Cabeçalho de novo ativo
                mh = _RE_ATIVO.match(line)
                if mh and not line.startswith(("Total", "Data", "Mercado")):
                    ativo_atual = mh.group(1)

    # Total geral = soma de TODOS os mercados (Ações + ETF + BDR + FII…)
    totais = {
        "daytrade": round(sum(a["daytrade"] for a in ativos), 2),
        "normal": round(sum(a["normal"] for a in ativos), 2),
        "outros": round(sum(a["outros"] for a in ativos), 2),
    }

    log.info(
        "MyCapital parseado: período %s, %d ativos, total Normal R$%.2f / DT R$%.2f / Outros R$%.2f",
        periodo, len(ativos), totais["normal"], totais["daytrade"], totais["outros"],
    )
    return {
        "periodo": periodo,
        "ativos": ativos,
        "totais": totais,
        "totais_mercado": totais_mercado,
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = parse_mycapital(sys.argv[1])
    soma_n = sum(a["normal"] for a in data["ativos"])
    soma_d = sum(a["daytrade"] for a in data["ativos"])
    soma_o = sum(a["outros"] for a in data["ativos"])
    print(f"\nPeríodo: {data['periodo']}  ({len(data['ativos'])} ativos)")
    print(f"Soma por ativo  → Normal {soma_n:.2f} | DT {soma_d:.2f} | Outros {soma_o:.2f}")
    print(f"Total relatório → Normal {data['totais']['normal']:.2f} "
          f"| DT {data['totais']['daytrade']:.2f} | Outros {data['totais']['outros']:.2f}")
