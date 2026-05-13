from pathlib import Path
import pandas as pd


ROOT_DIR = Path(__file__).parents[1].resolve()
BASE_YEAR = pd.Timestamp.now().year
BASE_YEAR_HEAD = pd.Timestamp(year=BASE_YEAR, month=1, day=1)
NEXT_YEAR_TAIL = pd.Timestamp(year=BASE_YEAR + 1, month=12, day=31)
BILLING_DATE_MIN = BASE_YEAR_HEAD - pd.Timedelta(days=BASE_YEAR_HEAD.day_of_week)
BILLING_DATE_MAX = NEXT_YEAR_TAIL + pd.Timedelta(days=6 - NEXT_YEAR_TAIL.day_of_week)
