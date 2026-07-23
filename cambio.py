"""
cambio — cotação PTAX do dólar (fonte oficial: API do Banco Central).

A Receita exige converter operações em moeda estrangeira pela cotação PTAX
da data de cada operação:
  • aquisição (compra do ativo)  → dólar de **venda**   da data
  • alienação (venda do ativo)   → dólar de **compra**  da data
  • rendimentos (dividendos)     → dólar de **compra**  da data

Em dia sem cotação (fim de semana/feriado), usa-se o último PTAX disponível
antes da data. Resultados ficam em cache (cambio_cache.json) para não
refazer chamadas.

Observação: este módulo depende de acesso à internet (olinda.bcb.gov.br).
No app publicado (Streamlit Cloud) isso funciona; em ambientes com rede
restrita, as datas sem cotação retornam vazio e o app usa o câmbio manual.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import ssl
import urllib.request

log = logging.getLogger(__name__)

BASE = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
CACHE_PATH = "cambio_cache.json"


def _fmt(iso: str) -> str:
    """YYYY-MM-DD → MM-DD-YYYY (formato exigido pela API do BCB)."""
    y, m, d = iso.split("-")
    return f"{m}-{d}-{y}"


def load_cache(path: str = CACHE_PATH) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache: dict, path: str = CACHE_PATH) -> None:
    try:
        with open(path, "w") as f:
            json.dump(cache, f)
    except Exception as exc:
        log.warning("Não foi possível salvar o cache de câmbio: %s", exc)


def _fetch_periodo(ini_iso: str, fim_iso: str, timeout: int = 20) -> list[dict]:
    url = (
        f"{BASE}/CotacaoDolarPeriodo(dataInicial=@i,dataFinalCotacao=@f)"
        f"?@i='{_fmt(ini_iso)}'&@f='{_fmt(fim_iso)}'&$format=json"
        f"&$select=cotacaoCompra,cotacaoVenda,dataHoraCotacao"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode()).get("value", [])


def get_ptax(datas, cache: dict | None = None) -> dict:
    """
    Recebe um iterável de datas 'YYYY-MM-DD' e devolve
    {data: {"compra": float, "venda": float}} para as que encontrou.

    Usa o último PTAX disponível <= data (cobre fim de semana/feriado).
    Faz UMA única chamada à API cobrindo todo o período necessário.
    """
    cache = cache if cache is not None else load_cache()
    datas = sorted(set(datas))
    if not datas:
        return {}

    resultado: dict[str, dict] = {}
    faltando = [d for d in datas if d not in cache]
    for d in datas:
        if d in cache and cache[d]:
            resultado[d] = cache[d]

    if faltando:
        try:
            ini = (datetime.date.fromisoformat(min(faltando)) - datetime.timedelta(days=10)).isoformat()
            fim = max(faltando)
            vals = sorted(_fetch_periodo(ini, fim), key=lambda v: v["dataHoraCotacao"])
            # (data → par) apenas dos dias com cotação
            serie = [(v["dataHoraCotacao"][:10],
                      {"compra": float(v["cotacaoCompra"]), "venda": float(v["cotacaoVenda"])})
                     for v in vals]
            for d in faltando:
                par = None
                for data_cot, p in serie:      # último pregão <= d
                    if data_cot <= d:
                        par = p
                    else:
                        break
                cache[d] = par
                if par:
                    resultado[d] = par
        except Exception as exc:
            log.warning("Falha ao buscar PTAX (%s a %s): %s", min(faltando), max(faltando), exc)

    save_cache(cache)
    return resultado


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    dts = sys.argv[1:] or ["2024-01-15", "2024-01-13"]  # sábado → usa sexta
    for d, v in get_ptax(dts).items():
        print(d, v)
