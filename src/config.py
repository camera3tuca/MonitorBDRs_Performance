"""
Configuration constants for the MonitorBDRs_Performance application.
"""

DB_PATH = "carteira.db"
DATA_DIR = "notas_pdf"

NOME_TICKER = {
    "AMAZON": "AMZO34", "APPLE": "AAPL34", "ALPHABET": "GOGL34", "MICROSOFT": "MSFT34",
    "TESLA INC": "TSLA34", "NVIDIA CORP": "NVDC34", "NETFLIX": "NFLX34",
    "MERCADOLIBRE": "MELI34", "JPMORGAN": "JPMC34", "BERKSHIRE": "BERK34",
    "ORACLE": "ORCL34", "MASTERCARD": "MSCD34", "MCDONALDS": "MCDC34",
    "COCA COLA": "COCA34", "INTEL": "ITLC34", "ALIBABAGR": "BABA34",
    "AIRBNB": "AIRB34", "WALMART": "WALM34", "EMBRAER": "EMBJ3",
    "TREND OURO": "GOLD11", "SYN PROP TEC": "SYNE3", "SYN PROP TEC ON": "SYNE3",
    "WALT DISNEY": "DISB34",
}

LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font_color="#ccc", margin=dict(l=4, r=4, t=30, b=4),
)
