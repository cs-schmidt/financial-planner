from pathlib import Path

ROOT_DIR = Path(__file__).parents[1].resolve()
ENV_DIR = ROOT_DIR / ".env"
DATA_DIR = ROOT_DIR / "data"

CPI_CSV_PATH = DATA_DIR / "cpi_canada_2013-01_2025-11.csv"
GCP_KEY_PATH = ENV_DIR / "gcp-service-account-key.json"
