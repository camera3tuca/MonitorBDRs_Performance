"""
Financial calculations for the MonitorBDRs_Performance application.
"""

import pandas as pd

def calc_posicao(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the position and P&L for each asset."""
    rows = []
    for nome, g in df.groupby("nome"):
        g = g.sort_values("data_dt")
        qtd = custo = pl = 0.0
        for _, r in g.iterrows():
            if r.cv == "Compra":
                custo += r.valor
                qtd += r.quantidade
            else:
                if qtd > 0:
                    cm = custo / qtd
                    pl += (r.preco - cm) * r.quantidade
                    custo -= cm * r.quantidade
                    qtd -= r.quantidade
        rows.append({
            "nome": nome, "ticker": g.ticker.iloc[0],
            "qtd_atual": qtd,
            "custo_medio": custo / qtd if qtd > 0 else 0,
            "custo_total": custo, "pl_realizado": pl,
        })
    return pd.DataFrame(rows)

def calc_pl_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the monthly P&L and volume statistics."""
    rows = []
    for mes, g in df.groupby("mes"):
        c = g[g.cv=="Compra"]["valor"].sum()
        v = g[g.cv=="Venda"]["valor"].sum()
        rows.append({
            "mes": mes, "label": g.mes_label.iloc[0],
            "vol_compra": c, "vol_venda": v, "saldo": v - c,
            "n_ops": len(g), "n_dt": int(g.day_trade.sum()),
        })
    return pd.DataFrame(rows).sort_values("mes")
