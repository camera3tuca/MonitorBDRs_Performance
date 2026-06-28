"""
b3_tickers — universo de tickers negociados na B3.

Busca a lista oficial de instrumentos da B3 em runtime (funciona no
Streamlit Cloud, que tem internet liberada), cacheia em disco com TTL e
cai num conjunto embarcado caso a rede falhe. Serve para validar o mapa
NOME_PARA_TICKER do app — apontando tickers que não existem de fato na B3.

Uso típico:
    from b3_tickers import carregar_tickers_b3, validar_mapeamento

    universo = carregar_tickers_b3()           # set[str] com todos os tickers
    invalidos = validar_mapeamento(NOME_PARA_TICKER, universo)
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────
# Cache em disco — evita bater na rede a cada rerun do Streamlit.
_CACHE_PATH = os.path.join(os.path.dirname(__file__), "b3_tickers_cache.json")
_CACHE_TTL = 7 * 24 * 3600          # 7 dias
_HTTP_TIMEOUT = 20                  # segundos

# Fontes públicas (sem necessidade de API key). Tentadas em ordem.
# brapi.dev/api/available devolve {"stocks": [...], "indexes": [...]} com
# todos os tickers à vista negociados na B3.
_FONTES = (
    "https://brapi.dev/api/available",
)

# Conjunto embarcado mínimo — fallback quando rede e cache falham.
# Não é exaustivo (a B3 tem milhares de tickers); cobre o que o app usa
# para nunca ficar sem nenhuma referência. É atualizado pelo cache online.
_FALLBACK: frozenset[str] = frozenset({
    # Índices/ETFs comuns
    "BOVA11", "IVVB11", "SMAL11", "HASH11", "KNCA11", "SNAG11",
    # Blue chips B3
    "PETR3", "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3",
    "B3SA3", "WEGE3", "EMBR3", "MRFG3", "SYNE3", "NUBR33",
})


# ─────────────────────────────────────────────
# CACHE EM DISCO
# ─────────────────────────────────────────────
def _ler_cache() -> set[str] | None:
    """Lê o cache em disco se existir e ainda estiver dentro do TTL."""
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        idade = time.time() - float(data.get("ts", 0))
        tickers = data.get("tickers", [])
        if idade <= _CACHE_TTL and tickers:
            log.debug("Cache de tickers B3 válido (%d tickers, %.0fh).",
                      len(tickers), idade / 3600)
            return set(tickers)
        log.debug("Cache de tickers B3 expirado (%.0fh).", idade / 3600)
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        log.debug("Falha ao ler cache de tickers B3: %s", exc)
    return None


def _gravar_cache(tickers: set[str]) -> None:
    """Persiste o universo de tickers em disco com timestamp."""
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "tickers": sorted(tickers)}, f)
        log.debug("Cache de tickers B3 gravado (%d tickers).", len(tickers))
    except OSError as exc:
        log.debug("Falha ao gravar cache de tickers B3: %s", exc)


# ─────────────────────────────────────────────
# BUSCA ONLINE
# ─────────────────────────────────────────────
def _extrair_tickers(payload) -> set[str]:
    """Extrai tickers de um JSON de formato variável, defensivamente.

    Aceita listas no topo ou aninhadas em dict (ex.: {"stocks": [...]}).
    Considera ticker toda string curta alfanumérica (3–8 chars)."""
    achados: set[str] = set()

    def _visit(node):
        if isinstance(node, str):
            t = node.strip().upper()
            if 3 <= len(t) <= 8 and t.isalnum() and any(c.isdigit() for c in t):
                achados.add(t)
        elif isinstance(node, list):
            for item in node:
                _visit(item)
        elif isinstance(node, dict):
            for item in node.values():
                _visit(item)

    _visit(payload)
    return achados


def _buscar_online() -> set[str] | None:
    """Tenta baixar o universo de tickers das fontes públicas.

    Respeita HTTPS_PROXY automaticamente (urllib lê o ambiente)."""
    for url in _FONTES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MonitorBDRs/1.0"})
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                payload = json.load(resp)
            tickers = _extrair_tickers(payload)
            if len(tickers) >= 100:   # sanidade: lista real tem milhares
                log.info("Universo de tickers B3 carregado de %s (%d tickers).",
                         url, len(tickers))
                return tickers
            log.warning("Fonte %s retornou poucos tickers (%d) — ignorada.",
                        url, len(tickers))
        except (urllib.error.URLError, json.JSONDecodeError, ValueError, OSError) as exc:
            log.warning("Falha ao buscar tickers B3 de %s: %s", url, exc)
    return None


# ─────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────
def carregar_tickers_b3(force: bool = False) -> set[str]:
    """Retorna o conjunto de tickers negociados na B3.

    Ordem de resolução:
      1. Cache em disco (se válido e force=False)
      2. Busca online (e regrava o cache)
      3. Cache expirado (melhor que nada)
      4. Conjunto embarcado de fallback

    Nunca lança exceção — sempre devolve um set utilizável.
    """
    if not force:
        cache = _ler_cache()
        if cache:
            return cache

    online = _buscar_online()
    if online:
        _gravar_cache(online)
        return online

    # Rede falhou — tenta cache mesmo expirado
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            tickers = json.load(f).get("tickers", [])
        if tickers:
            log.warning("Usando cache de tickers B3 expirado (rede indisponível).")
            return set(tickers)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        pass

    log.warning("Sem rede e sem cache — usando fallback embarcado (%d tickers).",
                len(_FALLBACK))
    return set(_FALLBACK)


def validar_ticker(ticker: str, universo: set[str] | None = None) -> bool:
    """True se o ticker existe no universo da B3."""
    if universo is None:
        universo = carregar_tickers_b3()
    return ticker.strip().upper() in universo


def validar_mapeamento(mapa: dict[str, str],
                       universo: set[str] | None = None) -> list[str]:
    """Devolve os tickers do mapa que NÃO existem no universo da B3.

    Como o fallback embarcado é pequeno, só reporta inválidos quando o
    universo é grande o bastante para ser confiável (≥100 tickers)."""
    if universo is None:
        universo = carregar_tickers_b3()
    if len(universo) < 100:
        log.debug("Universo B3 pequeno (%d) — validação de mapeamento pulada.",
                  len(universo))
        return []
    invalidos = sorted({
        tk for tk in mapa.values() if tk.strip().upper() not in universo
    })
    if invalidos:
        log.warning("Tickers mapeados ausentes no universo B3: %s",
                    ", ".join(invalidos))
    return invalidos


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    u = carregar_tickers_b3(force=True)
    print(f"Universo B3: {len(u)} tickers")
    print("Exemplos:", sorted(u)[:20])
