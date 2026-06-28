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
