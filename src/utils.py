"""
Utility functions for the MonitorBDRs_Performance application.
"""

def fmt(v: float) -> str:
    """Format a float value as BRL currency."""
    return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
