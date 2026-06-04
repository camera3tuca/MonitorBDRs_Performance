"""
Database operations for the MonitorBDRs_Performance application.
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.config import DB_PATH

def get_conn() -> sqlite3.Connection:
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)

def init_db() -> None:
    """Initialize the database schema."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nr_nota TEXT, data TEXT, nome TEXT, ticker TEXT, tipo TEXT,
            cv TEXT, day_trade INTEGER, quantidade REAL,
            preco REAL, valor REAL, fonte TEXT
        );
        CREATE TABLE IF NOT EXISTS notas_importadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE, importado TEXT
        );
    """)
    conn.commit()
    conn.close()

def ja_importada(f: str) -> bool:
    """Check if a note has already been imported."""
    conn = get_conn()
    r = conn.execute("SELECT 1 FROM notas_importadas WHERE filename=?", (f,)).fetchone()
    conn.close()
    return r is not None

def registrar(f: str) -> None:
    """Register a note as imported."""
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO notas_importadas(filename,importado) VALUES(?,?)",
                 (f, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def salvar(ops: List[Dict[str, Any]]) -> None:
    """Save parsed operations to the database."""
    conn = get_conn()
    conn.executemany("""INSERT INTO operacoes
        (nr_nota,data,nome,ticker,tipo,cv,day_trade,quantidade,preco,valor,fonte)
        VALUES (:nr_nota,:data,:nome,:ticker,:tipo,:cv,:day_trade,:quantidade,:preco,:valor,:fonte)""", ops)
    conn.commit()
    conn.close()

def carregar() -> pd.DataFrame:
    """Load operations from the database."""
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM operacoes ORDER BY data, nr_nota", conn)
    conn.close()
    if df.empty:
        return df
    df["data_dt"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["mes"] = df["data_dt"].dt.strftime("%Y-%m")
    df["mes_label"] = df["data_dt"].dt.strftime("%b/%Y")
    df["day_trade"] = df["day_trade"].astype(bool)
    return df
