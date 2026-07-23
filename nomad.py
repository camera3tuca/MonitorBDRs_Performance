"""
nomad — leitor dos extratos da corretora Nomad (Apex Clearing, ações EUA).

Diferente do MyCapital, o extrato da Nomad ("Account Statement") traz as
operações BRUTAS (compra/venda, quantidade fracionária, preço em US$), sem
o resultado apurado. Portanto apuramos o resultado realizado por venda via
FIFO (custo médio das compras anteriores), em dólar.

Seções relevantes do PDF:
  TRADING ACTIVITIES  → operações
      BUY  2026-06-01 2026-06-02 SANDISK CORP COM SNDK 0.00284 1,759.251 5.00 0.00 0.00 0.00 AGENCY
      SELL 2026-06-01 2026-06-02 ARM HOLDINGS ...      ARM -0.01631 410.156 6.69 ...
  NON-TRADING ACTIVITY → dividendos
      2026-06-09 CASH_DIVIDEND JOHNSON & JOHNSON COM ... JNJ 0.00 0.03 0.00

Layout de cada linha de trade (ancorado à direita):
  <BUY|SELL> <trade> <settle> <descrição...> <SYMBOL> <qtd> <preço> <net> <comissão> <taxa> <taxa> <CAPACITY>
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict, deque

import pdfplumber

log = logging.getLogger(__name__)

_CAPACITY = {"AGENCY", "PRINCIPAL"}
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _num(s: str):
    """Número no formato EUA (1,759.251) → float."""
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _periodo(iso: str) -> str:
    return iso[:7]  # YYYY-MM


def _data_br(iso: str) -> str:
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a[2:]}"


def parse_nomad_trades(file_obj) -> tuple[list[dict], list[dict]]:
    """Extrai (trades, dividendos) brutos de um extrato Nomad."""
    trades: list[dict] = []
    dividendos: list[dict] = []

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            for raw in (page.extract_text() or "").split("\n"):
                tk = raw.split()
                # ── Trade ──
                if len(tk) >= 9 and tk[0] in ("BUY", "SELL") and tk[-1] in _CAPACITY:
                    if not (_RE_DATA.match(tk[1]) and _RE_DATA.match(tk[2])):
                        continue
                    symbol = tk[-8]
                    qty, price, net = _num(tk[-7]), _num(tk[-6]), _num(tk[-5])
                    comm = _num(tk[-4]) or 0.0
                    if qty is None or price is None:
                        continue
                    nome = " ".join(tk[3:-8])  # descrição/nome da empresa
                    trades.append({
                        "lado": tk[0],
                        "trade_date": tk[1],
                        "symbol": symbol,
                        "nome": nome,
                        "quantidade": abs(qty),
                        "preco": price,
                        "valor": net if net is not None else abs(qty) * price,
                        "comissao": comm,
                    })
                # ── Dividendo ──
                elif len(tk) >= 6 and tk[1] == "CASH_DIVIDEND" and _RE_DATA.match(tk[0]):
                    valor = _num(tk[-2])
                    symbol = None
                    # símbolo = último token alfabético antes dos números finais
                    for t in reversed(tk[:-2]):
                        if re.match(r"^[A-Z]{1,6}$", t):
                            symbol = t
                            break
                    if valor:
                        dividendos.append({
                            "data": tk[0], "symbol": symbol or "", "valor": valor,
                        })

    return trades, dividendos


def apurar_fifo(trades: list[dict], dividendos: list[dict]) -> list[dict]:
    """
    Apura o resultado realizado por venda via FIFO e devolve uma lista de
    operações no mesmo schema usado pelo app (uma linha por trade/dividendo):

        periodo, mercado, ticker, data, tipo, daytrade, quantidade,
        preco, valor, res_daytrade, res_normal, res_outros
    """
    # ordena por data de trade (estável)
    trades = sorted(trades, key=lambda t: t["trade_date"])
    filas: dict[str, deque] = defaultdict(deque)  # symbol → lotes de compra
    ops: list[dict] = []

    for t in trades:
        sym = t["symbol"]
        q = t["quantidade"]
        preco = t["preco"]
        comm = t["comissao"]
        base = {
            "periodo": _periodo(t["trade_date"]),
            "mercado": "Ações EUA",
            "ticker": sym,
            "data": _data_br(t["trade_date"]),
            "_iso": t["trade_date"],
            "quantidade": q,
            "preco": preco,
            "valor": q * preco,
            "res_daytrade": 0.0,
            "res_normal": 0.0,
            "res_outros": 0.0,
        }
        if t["lado"] == "BUY":
            filas[sym].append({"qtd": q, "preco": preco,
                               "comm_unit": comm / q if q else 0.0,
                               "data": t["trade_date"]})
            base["tipo"] = "Compra"
            base["daytrade"] = False
        else:  # SELL
            rem = q
            custo = 0.0
            mesmo_dia = True
            casados = []  # lotes consumidos: (data_aquisição, qtd, custo_usd)
            fila = filas[sym]
            while rem > 1e-12 and fila:
                lote = fila[0]
                m = min(rem, lote["qtd"])
                custo_lote = m * (lote["preco"] + lote["comm_unit"])
                custo += custo_lote
                casados.append((lote["data"], m, custo_lote))
                if lote["data"] != t["trade_date"]:
                    mesmo_dia = False
                lote["qtd"] -= m
                rem -= m
                if lote["qtd"] <= 1e-12:
                    fila.popleft()
            if rem > 1e-9:  # vendeu mais do que temos histórico (posição anterior)
                mesmo_dia = False
            proventos = q * preco - comm  # líquido de comissão de venda
            resultado = proventos - custo
            base["tipo"] = "Venda DayTrade" if mesmo_dia else "Venda"
            base["daytrade"] = mesmo_dia
            if mesmo_dia:
                base["res_daytrade"] = resultado
            else:
                base["res_normal"] = resultado
            # Detalhe para conversão cambial (PTAX por data)
            base["_venda_bruta"] = q * preco
            base["_comissao"] = comm
            base["_sell_date"] = t["trade_date"]
            base["_lotes"] = casados
        ops.append(base)

    # dividendos → res_outros
    for d in dividendos:
        ops.append({
            "periodo": _periodo(d["data"]),
            "mercado": "Ações EUA",
            "ticker": d["symbol"],
            "data": _data_br(d["data"]),
            "_iso": d["data"],
            "tipo": "Dividendo",
            "daytrade": False,
            "quantidade": 0.0,
            "preco": 0.0,
            "valor": 0.0,
            "res_daytrade": 0.0,
            "res_normal": 0.0,
            "res_outros": d["valor"],
        })

    ops.sort(key=lambda o: (o["periodo"], o["data"]))
    return ops


def posicoes_abertas(trades: list[dict]) -> list[dict]:
    """
    Reconstrói, por FIFO, as posições ainda em carteira e seu custo de
    aquisição (US$) — base para a ficha "Bens e Direitos" da declaração.

    Retorna: [{symbol, nome, quantidade, custo_total, custo_medio}, ...]
    """
    trades = sorted(trades, key=lambda t: t["trade_date"])
    filas: dict[str, deque] = defaultdict(deque)
    nomes: dict[str, str] = {}
    for t in trades:
        sym = t["symbol"]
        nomes.setdefault(sym, t.get("nome", ""))
        if t.get("nome"):
            nomes[sym] = t["nome"]
        q = t["quantidade"]
        if t["lado"] == "BUY":
            filas[sym].append({"qtd": q,
                               "custo_unit": t["preco"] + (t["comissao"] / q if q else 0.0),
                               "data": t["trade_date"]})
        else:
            rem = q
            while rem > 1e-12 and filas[sym]:
                lote = filas[sym][0]
                m = min(rem, lote["qtd"])
                lote["qtd"] -= m
                rem -= m
                if lote["qtd"] <= 1e-12:
                    filas[sym].popleft()

    posicoes = []
    for sym, fila in filas.items():
        qtd = sum(l["qtd"] for l in fila)
        if qtd <= 1e-9:
            continue
        custo = sum(l["qtd"] * l["custo_unit"] for l in fila)
        lotes = [(l["data"], l["qtd"], l["qtd"] * l["custo_unit"])
                 for l in fila if l["qtd"] > 1e-9]
        posicoes.append({
            "symbol": sym,
            "nome": nomes.get(sym, ""),
            "quantidade": qtd,
            "custo_total": custo,
            "custo_medio": custo / qtd if qtd else 0.0,
            "lotes": lotes,  # [(data_aquisição, qtd, custo_usd)]
        })
    return sorted(posicoes, key=lambda p: p["symbol"])


def parse_nomad(file_obj) -> list[dict]:
    """Lê um extrato Nomad e devolve as operações já apuradas (FIFO, US$)."""
    trades, dividendos = parse_nomad_trades(file_obj)
    ops = apurar_fifo(trades, dividendos)
    log.info("Nomad: %d trades, %d dividendos → %d operações apuradas",
             len(trades), len(dividendos), len(ops))
    return ops


if __name__ == "__main__":
    import glob
    import sys
    logging.basicConfig(level=logging.INFO)
    padrao = sys.argv[1] if len(sys.argv) > 1 else "notas_pdf/Nomad-*.pdf"
    total_n = total_d = total_o = 0
    for f in sorted(glob.glob(padrao)):
        ops = parse_nomad(f)
        n = sum(o["res_normal"] for o in ops)
        dt = sum(o["res_daytrade"] for o in ops)
        o_ = sum(o["res_outros"] for o in ops)
        total_n += n; total_d += dt; total_o += o_
        print(f"{f.split('/')[-1]}: normal ${n:.2f} | daytrade ${dt:.2f} | div ${o_:.2f}")
    print(f"\nTOTAL: normal ${total_n:.2f} | daytrade ${total_d:.2f} | "
          f"dividendos ${total_o:.2f} | líquido ${total_n+total_d+total_o:.2f}")
