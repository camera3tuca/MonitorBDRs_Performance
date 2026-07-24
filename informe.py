"""
informe — leitor do "Informe de Rendimentos para Declaração de IR" (MyCapital).

Este relatório traz os dados já no formato das fichas da declaração anual:
  • Bens e Direitos (posições em 31/12, com Grupo, Código, CNPJ e valores)
  • Rendimentos isentos e não tributáveis (dividendos, bonificações, lucro
    isento de vendas ≤ R$20 mil/mês)
  • Rendimentos sujeitos à tributação exclusiva (Juros sobre Capital Próprio)
  • IR retido na fonte

É a fonte oficial das posições de fim de ano — que não podem ser
reconstruídas a partir dos relatórios mensais (o histórico é anterior).
"""

from __future__ import annotations

import logging
import re

import pdfplumber

log = logging.getLogger(__name__)

_CNPJ = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
_RE_ANO = re.compile(r"[Aa]no[- ]calendário de (\d{4})")


def _num(s: str):
    s = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_informe(file_obj) -> dict:
    """
    Devolve:
        {
          "ano": "2025",
          "bens_direitos": [ {mercado, grupo, codigo, ticker, cnpj,
                              discriminacao, v_ant, v_atual}, ... ],
          "dividendos": [ {tipo, fonte, cnpj, valor}, ... ],
          "jcp": [ {cnpj, fonte, valor}, ... ],
          "ir_retido": float | None,
        }
    """
    ano = None
    bens: list[dict] = []
    dividendos: list[dict] = []
    jcp: list[dict] = []
    ir_retido = None

    secao = None      # "bd" | "jcp" | None
    cur = None        # item de Bens e Direitos em construção (para continuação)

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            for raw in (page.extract_text() or "").split("\n"):
                s = raw.strip()
                if not s:
                    continue

                if ano is None:
                    ma = _RE_ANO.search(s)
                    if ma:
                        ano = ma.group(1)

                # ── Cabeçalho da tabela de Bens e Direitos ──
                if s.startswith("Mercado Grupo Código"):
                    secao = "bd"
                    cur = None
                    continue

                # ── JCP (tributação exclusiva) ──
                if "Juros Sobre o Capital" in s or "Juros Sobre Capital" in s:
                    secao = "jcp"
                    continue

                # ── IR retido na fonte ──
                if "IR Retido na Fonte" in s and "11.033" in s:
                    m = re.search(r"R\$\s*([\d.]+,\d{2})", s)
                    if m:
                        ir_retido = _num(m.group(1))

                # ── Dividendos isentos / bonificações / lucro isento ──
                mdiv = re.match(r"^(09|18|20)-", s)
                if mdiv:
                    tipo = mdiv.group(1)
                    val = None
                    mv = re.findall(r"[\d.]+,\d{2}", s)
                    if mv:
                        val = _num(mv[-1])
                    mc = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", s)
                    cnpj = mc.group(0) if mc else ""
                    # fonte = texto entre o rótulo e o CNPJ/valor
                    fonte = s[len(mdiv.group(0)):].strip()
                    if cnpj:
                        fonte = fonte.split(cnpj)[0].strip()
                    dividendos.append({"tipo": tipo, "fonte": fonte, "cnpj": cnpj, "valor": val})
                    continue

                if secao == "bd":
                    if s.startswith("Total:"):
                        secao = None
                        cur = None
                        continue
                    tk = s.split()
                    if tk[0] == "Vista" and len(tk) >= 6 and tk[1].isdigit():
                        v_ant, v_atual = _num(tk[-2]), _num(tk[-1])
                        cnpj = tk[4] if _CNPJ.match(tk[4]) else ""
                        i0 = 5 if cnpj else 4
                        disc = " ".join(tk[i0:-2])
                        cur = {
                            "mercado": tk[0], "grupo": tk[1], "codigo": tk[2],
                            "ticker": tk[3], "cnpj": cnpj, "discriminacao": disc,
                            "v_ant": v_ant, "v_atual": v_atual,
                        }
                        bens.append(cur)
                    elif cur is not None:
                        # linha de continuação da Discriminação
                        cur["discriminacao"] = (cur["discriminacao"] + " " + s).strip()

                elif secao == "jcp":
                    mj = re.match(r"^(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+(.+?)\s+([\d.]+,\d{2})$", s)
                    if mj:
                        jcp.append({"cnpj": mj.group(1), "fonte": mj.group(2).strip(),
                                    "valor": _num(mj.group(3))})
                    elif s.startswith("Total") or "ATENÇÃO" in s:
                        secao = None

    log.info("Informe %s: %d bens, %d dividendos, %d JCP, IR retido %s",
             ano, len(bens), len(dividendos), len(jcp), ir_retido)
    return {"ano": ano, "bens_direitos": bens, "dividendos": dividendos,
            "jcp": jcp, "ir_retido": ir_retido}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    d = parse_informe(sys.argv[1])
    print(f"\nAno {d['ano']}")
    tot = sum(b["v_atual"] or 0 for b in d["bens_direitos"])
    print(f"Bens e Direitos: {len(d['bens_direitos'])} itens, total 31/12 R$ {tot:.2f}")
    print(f"Dividendos: {len(d['dividendos'])} | JCP: {len(d['jcp'])} | IR retido: {d['ir_retido']}")
