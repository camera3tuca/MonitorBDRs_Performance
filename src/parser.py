"""
PDF parsing operations for the MonitorBDRs_Performance application.
"""

import pdfplumber
import re
import os
import streamlit as st
from pathlib import Path
from typing import List, Dict, Any
from src.config import NOME_TICKER, DATA_DIR
from src.database import ja_importada, salvar, registrar

LINE_RE = re.compile(
    r'B3\s+RV\s+LISTADO([CV])\s+'
    r'(?:FRACION[AÁ]RIO|VISTA|FUTURO)\s+'
    r'(.+?)\s+(DRN|CI|NM|ON|PN)\s*(?:ED|NM)?\s*(D)?\s*'
    r'(\d+)\s+([\d]+,[\d]+)\s+([\d]+,[\d]+)\s+([CD])'
)
NOTA_RE = re.compile(r'^\s*(\d{4,6})\s+(\d+)\s+(\d{2}/\d{2}/\d{4})')

def parse_pdf(path: str, fonte: str) -> List[Dict[str, Any]]:
    """Parse a PDF file to extract operations."""
    ops, gseen = [], {}
    with pdfplumber.open(path) as pdf:
        cur = {}
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            for line in lines:
                mn = NOTA_RE.match(line)
                if mn:
                    cur = {"nr": mn.group(1), "data": mn.group(3)}
                    break
            for line in lines:
                m = LINE_RE.search(line)
                if not m or not cur: continue
                nome  = re.sub(r'\s+(ED|NM|ON|PN)\s*$', '', m.group(2).strip())
                nr    = cur["nr"]
                chave = (m.group(1), nome, m.group(5), m.group(6), m.group(7))
                if nr not in gseen: gseen[nr] = set()
                if chave in gseen[nr]: continue
                gseen[nr].add(chave)
                ticker = NOME_TICKER.get(nome, nome[:8].upper().replace(" ",""))
                ops.append({
                    "nr_nota": nr, "data": cur["data"], "nome": nome,
                    "ticker": ticker, "tipo": m.group(3),
                    "cv": "Compra" if m.group(1)=="C" else "Venda",
                    "day_trade": 1 if m.group(4)=="D" else 0,
                    "quantidade": int(m.group(5)),
                    "preco": float(m.group(6).replace(",",".")),
                    "valor": float(m.group(7).replace(",",".")),
                    "fonte": fonte,
                })
    return ops

def auto_load() -> int:
    """Automatically load operations from PDF files in the data directory."""
    os.makedirs(DATA_DIR, exist_ok=True)
    total = 0
    for f in sorted(Path(DATA_DIR).glob("*.pdf")):
        if not ja_importada(f.name):
            try:
                ops = parse_pdf(str(f), f.name)
                if ops:
                    salvar(ops)
                    registrar(f.name)
                    total += len(ops)
            except Exception as e:
                st.warning(f"Erro em {f.name}: {e}")
    return total
